import sched
import time
import sys
import math
import random
from threading import Thread, Lock, Event

from control.flash.process import (
    Segment,
    SegmentType,
    PulseConf,
    PulseMode,
    PulseConfNative,
    PulseConfEmulated,
    PulseState,
    Interface,
    SampleConf
)
from control.data import (
    SamplerData,
    ACPayload
)
from control.flash.signals import (
    SampleSignals
)
from util.const import (
    RAMP_INTERVAL_S
)


# TODO adjust priorities and actually use them
SAMPLE_PRIORITY = 1
MOVE_PRIORITY = 1
PULSE_PRIORITY = 1


class ProcessRunner(Thread):
    """
    Generic segmented process controller. Uses functions passed as
    arguments to ramp or hold set points. Also capable of pulsed
    operation.
    """
    def __init__(self,
                segs : list[Segment],
                start_value : float,
                pulse : PulseConfNative | PulseConfEmulated,
                interface : Interface,
                sample : SampleConf
    ):
        """
        Initialize the process thread.

        Args:
            segs (list[Segment]): list of process segments
            start_value (float): initial setpoint
            pulse (PulseConfNative | PulseConfEmulated): pulse configuration
            interface (Interface): functions and object used to interface with the process
            sample (SampleConf): data collection configuration
        """
        # TODO start value?
        # TODO end behavior?
        super().__init__()

        self.segs = segs
        self.pulse_data = pulse
        self.start_value = start_value
        self.pulse_state = PulseState.LOW
        self.interface = interface
        self.events = interface.events
        self.sample_interval = sample.interval
        self.data_queue = sample.data_queue
        self.sample_signals = sample.sample_signals
        self.height = sample.height
        self.diameter = sample.diameter

        self.new_segs : list[Segment] = None
        self.new_start : float | None = None
        self.new_pulse : PulseConfEmulated | PulseConfNative = None
        self.new_segs_lock = Lock()
        self.next_move : sched.Event = None
        self.next_pulse : sched.Event = None
        self.update_event = Event()

        self.idx = 0
        self.paused = False

    def run(self):
        sc = sched.scheduler(time.monotonic, time.sleep)
        self.start_time = time.monotonic()
        sc.enterabs(self.start_time + self.sample_interval,
                    SAMPLE_PRIORITY, self.sample, 
                    (sc, self.start_time + self.sample_interval)
        )

        self.interface.set_val(self.start_value)
        self.schedule_next_move(sc)

        # set up pulsing
        if self.pulse_data.pulse:
            self.setup_pulse(sc)

        while not self.events.stop.is_set():

            if self.update_event.is_set():
                # if we are told to start again / change segments
                self.handle_update(sc)
                    
                self.update_event.clear()

            if not self.paused and self.events.pause.is_set():
                # we have just now entered pause
                self.paused = True

                # TODO notify of pause?
                
                if self.segs[self.idx].type == SegmentType.HOLD:
                    # if we are in a hold, subtract the time we have already held
                    #   from the prescribed hold time
                    elapsed = time.monotonic() - self.segs[self.idx].entered
                    self.segs[self.idx].time -= elapsed

            elif self.paused and not self.events.pause.is_set():
                # we have just been unpaused, so schedule next change
                self.schedule_next_move(sc)
            
            sc.run(False) # run any pending actions

        # if we are here, we received stop signal
        sc.queue.clear() # clear scheduler queue
        sys.exit() # close thread



    def update(self, segs : list[Segment], pulse : PulseConfEmulated | PulseConfNative, start : float | None = None):
        """
        Inform process thread to update segments continue with the
        first segment. If start is None, start from current value.
        Otherwise, set value to start then continue. Intended for external use.

        Args:
            segs (list[Segment]): new segments
        """ 
        with self.new_segs_lock:
            self.new_segs = segs
            self.new_pulse = pulse
            self.new_start = start
        self.update_event.set()

    def handle_update(self, sc : sched.scheduler):
        """
        Handle updates. For internal use.

        Args:
            sc (sched.scheduler): scheduler
        """
        with self.new_segs_lock:
            if not self.new_segs is None:
                self.segs = self.new_segs
                self.idx = 0
                if not self.new_start is None:
                    with self.interface.lock:
                        self.interface.set_val(self.start)
                if not self.next_move is None:
                    sc.cancel(self.next_move) # cancel old next move

            if not self.new_pulse is None:
                self.pulse_data = self.new_pulse
                if self.pulse_data.pulse:
                    self.setup_pulse(sc)
                else:
                    with self.interface.lock:
                        self.pulse_data.pulse_up(self.new_pulse.value)
                if not self.new_pulse is None:
                    sc.cancel(self.next_pulse)

        self.schedule_next_move(sc) # schedule next move

    def setup_pulse(self, sc : sched.scheduler):
        """
        Setup pulsing. For internal use.

        Args:
            sc (sched.scheduler): scheduler
        """
        match self.pulse_data.mode:
            case PulseMode.NATIVE:
                self.pulse_data.pulse_setup(
                        self.pulse_data.value,
                        self.pulse_data.period,
                        self.pulse_data.duty_cycle
                    )
            case PulseMode.EMULATED:
                self.pulse(sc, time.monotonic())

    def schedule_next_move(self, sc : sched.scheduler):
        """
        Determine when next setpoint change needs to occur, based
        on current segment. Schedule the next change. For internal use.

        Args:
            sc (sched.scheduler): scheduler
        """
        # TODO maybe use enterabs with target time for less drift
        if self.paused:
            # if we are paused, don't schedule next move
            return

        match self.segs[self.idx].type:
            case SegmentType.RAMP:
                # we are ramping, so schedule next increment
                self.next_move = sc.enter(RAMP_INTERVAL_S, MOVE_PRIORITY, self.ramp, (sc, time.monotonic()))
            case SegmentType.HOLD:
                # we are holding
                self.segs[self.idx].entered = time.monotonic()
                self.next_move = sc.enter(self.segs[self.idx].time, MOVE_PRIORITY, self.hold_end, (sc, time.monotonic()))

    def ramp(self, sc : sched.scheduler, last : float):
        """
        Increment setpoint towards target based on rate. If target has
        been reached, advance to next segment. Finally, schedule the next change.
        Called at each ramp time step. For internal use.

        Args:
            sc (sched.scheduler): scheduler
            last (float): time of last change
        """
        elapsed = time.monotonic() - last
        val : float
        with self.interface.lock:
            val = self.interface.get_val()
        if (abs(self.segs[self.idx].target - val)
        <= abs(elapsed * self.segs[self.idx].rate)):
            # we are within one step of the target, so just jump to it
            with self.interface.lock:
                self.interface.set_val(self.segs[self.idx].target)
            # go to next segment
            self.idx += 1
        elif self.segs[self.idx].target > val:
            # we are below the target, so increase set point
            with self.interface.lock:
                self.interface.set_val(val + elapsed * self.segs[self.idx].rate)
        elif self.segs[self.idx].target < val:
            # we are above the target, so decrease set point
            with self.interface.lock:
                self.interface.set_val(val - elapsed * self.segs[self.idx].rate)

        self.schedule_next_move(sc) # schedule next change

    def hold_end(self, sc : sched.scheduler):
        """
        Advance to the next segment then schedule the next change.
        Called at the end of a hold. For internal use.

        Args:
            sc (sched.scheduler): scheduler
        """
        # a hold has ended
        self.idx += 1 # go to next segment
        self.schedule_next_move(sc) # schedule next change

    def pulse(self, sc : sched.scheduler, target_time : float):
        """
        Toggle pulse state, then schedule next pulse change based on
        period and duty cycle. Called when pulse change should occur.
        For internal use.

        Args:
            sc (sched.scheduler): scheduler
            target_time (float): time this pulse was scheduled for
        """
        delay = 0
        match self.pulse_state:
            case PulseState.LOW:
                self.pulse_data.pulse_up(self.pulse_data.value)
                self.pulse_state = PulseState.HIGH
                # stay high for duty_cycle * period
                delay = self.pulse_data.duty_cycle * self.pulse_data.period
            case PulseState.HIGH:
                self.pulse_data.pulse_down()
                self.pulse_state = PulseState.LOW
                # stay low for (1-duty_cycle) * period
                delay = (1 - self.pulse_data.duty_cycle) * self.pulse_data.period

        next_pulse = sc.enterabs(target_time + delay, PULSE_PRIORITY, self.pulse, (sc, target_time + delay))

    def sample(self, sc : sched.scheduler, target_time : float):
        """
        Take a measurement, process it, then forward it to control thread
        and data queue. Called at regular intervals for sampling.
        For internal use.

        For now, only supports flash experiments.

        Args:
            sc (sched.scheduler): scheduler
            target_time (float): time this sample was scheduled for
        """
        # print('sample!')
        with self.interface.lock:
            raw = self.interface.meas()
        area = 0.25 * math.pi * self.diameter * self.diameter

        processed = SamplerData(
            voltage=raw.voltage,
            current=raw.current,
            power=raw.power,
            e_field=raw.voltage / self.height,
            curr_density=raw.current / area,
            power_density=raw.power / area,
            timestamp=raw.timestamp,
            time=raw.time - self.start_time,
            temperature=random.randint(0, 100), # TODO measure temperature?
            payload=raw.payload
        )

        # send to control to forward to gui
        self.sample_signals.newDataSig.emit(processed)
        # send to queue for saving
        self.data_queue.put(processed)

        # check event to see if we should continue
        if not self.events.stop.is_set():
            # schedule next sample
            next_time = target_time + self.sample_interval
            sc.enterabs(next_time, SAMPLE_PRIORITY, self.sample, argument=(sc, next_time))