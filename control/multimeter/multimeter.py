from enum import StrEnum
import pyvisa
import pyvisa.constants
import time

rm = pyvisa.ResourceManager()

class Mode(StrEnum):
    AC_VOLT = 'VOLT:AC'
    AC_CURR = 'CURR:AC'
    DC_VOLT = 'VOLT:DC'
    DC_CURR = 'CURR:DC'
    RESIST = 'RES'
    RESIST_4WIRE = 'FRES'
    FREQ = 'FREQ'
    PERIOD = 'PER'

class Range(StrEnum):
    MIN = 'MIN'
    MAX = 'MAX'
    AUTO = 'DEF'

class Multimeter:
    def __init__(self,
        port : int
    ):
        self.port = port
        self.connected = False
        self.res : pyvisa.resources.SerialInstrument

    def connect(self) -> None:
        if not self.connected:
            self.res = rm.open_resource(f'ASRL{self.port}::INSTR')
            self.res.data_bits = 7
            self.res.stop_bits = pyvisa.constants.StopBits.two
            self.res.parity = pyvisa.constants.Parity.even
            self.res.flow_control = pyvisa.constants.ControlFlow.dtr_dsr

        # make sure this device is what we think it is
        print(self.res.query('*IDN?'))
        if "HEWLETT-PACKARD,34401A,0,11-5-2" not in self.res.query('*IDN?'):
            raise Exception("Device not recognized.")
        
        # TODO any necessary reset
        self.res.write('SYST:REM') # set to remote mode

        self.connected = True
    
    def disconnect(self) -> None:
        if self.connected:
            self.res.close()

    def configure(self,
        mode : Mode,
        range : Range | float = Range.AUTO,
        resolution : Range | float = Range.AUTO,
        count : int = 1,
        delay : float | None = None,
    ) -> None:
        # set mode, range, and resolution
        self.res.write(f'CONF:{str(mode)} {str(range)},{str(resolution)}')

        self.res.write(f'SAMP:COUN {count}') # set sample count
        if not delay is None and delay > 0:
            self.res.write(f'TRIG:DEL {delay}') # set sample delay
        self.res.write(f'TRIG:SOUR IMM') # set to trigger immediately on READ?

    def read(self) -> list[float]:
        data = self.res.query_ascii_values('READ?')
        return data
    
    def measure(self,
        mode : Mode,
        range : Range = Range.AUTO,
        resolution : Range = Range.AUTO
    ) -> float:
        print(f'MEAS:{str(mode)}? {str(range)},{str(resolution)}')
        return float(self.res.query(f'MEAS:{str(mode)}? {str(range)},{str(resolution)}'))

def main():
    mm = Multimeter(3)
    mm.connect()
    for _ in range(4):
        print(mm.res.query('SYST:ERR?'))

    mm.configure(
        mode=Mode.DC_VOLT,
    )

    mm.res.write('TRIG:COUN:INF')
    while True:
        try:
            mm.res.write('READ?')
            print(mm.res.read())
        except KeyboardInterrupt as e:
            break
    mm.res.write('SYST:LOC')

if __name__ == "__main__":
    main()