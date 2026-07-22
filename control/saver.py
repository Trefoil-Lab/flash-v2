import time
import sys
from threading import Thread, Event
from queue import SimpleQueue, Empty
import sched

from util.const import (
    SAVE_INTERVAL_S,
)
from util.data import (
    Data
)


class SaveRunner(Thread):
    def __init__(self, 
        filepath : str,
        memo : str,
        data_queue : SimpleQueue, 
        stop_event : Event,
    ):
        super().__init__()
        self.filepath = filepath
        self.queue = data_queue
        self.stop_event = stop_event
        self.memo = memo
        self.first = True

    def save(self, sc : sched.scheduler | None):
        d : Data
        with open(self.filepath, 'a') as f:
            while not self.queue.empty():
                try:
                    d = self.queue.get_nowait()
                except Empty:
                    break
                if self.first:
                    f.write(d.header + '\n')
                    self.first = False
                f.write(','.join( [str(x) for x in d] ) + '\n')
        
        if not self.stop_event.is_set() and sc != None:
            sc.enter(SAVE_INTERVAL_S, 1, self.save, (sc, ))

    def run(self):
        print('Saving thread started')
        with open(self.filepath, 'w') as f:
            f.write('# ' + self.memo + '\n')

        sc = sched.scheduler(time.monotonic, time.sleep)
        sc.enter(SAVE_INTERVAL_S, 1, self.save, (sc, ))
        
        while not self.stop_event.is_set():
            sc.run(False)
            time.sleep(0.2)
        self.save(None)
        sys.exit()