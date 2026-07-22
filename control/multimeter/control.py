from threading import Thread, Event
from queue import SimpleQueue

from control.multimeter import (
    multimeter
)
from control.data import (
    MultimeterData
)

class ControlRunner(Thread):
    def __init__(self):
        super().__init__()

    def start(self):
        pass