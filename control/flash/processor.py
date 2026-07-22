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


# TODO adjust priorities
SAMPLE_PRIORITY = 1
MOVE_PRIORITY = 1
PULSE_PRIORITY = 1


class ProcessRunner(Thread):
    def __init__(self,
                segs : list[Segment],
                start_value : float,
                pulse : PulseConf,
                interface : Interface,
                sample : SampleConf
    ):
        # TODO start value?
        # TODO end behavior?
        super().__init__()

        self.segs = segs
        self.pulse_data = pulse
        self.start_value = start_value
        self.pulse_state = PulseState.LOW # TODO
        self.interface = interface
        self.events = interface.events
        self.sample_interval = sample.interval
        self.data_queue = sample.data_queue
        self.sample_signals = sample.sample_signals
        self.height = sample.height
        self.diameter = sample.diameter

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
        self.pulse(sc, time.monotonic())
        self.schedule_next_move(sc)

        while not self.events.stop.is_set():

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

    def schedule_next_move(self, sc : sched.scheduler):
        # TODO maybe use enterabs with target time for less drift
        if self.paused:
            # if we are paused, don't schedule next move
            return

        match self.segs[self.idx].type:
            case SegmentType.RAMP:
                # we are ramping, so schedule next increment
                sc.enter(RAMP_INTERVAL_S, 1, self.ramp, (sc, time.monotonic()))
            case SegmentType.HOLD:
                # we are holding
                self.segs[self.idx].entered = time.monotonic()
                sc.enter(self.segs[self.idx].time, 1, self.hold_end, (sc, time.monotonic()))

    def ramp(self, sc : sched.scheduler, last : float):
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
        # a hold has ended
        self.idx += 1 # go to next segment
        self.schedule_next_move(sc) # schedule next change

    def pulse(self, sc : sched.scheduler, target_time : float):
        delay = 0
        match self.pulse_state:
            case PulseState.LOW:
                self.interface.pulse_on(self.pulse_data.value)
                self.pulse_state = PulseState.HIGH
                # stay high for duty_cycle * period
                delay = self.pulse_data.duty_cycle * self.pulse_data.period
            case PulseState.HIGH:
                self.interface.pulse_off()
                self.pulse_state = PulseState.LOW
                # stay low for (1-duty_cycle) * period
                delay = (1 - self.pulse_data.duty_cycle) * self.pulse_data.period

        sc.enterabs(target_time + delay, 1, self.pulse, (sc, target_time + delay))

    def sample(self, sc : sched.scheduler, target_time : float):
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
                sc.enterabs(next_time, 1, self.sample, argument=(sc, next_time))