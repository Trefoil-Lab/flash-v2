from dataclasses import dataclass
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from util.data import (
    SamplerData,
)


@dataclass
class RampParams:
    ramp: bool
    start: float
    end: float
    rate: float

@dataclass
class PulseParams:
    pulse: bool
    period: float
    duty_cycle: float

@dataclass
class Params:
    ramp_data: RampParams | None
    pulse_data: PulseParams | None
    e_field: float
    curr_density: float
    diameter: float
    height: float
    sample_interval: float
    freq: float | None = None

class GuiSignals(QObject):
    connectSig = pyqtSignal(str, str) # addr, filepath
    disconnectSig = pyqtSignal()
    setParamsSig = pyqtSignal(Params)
    startSig = pyqtSignal()
    stopSig = pyqtSignal()
    exitSig = pyqtSignal()

class SampleSignals(QObject):
    newDataSig = pyqtSignal(SamplerData)

class ControlSignals(QObject):
    newDataSig = pyqtSignal(SamplerData)

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
