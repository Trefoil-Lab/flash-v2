import time
import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
import pyvisa

from control.data import (
    SupplyData,
    ACPayload,
    AC_PAYLOAD_CSV_HEADER,
    DC_PAYLOAD_CSV_HEADER,
)


rm = pyvisa.ResourceManager()


class Supply(ABC):
    """
    Abstract base class for AC and DC power supplies.
    """
    @abstractmethod
    def __init__(self, addr : str):
        pass

    @abstractmethod
    def meas(self) -> SupplyData:
        """
        Take output measurements.

        Returns:
            Data: Voltage, current, power, timestamp, and any additional data
        """
        pass

    @abstractmethod
    def getHeader(self) -> str:
        """
        Get CSV header for additional data other than power, voltage, and current.

        Returns:
            str: comma-seperated single line header
        """
        pass

    @abstractmethod
    def connect(self) -> None:
        """
        Connect to the power supply.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnect from the power supply.
        """
        pass

    @abstractmethod
    def enable(self) -> None:
        """
        Enable the power supply output.
        """
        pass

    @abstractmethod
    def disable(self) -> None:
        """
        Disable the power supply output.
        """
        pass

    @abstractmethod
    def setV(self, v : float) -> None:
        """
        Set power supply voltage.

        Args:
            v (float): voltage (volts)
        """
        pass

    @abstractmethod
    def setI(self, i : float) -> None:
        """
        Set power supply current limit.

        Args:
            i (float): current (amps)
        """
        pass

    @abstractmethod
    def getV(self) -> float:
        """
        Get voltage setting.

        Returns:
            float: voltage (volts)
        """
        pass

    @abstractmethod
    def getI(self) -> float:
        """
        Get current limit setting.

        Returns:
            float: current (amps)
        """
        pass

    @abstractmethod
    def measI(self) -> float:
        """
        Measure current output.

        Returns:
            float: current (amps)
        """
        pass

    @abstractmethod
    def measV(self) -> float:
        """
        Measure voltage output.

        Returns:
            float: voltage (volts)
        """
        pass


class DCSupply(Supply):
    def __init__(self : DCSupply, addr : str):
        self.addr = addr
        self.connected = False

    def meas(self):
        return SupplyData(
            voltage=self.measV(),
            current=self.measI(),
            power=self.measP(),
            # temperature=random.randint(1, 100),
            timestamp=datetime.datetime.now().timestamp(),
            time=time.monotonic()
        )

    def getHeader(self):
        return DC_PAYLOAD_CSV_HEADER

    def connect(self):
        if not self.connected:
            self.res : pyvisa.resources.Resource = rm.open_resource(self.addr)

        # make sure this device is what we think it is
        print(self.res.query('*IDN?'))
        if "B&K Precision,MR3K160120,615E25116,3.13-3.13-1.06-1.H8" not in self.res.query('*IDN?'):
            raise Exception("Device not recognized.")
        
        # reset back to zero voltage, zero current, output off
        self.disable()
        self.setI(0)
        self.setV(0)
        # TODO reset other parameters

        self.connected = True

    def disconnect(self):
        if self.connected:
            self.disable()
            self.res.close()
            self.connected = False

    def setV(self, v : float) -> None:
        self.res.write(f'volt {v}')
        
    def setI(self, i : float) -> None:
        self.res.write(f'curr {i}')

    def getV(self) -> float:
        return float(self.res.query('volt?'))

    def getI(self) -> float:
        return float(self.res.query('curr?'))

    def measV(self) -> float:
        return float(self.res.query('meas:volt?'))

    def measI(self) -> float:
        return float(self.res.query('meas:curr?'))
    
    def measP(self) -> float:
        return float(self.res.query('meas:pow?'))

    def enable(self) -> None:
        self.res.write('outp on')

    def disable(self) -> None:
        self.res.write('outp off')


