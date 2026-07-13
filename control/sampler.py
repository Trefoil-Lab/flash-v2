import sys
import time
import datetime
import math
import random
import sched
from threading import Thread, Event, Lock
from queue import SimpleQueue, Empty

from util.signals import (
    SampleSignals
)
from control.supply import (
    Supply,
    Data
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
        data : Data

        def sample(sc : sched.scheduler, target_time : float):
            with self.supply_lock:
                data = self.supply.meas()
            self.sample_signal.newDataSig.emit((
                time.perf_counter() - start_time, # time
                data.voltage, # V
                data.current, #I
                data.power, # P
                data.temperature, # T
            ))

            # send to queue for saving
            area = 0.25 * math.pi * self.control_runner.params.diameter * self.control_runner.params.diameter
            queue_data = (
                data.timestamp, # timestamp
                time.perf_counter() - start_time, # time
                data.voltage, # voltage
                data.current, # current
                data.power, # apparent power
                data.voltage / self.control_runner.params.height, # E
                data.current / area, # J
                data.power / area, # P
                data.temperature, # temprature
                *data.payload, # any additional data
            )
            self.queue.put(queue_data)

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