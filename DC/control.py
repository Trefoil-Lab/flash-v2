from PyQt6.QtCore import QObject, QRunnable, QEventLoop, pyqtSignal, pyqtSlot
import time
import sched
import random
import math
import sys
import datetime
from threading import Thread, Lock, Event
from queue import SimpleQueue, Empty

from control.control import Status
from control.supply import DCSupply
from util.signals import Params, ControlSignals, SampleSignals, GuiSignals

RAMP_INTERVAL_S = 0.200
SAVE_INTERVAL_S = 10
CSV_HEADER = 'Timestamp,Time,Voltage,Current,E,J,P,T'

class ControlRunner(QRunnable):
    def __init__(
        self,
        supply_addr : str,
        gui_signals : GuiSignals,
        params : Params
    ):
        super().__init__()
        self.signals = ControlSignals()
        self.gui_signals = gui_signals

        self.addr = supply_addr
        self.params = params

        self.status = Status(False, False) # for gui synchronization
        self.status_lock = Lock()

        self.supply = DCSupply(self.addr)
        self.supply_lock = Lock()

        self.data_queue = SimpleQueue()

        # set up sampling thread
        self.stop_event = Event()
        self.sample_signal = SampleSignals()

        # set up listeners for events from GUI
        self.gui_signals.exitSig.connect(self.exit)
        self.gui_signals.connectSig.connect(self.connect)
        self.gui_signals.disconnectSig.connect(self.disconnect)
        self.gui_signals.setParamsSig.connect(self.setParams)
        self.gui_signals.startSig.connect(self.start)
        self.gui_signals.stopSig.connect(self.stop)
        
        # set up listener for newData event from sample collector
        self.sample_signal.newDataSig.connect(self.receiveData)

        # set up listener for direct set params
        self.signals.setParamsDirectSig.connect(self.setParamsDirect)

    #@pyqtSlot
    def run(self):
        print('Control thread starting.')
        self.eventloop = QEventLoop()
        self.eventloop.exec() # run event loop

    ######################
    # GUI event handlers #
    ######################

    def exit(self):
        self.eventloop.exit()

    def connect(self, filepath):
        self.signals.connectingSig.emit()
        with self.supply_lock:
            self.supply.connect()
            time.sleep(1)

        self.filepath = filepath
        self.save_thread = SaveRunner(self.filepath, self.data_queue, self.stop_event)

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

        # print(new_params)

        with self.supply_lock:
            area = 0.25 * math.pi * new_params.diameter * new_params.diameter
            self.supply.setV(new_params.e_field * new_params.height)
            self.supply.setI(new_params.curr_density * area)

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

        if self.status.running == True and new_params.ramp_data.ramp == True and new_params.ramp_data.end != self.params.curr_density:
            # if running and ramping is enabled and target current density changes, we need to ramp
            
            # if we are already running...
            # TODO: is this how we want to do it? should we even allow ramping while running?
            #       would it make more sense to ramp from the present current setting?
            # area = 0.25 * math.pi * new_params.diameter * new_params.diameter
            # with self.supply_lock:
            #     new_params.ramp_data.start = self.supply.measI() / area
            
            self.params.ramp_data = new_params.ramp_data
            self.ramp()
        else:
            # otherwise just set the parameters directly
            self.setParamsDirect(new_params)
        
        self.signals.setParamsDoneSig.emit()

    def ramp(self):
        self.signals.rampingSig.emit()
        # assume the present current density is the same as our target start
        self.ramping_thread = RampRunner(self.signals, self.gui_signals, self.params, self.stop_event)
        # spawn ramping thread
        self.ramping_thread.start()

    def start(self):
        self.signals.startingSig.emit()
        with self.supply_lock:
            self.supply.enable()

        self.stop_event.clear()
        self.sample_thread = SampleRunner(self.supply, self.supply_lock, self.sample_signal,
                                          self.params.sample_interval, self.stop_event, self, self.data_queue)
        self.sample_thread.start() # start sample thread

        # if ramping is enabled, go do that
        if self.params.ramp_data.ramp:
            self.ramp()

        # start saving thread
        self.save_thread = SaveRunner(self.filepath, self.data_queue, self.stop_event)
        self.save_thread.start()

        with self.status_lock:
            self.status.running = True
        self.signals.startedSig.emit()

    def stop(self):
        self.signals.stoppingSig.emit()
        
        with self.supply_lock:
            if self.supply.connected:
                self.supply.disable()
        
        if self.status.running:
            self.stop_event.set() # tell sampling to stop
            self.sample_thread.join() # wait for sample thread to stop
            self.save_thread.join()

            with self.status_lock:
                self.status.running = False
        self.signals.stoppedSig.emit()
    
    ##########################
    # sample signal handlers #
    ##########################

    def receiveData(self, inc_data : tuple[float]):
        area = 0.25 * math.pi * self.params.diameter * self.params.diameter
        # (time, V, I, P, T) -> (time, E, J, P, T, V, I)
        out_data = list(inc_data)
        out_data[1] = inc_data[1] / self.params.height # e-field from voltage
        out_data[2] = inc_data[2] / area # current density from current
        out_data[3] = inc_data[3] / area # power density from power

        out_data.append(inc_data[1])
        out_data.append(inc_data[2])

        # TODO use queue to communicate between sampler and control thread to ensure reliability
        # TODO prepare for saving data
        
        self.signals.newDataSig.emit(tuple(out_data))

