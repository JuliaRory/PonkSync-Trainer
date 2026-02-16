import pyqtgraph as pg
from PyQt5.QtWidgets import QFrame, QHBoxLayout

class OnlineGraph(QFrame):
         
    def __init__(self, settings, data_processor, parent=None):
        super().__init__(parent)

        self.data_processor = data_processor
        self.settings = settings.plot_settings

        self._setup_ui()
        self._setup_layout()
     
    def _setup_ui(self):
        # EMG/TKEO(EMG) vs time plot
        title = "EMG"
        
        scale_factor = 10 ** self.settings.scale_factor     # self.scale_factor - это степень (например -5), принятая из настроек
        pen = pg.mkPen(color=(255, 255, 255))               # set white color for a curve 
        max_width, max_height = 900, 400 

        self.figure = pg.PlotWidget(self)     # list с виджетами для графиков миограмм
        self.line = self.figure.plot(y=self.data_processor.emg, x=self.data_processor.ts)    # отображение "ничего" на месте сигнала миограммы

        self._trigger_line = self.figure.plot(y=self.data_processor.emg, x=self.data_processor.ts, pen="b")    # отображение "ничего" на месте сигнала миограммы

        self.trigger_lines = []

        self.figure.setMinimumSize(max_width, max_height)
        self.figure.setBackground("k")  # set black color for a background

        self.figure.setTitle(title)
        self.figure.setLabel("left", "Voltage [mV]")
        self.figure.setLabel("bottom", "Time [ms]")
        self.figure.showGrid(x=True, y=True)
        self.figure.setYRange(self.settings.ymin * scale_factor, self.settings.ymax * scale_factor)

    def _setup_layout(self):
        layout = QHBoxLayout(self)
        layout.addWidget(self.figure)

    def update_plot(self):
        self.line.setData(x=self.data_processor.ts, y=self.data_processor.emg)

        self._trigger_line.setData(x=self.data_processor.ts, y=self.data_processor.trigger)

        self.check_trigger_lines()
    
    def check_trigger_lines(self):
        # view_range = self.figure.viewRange()
        # xmin, xmax = view_range[0]
        xmin = self.data_processor.ts[0]
        for line in self.trigger_lines[:]:
            if line.value() < xmin:
                self.figure.removeItem(line)
                self.trigger_lines.remove(line)

    def plot_trigger(self, idx):
        x_coord = self.data_processor.ts[-idx]
        line = pg.InfiniteLine(pos=x_coord, angle=90, pen="r")
        self.trigger_lines.append(line)
        self.figure.addItem(line)
        # self.figure.plot(y=self.data_processor.emg, x=self.data_processor.ts)    # отображение "ничего" на месте сигнала миограммы