"""
Classes for communication between threads in flash control
"""

from dataclasses import dataclass
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from control.data import (
    SamplerData,
)


@dataclass
class RampParams:
    """
    Ramping configuration
    """
    ramp: bool
    start: float
    end: float
    rate: float

@dataclass
class PulseParams:
    """
    Pulse configuration
    """
    pulse: bool
    period: float
    duty_cycle: float

@dataclass
class Params:
    """
    Flash experiment parameters from GUI.
    """
    ramp_data: RampParams | None
    pulse_data: PulseParams | None
    e_field: float
    curr_density: float
    diameter: float
    height: float
    sample_interval: float
    freq: float | None = None

class GuiSignals(QObject):
    """
    Signals from GUI
    """
    connectSig = pyqtSignal(str, str) # addr, filepath
    disconnectSig = pyqtSignal()
    setParamsSig = pyqtSignal(Params)
    startSig = pyqtSignal()
    stopSig = pyqtSignal()
    exitSig = pyqtSignal()

class SampleSignals(QObject):
    """
    Signals from thread handling data sampling
    """
    newDataSig = pyqtSignal(SamplerData)

class ControlSignals(QObject):
    """
    Signals from control thread
    """
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

    errorSig = pyqtSignal(str, str) # title, text
