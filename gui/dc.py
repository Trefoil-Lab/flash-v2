"""
GUI for DC flash experiments.
"""

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
import datetime

from .ui.DCMainWindow import Ui_MainWindow
from .ui.ConnectDialog import Ui_Dialog
from control.flash.control import ControlRunner
from control.flash.signals import (
    GuiSignals, 
    ControlSignals, 
    Params, 
    RampParams,
    PulseParams
)
from util.const import (
    DC_SOURCE_ADDR,
    SupplyType,
)
from control.data import (
    SamplerData,
    ACPayload
)


WINDOW_TITLE = 'DC flash'
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
    """
        Main window for DC flash GUI.
    
        Spawns a control.flash.control.ControlRunner thread to manage
        the experiment. The ControlRunner thread then spawns
        additional threads.
    
        Qt signals are used for communication between the GUI and the
        control thread.
        """
    def __init__(self, *args, obj=None, **kwargs):
        """
        Create the main window and spawn the control thread.
        
        Creates a control.flash.signals.GuiSignals object for
        coordination with the control thread.
        """
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        ###############################
        # custom initialization below #
        ###############################

        self.setWindowTitle(WINDOW_TITLE)

        # set up control thread
        self.signals = GuiSignals()
        self.threadpool = QThreadPool()
        self.control_thread = ControlRunner(self.signals, 
                                            Params(
                                                ramp_data=RampParams(
                                                    ramp=self.currentDensityModeComboBox.currentText == 'Ramp',
                                                    start=self.currentDensityStartDoubleSpinBox.value(),
                                                    end=self.currentDensityEndDoubleSpinBox.value(),
                                                    rate=self.currentDensityRateDoubleSpinBox.value()
                                                ),
                                                pulse_data=PulseParams(
                                                    pulse=self.pulseEnableCheckBox.isChecked(),
                                                    period=self.periodDoubleSpinBox.value(),
                                                    duty_cycle=self.dutyCycleSpinBox.value()
                                                ),
                                                e_field=self.eFieldDoubleSpinBox.value(),
                                                curr_density=self.currentDensityStartDoubleSpinBox.value(),
                                                diameter=self.diameterCmDoubleSpinBox.value(),
                                                height=self.heightCmDoubleSpinBox.value(),
                                                sample_interval=self.sampleRateDoubleSpinBox.value()
                                            ),
                                            SupplyType.DC
        )
        
        # set up control signal listeners
        self.control_thread.signals.errorSig.connect(self.error)
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
        self.pulseEnableCheckBox.checkStateChanged.connect(self.pulseCheckChange)
        self.diameterCmDoubleSpinBox.valueChanged.connect(self.updateSpinBoxLimits)
        self.heightCmDoubleSpinBox.valueChanged.connect(self.updateSpinBoxLimits)
        self.eFieldDoubleSpinBox.valueChanged.connect(self.updateSpinBoxLimits)
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
        """
        Handle changes to the current density mode selections: if
        'Hold' is selected, disable GUI elements related to ramp
        mode. If 'Ramp' is selected, enable GUI elements related
        to ramp mode.
        """
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

    def pulseCheckChange(self):
        """
        Handle changes to the pulse checkbox: if checked, enable
        GUI elements related to pulse options, otherwise disable
        these elements.
        """
        if self.pulseEnableCheckBox.isChecked():
            self.periodLabel.setDisabled(False)
            self.periodDoubleSpinBox.setDisabled(False)
            self.dutyCycleLabel.setDisabled(False)
            self.dutyCycleSpinBox.setDisabled(False)
        else:
            self.periodLabel.setDisabled(True)
            self.periodDoubleSpinBox.setDisabled(True)
            self.dutyCycleLabel.setDisabled(True)
            self.dutyCycleSpinBox.setDisabled(True)

    def updateSpinBoxLimits(self):
        """
        Based on the height and diameter selected by the user,
        update the limits on the E-field spin box to be within the
        voltage limits of the power supply. Based on the dimensions
        and E-field selected by the user, update the current density
        limits.
        
        This function is called every time the height, diameter, or
        E-field data entries are changed.
        
        For now, supply voltage and current limits are hardcoded for
        the BK Precision MR3K160120.
        """
        height = self.heightCmDoubleSpinBox.value()
        diameter = self.diameterCmDoubleSpinBox.value()
        area = 0.25 * math.pi * diameter * diameter

        # update e field limits based on max voltage
        e_field_max = 160 / height
        self.eFieldDoubleSpinBox.setMaximum(e_field_max)

        # update current density limits based on max current
        curr_density_max = 120 / area
        self.currentDensityStartDoubleSpinBox.setMaximum(curr_density_max)
        self.currentDensityEndDoubleSpinBox.setMaximum(curr_density_max)

    def closeEvent(self, event):
        """
        Issues stop, disconnect, and exit signals to the control
        thread, then closes the window. Called when the window is
        closed.
        """
        print('Stopping.')
        self.signals.stopSig.emit()
        print('Disconnecting.')
        self.signals.disconnectSig.disconnect()
        print('Stopping control thread.')
        self.signals.exitSig.emit()
        print('Exiting...')
        event.accept()

    def applyPress(self):
        """
        Handle presses of the apply button: send the entered
        parameters to the control thread, and update the preview
        on the current density and E-field graph.
        """
        self.applyButton.setDisabled(True) # prevent further presses
        params = Params(
            ramp_data=RampParams(
                ramp=self.currentDensityModeComboBox.currentText() == 'Ramp',
                start=self.currentDensityStartDoubleSpinBox.value(),
                end=self.currentDensityEndDoubleSpinBox.value(),
                rate=self.currentDensityRateDoubleSpinBox.value()
            ),
            pulse_data=PulseParams(
                pulse=self.pulseEnableCheckBox.isChecked(),
                period=self.periodDoubleSpinBox.value(),
                duty_cycle=self.dutyCycleSpinBox.value()
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
        """
        Handle presses of the connect/disconnect button. If the 
        control thread is connected to the power supply, issue a
        disconnect signals. Else open a ConnectDialog.
        """
        self.connectionButton.setDisabled(True) # prevent further presses

        if self.control_thread.status.connected:
            self.signals.disconnectSig.emit()
        else:
            dlg = FlashConnectDialog(self.signals, self.connectionButton)
            dlg.exec()

    def startPress(self):
        """
        Handle presses of the start button. Emit the start signal and
        clear previously plotted data.
        """
        self.startButton.setDisabled(True) # prevent further presses

        self.signals.startSig.emit()

        # clear previously plotted data
        self.time = []
        self.E = []
        self.J = []
        self.T = []
        self.P = []

    def stopPress(self):
        """
        Handle presses of the stop button. Emit the stop signal.
        """
        self.stopButton.setDisabled(True) # prevent further presses

        self.signals.stopSig.emit()

    ###########################
    # control signal handlers #
    ###########################

    def error(self, title : str, text : str):
        """
        Handles error messages from the control thread. Displays
        errors in a pop up message box.

        Args:
            title (str): title
            text (str): description
        """
        QMessageBox.critical(None, title, text)

    def receiveData(self, data : SamplerData):
        """
        Handles data received from the control thread. Plots received
        data and provides readouts on the status bar.

        Args:
            data (SamplerData): data from the control thread
        """
        self.time.append(data.time)
        self.E.append(data.e_field)
        self.J.append(data.curr_density)
        self.P.append(data.power_density)
        self.T.append(data.temperature)

        self.graph1.getPlotItem().removeItem(self.EPlotItem)
        self.graph1.getPlotItem().removeItem(self.JPlotItem)
        self.graph2.getPlotItem().removeItem(self.PPlotItem)
        self.graph2.getPlotItem().removeItem(self.TPlotItem)
        self.EPlotItem = self.graph1.plot(self.time, self.E, pen=pg.mkPen(color=E_FIELD_COLOR_STR))
        self.JPlotItem = self.graph1.plot(self.time, self.J, pen=pg.mkPen(color=CURRENT_DENSITY_COLOR_STR))
        self.PPlotItem = self.graph2.plot(self.time, self.P, pen=pg.mkPen(color=POWER_DENSITY_COLOR_STR))
        self.TPlotItem = self.graph2.plot(self.time, self.T, pen=pg.mkPen(color=TEMPERATURE_COLOR_STR))
        
        self.readoutV.setText(f'V={data.voltage}')
        self.readoutI.setText(f'I={data.current}')

    def connecting(self):
        """
        Handles the connecting signal from the control thread: shows
        a message on the status bar.
        """
        self.statusbar.showMessage('Connecting...')

    def connected(self):
        """
        Handles the connected signal from the control thread: enables
        the start button, apply button, and disconnect button. Set the
        text of the connection button to be "Disconnect". Displays a
        message on the status bar.
        """
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
        """
        Handles the connecting signal from the control thread: shows
        a message on the status bar.
        """
        self.statusbar.showMessage('Disconnecting...')

    def disconnected(self):
        """
        Handles the disconnected signal from the control thread:
        disables the apply, start, and stop buttons. Sets the
        connection button text to "Connect". Shows a message on the
        status bar.
        """
        self.connectionButton.setDisabled(False)
        self.applyButton.setDisabled(True)
        self.startButton.setDisabled(True)
        self.stopButton.setDisabled(True)
        self.connectionButton.setText('Connect')
        self.statusbar.showMessage('Disconnected!', 1000)

    def settingParams(self):
        """
        Handles the setting parameters signal: shows a message on the
        status bar.
        """
        self.statusbar.showMessage('Applying...')

    def setParamsDone(self):
        """
        Handles the set parameters done signal: shows a message on
        the status bar.
        """
        self.applyButton.setDisabled(False)
        self.statusbar.showMessage('Applied!', 1000)

    def starting(self):
        """
        Handles the starting signal: shows a message on the status
        bar.
        """
        self.statusbar.showMessage('Starting...')

    def ramping(self):
        """
        Handles the ramping signal: disables the apply button while
        ramping is in progress.
        """
        self.applyButton.setDisabled(True)

    def rampingDone(self):
        """
        Handles the ramping done signal: enables the apply button and
        shows a message on the status bar.
        """
        self.applyButton.setDisabled(False)
        self.statusbar.showMessage('Ramping done!', 1000)

    def started(self):
        """
        Handles the started signal: enables the stop button, unhides
        the readouts on the status bar, and shows a message on the
        status bar.
        """
        self.stopButton.setDisabled(False)
        self.readoutI.show()
        self.readoutV.show()
        self.statusbar.showMessage('Started!', 1000)

    def stopping(self):
        """
        Handles the stopping signal: shows a message on the status bar.
        """
        self.statusbar.showMessage('Stopping...')

    def stopped(self):
        """
        Handles the stopped signal: enables the start and apply buttons,
        hides the status bar readouts, and shows a message on the
        status bar.
        """
        self.startButton.setDisabled(False)
        self.applyButton.setDisabled(False)
        self.readoutI.hide()
        self.readoutV.hide()
        self.statusbar.showMessage('Stopped!', 1000)

class FlashConnectDialog(Ui_Dialog, QDialog):
    """
    Dialog that is shown the connect button is pressed in the DC
    flash GUI. Prompts the user for experiment metadata and data
    output location.
    """
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
        """
        Browse button press handler. Opens file browser dialog and
        places the path of the chosen folder in the filepath line
        edit element.
        """
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.Directory)

        if file_dialog.exec():
            folder = file_dialog.selectedFiles()[0]
            self.filePathLineEdit.setText(folder)

    def accept(self):
        """
        Accept button press handler. Checks that the chosen folder is
        valid, then constructs a file name from the provided metadata.
        The connect signal is then emitted to the control thread.
        """
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

        self.gui_signals.connectSig.emit(DC_SOURCE_ADDR, filepath)

        return super().accept()
    
    def reject(self):
        """
        Handle reject button press: enables connection button.
        """
        self.connection_button.setDisabled(False)
        return super().reject()

if __name__ == "__main__":
    main()
