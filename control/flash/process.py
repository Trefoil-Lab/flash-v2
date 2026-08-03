"""
Utility classes for the process control thread.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple, Callable, ClassVar
from threading import Lock, Event
from queue import SimpleQueue
from abc import ABC

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

class PulseMode(Enum):
    """
    Indicate how pulsing should be acheived.
    """
    NATIVE = 0
    EMULATED = 1

class PulseState(Enum):
    """
    For internal tracking of pulse state
    """
    LOW = False
    HIGH = True

@dataclass
class PulseConf(ABC):
    """
    Pulse configuration abstract base class. 
    """
    pulse : bool
    mode : ClassVar[PulseMode]
    value : float
    period : float | None
    duty_cycle : float | None

    def __post_init__(self) -> None:
        if self.pulse:
            if self.period is None or self.duty_cycle is None:
                raise ValueError("'pulse=True' requires both 'period' and 'duty_cycle'.")
            else:
                if self.period <= 0:
                    raise ValueError("'period' must be greater than 0.")
                if not (0 < self.duty_cycle < 100):
                    raise ValueError("'duty_cycle' must be between 0 and 100 exclusive.")

@dataclass
class PulseConfNative(PulseConf):
    """
    Pulse configuration for instruments supporting native pulse functionality.
    """
    mode : ClassVar[PulseMode] = PulseMode.NATIVE
    pulse_setup : Callable[[float, float, float], None]

@dataclass
class PulseConfEmulated(PulseConf):
    """
    Pulse configuration for instruments requiring software emulation of pulsing.
    """
    mode : ClassVar[PulseMode] = PulseMode.EMULATED
    pulse_up : Callable[[float], None]
    pulse_down : Callable[[None], None]

class Interface(NamedTuple):
    """
    Callback functions and other objects used by the process thread to
    interface with the process.
    """
    lock : Lock
    set_val : Callable[[float], None]
    get_val : Callable[[], float]
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