class ACSupply(Supply):
    def __init__(self : ACSupply, addr : str):
        self.addr = addr
        self.connected = False

    def meas(self):
        return SupplyData(
            voltage=self.measVAC(),
            current=self.measIAC(),
            power=self.measP_apparent(),
            # temperature=random.randint(1, 100),
            timestamp=datetime.datetime.now().timestamp(),
            time=time.monotonic(),
            payload=ACPayload(
                complex_power=self.measP_real() + self.measP_reactive()*1j,
                frequency=self.measFreq(), # frequency
            )
        )

    def getHeader(self):
        return AC_PAYLOAD_CSV_HEADER

    def connect(self):
        if not self.connected:
            self.res : pyvisa.resources.Resource = rm.open_resource(self.addr)

        # make sure this device is what we think it is
        print(self.res.query('*IDN?'))
        if "B&K PRECISION,9833B,581H24111,8.08/8.011a/8.004b/1.H8/A.004c" not in self.res.query('*IDN?'):
            raise Exception("Device not recognized.")
        
        # reset back to zero voltage, zero current, output off
        self.disable()
        self.setI(0)
        self.setVAC(0)
        # TODO reset other parameters

        self.connected = True

    def disconnect(self):
        if self.connected:
            self.disable()
            self.res.close()
            self.connected = False

    def setVAC(self, v : float) -> None:
        if v > 150:
            self.res.write('volt:rang high')
        else:
            self.res.write('volt:rang low')
        self.res.write(f'volt:ac {v}')
        
    def setI(self, i : float) -> None:
        self.res.write(f'outp:lim:curr {i}')

    def setFreq(self, f : float) -> None:
        self.res.write(f'freq {f}')

    def getVAC(self) -> float:
        return float(self.res.query('volt:ac?'))

    def getI(self) -> float:
        return float(self.res.query('outp:lim:curr?'))

    def getFreq(self) -> float:
        return float(self.res.query('freq?'))

    def measVAC(self) -> float:
        return float(self.res.query('meas:volt:ac?'))

    def measIAC(self) -> float:
        return float(self.res.query('meas:curr:ac?'))
    
    def measI_inrush(self) -> float:
        return float(self.res.query('meas:curr:inrush?'))
    
    def measP_apparent(self) -> float:
        return float(self.res.query('meas:pow:ac:app?'))
    
    def measP_real(self) -> float:
        return float(self.res.query('meas:pow:ac:real?'))

    def measP_reactive(self) -> float:
        return float(self.res.query('meas:pow:ac:reac?'))

    def measFreq(self) -> float:
        return float(self.res.query('meas:freq?'))

    def enable(self) -> None:
        self.res.write('outp on')

    def disable(self) -> None:
        self.res.write('outp off')

    def getV(self):
        return self.getVAC()

    def measI(self):
        return self.measIAC()
    
    def measV(self):
        self.measVAC()

    def setV(self, v):
        return self.setVAC(v)


def cli_AC():
    PROMPT_STR = '> '
    def help():
        print('usage: <command> [<arg> [<arg>]]')
        print('commands:')
        print('\tQ\t\texit')
        print('\tH\t\tprint this message')
        print('\tC\t\ttoggle device connection (initially disconnected)')
        print('\tV <volt>\tset voltage to <volt>')
        print('\tV?\t\tget voltage setting')
        print('\tI <curr>\tset current to <curr>')
        print('\tI?\t\tget current setting')
        print('\tM [V|I|P]\tmeasure voltage, current, or power. if unspecified, report all three')
        print('\tM L [<count>]\tmeasure measurement latency with count iterations. default 1000')
        print()

    # create DC source object
    source : ACSupply = ACSupply(AC_SOURCE_ADDR)
    # source.connect()

    # print directions
    help()

    cmd : str = input(PROMPT_STR).lower()
    while cmd != 'q':
        if not source.connected and cmd != 'c':
            print('Not currently connected.')
            cmd = input(PROMPT_STR)
            continue
        match cmd[0]:
            case 'h': #help
                help()
            case 'c': # toggle connection
                if source.connected:
                    source.disconnect()
                    print('Disconnected.')
                else:
                    source.connect()
                    print('Connected.')
            case 'e': # enable
                source.enable()
            case 'd': # disable
                source.disable()
            case 'v': # voltage setting
                if cmd == 'v?':
                    print(source.getVAC())
                else:
                    try:
                        v = float(cmd.split()[1])
                        source.setVAC(v)
                    except Exception as e:
                        print('Invalid command.')
            case 'i': # current setting
                if cmd == 'i?':
                    print(source.getI())
                else:
                    try:
                        i = float(cmd.split()[1])
                        source.setI(i)
                    except ValueError:
                        print('Invalid command.')
            case 'm': # measure
                if len(cmd.split()) > 1:
                    match cmd.split()[1]:
                        case 'v': # voltage
                            print(source.measVAC())
                        case 'i': # current
                            print(source.measIAC())
                        case 'p': # power
                            print(source.measP_apparent())
                        case 'l': # latency
                            count : int = 1000
                            if len(cmd.split()) > 2:
                                try:
                                    count = int(cmd.split()[2])
                                except ValueError:
                                    print('Invalid command.')
                                    count  = 1000
                            time_before = time.perf_counter()
                            for _ in range(0, count):
                                source.measVAC()
                            elapsed = time.perf_counter() - time_before
                            print(f'{count} iterations: {elapsed}s, {elapsed/float(count)}s per iteration')
                        case _:
                            print('Invalid command.')
                else:
                    print(f'V={source.measVAC()}\tI={source.measIAC()}\tP={source.measP_apparent()}')
            case _:
                print('Invalid command.')
        
        cmd = input(PROMPT_STR)

