from enum import Enum

DC_SOURCE_ADDR = "USB0::0x3121::0x1004::615E25116::INSTR"
AC_SOURCE_ADDR = "USB0::0xFFFF::0x7749::581H24111::INSTR"


RAMP_INTERVAL_S = 0.200
SAVE_INTERVAL_S = 10
CSV_HEADER = 'Timestamp,Time,Volts(rms),Amps(rms),|S|(VA),E,J,P,T'


class SupplyType(Enum):
    DC = 1
    AC = 2