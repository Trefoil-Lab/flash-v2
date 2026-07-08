import pyvisa
import time

DC_SOURCE_ADDR = "USB0::0x3121::0x1004::615E25116::INSTR"

rm = pyvisa.ResourceManager()

class DCSupply:
    def __init__(self : DCSupply, addr : str):
        self.addr = addr
        self.connected = False

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


def cli():
    PROMPT_STR = '> '
    def help():
        print('usage: <command> [<arg> [<arg>]]')
        print('commands:')
        print('\tQ\t\texit')
        print('\tH\t\tprint this message')
        print('\tC\t\ttoggle device connection (initially connected)')
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
    cli()