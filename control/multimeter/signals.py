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
    

class GuiSignals(QObject):
    connectSig = pyqtSignal(int) # com port
    disconnectSig = pyqtSignal()
    startSig = pyqtSignal()