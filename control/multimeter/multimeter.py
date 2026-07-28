"""
Multimeter drivers.
"""

from enum import StrEnum
import pyvisa
import pyvisa.constants
import time

# from util import util


rm = pyvisa.ResourceManager()

class Mode(StrEnum):
    """
    Multimeter operation mode.
    """
    AC_VOLT = 'VOLT:AC'
    AC_CURR = 'CURR:AC'
    DC_VOLT = 'VOLT:DC'
    DC_CURR = 'CURR:DC'
    RESIST = 'RES'
    RESIST_4WIRE = 'FRES'
    FREQ = 'FREQ'
    PERIOD = 'PER'

class Range(StrEnum):
    """
    Minimum, maximum, and default options for numerical fields
    """
    MIN = 'MIN'
    MAX = 'MAX'
    AUTO = 'DEF'

class Multimeter:
    """
    Multimeter driver. Currently supports only the Hewlett-Packard 34401A.
    """
    # range_limits : dict[Mode, util.Limits] = {
    #     Mode.AC_VOLT: util.Limits(1e-1, 1e3),
    #     Mode.AC_CURR: util.Limits(1e0, 3e0),
    #     Mode.DC_VOLT: util.Limits(1e-3, 1e3),
    #     Mode.DC_CURR: util.Limits(1e-2, 3e0),
    #     Mode.RESIST: util.Limits(1e2, 1e8),
    #     Mode.RESIST_4WIRE: util.Limits(1e2, 1e8),
    #     Mode.FREQ: util.Limits(1e-1, 1e3),
    #     Mode.PERIOD: util.Limits(1e-1, 1e3)
    # }

# VOLT:AC: MAX=+9.99999900E-02
#  MIN=+1.00000000E-03

# CURR:AC: MAX=+1.00000000E-04
#  MIN=+1.00000000E-06

# VOLT:DC: MAX=+1.00000000E-03
#  MIN=+3.00000000E-06

# CURR:DC: MAX=+1.00000000E-04
#  MIN=+3.00000000E-07

# RES: MAX=+1.00000000E+04
#  MIN=+3.00000000E+01

# FRES: MAX=+1.00000000E+04
#  MIN=+3.00000000E+01

    def __init__(self,
        port : int
    ):
        """
        Create the multimeter object.

        Args:
            port (int): COM port to use
        """
        self.port = port
        self.connected = False
        self.res : pyvisa.resources.SerialInstrument

    def connect(self) -> None:
        """
        Connect to the multimeter.

        Raises:
            Exception: Device not recognized
        """
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
        """
        Disconnect the multimeter.
        """
        if self.connected:
            self.res.write('SYST:LOC')
            self.res.close()

    def configure(self,
        mode : Mode,
        range : Range | float = Range.AUTO,
        resolution : Range | float = Range.AUTO,
        auto_zero : bool = True,
        count : int = 1,
        delay : float | None = None,
    ) -> None:
        """
        Configure the multimeter for data collection. Once configured,
        call read() to take measurements.

        Args:
            mode (Mode): Operating mode
            range (Range | float, optional): Measurement range. Defaults to Range.AUTO.
            resolution (Range | float, optional): Measurement resolution. Defaults to Range.AUTO.
            auto_zero (bool, optional): Auto zero. Defaults to True.
            count (int, optional): Samples to collect. Defaults to 1.
            delay (float | None, optional): Delay after trigger and between samples. Defaults to None.
        """
        # set mode, range, and resolution
        self.res.write(f'CONF:{str(mode)} {str(range)},{str(resolution)}')
        self.res.write(f'ZERO:AUTO {'ON' if auto_zero else 'OFF'}')

        self.res.write(f'SAMP:COUN {count}') # set sample count
        if not delay is None and delay > 0:
            self.res.write(f'TRIG:DEL {delay}') # set sample delay
        self.res.write(f'TRIG:SOUR IMM') # set to trigger immediately on READ?

    def read(self) -> list[float]:
        """
        Take measurement. The multimeter should first be configured
        with configure().

        Returns:
            list[float]: list of reading(s)
        """
        data = self.res.query_ascii_values('READ?')
        return data
    
    def measure(self,
        mode : Mode,
        range : Range = Range.AUTO,
        resolution : Range = Range.AUTO
    ) -> float:
        """
        Take a one-off measurement.

        Args:
            mode (Mode): Operating mode
            range (Range, optional): Measurement range. Defaults to Range.AUTO.
            resolution (Range, optional): Measurement resolution. Defaults to Range.AUTO.

        Returns:
            float: measured value
        """
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

    for i in Mode:
        print(f'{i}: MAX={mm.res.query(i + ':RES? MAX')} MIN={mm.res.query(i + ':RES? MIN')}')

    # mm.res.write('TRIG:COUN:INF')
    # while True:
    #     try:
    #         mm.res.write('READ?')
    #         print(mm.res.read())
    #     except KeyboardInterrupt as e:
    #         break
    # mm.res.write('SYST:LOC')

if __name__ == "__main__":
    main()