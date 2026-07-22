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
    def __iter__(self):
        return iter(tuple())
    @property
    def header(self) -> str:
        return ''

@dataclass
class ACPayload(Payload):
    complex_power: complex
    frequency : float

    def __iter__(self):
        return iter((self.complex_power, self.frequency))
    @property
    def header(self) -> str:
        return AC_PAYLOAD_CSV_HEADER


@dataclass
class Data(ABC):
    time : float

    def __iter__(self):
        return iter((self.time))
    @abstractmethod
    @property
    def header(self) -> str:
        pass

@dataclass
class MultimeterData(Data):
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
    voltage : float
    current : float
    power : float
    timestamp : float # provided by datetime.datetime.now().timestamp()
    time : float # provided by time.monotonic()
    payload : Payload = Payload()
    temperature : float | None = None # TODO seperate temperature collection?

    def __iter__(self):
        return iter((self.timestamp, self.time, self.voltage, self.current, self.power, self.temperature, *self.payload))
    @property
    def header(self) -> str:
        return '' # TODO maybe

@dataclass
class SamplerData(Data):
    voltage : float
    current : float
    power : float
    e_field : float
    curr_density : float
    power_density : float
    timestamp : float
    time : float
    temperature : float
    payload : Payload = Payload()

    def __iter__(self):
        return iter(
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
        )
    @property
    def header(self):
        return FLASH_CSV_HEADER + ',' + self.payload.header
