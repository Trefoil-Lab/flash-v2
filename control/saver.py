"""
Utilities for saving data
"""

import time
import sys
from threading import Thread, Event
from queue import SimpleQueue, Empty
import sched

from util.const import (
    SAVE_INTERVAL_S,
)
from control.data import (
    Data
)


class SaveRunner(Thread):
    """
    Generic thread for saving collected data.

    Intakes data through a thread-safe queue, and appends it to a CSV
    file every ten seconds.

    Listens to an Event to know when to stop.
    """
    def __init__(self, 
        filepath : str,
        memo : str,
        data_queue : SimpleQueue, 
        stop_event : Event,
    ):
        """
        Save collected data. Intakes Data objects through `data_queue` and
        appends data to a CSV file every ten seconds.

        Continues until `stop_event` is set. When this happens, all remaining
        data is saved and the thread exits.

        `memo` is prepended with '# ' and written to the first line. The CSV
        header is determined by Data.header.

        Args:
            filepath (str): output CSV file (will be overwritten)
            memo (str): memo saved at top of file
            data_queue (SimpleQueue): queue of objects implementing Data
            stop_event (Event): thread exits when set
        """
        super().__init__()
        self.filepath = filepath
        self.queue = data_queue
        self.stop_event = stop_event
        self.memo = memo
        self.first = True

    def save(self, sc : sched.scheduler | None):
        """
        Append all entries in `self.data_queue` to output CSV, and
        schedule next save if `self.stop_event` is not set and `sc` is
        not None.

        Args:
            sc (sched.scheduler | None): if None, do not schedule next save
        """
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
        
        if not self.stop_event.is_set() and not sc is None:
            sc.enter(SAVE_INTERVAL_S, 1, self.save, (sc, ))

    def run(self):
        """
        Create output file, schedule first save, then run scheduled
        tasks until `self.stop_event` is set.
        """
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