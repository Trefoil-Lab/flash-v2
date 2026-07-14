import time
import sys
from threading import Thread, Event
from queue import SimpleQueue, Empty
import sched

from util.const import (
    SAVE_INTERVAL_S,
    CSV_HEADER,
)
from util.data import (
    SamplerData
)


class SaveRunner(Thread):
    def __init__(self, 
        filepath : str, 
        data_queue : SimpleQueue, 
        stop_event : Event,
        payload_header : str
    ):
        super().__init__()

        self.filepath = filepath
        self.queue = data_queue
        self.stop_event = stop_event
        self.payload_header = payload_header

    def save(self, sc : sched.scheduler | None):
        d : SamplerData
        with open(self.filepath, 'a') as f:
            while not self.queue.empty():
                try:
                    d = self.queue.get_nowait()
                except Empty:
                    break
                f.write(','.join( [str(x) for x in (
                    d.timestamp, d.delta_time, d.voltage, d.current, d.power,
                    d.e_field, d.curr_density, d.power_density, d.temperature,
                    *d.payload
                )] ) + '\n')
        
        if not self.stop_event.is_set() and sc != None:
            sc.enter(SAVE_INTERVAL_S, 1, self.save, (sc, ))

    def run(self):
        print('Saving thread started')
        with open(self.filepath, 'w') as f:
            f.write(CSV_HEADER + ',' + self.payload_header + '\n')

        sc = sched.scheduler(time.monotonic, time.sleep)
        sc.enter(SAVE_INTERVAL_S, 1, self.save, (sc, ))
        
        while not self.stop_event.is_set():
            sc.run(False)
            time.sleep(0.2)
        self.save(None)
        sys.exit()