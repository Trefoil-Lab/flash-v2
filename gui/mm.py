"""
GUI for measurements with a multimeter.
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
import cmath
import datetime

from .ui.MultimeterMainWindow import Ui_MainWindow
from .ui.SerialConnectionDialog import Ui_Dialog
from control.multimeter.control import (
    ControlRunner,
)
from control.multimeter.multimeter import (
    Mode
)
from control.multimeter.signals import (
    GuiSignals,
    ControlSignals,
    Config,
)
from control.data import (
    MultimeterData
)


WINDOW_TITLE = 'Multimeter'
CONNECTION_DIALOG_TITLE = 'connection dialog'

GRAPH_COLOR_STR = '#FF0000'

MODE_MAP = {
    'DC Voltage': Mode.DC_VOLT,
    'DC Current': Mode.DC_CURR,
    'AC Voltage': Mode.AC_VOLT,
    'AC Current': Mode.AC_CURR,
    'Resistance': Mode.RESIST,
    'Resistance (4 probe)': Mode.RESIST_4WIRE,
    'Frequency': Mode.FREQ,
    'Period': Mode.PERIOD,
}

def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()

class MainWindow(QMainWindow, Ui_MainWindow):
    """
    Main window for multimeter GUI.

    Spawns a control.multimeter.control.ControlRunner thread to manage
    the experiment. The ControlRunner thread then spawns
    additional threads.

    Qt signals are used for communication between the GUI and the
    control thread.
    """
    def __init__(self, *args, obj=None, **kwargs):
        """
        Create the main window and spawn the control thread.

        Creates a control.multimeter.signals.GuiSignals object for
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
        self.control_thread = ControlRunner(self.signals)
        self.threadpool.start(self.control_thread)
        
        # set up control signal listeners
        self.control_thread.signals.newDataSig.connect(self.receiveData)
        self.control_thread.signals.connectingSig.connect(self.connecting)
        self.control_thread.signals.connectedSig.connect(self.connected)
        self.control_thread.signals.disconnectingSig.connect(self.disconnecting)
        self.control_thread.signals.disconnectedSig.connect(self.disconnected)
        self.control_thread.signals.startingSig.connect(self.starting)
        self.control_thread.signals.startedSig.connect(self.started)
        self.control_thread.signals.stoppingSig.connect(self.stopping)
        self.control_thread.signals.stoppedSig.connect(self.stopped)

        # connect buttons
        self.connectionPushButton.clicked.connect(self.connectionTogglePress)
        self.startStopPushButton.clicked.connect(self.startStopPress)
        self.browseButton.clicked.connect(self.browse)

        # set up graphs
        self.time = []
        self.val = []
        self.valPlotItem = self.graph.plot(self.time, self.val, pen=pg.mkPen(color=GRAPH_COLOR_STR))
        self.graph.setLimits(xMin=0)
        self.graph.setBackground(background=None)


    #########################
    # button press handlers #
    #########################


    def connectionTogglePress(self):
        """
        Handle presses of the connect/disconnect button. If the 
        control thread is connected to the multimeter, issue a
        disconnect signals. Else open a SerialConnectionDialog.
        """
        self.connectionButton.setDisabled(True) # prevent further presses

        if self.control_thread.status.connected:
            self.signals.disconnectSig.emit()
        else:
            dlg = SerialConnectionDialog(self, self.signals)
            dlg.exec()

    def startStopPress(self):
        """
        Handle presses of the start/stop button. If the experiment is
        already running, issue a stop signal. If it is not running,
        validate the folder specified by the user for data collection,
        and build a filename using the timestamp and the user-provided
        memo. Pass configuration details to the control thread in a
        start signal.
        """
        self.startStopPushButton.setDisabled(True) # prevent further presses
        
        if self.control_thread.status.running:
            self.startStopPushButton.setText('Start')
            self.signals.stopSig.emit()
        else:
            # validate file path
            folder = self.folderLineEdit.text()
            if not os.path.isdir(folder):
                QMessageBox.critical(None, 'Error', 'Invalid directory.')
                return
            
            # build file name
            filename : str = datetime.datetime.now().strftime('%y-%m-%d-%H%M')
            filename += '_' + '-'.join(self.memoLineEdit.text().split())
            filename += '.csv'
            print(folder)
            print(filename)
            filepath = os.path.join(folder, filename)

            # create configuration
            conf = Config(
                mode=MODE_MAP[self.functionComboBox.currentText()],
                auto_zero=self.autoZeroCheckBox.isChecked(),
                memo=self.memoLineEdit.text().strip(),
                filepath=filepath
            )

            self.signals.startSig.emit(conf)
            self.startStopPushButton.setText('Stop')
            self.connectionPushButton.setDisabled(True)
            
            # clear previously plotted data
            self.time = []
            self.val = []

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

    ###########################
    # control signal handlers #
    ###########################

    def receiveData(self, data : MultimeterData):
        """
        Handles data received from the control thread. Plots data and
        updates the lcd readout.

        Args:
            data (MultimeterData): data from the control thread
        """
        self.time.append(data.time)
        self.val.append(data.value)

        self.graph.getPlotItem().removeItem(self.valPlotItem)
        self.valPlotItem = self.graph.plot(self.time, self.val, pen=pg.mkPen(color=GRAPH_COLOR_STR))
        
        self.lcdNumber.display(data.value)

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
        self.startStopPushButton.setDisabled(False)
        self.applyButton.setDisabled(False)
        with self.control_thread.status_lock:
            if self.control_thread.status.running:
                self.stopButton.setDisabled(False)
            else:
                self.startStopPushButton.setDisabled(False)
        self.connectionButton.setText('Disconnect')
        self.statusbar.showMessage('Connected!', 1000)

    def disconnecting(self):
        """
        Handles the disconnecting signal from the control thread: shows
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
        self.startStopPushButton.setDisabled(True)
        self.connectionButton.setText('Connect')
        self.statusbar.showMessage('Disconnected!', 1000)

    def starting(self):
        """
        Handles the starting signal: shows a message on the status
        bar.
        """
        self.statusbar.showMessage('Starting...')

    def started(self):
        """
        Handles the started signal: enables the stop button and
        shows a message on the status bar.
        """
        self.startStopPushButton.setDisabled(False)
        self.statusbar.showMessage('Started!', 1000)

        # disable configuration fields
        self.functionLabel.setDisabled(True)
        self.functionComboBox.setDisabled(True)
        self.autoZeroLabel.setDisabled(True)
        self.autoZeroCheckBox.setDisabled(True)
        self.memoLabel.setDisabled(True)
        self.memoLineEdit.setDisabled(True)
        self.folderLabel.setDisabled(True)
        self.folderLineEdit.setDisabled(True)
        self.browseButton.setDisabled(True)
        # enable lcd number
        self.lcdNumber.setDisabled(False)

        # clear data
        self.val = []
        self.time = []

    def stopping(self):
        """
        Handles the stopping signal: shows a message on the status bar.
        """
        self.statusbar.showMessage('Stopping...')

    def stopped(self):
        """
        Handles the stopped signal: enables the start and connection buttons,
        and shows a message on the status bar.
        """
        self.startStopPushButton.setDisabled(False)
        self.statusbar.showMessage('Stopped!', 1000)

        # enable configuration fields, connection button
        self.connectionPushButton.setDisabled(False)
        self.functionLabel.setDisabled(False)
        self.functionComboBox.setDisabled(False)
        self.autoZeroLabel.setDisabled(False)
        self.autoZeroCheckBox.setDisabled(False)
        self.memoLabel.setDisabled(False)
        self.memoLineEdit.setDisabled(False)
        self.folderLabel.setDisabled(False)
        self.folderLineEdit.setDisabled(False)
        self.browseButton.setDisabled(False)
        # disable lcd number
        self.lcdNumber.setDisabled(True)


class SerialConnectionDialog(QDialog, Ui_Dialog):
    """
    Dialog that is shown when the connect button is pressed in the
    multimeter GUI. Prompts the user for the COM port.
    """
    def __init__(self, main_window : MainWindow, gui_signals : GuiSignals):
        super().__init__()
        self.setupUi(self)

        ###############################
        # custom initialization below #
        ###############################

        self.main_window = main_window
        self.gui_signals = gui_signals

        self.setWindowTitle(CONNECTION_DIALOG_TITLE)

    def accept(self):
        """
        Accept button press handler. Emits the connect signal with
        the selected COM port number.
        """
        self.main_window.connectionPushButton.setDisabled(True)
        self.gui_signals.connectSig.emit(
            self.portSpinBox.value(),
        )
        return super().accept()

if __name__ == "__main__":
    main()
