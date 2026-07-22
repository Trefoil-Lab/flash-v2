import sys
import time
import datetime
import math
import random
import sched
from threading import Thread, Event, Lock
from queue import SimpleQueue, Empty

from control.flash.signals import (
    SampleSignals
)
from control.flash.supply import (
    Supply,
)
from control.data import (
    SupplyData,
    SamplerData,
    ACPayload
)


class SampleRunner(Thread):
    def __init__(self,
        supply : Supply,
        supply_lock : Lock,
        sample_signal : SampleSignals,
        interval : float,
        stop_event : Event,
        control_runner,
        data_queue : SimpleQueue
    ):
        super().__init__()

        self.interval = interval
        self.supply = supply
        self.supply_lock = supply_lock
        self.sample_signal = sample_signal
        self.stop_event = stop_event
        self.control_runner = control_runner
        self.queue = data_queue


    def run(self):
        sc = sched.scheduler(time.perf_counter, time.sleep)

        start_time = time.perf_counter()
        data : SupplyData

        def sample(sc : sched.scheduler, target_time : float):
            with self.supply_lock:
                raw = self.supply.meas()
            area = 0.25 * math.pi * self.control_runner.params.diameter * self.control_runner.params.diameter

            processed = SamplerData(
                voltage=raw.voltage,
                current=raw.current,
                power=raw.power,
                e_field=raw.voltage / self.control_runner.params.height,
                curr_density=raw.current / area,
                power_density=raw.power / area,
                timestamp=raw.timestamp,
                time=raw.time - start_time,
                temperature=random.randint(0, 100), # TODO measure temperature?
                payload=raw.payload
            )

            # send to control to forward to gui
            self.sample_signal.newDataSig.emit(processed)
            # send to queue for saving
            self.queue.put(processed)

            # check event to see if we should continue
            if not self.stop_event.is_set():
                # schedule next sample
                next_time = target_time + self.interval / 1000
                sc.enterabs(next_time, 1, sample, argument=(sc, next_time))
            else:
                print('Sample thread stopping')
                sys.exit()

        print('Sample thread started')
        # schedule first sample
        next_time = start_time + self.interval / 1000
        sc.enterabs(next_time, 1, sample, argument=(sc, next_time))
        sc.run()