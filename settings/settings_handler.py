
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

        self._setup_units()
        self._update_thr()


    def _setup_connections(self):
        self._scale_panel.spin_box_scale.valueChanged[int].connect(self._update_scale)

        self._peak_panel.spin_box_threshold_curr.valueChanged[int].connect(self._update_threshold)
        self._peak_panel.spin_box_threshold_mv.valueChanged[float].connect(self._update_threshold_mv)

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

        self._setup_units()
        self._update_thr()

    def _setup_units(self):
        factor = self.settings.plot_settings.scale_factor
        text = f"<span style='font-size: 14pt;'>&times; 10<sup>{factor}</sup></span>"
        self._peak_panel.label_units.setText(text)