class SaveRunner(Thread):
    def __init__(self, filepath : str, data_queue : SimpleQueue, stop_event : Event):
        super().__init__()

        self.filepath = filepath
        self.queue = data_queue
        self.stop_event = stop_event

    def save(self, sc : sched.scheduler | None):
        d : tuple
        with open(self.filepath, 'a') as f:
            while not self.queue.empty():
                try:
                    d = self.queue.get_nowait()
                except Empty:
                    break
                f.write(','.join( [str(x) for x in d] ) + '\n')
        
        if not self.stop_event.is_set() and sc != None:
            sc.enter(SAVE_INTERVAL_S, 1, self.save, (sc, ))

    def run(self):
        print('Saving thread started')
        with open(self.filepath, 'w') as f:
            f.write(CSV_HEADER + '\n')

        sc = sched.scheduler(time.monotonic, time.sleep)
        sc.enter(SAVE_INTERVAL_S, 1, self.save, (sc, ))
        
        while not self.stop_event.is_set():
            sc.run(False)
            time.sleep(0.2)
        self.save(None)
        sys.exit()

class RampRunner(Thread):
    def __init__(self,
                control_signals : ControlSignals,
                gui_signals : GuiSignals,
                params : Params,
                stop_event : Event
    ):
        super().__init__()

        self.control_signals = control_signals
        self.gui_signals = gui_signals
        self.params = params
        self.stop_event = stop_event

    def move(self, sc : sched.scheduler, target_time : float):
        # check if we should stop
        if self.stop_event.is_set():
            sys.exit() # close thread

        if abs(self.params.curr_density - self.params.ramp_data.end) <= (self.params.ramp_data.rate * RAMP_INTERVAL_S):
            # if we are at the target...
            self.params.curr_density = self.params.ramp_data.end
            self.control_signals.setParamsDirectSig.emit(self.params)
            self.control_signals.rampingDoneSig.emit()
            sys.exit() # close thread
        
        # adjust current density
        if self.params.ramp_data.start < self.params.ramp_data.end:
            self.params.curr_density += (self.params.ramp_data.rate * RAMP_INTERVAL_S)
        else:
            self.params.curr_density -= (self.params.ramp_data.rate * RAMP_INTERVAL_S)
        self.control_signals.setParamsDirectSig.emit(self.params)

        # schedule next move
        target_time += RAMP_INTERVAL_S
        sc.enterabs(target_time, 1, self.move, (sc, target_time))

    def run(self):
        print('Ramping thread started.')
        sc = sched.scheduler(time.perf_counter, time.sleep)

        # set start parameters
        self.params.curr_density = self.params.ramp_data.start
        self.control_signals.setParamsDirectSig.emit(self.params)
        
        # schedule moves
        target_time = time.perf_counter() + RAMP_INTERVAL_S
        sc.enterabs(target_time, 1, self.move, (sc, target_time))
        sc.run()

class SampleRunner(Thread):
    def __init__(self,
        supply : DCSupply,
        supply_lock : Lock,
        sample_signal : SampleSignals,
        interval : float,
        stop_event : Event,
        control_runner : ControlRunner,
        data_queue : SimpleQueue
    ):
        super().__init__()

        self.interval = interval
        self.supply = supply
        self.supply_lock = supply_lock
        self.sample_signal = sample_signal
        self.stop_event = stop_event
        self.control_runner = control_runner
        self.queue = data_queue


    def run(self):
        sc = sched.scheduler(time.perf_counter, time.sleep)

        start_time = time.perf_counter()
        data = [0,0,0,0] # (time, V, I, P, T)

        def sample(sc : sched.scheduler, target_time : float):
            # print('sampling!')
            with self.supply_lock:
                data = [0, # time
                        self.supply.measV(), # voltage 
                        self.supply.measI(), # current
                        self.supply.measP(), # power
                        random.randint(0, 10) # temperature
                ]
            data[0] = time.perf_counter() - start_time
            self.sample_signal.newDataSig.emit(tuple(data))

            # send to queue for saving
            area = 0.25 * math.pi * self.control_runner.params.diameter * self.control_runner.params.diameter
            queue_data = (
                datetime.datetime.now().timestamp(), # timestamp
                data[0], # time
                data[1], # voltage
                data[2], # current
                data[1] / self.control_runner.params.height, # E
                data[2] / area, # J
                data[3] / area, # P
            )
            self.queue.put(queue_data)

            # print(f'time: {data[0]}\tVoltage: {data[1]}\tCurrent: {data[2]}\tPower: {data[3]}\tTemperature: {data[4]}')

            # check event to see if we should continue
            if not self.stop_event.is_set():
                # schedule next sample
                next_time = target_time + self.interval / 1000
                sc.enterabs(next_time, 1, sample, argument=(sc, next_time))
            else:
                print('Sample thread stopping')
                sys.exit()

        print('Sample thread started')
        # schedule first sample
        next_time = start_time + self.interval / 1000
        sc.enterabs(next_time, 1, sample, argument=(sc, next_time))
        sc.run()