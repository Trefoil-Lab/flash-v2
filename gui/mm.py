import sys
from PyQt6.QtCore import QSize, Qt, QThreadPool
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QDialog,
    QFileDialog,
    QLabel,
    QPushButton,
    QMessageBox,
    QSpacerItem,
    QSizePolicy
)
from PyQt6 import QtGui
import pyqtgraph as pg
import numpy as np
import os
import math
import cmath
import datetime

from .ui.MultimeterMainWindow import Ui_MainWindow
from .ui.ConnectDialog import Ui_Dialog
from control.multimeter.control import (
    MultiMeterRunner
)
from control.flash.signals import (
    GuiSignals,
    ControlSignals,
    Params,
    RampParams,
    PulseParams,
)
from util.const import (
    AC_SOURCE_ADDR,
    SupplyType
)
from control.data import (
    SamplerData,
    ACPayload
)


WINDOW_TITLE = 'AC flash'
CONNECTION_DIALOG_TITLE = 'connection dialog'

E_FIELD_COLOR_STR = '#00FFFF'
CURRENT_DENSITY_COLOR_STR = '#FF0000'
POWER_DENSITY_COLOR_STR = '#FFFF00'
TEMPERATURE_COLOR_STR = '#00FF00'


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        ###############################
        # custom initialization below #
        ###############################

        self.setWindowTitle(WINDOW_TITLE)

        # set up control thread
        self.signals = GuiSignals()
        
        # set up control signal listeners
        self.control_thread.signals.newDataSig.connect(self.receiveData)
        self.control_thread.signals.connectingSig.connect(self.connecting)
        self.control_thread.signals.connectedSig.connect(self.connected)
        self.control_thread.signals.disconnectingSig.connect(self.disconnecting)
        self.control_thread.signals.disconnectedSig.connect(self.disconnected)
        self.control_thread.signals.settingParamsSig.connect(self.settingParams)
        self.control_thread.signals.setParamsDoneSig.connect(self.setParamsDone)
        self.control_thread.signals.startingSig.connect(self.starting)
        self.control_thread.signals.startedSig.connect(self.started)
        self.control_thread.signals.stoppingSig.connect(self.stopping)
        self.control_thread.signals.stoppedSig.connect(self.stopped)
        self.control_thread.signals.rampingSig.connect(self.ramping)
        self.control_thread.signals.rampingDoneSig.connect(self.rampingDone)

        # connect buttons
        self.currentDensityModeComboBox.currentIndexChanged.connect(self.currDensityModeSelect)
        self.pulseEnableCheckBox.checkStateChanged.connect(self.pulseCheckChange)
        self.diameterCmDoubleSpinBox.valueChanged.connect(self.updateSpinBoxLimits)
        self.heightCmDoubleSpinBox.valueChanged.connect(self.updateSpinBoxLimits)
        self.eFieldDoubleSpinBox.valueChanged.connect(self.updateSpinBoxLimits)
        self.applyButton.clicked.connect(self.applyPress)
        self.connectionButton.clicked.connect(self.connectionTogglePress)
        self.startButton.clicked.connect(self.startPress)
        self.stopButton.clicked.connect(self.stopPress)

        # set up graphs
        self.time = []
        self.val = []
        self.valPlotItem = self.graph1.plot(self.time, self.val, pen=pg.mkPen(color=E_FIELD_COLOR_STR))
        self.graph.setLimits(xMin=0)
        self.graph.setBackground(background=None)


    #########################
    # button press handlers #
    #########################

    def closeEvent(self, event):
        print('Stopping.')
        self.signals.stopSig.emit()
        print('Disconnecting.')
        self.signals.disconnectSig.disconnect()
        print('Stopping control thread.')
        self.signals.exitSig.emit()
        print('Exiting...')
        event.accept()

    def connectionTogglePress(self):
        self.connectionButton.setDisabled(True) # prevent further presses

        if self.control_thread.status.connected:
            self.signals.disconnectSig.emit()
        else:
            dlg = ConnectDialog(self.signals, self.connectionButton)
            dlg.exec()

    def startPress(self):
        self.startButton.setDisabled(True) # prevent further presses

        self.signals.startSig.emit()

        # clear previously plotted data
        self.time = []
        self.val = []

    def stopPress(self):
        self.stopButton.setDisabled(True) # prevent further presses

        self.signals.stopSig.emit()

    ###########################
    # control signal handlers #
    ###########################

    def receiveData(self, data : SamplerData):
        self.time.append(data.time)
        self.val.append(data.e_field)


    def connecting(self):
        self.statusbar.showMessage('Connecting...')

    def connected(self):
        self.connectionButton.setDisabled(False)
        self.startButton.setDisabled(False)
        self.applyButton.setDisabled(False)
        with self.control_thread.status_lock:
            if self.control_thread.status.running:
                self.stopButton.setDisabled(False)
            else:
                self.startButton.setDisabled(False)
        self.connectionButton.setText('Disconnect')
        self.statusbar.showMessage('Connected!', 1000)

    def disconnecting(self):
        self.statusbar.showMessage('Disconnecting...')

    def disconnected(self):
        self.connectionButton.setDisabled(False)
        self.applyButton.setDisabled(True)
        self.startButton.setDisabled(True)
        self.stopButton.setDisabled(True)
        self.connectionButton.setText('Connect')
        self.statusbar.showMessage('Disconnected!', 1000)

    def started(self):
        self.stopButton.setDisabled(False)
        self.readoutI.show()
        self.readoutV.show()
        self.readoutS.show()
        self.statusbar.showMessage('Started!', 1000)

    def stopping(self):
        self.statusbar.showMessage('Stopping...')

    def stopped(self):
        self.startButton.setDisabled(False)
        self.applyButton.setDisabled(False)
        self.readoutI.hide()
        self.readoutV.hide()
        self.readoutS.hide()
        self.statusbar.showMessage('Stopped!', 1000)

class ConnectDialog(Ui_Dialog, QDialog):
    def __init__(self, gui_signals : GuiSignals, connection_button : QPushButton):
        super().__init__()
        self.setupUi(self)

        ######################
        # custom setup below #
        ######################

        self.gui_signals = gui_signals
        self.connection_button = connection_button
        self.setWindowTitle(CONNECTION_DIALOG_TITLE)

        # set up event listeners
        self.browseButton.pressed.connect(self.browse)
    
    def browse(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.Directory)

        if file_dialog.exec():
            folder = file_dialog.selectedFiles()[0]
            self.filePathLineEdit.setText(folder)

    def accept(self):
        folder = self.filePathLineEdit.text()
        if not os.path.isdir(folder):
            QMessageBox.critical(None, 'Error', 'Invalid directory.')
            return
        
        # build file name
        filename : str = datetime.datetime.now().strftime('%y-%m-%d-%H%M')
        for input in (self.materialLineEdit, self.temperatureLineEdit, self.volumeLineEdit, self.currentLineEdit):
            if len(input.text()) != 0:
                filename += '_' + '-'.join(input.text().split())
        filename += '.csv'
        print(folder)
        print(filename)
        filepath = os.path.join(folder, filename)
        print(filepath)

        self.gui_signals.connectSig.emit(AC_SOURCE_ADDR, filepath)

        return super().accept()
    
    def reject(self):
        self.connection_button.setDisabled(False)
        return super().reject()

if __name__ == "__main__":
    main()
