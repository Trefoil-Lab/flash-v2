from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple, Callable
from threading import Lock, Event
from queue import SimpleQueue

from util.data import (
    SupplyData
)
from util.signals import (
    SampleSignals
)


class SegmentType(Enum):
    END = 0
    HOLD = 1
    RAMP = 2

@dataclass
class Segment:
    type : SegmentType
    target : float | None
    rate : float | None # / sec
    time : float | None # hold time
    entered : float | None = None # time hold entered, for internal use

@dataclass
class PulseConf:
    pulse : bool
    value : float
    period : float | None = None
    duty_cycle : float | None = None

class PulseState(Enum):
    LOW = False
    HIGH = True

class Interface(NamedTuple):
    lock : Lock
    set_val : Callable[[float], None]
    get_val : Callable[[], float]
    pulse_on : Callable[[float], None]
    pulse_off : Callable[[], None]
    meas : Callable[[], SupplyData]
    events : Events

class SampleConf(NamedTuple):
    interval : float
    sample_signals : SampleSignals
    data_queue : SimpleQueue
    height : float
    diameter : float

class Events(NamedTuple):
    stop : Event
    pause : Event
    jump : Event