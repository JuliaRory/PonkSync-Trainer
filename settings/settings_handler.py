
from dataclasses import is_dataclass
import json
from dataclasses import asdict

from numpy import sqrt

class SettingsHandler:
    """
    «Связующее звено» между UI и логикой processing:
    -- Слушает изменения в UI.
    -- Обновляет соответствующие поля в Settings.
    -- Вызывает методы DataProcessor, PlotUpdater или других классов, чтобы применить новые настройки

    Args:
        settings(Settings): 
        data_processor(DataProcessor):
        plot_updater(PlotUpdater):
        ui(QWidget):

    """
    def __init__(self, settings, data_processor, plot_updater, ui):
        self.data_processor = data_processor
        self.settings = settings
        self.plot_updater = plot_updater
        self.ui = ui

        self._init_state()
        self._setup_connections()
    
    def _init_state(self):
        self._filter_panel = self.ui._filter_panel
        self._scale_panel = self.ui._scale_panel
        self._peak_panel = self.ui._peak_panel
        self._graph = self.ui._figure_panel

        self._setup_units()
        self._update_thr()


    def _setup_connections(self):
        self._scale_panel.spin_box_scale.valueChanged[int].connect(self._update_scale)
        self._scale_panel.spin_box_max_value.valueChanged[int].connect(self._update_ymax)
        self._scale_panel.spin_box_min_value.valueChanged[int].connect(self._update_ymin)
        self._scale_panel.spin_box_scale_offset.valueChanged[int].connect(self._update_offset)
        self._scale_panel.spin_box_time_range.valueChanged[int].connect(self._update_timerange)

        self._filter_panel.spin_box_lower_freq.valueChanged[int].connect(self._update_low_freq)
        self._filter_panel.spin_box_upper_freq.valueChanged[int].connect(self._update_high_freq)
        self._filter_panel.check_box_notch.stateChanged.connect(self._update_notch)
        self._filter_panel.check_box_lowpass.stateChanged.connect(self._update_lowpass)
        self._filter_panel.check_box_highpass.stateChanged.connect(self._update_highpass)

        self._peak_panel.spin_box_threshold_curr.valueChanged[int].connect(self._update_threshold)
        self._peak_panel.spin_box_threshold_mv.valueChanged[float].connect(self._update_threshold_mv)

    # === plot settings === 

    def _update_threshold(self, thr):
        self.settings.detection_settings.threshold = thr
        mv = sqrt(thr) / 1E3
        self._peak_panel.spin_box_threshold_mv.setValue(mv)
        self.settings.detection_settings.threshold_mv = mv
        self._update_thr()

    def _update_threshold_mv(self, thr):
        self.settings.detection_settings.threshold_mv = thr
        tkeo_thr = (thr ** 2) * ((1/1000) ** 2) 
        scale = 10 ** (self.settings.plot_settings.scale_factor)
        coef = tkeo_thr / scale
        self._peak_panel.spin_box_threshold_curr.setValue(int(coef))
        self.settings.detection_settings.threshold = int(coef)
        self._update_thr()
    
    def _update_thr(self):
        thr = self.settings.detection_settings.threshold * 10 ** (self.settings.plot_settings.scale_factor)
        self.plot_updater.change_thr_line(thr)

    def _update_scale(self, scale):
        self.settings.plot_settings.scale_factor = scale

        self._graph.update_yrange()
        self._setup_units()
        self._update_thr()
    
    def _update_ymax(self, value):
        self.settings.plot_settings.ymax = value
        self._graph.update_yrange()
    
    def _update_ymin(self, value):
        self.settings.plot_settings.ymin = value
        self._graph.update_yrange()
    
    def _update_offset(self, value):
        self.settings.plot_settings.scale_offset = value
        print("DOES NOT WORK YET")
    
    def _update_timerange(self, value):
        self.settings.plot_settings.time_range_ms = value * 1000
        print("DOES NOT WORK YET")

    def _setup_units(self):
        factor = self.settings.plot_settings.scale_factor
        text = f"<span style='font-size: 14pt;'>&times; 10<sup>{factor}</sup></span>"
        self._peak_panel.label_units.setText(text)
    

    # === filter settings === 
    def _update_low_freq(self, value):
        self.settings.processing_settings.freq_low = value
        self.data_processor.create_butter()
    
    def _update_high_freq(self, value):
        self.settings.processing_settings.freq_high = value
        self.data_processor.create_butter()
    
    def _update_notch(self, status):
        self.settings.processing_settings.do_notch = status
        self.data_processor.create_notch()
    
    def _update_lowpass(self, status):
        self.settings.processing_settings.do_lowpass = status
        self.data_processor.create_butter()
    
    def _update_highpass(self, status):
        self.settings.processing_settings.do_highpass = status
        self.data_processor.create_butter()