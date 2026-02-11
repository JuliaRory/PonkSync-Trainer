import numpy as np

class PlotUpdater:
    def __init__(self, panel, settings):
        """
        panel: qt window
        settings: settings_plot
        """
        self.plot_panel = panel
        self.settings = settings            # settings plot_settings
    
    def plot_pack(self, pack, processor):
        s = self.settings.processing_settings
        if s.do_notch:
            emg = processor.apply_notch()
        if s.do_butter:
            emg = processor.apply_butter()

        self.panel.figure.update_plot(emg)