def cli_DC():
    PROMPT_STR = '> '
    def help():
        print('usage: <command> [<arg> [<arg>]]')
        print('commands:')
        print('\tQ\t\texit')
        print('\tH\t\tprint this message')
        print('\tC\t\ttoggle device connection (initially disconnected)')
        print('\tV <volt>\tset voltage to <volt>')
        print('\tV?\t\tget voltage setting')
        print('\tI <curr>\tset current to <curr>')
        print('\tI?\t\tget current setting')
        print('\tM [V|I|P]\tmeasure voltage, current, or power. if unspecified, report all three')
        print('\tM L [<count>]\tmeasure measurement latency with count iterations. default 1000')
        print()

    # create DC source object
    source : DCSupply = DCSupply(DC_SOURCE_ADDR)
    # source.connect()

    # print directions
    help()

    cmd : str = input(PROMPT_STR).lower()
    while cmd != 'q':
        if not source.connected and cmd != 'c':
            print('Not currently connected.')
            cmd = input(PROMPT_STR)
            continue
        match cmd[0]:
            case 'h': #help
                help()
            case 'c': # toggle connection
                if source.connected:
                    source.disconnect()
                    print('Disconnected.')
                else:
                    source.connect()
                    print('Connected.')
            case 'e': # enable
                source.enable()
            case 'd': # disable
                source.disable()
            case 'v': # voltage setting
                if cmd == 'v?':
                    print(source.getV())
                else:
                    try:
                        v = float(cmd.split()[1])
                        source.setV(v)
                    except Exception as e:
                        print('Invalid command.')
            case 'i': # current setting
                if cmd == 'i?':
                    print(source.getI())
                else:
                    try:
                        i = float(cmd.split()[1])
                        source.setI(i)
                    except ValueError:
                        print('Invalid command.')
            case 'm': # measure
                if len(cmd.split()) > 1:
                    match cmd.split()[1]:
                        case 'v': # voltage
                            print(source.measV())
                        case 'i': # current
                            print(source.measI())
                        case 'p': # power
                            print(source.measP())
                        case 'l': # latency
                            count : int = 1000
                            if len(cmd.split()) > 2:
                                try:
                                    count = int(cmd.split()[2])
                                except ValueError:
                                    print('Invalid command.')
                                    count  = 1000
                            time_before = time.perf_counter()
                            for _ in range(0, count):
                                source.measV()
                            elapsed = time.perf_counter() - time_before
                            print(f'{count} iterations: {elapsed}s, {elapsed/float(count)}s per iteration')
                        case _:
                            print('Invalid command.')
                else:
                    print(f'V={source.measV()}\tI={source.measI()}\tP={source.measP()}')
            case _:
                print('Invalid command.')
        
        cmd = input(PROMPT_STR)

if __name__ == "__main__":
    cli_DC()