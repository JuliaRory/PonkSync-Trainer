
from dataclasses import is_dataclass
import json
from dataclasses import asdict

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
    def __init__(self, settings, data_processor):
        self.data_processor = data_processor
        self.settings = settings
        self.plot_updater = None
        self.ui = None

    def setupUI(self, filter_panel, plot_updater, scale_panel):
        self.plot_updater = plot_updater

        self.ui_filter = filter_panel
        self.ui_scale = scale_panel 

    # def setup_connections(self):
        # self.ui_scale
    #     self.ui_filter.check_box_notch.stateChanged.connect(self.)

