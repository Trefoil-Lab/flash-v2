from dataclasses import dataclass
from typing import NamedTuple

@dataclass
class SupplyData:
    voltage : float
    current : float
    power : float
    timestamp : float # provided by datetime.datetime.now().timestamp()
    monotonic_time : float # provided by time.monotonic()
    payload : NamedTuple = tuple()
    temperature : float | None = None # TODO seperate temperature collection?

@dataclass
class SamplerData:
    voltage : float
    current : float
    power : float
    e_field : float
    curr_density : float
    power_density : float
    timestamp : float
    delta_time : float
    temperature : float
    payload : NamedTuple = tuple()

class ACPayload(NamedTuple):
    complex_power: complex
    frequency : float

AC_PAYLOAD_CSV_HEADER = 'S (VA),freq (Hz)'

DC_PAYLOAD_CSV_HEADER = ''