from dataclasses import dataclass
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

@dataclass
class Status:
    connected : bool = False
    running : bool = False

@dataclass
class RampData:
    ramp: bool
    start: float
    end: float
    rate: float

@dataclass
class Params:
    ramp_data: RampData | None
    e_field: float
    curr_density: float
    diameter: float
    height: float
    sample_interval: float

class GuiSignals(QObject):
    connectSig = pyqtSignal(str)
    disconnectSig = pyqtSignal()
    setParamsSig = pyqtSignal(Params)
    startSig = pyqtSignal()
    stopSig = pyqtSignal()
    exitSig = pyqtSignal()

class SampleSignals(QObject):
    newDataSig = pyqtSignal(tuple) # (time, V, I, P, T)

class ControlSignals(QObject):
    newDataSig = pyqtSignal(tuple) # (time, E, J, P, T)

    connectingSig = pyqtSignal()
    connectedSig = pyqtSignal()

    disconnectingSig = pyqtSignal()
    disconnectedSig = pyqtSignal()

    rampingSig = pyqtSignal()
    rampingDoneSig = pyqtSignal()

    setParamsDirectSig = pyqtSignal(Params)
    settingParamsSig = pyqtSignal()
    setParamsDoneSig = pyqtSignal()

    startingSig = pyqtSignal()
    startedSig = pyqtSignal()

    stoppingSig = pyqtSignal()
    stoppedSig = pyqtSignal()
