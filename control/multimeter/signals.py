"""
Classes for communication between threads in multimeter control.
"""

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
    """
    Experiment configuration.
    """
    mode : multimeter.Mode
    auto_zero : bool
    memo : str
    filepath : str

class GuiSignals(QObject):
    """
    Signals from GUI
    """
    connectSig = pyqtSignal(int) # com port
    disconnectSig = pyqtSignal()
    startSig = pyqtSignal(Config)
    stopSig = pyqtSignal()
    exitSig = pyqtSignal()

class ControlSignals(QObject):
    """
    Signals from control thread
    """
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
    """
    Signals from sampler thread
    """
    newDataSig = pyqtSignal(MultimeterData)