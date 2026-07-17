import pyvisa

rm = pyvisa.ResourceManager()
class Multimeter:
    def __init__(self,
                    port : int
    ):
        self.port = port
        self.connected = False
        self.res : pyvisa.resources.Resource

    def connect(self) -> None:
        if not self.connected:
            self.res = rm.open_resource(f'ASRL{self.port}::INSTR')

        # make sure this device is what we think it is
        print(self.res.query('*IDN?'))
        if "B&K Precision,MR3K160120,615E25116,3.13-3.13-1.06-1.H8" not in self.res.query('*IDN?'):
            raise Exception("Device not recognized.")
        
        # TODO any necessary reset
    
    def disconnect(self) -> None:
        if self.connected:
            self.res.close()