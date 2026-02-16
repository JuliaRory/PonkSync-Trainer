import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout, QHBoxLayout

import time, random
from h5py import File
from numpy import diff, arange, array, full, sum, tile, newaxis, vstack, linspace, pi, sin


from collections import deque
import copy

from settings.settings import Settings 
from logic.sources.stream import StreamSource
from logic.data_processor import DataProcessor
from logic.plot_updater import PlotUpdater

from ui.online_graph import OnlineGraph
from ui.scale_panel import ScalePanel
from ui.filter_panel import FilterPanel

WIDTH_SET, HEIGHT_SET = 1200, 800

class MainWindow(QWidget):
    def __init__(self, input_data_stream, input_message_stream):
        super().__init__()
        self.setWindowTitle("SyncPonk Trainer")
        # self.setWindowIcon(QIcon(r"./resources/icon.png"))

        # self._resonance = resonance                       # прокси для управления резонансными модулями
        self.settings = Settings()                        # Хранилище настроек

        self._input_stream = StreamSource(input_data_stream, input_message_stream)                              # Приёмник (онлайн) данных
        self._data_processor = DataProcessor(self.settings)              
        
        self._setup_widgets()
        self._setup_layout()

        self._plot_updater = PlotUpdater(self._figure_panel, self.settings)

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
        self._figure_panel = OnlineGraph(self.settings, self._data_processor, parent=self)       # создать блок с графиками миограммы            --> self.plot_emg_graph

    
    ## =======================
    ## === LAYOUT ===========
    ## =======================

    def _setup_layout(self):
        layout = QGridLayout(self)
        
        layout.addWidget(self._scale_panel, 0, 0, 1, 1, alignment=Qt.AlignRight)
        layout.addWidget(self._filter_panel, 1, 0, 1, 1, alignment=Qt.AlignRight)
        layout.addWidget(self._figure_panel, 0, 1, 4, 3)
        

    def _setup_connections(self):
        # работа с потоками данных
        self._input_stream.dataReady.connect(lambda epoch, ts: self._data_processor.add_pack(epoch, ts))
        self._data_processor.newDataProcessed.connect(lambda: self._plot_updater.plot_pack())
        self._data_processor.triggerIdx.connect(lambda idx: self._plot_updater.plot_trigger(idx))
   

    def _finilaze(self):
        self.show()


    def set_max_value(self, value):
        self.max_value = value
        scale_factor = 10 ** self.scale_factor
        for plot in self.plots:
            plot.setYRange(self.min_value * scale_factor, value * scale_factor)


    def set_min_value(self, value):
        self.min_value = value
        scale_factor = 10 ** self.scale_factor
        for plot in self.plots:
            plot.setYRange(value * scale_factor, self.max_value * scale_factor)


    def set_time_range_emg(self, value):
        self.time_range_emg = value * 1000 
        maxlen = int(value * 1000 / self.params["Fs"])
        self.ts =  deque(maxlen=maxlen)                             # стек с данными таймстемпов
        self.emg = [deque(maxlen=maxlen), deque(maxlen=maxlen)]     # стеки с данными EMG


    def set_time_range_clf(self, value):
        self.time_range_clf = value * 1000 
    
    
    def set_scale_factor(self, value):
        self.scale_factor = value
        scale_factor = 10 ** value
        for plot in self.plots:
            plot.setYRange(self.min_value*scale_factor, self.max_value*scale_factor)
    

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
    