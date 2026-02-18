import numpy as np

class PlotUpdater:
    def __init__(self, panel, settings):
        """
        panel: qt window
        settings: settings_plot
        """
        self.plot_panel = panel
        self.settings = settings            # settings plot_settings
    
    def plot_pack(self):
        self.plot_panel.update_plot()
    
    def plot_trigger(self, idx):
        self.plot_panel.plot_trigger(idx)
    
    def plot_peak(self, idx):
        self.plot_panel.plot_peak(idx)
    
    def change_thr_line(self, thr):
        self.plot_panel.update_thr_line(thr)

