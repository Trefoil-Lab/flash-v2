from PyQt6.QtCore import QObject, pyqtSignal
from dataclasses import dataclass

from control.data import (
    MultimeterData
)
from control.multimeter import (
    multimeter
)


@dataclass
class Config:
    mode : multimeter.Mode
    auto_zero : bool
    memo : str
    filepath : str

class GuiSignals(QObject):
    connectSig = pyqtSignal(int) # com port
    disconnectSig = pyqtSignal()
    startSig = pyqtSignal(Config)
    stopSig = pyqtSignal()
    exitSig = pyqtSignal()

class ControlSignals(QObject):
    newDataSig = pyqtSignal(MultimeterData)

    connectingSig = pyqtSignal()
    connectedSig = pyqtSignal()

    disconnectingSig = pyqtSignal()
    disconnectedSig = pyqtSignal()

    startingSig = pyqtSignal()
    startedSig = pyqtSignal()

    stoppingSig = pyqtSignal()
    stoppedSig = pyqtSignal()

class SampleSignals(QObject):
    newDataSig = pyqtSignal(MultimeterData)