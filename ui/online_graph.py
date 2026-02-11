import pyqtgraph as pg
from PyQt5.QtWidgets import QFrame

class OnlineGraph(QFrame):
         
    def __init__(self, settings, data_processor, parent=None):
        super().__init__(parent)

        self.data_processor = data_processor
        self.settings = settings.plot_settings

        self._setup_ui()
     
    def _setup_ui(self):
        # EMG/TKEO(EMG) vs time plot
        title = "EMG"
        
        scale_factor = 10 ** self.settings.scale_factor     # self.scale_factor - это степень (например -5), принятая из настроек
        pen = pg.mkPen(color=(255, 255, 255))               # set white color for a curve 
        max_width, max_height = 900, 400 

        self.figure = pg.PlotWidget(self)     # list с виджетами для графиков миограмм
        self.line = self.figure.plot(y=self.data_processor.emg, x=self.data_processor.ts)    # отображение "ничего" на месте сигнала миограммы

        self.figure.setMinimumSize(max_width, max_height)
        self.figure.setBackground("k")  # set black color for a background

        self.figure.setTitle(title)
        self.figure.setLabel("left", "Voltage [mV]")
        self.figure.setLabel("bottom", "Time [ms]")
        self.figure.showGrid(x=True, y=True)
        self.figure.setYRange(self.settings.ymin * scale_factor, self.settings.ymax * scale_factor)

    def _setup_layout(self):
        self.figure.move(0, 0)

    def update_plot(self, emg):
        self.line.setData(emg, self.data_processor.ts)