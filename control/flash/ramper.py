import sys
import time
import sched
from threading import Thread, Event

from util.const import (
    RAMP_INTERVAL_S
)
from control.flash.signals import (
    ControlSignals,
    GuiSignals,
    Params,
)


class RampRunner(Thread):
    def __init__(self,
                control_signals : ControlSignals,
                gui_signals : GuiSignals,
                params : Params,
                stop_event : Event
    ):
        super().__init__()

        self.control_signals = control_signals
        self.gui_signals = gui_signals
        self.params = params
        self.stop_event = stop_event

    def move(self, sc : sched.scheduler, target_time : float):
        # check if we should stop
        if self.stop_event.is_set():
            sys.exit() # close thread

        if abs(self.params.curr_density - self.params.ramp_data.end) <= (self.params.ramp_data.rate * RAMP_INTERVAL_S):
            # if we are at the target...
            self.params.curr_density = self.params.ramp_data.end
            self.control_signals.setParamsDirectSig.emit(self.params)
            self.control_signals.rampingDoneSig.emit()
            sys.exit() # close thread
        
        # adjust current density
        if self.params.ramp_data.start < self.params.ramp_data.end:
            self.params.curr_density += (self.params.ramp_data.rate * RAMP_INTERVAL_S)
        else:
            self.params.curr_density -= (self.params.ramp_data.rate * RAMP_INTERVAL_S)
        self.control_signals.setParamsDirectSig.emit(self.params)

        # schedule next move
        target_time += RAMP_INTERVAL_S
        sc.enterabs(target_time, 1, self.move, (sc, target_time))

    def run(self):
        print('Ramping thread started.')
        sc = sched.scheduler(time.perf_counter, time.sleep)

        # set start parameters
        self.params.curr_density = self.params.ramp_data.start
        self.control_signals.setParamsDirectSig.emit(self.params)
        
        # schedule moves
        target_time = time.perf_counter() + RAMP_INTERVAL_S
        sc.enterabs(target_time, 1, self.move, (sc, target_time))
        sc.run()