import time
from dataclasses import dataclass
from threading import Thread, Event
from queue import SimpleQueue
from PyQt6.QtCore import QEventLoop, QRunnable
from pyvisa import VisaIOError

from control.saver import (
    SaveRunner
)
from control.multimeter import (
    multimeter
)
from control.data import (
    MultimeterData
)
from control.multimeter.signals import (
    ControlSignals,
    GuiSignals,
    SampleSignals,
    Config,
)
from control.multimeter.sampler import (
    SampleRunner
)

class ControlRunner(QRunnable):
    """
    Handles control signals from GUI. Spawns and manages other control threads.
    """
    def __init__(self,
        gui_signals : GuiSignals,
    ):
        """
        Initialize control thread.

        Args:
            gui_signals (GuiSignals): signals from the GUI
        """
        super().__init__()

        self.status = Status()

        # signal objects
        self.signals = ControlSignals()
        self.gui_signals = gui_signals
        self.sample_signals = SampleSignals()

        self.stop_event = Event()

        self.data_queue = SimpleQueue()

        # set up GUI listeners
        self.gui_signals.exitSig.connect(self.exit)
        self.gui_signals.connectSig.connect(self.connect)
        self.gui_signals.disconnectSig.connect(self.disconnect)
        self.gui_signals.startSig.connect(self.start)
        self.gui_signals.stopSig.connect(self.stop)

        # set up data listener
        self.sample_signals.newDataSig.connect(self.receiveData)

    def run(self):
        self.eventloop = QEventLoop()
        self.eventloop.exec() # run event loop

    ######################
    # GUI event handlers #
    ######################

    def exit(self):
        """
        Handle exit signal.
        """
        self.eventloop.exit()

    def connect(self, port : int):
        """
        Connect to multimeter.

        Args:
            port (int): COM port to use
        """
        self.signals.connectingSig.emit()

        try:
            self.mm = multimeter.Multimeter(port)
            self.mm.connect()
            self.status.connected = True
            self.signals.connectedSig.emit()
        except VisaIOError as e:
            self.signals.errorSig.emit('Connection Error', str(e))


    def disconnect(self):
        """
        Disconnect from multimeter.
        """
        self.signals.disconnectingSig.emit()

        self.mm.disconnect()
        self.status.connected = False

        self.signals.disconnectedSig.emit()

    def start(self, conf : Config):
        """
        Start the experiment. Create and start sample and saver
        threads. 

        Args:
            conf (Config): configuration
        """
        self.signals.startingSig.emit()
        self.stop_event.clear()

        self.save_thread = SaveRunner(
            filepath=conf.filepath,
            memo=conf.memo,
            data_queue=self.data_queue,
            stop_event=self.stop_event,
        )

        self.sample_thread = SampleRunner(
            multimeter=self.mm,
            config=conf,
            stop_event=self.stop_event,
            data_queue=self.data_queue,
            sample_signals=self.sample_signals
        )

        self.save_thread.start()
        self.sample_thread.start()
        self.status.running = True

        self.signals.startedSig.emit()

    def stop(self):
        """
        Stop the experiment. Child threads are given the signal to stop.
        """
        self.signals.stoppingSig.emit()
        
        if self.status.running:
            self.stop_event.set() # tell sampling to stop
            self.sample_thread.join() # wait for process thread to stop
            self.save_thread.join()

            self.status.running = False

        self.signals.stoppedSig.emit()

    ##########################
    # sample signal handlers #
    ##########################

    def receiveData(self, inc_data : MultimeterData):
        """
        Receive data from the sampler thread and forward it to the GUI.

        Args:
            inc_data (MultimeterData): data from the sampler thread
        """
        self.signals.newDataSig.emit(inc_data)


@dataclass
class Status:
    """
    Status flags for the control thread.
    """
    connected : bool = False
    running : bool = False