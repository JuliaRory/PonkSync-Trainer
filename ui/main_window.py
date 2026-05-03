import pyqtgraph as pg
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout, QHBoxLayout, QFrame

from numpy import diff, arange, array, full, sum, tile, newaxis, vstack, linspace, pi, sin


from collections import deque
import os
import subprocess

from settings.settings import Settings 
from settings.settings_handler import SettingsHandler

from logic.sources.stream import StreamSource
from logic.data_processor import DataProcessor
from logic.plot_updater import PlotUpdater

from ui.online_graph import OnlineGraph
from ui.scale_panel import ScalePanel
from ui.filter_panel import FilterPanel
from ui.peak_panel import PeakDetectionPanel
from ui.stimuli_control_panel import StimuliControlPanel
from ui.mep_panel import MEPPlotsWindow
from utils.ui_helpers import create_button

WIDTH_SET, HEIGHT_SET = 1400, 800

class MainWindow(QWidget):
    def __init__(self, input_data_stream, input_message_stream, output_stream_ponk, resonance):
        super().__init__()
        self.setWindowTitle("SyncPonk Trainer")
        # self.setWindowIcon(QIcon(r"./resources/icon.png"))

        self._resonance = resonance                       # прокси для управления резонансными модулями
        self.settings = Settings()                        # Хранилище настроек

        self._input_stream = StreamSource(input_data_stream, input_message_stream)                              # Приёмник (онлайн) данных
        self._data_processor = DataProcessor(self.settings, output_stream_ponk)

        if self.settings.activate_bat:
            # Запуск батника с qml-файлом для управления резонансными модулями
            try:
                cwd = os.path.dirname(self.settings.bat_file) # cwd = папка с батником
                subprocess.Popen([self.settings.bat_file], cwd=cwd)
            except:
                cwd = os.path.dirname(self.settings.bat_file_home) # cwd = папка с батником
                subprocess.Popen([self.settings.bat_file_home], cwd=cwd)             
        
        self._setup_widgets()
        self._setup_layout()

        self._plot_updater = PlotUpdater(self._figure_panel, self.settings)
        self._settings_handler = SettingsHandler(self.settings, self._data_processor, self._plot_updater, ui=self)

        self._setup_connections()

        self.resize(WIDTH_SET, HEIGHT_SET)
        self._finilaze()

    ## =======================
    ## === WIDGETS ===========
    ## =======================

    def _setup_widgets(self):
        # self.create_scale_settings()    # создать блок с настройками масштабирования    --> self.box_scale_settings
        # self.create_filter_settings()   # создать блок с настройками фильтрации         --> self.box_filter_settings

        self._scale_panel = ScalePanel(self.settings, parent=self)
        self._filter_panel = FilterPanel(self.settings, parent=self)
        self._peak_panel = PeakDetectionPanel(self.settings, parent=self)
        self._figure_panel = OnlineGraph(self.settings, self._data_processor, parent=self)       # создать блок с графиками миограммы            --> self.plot_emg_graph
        self._stimuli_panel = StimuliControlPanel(self.settings, self._resonance, parent=self)
        self._mep_window = None
        self._mep_panel = QFrame(self)
        self._button_mep_plots = create_button("MEP plots", parent=self._mep_panel, w=120)
        self._label_mep_mean = QLabel("Mean MEP amp: -- mV", self._mep_panel)
    
    ## =======================
    ## === LAYOUT ===========
    ## =======================

    def _setup_layout(self):
        layout = QGridLayout(self)
        mep_layout = QVBoxLayout(self._mep_panel)
        mep_layout.setContentsMargins(0, 0, 0, 0)
        mep_layout.addWidget(self._button_mep_plots)
        mep_layout.addWidget(self._label_mep_mean)
        
        layout.addWidget(self._scale_panel, 0, 0, 1, 1, alignment=Qt.AlignRight)
        layout.addWidget(self._filter_panel, 1, 0, 1, 1, alignment=Qt.AlignRight)
        
        layout.addWidget(self._figure_panel, 0, 1, 5, 3)
        
        layout.addWidget(self._mep_panel, 0, 4, 1, 2, alignment=Qt.AlignLeft)
        layout.addWidget(self._peak_panel, 1, 4, 1, 2, alignment=Qt.AlignLeft)
        layout.addWidget(self._stimuli_panel, 2, 4, 1, 2, alignment=Qt.AlignLeft)

        
    ## =======================
    ## === CONNECTIONS =======
    ## =======================

    def _setup_connections(self):
        # работа с потоками данных
        self._input_stream.dataReady.connect(lambda epoch, ts: self._data_processor.add_pack(epoch, ts))
        self._data_processor.newDataProcessed.connect(lambda: self._plot_updater.plot_pack())
        self._data_processor.triggerIdx.connect(lambda idx: self._plot_updater.plot_trigger(idx))
        self._data_processor.peakIdx.connect(lambda idx: self._plot_updater.plot_peak(idx))

        self._data_processor.delayValue[int].connect(lambda delay: self._process_delay(delay))
        self._stimuli_panel.stimuliEnded.connect(lambda: self._data_processor.get_delays())
        self._stimuli_panel.changeFile.connect(lambda fl: self._data_processor.change_file(fl))
        self._stimuli_panel.recordingStarted.connect(self._on_mep_recording_started)
        self._stimuli_panel.recordingFinished.connect(lambda: self._data_processor.finish_mep_recording())
        self._data_processor.mepEpochReady.connect(self._on_mep_epoch_ready)
        self._data_processor.mepRecordingFinished.connect(self._on_mep_recording_finished)
        self._button_mep_plots.clicked.connect(self._show_mep_window)
   
        self._data_processor.delayValues.connect(lambda delays: self._process_delays(delays))

    # logic

    def _show_mep_window(self):
        if self._mep_window is None:
            self._mep_window = MEPPlotsWindow(self.settings)
        self._mep_window.show()
        self._mep_window.raise_()
        self._mep_window.activateWindow()

    def _on_mep_epoch_ready(self, mep):
        if self._mep_window is not None:
            self._mep_window.add_mep(mep)

    def _on_mep_recording_started(self, path):
        self._label_mep_mean.setText("Mean MEP amp: -- mV")
        if self._mep_window is not None:
            self._mep_window.set_record_mean(np.nan, 0, path)
        self._data_processor.start_mep_recording(path)

    def _on_mep_recording_finished(self, mean_amp, n_epochs, saved_path):
        if n_epochs <= 0 or not np.isfinite(mean_amp):
            self._label_mep_mean.setText("Mean MEP amp: -- mV")
        else:
            self._label_mep_mean.setText(f"Mean MEP amp: {mean_amp:.2f} mV (n={n_epochs})")

        if self._mep_window is not None:
            self._mep_window.set_record_mean(mean_amp, n_epochs, saved_path)

    def _process_delay(self, delay):
        stimuli_settings = self.settings.stimuli_settings

        # Prefill feedback before video end only for immediate single-stimulus mode.
        if stimuli_settings.stimuli_curr == 2:
            return
        if stimuli_settings.feedback_mode_curr != 0:
            return
        if stimuli_settings.sham_feedback:
            return

        print("show delay -> ", delay)
        self._stimuli_panel.show_delay(delay)
    
    def _process_delays(self, delays):

        # print("show delays for triplets -> ")
        self._stimuli_panel.show_delay(delays)


    def _finilaze(self):
        self.show()


    def set_time_range_emg(self, value):
        self.time_range_emg = value * 1000 
        maxlen = int(value * 1000 / self.params["Fs"])
        self.ts =  deque(maxlen=maxlen)                             # стек с данными таймстемпов
        self.emg = [deque(maxlen=maxlen), deque(maxlen=maxlen)]     # стеки с данными EMG


    def set_time_range_clf(self, value):
        self.time_range_clf = value * 1000 
    
  
    def set_scale_offset(self, value):
        scale_factor = 10 ** self.scale_factor
        self.scale_offset = scale_factor * value


    def set_notch_fr(self, value):
        self.notch_fr = value
    

    def set_notch_width(self, value):
        self.notch_width = value

    
    def set_butter_order(self, value):
        self.butter_order = value

    
    def set_butter_lower_fr(self, value):
        self.butter_lower_fr = value

    
    def set_butter_upper_fr(self, value):
        self.butter_upper_fr = value

    
    def update_plot_title(self):
        titles = ["LEFT", "RIGHT"]
        if self.check_box_show_tkeo_emg.isChecked():        # если показывать TKEO
            titles = [t + ': TKEO' for t in titles] 
        for i, plot in enumerate(self.plots):
            plot.setTitle(titles[i])
    
    def closeEvent(self, event):
        # self._settings_handler.save_to_json(default=True)
        # self._settings_handler_record.save_to_json(default=True)
        
        if self.settings.activate_bat:
            service = self._resonance.getService("Resonance-control")     # Берем сервис
            service.sendTransition('!terminate')
        event.accept()
