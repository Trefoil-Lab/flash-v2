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
    QWidget,
    QSpacerItem,
    QSizePolicy
)
from PyQt6 import QtGui
import pyqtgraph as pg
import numpy as np
import os
import datetime

from .MainWindow import Ui_MainWindow
from .ConnectDialog import Ui_Dialog
from .util import GuiSignals, ControlSignals, Params, RampData
from .control import ControlRunner

DC_SOURCE_ADDR = "USB0::0x3121::0x1004::615E25116::INSTR"

WINDOW_TITLE = 'flash-v1'
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
        self.threadpool = QThreadPool()
        self.control_thread = ControlRunner(DC_SOURCE_ADDR, self.signals, 
                                            Params(
                                                ramp_data=RampData(
                                                    ramp=self.currentDensityModeComboBox.currentText == 'Ramp',
                                                    start=self.currentDensityStartDoubleSpinBox.value(),
                                                    end=self.currentDensityEndDoubleSpinBox.value(),
                                                    rate=self.currentDensityRateDoubleSpinBox.value()
                                                ),
                                                e_field=self.eFieldDoubleSpinBox.value(),
                                                curr_density=self.currentDensityStartDoubleSpinBox.value(),
                                                diameter=self.diameterCmDoubleSpinBox.value(),
                                                height=self.heightCmDoubleSpinBox.value(),
                                                sample_interval=self.sampleRateDoubleSpinBox.value()
                                            ))
        
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

        # start control thread
        self.threadpool.start(self.control_thread)

        # connect buttons
        self.currentDensityModeComboBox.currentIndexChanged.connect(self.currDensityModeSelect)
        self.applyButton.clicked.connect(self.applyPress)
        self.connectionButton.clicked.connect(self.connectionTogglePress)
        self.startButton.clicked.connect(self.startPress)
        self.stopButton.clicked.connect(self.stopPress)

        # set up status bar V and I read out
        self.readoutV = QLabel()
        self.statusbar.addPermanentWidget(self.readoutV)
        self.readoutV.hide()
        self.readoutI = QLabel()
        self.statusbar.addPermanentWidget(self.readoutI)
        self.readoutI.hide()

        # set parameter label colors
        self.eFieldLabel.setStyleSheet(f'QLabel {{color: {E_FIELD_COLOR_STR}}}')
        self.currentDensityLabel.setStyleSheet(f'QLabel {{color: {CURRENT_DENSITY_COLOR_STR}}}')

        # graph 1
        self.graph1 = pg.PlotWidget()
        self.graph1.setSizePolicy(self.graphPlaceholder1.sizePolicy())
        self.graph1.setMinimumSize(self.graphPlaceholder1.minimumSize())
        self.graph1.setObjectName('graph1')
        self.GraphBox.replaceWidget(self.graphPlaceholder1, self.graph1)
        self.graphPlaceholder1.hide()

        # graph 2
        self.graph2 = pg.PlotWidget()
        self.graph2.setSizePolicy(self.graphPlaceholder2.sizePolicy())
        self.graph2.setMinimumSize(self.graphPlaceholder2.minimumSize())
        self.graph2.setObjectName('graph2')
        self.GraphBox.replaceWidget(self.graphPlaceholder2, self.graph2)
        self.graphPlaceholder2.hide()

        # set up graphs

        self.time = []
        self.J = []
        self.P = []
        self.T = []
        self.E = []

        self.rampPlotItem = None
        self.ELinePlotItem = None
        self.JLinePlotItem = None
        self.EPlotItem = self.graph1.plot(self.time, self.E, pen=pg.mkPen(color=E_FIELD_COLOR_STR))
        self.JPlotItem = self.graph1.plot(self.time, self.J, pen=pg.mkPen(color=CURRENT_DENSITY_COLOR_STR))
        self.PPlotItem = self.graph2.plot(self.time, self.P, pen=pg.mkPen(color=POWER_DENSITY_COLOR_STR))
        self.TPlotItem = self.graph2.plot(self.time, self.T, pen=pg.mkPen(color=TEMPERATURE_COLOR_STR))

        self.graph1.setLabel('left', 'E-field', color=E_FIELD_COLOR_STR)
        self.graph1.setLabel('right', 'Current Density', color=CURRENT_DENSITY_COLOR_STR)
        self.graph1.setLimits(xMin=0)

        self.graph2.setLabel('left', 'Power Density', color=POWER_DENSITY_COLOR_STR)
        self.graph2.setLabel('right', 'Temperature', color=TEMPERATURE_COLOR_STR)
        self.graph2.setLimits(xMin=0)

        self.graph1.setBackground(background=None)
        self.graph2.setBackground(background=None)

        # TODO visual indication that parameters have not been applied

    #########################
    # button press handlers #
    #########################

    def currDensityModeSelect(self):
        if self.currentDensityModeComboBox.currentText() == 'Hold':
            self.currentDensityEndDoubleSpinBox.setDisabled(True)
            self.currentDensityEndLabel.setDisabled(True)
            self.currentDensityRateDoubleSpinBox.setDisabled(True)
            self.currentDensityRateLabel.setDisabled(True)
        else:
            self.currentDensityEndDoubleSpinBox.setDisabled(False)
            self.currentDensityEndLabel.setDisabled(False)
            self.currentDensityRateDoubleSpinBox.setDisabled(False)
            self.currentDensityRateLabel.setDisabled(False)

    def closeEvent(self, event):
        print('Stopping.')
        self.signals.stopSig.emit()
        print('Disconnecting.')
        self.signals.disconnectSig.disconnect()
        print('Stopping control thread.')
        self.signals.exitSig.emit()
        print('Exiting...')
        event.accept()

    def applyPress(self):
        # TODO verify height and diameter are nonzero
        self.applyButton.setDisabled(True) # prevent further presses
        params = Params(
            ramp_data=RampData(
                ramp=self.currentDensityModeComboBox.currentText() == 'Ramp',
                start=self.currentDensityStartDoubleSpinBox.value(),
                end=self.currentDensityEndDoubleSpinBox.value(),
                rate=self.currentDensityRateDoubleSpinBox.value()
            ),
            e_field=self.eFieldDoubleSpinBox.value(),
            curr_density=self.currentDensityStartDoubleSpinBox.value(),
            diameter=self.diameterCmDoubleSpinBox.value(),
            height=self.heightCmDoubleSpinBox.value(),
            sample_interval=self.sampleRateDoubleSpinBox.value()
        )
        self.signals.setParamsSig.emit(params)

        # parameters preview
        if self.rampPlotItem != None: # removing existing ramp preview if applicable
                self.graph1.getPlotItem().removeItem(self.rampPlotItem)
        if params.ramp_data.ramp:
            # only show current ramp preview if ramping is enabled
            x = []
            y = []
            if self.control_thread.status.running:
                x.append(self.time[-1])
            else:
                x.append(0)
            y.append(params.ramp_data.start)
            dur = abs(params.ramp_data.start - params.ramp_data.end) / params.ramp_data.rate
            x.append(x[0] + dur)
            y.append(params.ramp_data.end)

            self.rampPlotItem = self.graph1.plot(x, y, pen=pg.mkPen(color=CURRENT_DENSITY_COLOR_STR, style=Qt.PenStyle.DashLine))
        
        # current density and e-field limits
        if self.JPlotItem != None:
            self.graph1.getPlotItem().removeItem(self.JPlotItem)
        if self.EPlotItem != None:
            self.graph1.getPlotItem().removeItem(self.EPlotItem)
        self.ELinePlotItem = self.graph1.getPlotItem().addLine(
            y=params.e_field, pen=pg.mkPen(color=E_FIELD_COLOR_STR, style=Qt.PenStyle.DashLine)
        )
        j_limit = params.ramp_data.end if params.ramp_data.ramp else params.curr_density
        self.JLinePlotItem = self.graph1.getPlotItem().addLine(
            y=j_limit, pen=pg.mkPen(color=CURRENT_DENSITY_COLOR_STR, style=Qt.PenStyle.DashLine)
        )

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
        self.E = []
        self.J = []
        self.T = []
        self.P = []

    def stopPress(self):
        self.stopButton.setDisabled(True) # prevent further presses

        self.signals.stopSig.emit()

    ###########################
    # control signal handlers #
    ###########################

    def receiveData(self, data : tuple[float]):
        # (time, E, J, P, T, V, I)
        self.time.append(data[0])
        self.E.append(data[1])
        self.J.append(data[2])
        self.P.append(data[3])
        self.T.append(data[4])

        self.graph1.getPlotItem().removeItem(self.EPlotItem)
        self.graph1.getPlotItem().removeItem(self.JPlotItem)
        self.graph2.getPlotItem().removeItem(self.PPlotItem)
        self.graph2.getPlotItem().removeItem(self.TPlotItem)
        self.EPlotItem = self.graph1.plot(self.time, self.E, pen=pg.mkPen(color=E_FIELD_COLOR_STR))
        self.JPlotItem = self.graph1.plot(self.time, self.J, pen=pg.mkPen(color=CURRENT_DENSITY_COLOR_STR))
        self.PPlotItem = self.graph2.plot(self.time, self.P, pen=pg.mkPen(color=POWER_DENSITY_COLOR_STR))
        self.TPlotItem = self.graph2.plot(self.time, self.T, pen=pg.mkPen(color=TEMPERATURE_COLOR_STR))
        
        self.readoutV.setText(f'V={data[5]}')
        self.readoutI.setText(f'I={data[6]}')

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

    def settingParams(self):
        self.statusbar.showMessage('Applying...')

    def setParamsDone(self):
        self.applyButton.setDisabled(False)
        self.statusbar.showMessage('Applied!', 1000)

    def starting(self):
        self.statusbar.showMessage('Starting...')

    def ramping(self):
        self.applyButton.setDisabled(True)

    def rampingDone(self):
        self.applyButton.setDisabled(False)
        self.statusbar.showMessage('Ramping done!', 1000)

    def started(self):
        self.stopButton.setDisabled(False)
        self.readoutI.show()
        self.readoutV.show()
        self.statusbar.showMessage('Started!', 1000)

    def stopping(self):
        self.statusbar.showMessage('Stopping...')

    def stopped(self):
        self.startButton.setDisabled(False)
        self.applyButton.setDisabled(False)
        self.readoutI.hide()
        self.readoutV.hide()
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

        self.gui_signals.connectSig.emit(filepath)

        return super().accept()
    
    def reject(self):
        self.connection_button.setDisabled(False)
        return super().reject()

if __name__ == "__main__":
    main()
