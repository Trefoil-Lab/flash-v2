"""
Classes for data exchange and collection.
"""

from dataclasses import dataclass
from typing import NamedTuple, ClassVar
from abc import ABC, abstractmethod

from control.multimeter.multimeter import (
    Mode
)


FLASH_CSV_HEADER = 'Timestamp,Time,Volts,Amps,|S|(VA),E,J,P,T'
AC_PAYLOAD_CSV_HEADER = 'S (VA),freq (Hz)'
DC_PAYLOAD_CSV_HEADER = ''

@dataclass
class Payload:
    """
    Payload base class for adding context specific data to Data
    and its subclasses.

    Implements __iter__ so it can be cast to an iterable or
    unpacked like a tuple.
    """
    def __iter__(self):
        return iter(tuple())
    @property
    def header(self) -> str:
        """
        Comma-seperated string to be placed in the header of a CSV
        file to label the data provided by the payload.
        """
        return ''

@dataclass
class ACPayload(Payload):
    """
    Additional data, specific to AC power supplies, to be attached to
    the SupplyData and SamplerData classes.
    """
    complex_power: complex
    frequency : float

    def __iter__(self):
        return iter((self.complex_power, self.frequency))
    @property
    def header(self) -> str:
        return AC_PAYLOAD_CSV_HEADER


@dataclass
class Data(ABC):
    """
    Abstract base class for data collection and exchange. At mimimum
    provides time data.

    Implements __iter__ so it can be cast to an iterable or
    unpacked like a tuple.
    """
    time : float

    def __iter__(self):
        return iter((self.time,))
    @property
    @abstractmethod
    def header(self) -> str:
        """
        Comma-seperated string to be placed in the header of a CSV
        file to label the data provided.
        """
        pass

@dataclass
class MultimeterData(Data):
    """
    Implementation of Data for multimeter measurements.

    * `timestamp : float` timestamp provided by datetime.datetime.now().timestamp()
    * `time : float` delta time provided by time.monotonic()
    * `value : float` measured value
    * `mode : Mode` multimeter mode used for the measurement
    """
    timestamp : float
    time : float
    value : float
    mode : Mode

    def __iter__(self):
        return iter((self.timestamp, self.time, self.value))
    @property
    def header(self):
        return 'timestamp,time,' + str(self.mode.name)

@dataclass
class SupplyData(Data):
    """
        Implementation of Data for measurements taken directly by power
        supply driver classes.
    
        * `timestamp : float` timestamp provided by datetime.datetime.now().timestamp()
        * `time : float` delta time provided by time.monotonic()
        * `voltage : float` measured output voltage
        * `current : float` measured output current
        * `power : float` measured output power
        * `temperature : float` temperature
        * `payload : Payload` additional data specific to the power supply model or type
        """
    voltage : float
    current : float
    power : float
    timestamp : float # provided by datetime.datetime.now().timestamp()
    time : float # provided by time.monotonic()
    payload : Payload = None
    temperature : float | None = None # TODO seperate temperature collection?

    def __iter__(self):
        return iter((self.timestamp, self.time, self.voltage, self.current, self.power, self.temperature, *self.payload))
    @property
    def header(self) -> str:
        return '' # TODO maybe (not actually used anywhere)

@dataclass
class SamplerData(Data):
    """
            Implementation of Data for measurements in flash experiments
            after processing.
        
            * `timestamp : float` timestamp provided by datetime.datetime.now().timestamp()
            * `time : float` delta time provided by time.monotonic()
            * `voltage : float` measured output voltage
            * `current : float` measured output current
            * `power : float` measured output power
            * `e_field : float` calculated E-field
            * `curr_density : float` calculated current density
            * `power_density : float` calculated power density
            * `temperature : float` temperature
            * `payload : Payload` additional data specific to the power supply model or type
            """
    voltage : float
    current : float
    power : float
    e_field : float
    curr_density : float
    power_density : float
    timestamp : float
    time : float
    temperature : float
    payload : Payload = None

    def __iter__(self):
        return iter((
            self.timestamp,
            self.time,
            self.voltage,
            self.current,
            self.power,
            self.e_field,
            self.curr_density,
            self.power_density,
            self.temperature,
            *self.payload
        ))
    @property
    def header(self):
        return FLASH_CSV_HEADER + ',' + self.payload.header
