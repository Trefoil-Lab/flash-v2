from dataclasses import dataclass
from queue import SimpleQueue, Empty
from threading import Lock, Event
import math
import time

from PyQt6.QtCore import (
    QRunnable,
    QEventLoop
)

from util.const import (
    SupplyType
)
from util.signals import (
    ControlSignals,
    GuiSignals,
    SampleSignals,
    Params
)
from util.data import (
    SamplerData
)
from util.process import (
    Segment,
    SegmentType,
    Interface,
    PulseConf,
    Events,
    SampleConf
)
from control.supply import (
    Supply,
    DCSupply,
    ACSupply
)
from control.ramper import RampRunner
from control.sampler import SampleRunner
from control.saver import SaveRunner
from control.processor import ProcessRunner

class ControlRunner(QRunnable):
    """
    Handles control signals from GUI. Spawns and manages other control threads.
    """
    def __init__(
            self,
            gui_signals : GuiSignals,
            params : Params,
            supply_type : SupplyType
    ):
        super().__init__()

        self.params = params

        self.supply_type = supply_type
        self.supply : Supply = None
        self.supply_lock = Lock()

        self.status = Status(False, False) # for gui synchronization
        self.status_lock = Lock()

        self.stop_event = Event() # used by sampler, saver, and process threads
        self.pause_event = Event()
        self.jump_event = Event()

        self.data_queue = SimpleQueue() # data from sampler to saver

        # set up signal objects
        self.gui_signals = gui_signals
        self.signals = ControlSignals()
        self.sample_signals = SampleSignals()

        # set up GUI listeners
        self.gui_signals.exitSig.connect(self.exit)
        self.gui_signals.connectSig.connect(self.connect)
        self.gui_signals.disconnectSig.connect(self.disconnect)
        self.gui_signals.setParamsSig.connect(self.setParams)
        self.gui_signals.startSig.connect(self.start)
        self.gui_signals.stopSig.connect(self.stop)

        # set up data listener
        self.sample_signals.newDataSig.connect(self.receiveData)

        # set up listener for direct set params
        self.signals.setParamsDirectSig.connect(self.setParamsDirect)

    def run(self):
        self.eventloop = QEventLoop()
        self.eventloop.exec() # run event loop

    ######################
    # GUI event handlers #
    ######################

    def exit(self):
        self.eventloop.exit()

    def connect(self, addr, filepath):
        self.signals.connectingSig.emit()

        with self.supply_lock:
            if self.supply is None:
                match self.supply_type:
                    case SupplyType.DC:
                        self.supply = DCSupply(addr)
                    case SupplyType.AC:
                        self.supply = ACSupply(addr)
            self.supply.connect()
            time.sleep(1)

        self.filepath = filepath
        self.save_thread = SaveRunner(self.filepath, self.data_queue, self.stop_event, self.supply.getHeader())

        with self.status_lock:
            self.status.connected = True
        self.signals.connectedSig.emit()

    def disconnect(self):
        self.signals.disconnectingSig.emit()
        with self.supply_lock:
            self.supply.disconnect()
        self.status.connected = False
        self.signals.disconnectedSig.emit()

    def setParamsDirect(self, new_params : Params):
        # ignores any ramp information

        with self.supply_lock:
            area = 0.25 * math.pi * new_params.diameter * new_params.diameter
            self.supply.setV(new_params.e_field * new_params.height)
            self.supply.setI(new_params.curr_density * area)
            if self.supply_type == SupplyType.AC:
                self.supply.setFreq(new_params.freq)

        # do we need to update sample interval?
        if new_params.sample_interval != self.params.sample_interval:
            self.sample_thread.interval = new_params.sample_interval
        
        ramp_data = self.params.ramp_data
        self.params = new_params
        self.params.ramp_data = ramp_data # preserve ramp data

    def setParams(self, new_params : Params):
        self.signals.settingParamsSig.emit()

        if new_params == self.params: # only update if we need to
            self.signals.setParamsDoneSig.emit()
            return
        
        self.params.ramp_data = new_params.ramp_data

        self.setParamsDirect(new_params)

        self.signals.setParamsDoneSig.emit()

    def start(self):
        self.signals.startingSig.emit()
        with self.supply_lock:
            self.supply.enable()

        self.stop_event.clear()

        area = 0.25 * math.pi * self.params.diameter * self.params.diameter

        if self.params.ramp_data.ramp:
            segs = [
                Segment(
                    type=SegmentType.RAMP,
                    target=self.params.ramp_data.end,
                    rate=self.params.ramp_data.rate,
                ),
                Segment(
                    type=SegmentType.END
                )
            ]
        else:
            segs = [
                Segment(type=SegmentType.END)
            ]
        self.process_thread = ProcessRunner(
            segs=segs,
            start_value=self.params.curr_density,
            pulse=PulseConf(
                pulse=self.params.pulse_data.pulse,
                value=self.params.e_field * self.params.height,
                period=self.params.pulse_data.period,
                duty_cycle=self.params.pulse_data.duty_cycle
            ),
            interface=Interface(
                lock=self.supply_lock,
                set_val=self.supply.setI,
                get_val=self.supply.getI,
                pulse_on=self.supply.setV,
                pulse_off=lambda : self.supply.setV(0),
                meas=self.supply.meas,
                events=Events(
                    self.stop_event,
                    self.pause_event,
                    self.jump_event
                )
            ),
            sample=SampleConf(
                self.params.sample_interval,
                self.sample_signals,
                self.data_queue
            )
        )

        # start saving thread
        self.save_thread = SaveRunner(self.filepath, self.data_queue, self.stop_event, self.supply.getHeader())
        self.save_thread.start()

        # start process runner
        self.process_thread.start()

        with self.status_lock:
            self.status.running = True
        self.signals.startedSig.emit()

    def stop(self):
        self.signals.stoppingSig.emit()
        
        with self.supply_lock:
            try:
                self.supply.disable()
            except AttributeError:
                pass
        
        if self.status.running:
            self.stop_event.set() # tell sampling to stop
            self.process_thread.join() # wait for process thread to stop
            self.save_thread.join()

            with self.status_lock:
                self.status.running = False
        self.signals.stoppedSig.emit()
    
    ##########################
    # sample signal handlers #
    ##########################

    def receiveData(self, inc_data : SamplerData):
        self.signals.newDataSig.emit(inc_data)


@dataclass
class Status:
    connected : bool = False
    running : bool = False