"""
Utility classes for the process control thread.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple, Callable
from threading import Lock, Event
from queue import SimpleQueue

from control.data import (
    SupplyData
)
from control.flash.signals import (
    SampleSignals
)


class SegmentType(Enum):
    """
    Type of process segment: END, HOLD, or RAMP.
    * `END`: end of process
    * `HOLD`: maintain value for set duration
    * `RAMP`: ramp from current value to target value at rate
    """
    END = 0
    HOLD = 1
    RAMP = 2

@dataclass
class Segment:
    """
    Specify segment of a process.
    """
    type : SegmentType
    target : float | None
    rate : float | None # / sec
    time : float | None # hold time
    entered : float | None = None # time hold entered, for internal use

@dataclass
class PulseConf:
    """
    Pulse configuration
    """
    pulse : bool
    value : float
    period : float | None = None
    duty_cycle : float | None = None

class PulseState(Enum):
    """
    For internal tracking of pulse state
    """
    LOW = False
    HIGH = True

class Interface(NamedTuple):
    """
    Callback functions and other objects used by the process thread to
    interface with the process.
    """
    lock : Lock
    set_val : Callable[[float], None]
    get_val : Callable[[], float]
    pulse_on : Callable[[float], None]
    pulse_off : Callable[[], None]
    meas : Callable[[], SupplyData]
    events : Events

class SampleConf(NamedTuple):
    """
    Configuration of sample collection.
    """
    interval : float
    sample_signals : SampleSignals
    data_queue : SimpleQueue
    height : float
    diameter : float

class Events(NamedTuple):
    """
    Events used to communicate with the process thread.
    """
    stop : Event
    pause : Event
    jump : Event