import sys
import time
import datetime
import math
import random
import sched
from threading import Thread, Event, Lock
from queue import SimpleQueue, Empty

from control.multimeter.signals import (
    SampleSignals,
    Config
)
from control.multimeter import (
    multimeter
)
from control.data import (
    MultimeterData,
)


class SampleRunner(Thread):
    def __init__(self,
        multimeter : multimeter.Multimeter,
        config : Config,
        stop_event : Event,
        data_queue : SimpleQueue,
        sample_signals : SampleSignals,
    ):
        super().__init__()

        self.mm = multimeter
        self.conf = config
        self.stop_event = stop_event
        self.queue = data_queue
        self.sample_signals = sample_signals


    def run(self):
        self.mm.configure(
            mode=self.conf.mode,
            auto_zero=self.conf.auto_zero,
        )

        start_time = time.monotonic()

        while not self.stop_event.is_set():
            val = self.mm.read()[0]
            now = time.monotonic()
            data = MultimeterData(
                time=now - start_time,
                timestamp=datetime.datetime.now().timestamp(),
                value=val,
                mode=self.conf.mode,
            )
            self.sample_signals.newDataSig.emit(data)
            self.queue.put(data)
            
            time.sleep(0.01)