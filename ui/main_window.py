import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout

import time, random
from h5py import File
from numpy import diff, arange, array, full, sum, tile, newaxis, vstack, linspace, pi, sin
from scipy.signal import iirnotch, tf2sos, butter, sosfilt, sosfilt_zi

from collections import deque
import copy



class ArtemMainWindow(QWidget):
    def __init__(self, dispatcher=None, settings=None):
        super().__init__()
        self.setWindowTitle("SyncPonk Trainer")
        # self.setWindowIcon(QIcon(r"./resources/icon.png"))

        self._resonance = 
        if settings is None:
            raise Exception("No settings are provided.")
        self.params = settings

        
        if dispatcher is not None:              # RESONANCE STREAM
            self.dispatcher = dispatcher
            self.dispatcher[0].set_callback(self.get_data_nvx)                      # функция-обработчик входящего потока: активируется при получении новых данных
        elif settings["stream_mode"] == 'LSL':  # NEOREC STREAM
            self.receiver = LSLReceiver(stream_name=settings["LSL_stream_name"])    # Приёмник потока с LSL
            self.receiver.new_sample.connect(self.get_data_lsl)                     # Функция-обработчик входящего потока: активируется при получении новых данных
            self.receiver.start()
            self.data = []         # list для накопления сэмплов

        self.t1 = time.perf_counter()
        # self.setObjectName('MainWindow')
        # self.setStyleSheet("#MainWindow{background-image:url(./resources/background_cats.png);")
        # palette = QtGui.QPalette()
        # palette.setBrush(QtGui.QPalette.Background, QtGui.QBrush(QtGui.QImage(r"../resources/background_cats2.png")))
        # self.setPalette(palette)

        # self.pallete = QtGui.QPalette()
        # self.pallete.setColor(QtGui.QPalette.Background, QtCore.Qt.white)

        # self.opacity_effect = QtWidgets.QGraphicsOpacityEffect() 
        # self.opacity_effect.setOpacity(0.7)
        # self.setGraphicsEffect(self.opacity_effect) 

        

        self.max_value, self.min_value = 2, -2
        self.scale_offset, self.scale_factor = 0, 0
        self.time_range_emg = self.params["time_range_ms"]
        self.time_range_clf = 5000
        self.notch_fr, self.notch_width = 50, 1
        self.butter_order = 4
        self.butter_lower_fr, self.butter_upper_fr = 5, 150

        self.thr = 0.001
        self.proba_thr = 0.5
        self.fb_window = 1000

        self.extra_samples = 500

        maxlen = int(self.params["time_range_ms"] * self.params["Fs"] / 1000)
        zeros = [0 for _ in range(maxlen)]
        self.ts =  deque(range(0, self.params["time_range_ms"], int(1000/self.params["Fs"])), maxlen=maxlen)                             # стек с данными таймстемпов
        self.emg = [deque(zeros, maxlen=maxlen), deque(zeros, maxlen=maxlen)]     # стеки с данными EMG

        self.timestamp = 0
        
        self.resize(WIDTH_SET, HEIGHT_SET)
        self.show_window()
        

    def show_window(self):
        layout = QGridLayout(self)

        self.current_size = 0
        self.current_emg_timestamp = 0
        self.counter = 0

        self.create_scale_settings()    # создать блок с настройками масштабирования    --> self.box_scale_settings
        self.create_filter_settings()   # создать блок с настройками фильтрации         --> self.box_filter_settings
        self.create_sensor_emg()        # создать блок с сенсором миограммы             --> self.box_sensor

        self.create_filters()
        self.create_emg_graphs()        # создать блок с графиками миограммы            --> self.plot_emg_graph

        settings_box = QWidget() # create box with settings
        # self.left_column.setStyleSheet('QWidget {background: white; }')
        settings_layout = QGridLayout(settings_box)
        self.check_box_mode = self.check_box(False, 'offline mode')
        self.check_box_mode.clicked.connect(self.change_mode)
        settings_layout.addWidget(self.check_box_mode, 0, 0, 1, 1)
        settings_layout.addWidget(self.box_scale_settings, 1, 0, 1, 1, Qt.AlignCenter)
        settings_layout.addWidget(self.box_filter_settings, 2, 0, 2, 1, Qt.AlignCenter)

        # left column
        layout.addWidget(settings_box, 0, 0, 7, 1, Qt.AlignCenter)
        # center column 
        layout.addWidget(self.box_sensor, 3, 1, 4, 1, Qt.AlignCenter)
        # right column
        layout.addWidget(self.plots[0], 0, 2, 3, 2, Qt.AlignCenter)
        layout.addWidget(self.plots[1], 3, 2, 4, 2, Qt.AlignCenter)
        
        self.show()


    def create_sensor_emg(self):
        self.box_sensor = QWidget()
        #self.box_sensor.setStyleSheet("QWidget""{""background : white;""}")
        layout = QGridLayout()

        label_threshold = QLabel('EMG threshold', self)
        spin_box_threshold = self.spin_box(0, 100, self.thr, data_type='float', step=0.0001)
        #spin_box_threshold.valueChanged[float].connect(self.set_threshold)

        self.emg_sensor = QPushButton(self, text='GOOD')
        self.emg_sensor.setDisabled(True)
        self.emg_sensor.setStyleSheet('QPushButton {background-color: "green"; color: rgb(255, 255, 255)}')

        layout.addWidget(label_threshold, 0, 0)
        layout.addWidget(spin_box_threshold, 0, 1)
        layout.addWidget(self.emg_sensor, 1, 0, 1, 2, Qt.AlignCenter)
        self.box_sensor.setLayout(layout)


    def check_signal_amplitude(self):
        amp_value = max(self.emg_tkeo[self.extra_samples:])

        current_color = 'red' if amp_value >= self.thr else 'green'
        current_text = 'BAD' if amp_value >= self.thr else 'GOOD'
        self.emg_sensor.setStyleSheet('QPushButton {background-color:' + current_color + '; color: rgb(255, 255, 255)}')
        self.emg_sensor.setText(current_text)


    def create_emg_graphs(self):
        # EMG/TKEO(EMG) vs time plot
        titles = ["LEFT", "RIGHT"]
        if self.check_box_show_tkeo_emg.isChecked():        # если показывать TKEO
            titles = [t + ': TKEO' for t in titles] 
        scale_factor = 10 ** self.scale_factor              # self.scale_factor - это степень (например -5), принятая из настроек
        pen = pg.mkPen(color=(255, 255, 255))               # set white color for a curve 
        max_width, max_height = 900, 400 

        self.plots = [pg.PlotWidget(), pg.PlotWidget()]     # list с виджетами для графиков миограмм
        self.lines = []                                     # list для сохранения кривых
        for i, plot in enumerate(self.plots):

            plot.setMinimumSize(max_width, max_height)
            plot.setBackground("k")  # set black color for a background

            line = plot.plot(y=self.emg[0], x=self.ts)    # отображение "ничего" на месте сигнала миограммы
            self.lines.append(line)
             
            plot.setTitle(titles[i])
            # self.plot_graph.setLabel("left", "Voltage (mV)")
            plot.setLabel("bottom", "Time (ms)")
            plot.showGrid(x=True, y=True)
            plot.setYRange(self.min_value * scale_factor, self.max_value * scale_factor)

    def create_filters(self):
        n_ch = len(self.params["EMG_channels"]) // 2
        # 50 Hz Notch filter
        
        Q = self.notch_fr / self.notch_width
        b_notch, a_notch = iirnotch(self.notch_fr, Q, fs=1000)
        self.sos_notch = tf2sos(b_notch, a_notch)
        zi_base = sosfilt_zi(self.sos_notch)
        self.zi_notch = tile(zi_base[:, :, newaxis], (1, 1, n_ch))
            
        # butterworth filter
        
        lower_fr, upper_fr = None, None
        butter_type = None
        if self.check_box_lower_fr.isChecked():
            lower_fr = self.butter_lower_fr
        if self.check_box_upper_fr.isChecked():
            upper_fr = self.butter_upper_fr
        if lower_fr is not None and upper_fr is not None:
            butter_type='bandpass'
            freqs = [lower_fr, upper_fr]
        elif lower_fr is None and upper_fr is not None:
            butter_type='lowpass'
            freqs=upper_fr
        elif lower_fr is not None and upper_fr is None:
            butter_type='highpass'
            freqs=lower_fr
        if butter_type is not None:
            self.sos_butter = butter(N=self.butter_order, Wn=freqs, btype=butter_type, output='sos', fs=1000)
            zi_base = sosfilt_zi(self.sos_butter)
            self.zi_butter = tile(zi_base[:, :, newaxis], (1, 1, n_ch))
    
    def get_data_nvx(self, msg, ts):     # get data from nvx or speed
        emg = msg
        if self.params["stream_mode"] == "NVX":
            raw_emg_ch = self.params["EMG_channels"]        # emg_channels : list of channels, e.g. [64, 65, 66, 67]
            
            emg_ch = [[ch, ch+1] for ch in raw_emg_ch[::2]] # pairs of electrodes (one or two), eg [[64, 65], [66, 67]]

            emg = array([diff(msg[:, ch], axis=1).squeeze() * 1000 for ch in emg_ch]).round(3)   # взять только каналы с ЭМГ и посчитать их разницу --> np.array [n_samples, n_emg_ch]
        
        self.process_data(emg)  # вызвать функцию для обработки данных
    
    def get_data_lsl(self, sample):
        # sample: list of samples, size = n_channels
        raw_emg_ch = self.params["EMG_channels"]            # EMG_channels : list of channels, e.g. [64, 65, 66, 67]
        #print(raw_emg_ch)
        #emg_ch = [[ch, ch+1] for ch in raw_emg_ch[::2]]     # pairs of electrodes (one or two), eg [[64, 65], [66, 67]]
        emg_ch = [[raw_emg_ch[0], raw_emg_ch[1]], [raw_emg_ch[2], raw_emg_ch[3]]]
        self.data.append([array(sample)[0].squeeze() *1000 for ch1_ch2 in emg_ch])
        # self.data.append([diff(array(sample)[ch1_ch2]).squeeze() *1000 for ch1_ch2 in emg_ch])
        if len(self.data) == self.params["LSL_block_size"]:     # если набралось нужное количество сэмплов
            # print(f"update plots (new epoch): {time.perf_counter() - self.t1:.6f} сек")
            # self.t1 = time.perf_counter()
            self.process_data(array(self.data).round(3))        # вызвать функцию для обработки данных
            self.data = []                                      # очистить стек с данными

    def TKEO(self, x):
        tkeo = x[1:-1]**2 - x[:-2] * x[2:]
        return vstack([tkeo[0], tkeo, tkeo[-1]])   # добавление крайних соседей для сохранения длины
            
    def process_data(self, emg):
        # emg --> np.array [n_samples, n_emg_ch]

        # filtering                                        -- optional (for NVX or NeoRec data)
        if self.check_box_notch.isChecked():                  # 50 Hz Notch filter
            emg, self.zi_notch = sosfilt(self.sos_notch, emg, axis=0, zi=self.zi_notch)
        
        if self.check_box_butter.isChecked():                 # bandpass (/highpass/lowpass) butterworth filter
            emg, self.zi_butter = sosfilt(self.sos_butter, emg, axis=0, zi=self.zi_butter)

        if self.check_box_show_tkeo_emg.isChecked():          # calculate TKEO
            emg = self.TKEO(emg)

        # update data
        time = int(emg.shape[0] * 1000 / self.params["Fs"])
        self.ts.extend(arange(self.timestamp, self.timestamp + time, 1000//self.params["Fs"]))
        
        self.timestamp += time
        for i in range(emg.shape[1]):
            self.emg[i].extend(emg[:, i])
            self.lines[i].setData(y=self.emg[i], x=self.ts)
            

    def create_scale_settings(self):
        self.box_scale_settings = QWidget()
        # self.box_scale_settings.setStyleSheet("QWidget""{""background : white;""}")
        layout = QGridLayout()

        # scale factor
        label_scale_factor = QLabel('scale factor', self)

        box_scale_factor = QWidget()
        layout_scale_factor = QGridLayout()
        label_1e = QLabel('1E', self)
        spin_box_scale_factor = self.spin_box(-20, 20, self.scale_factor)
        spin_box_scale_factor.valueChanged[int].connect(self.set_scale_factor)
        layout_scale_factor.addWidget(label_1e, 0, 0, 1, 1)
        layout_scale_factor.addWidget(spin_box_scale_factor, 0, 1, 1, 2)
        box_scale_factor.setLayout(layout_scale_factor)

        # maximum value
        label_max_value = QLabel('maximum value', self)
        spin_box_max_value = self.spin_box(-100, 100, self.max_value)
        spin_box_max_value.valueChanged[int].connect(self.set_max_value)

        # minimum value
        label_min_value = QLabel('minimum value', self)
        spin_box_min_value = self.spin_box(-100, 100, self.min_value)
        spin_box_min_value.valueChanged[int].connect(self.set_min_value)

        # scale step
        # label_scale_step = QtWidgets.QLabel('scale step', self)
        # spin_box_scale_step = self.spin_box(0, 100, 2)
        # spin_box_scale_step.valueChanged[int].connect(self.set_scale_step)

        # scale offset
        label_scale_offset = QLabel('scale offset', self)
        spin_box_scale_offset = self.spin_box(-100, 100, self.scale_offset)
        spin_box_scale_offset.valueChanged[int].connect(self.set_scale_offset)

        # time range
        label_time_range_EMG = QLabel('time range EMG', self)
        box_time_range_EMG = self.spin_box_with_unit(unit='c', min=0, max=20, value=int(self.time_range_emg // 1000), function=self.set_time_range_emg)
        
        label_time_range_CLF = QLabel('time range CLF', self)
        box_time_range_CLF = self.spin_box_with_unit(unit='c', min=0, max=20, value=int(self.time_range_clf // 1000), function=self.set_time_range_clf)

        row = 0
        layout.addWidget(label_scale_factor, row, 0)
        layout.addWidget(box_scale_factor, row, 1)
        layout.addWidget(label_scale_offset, row, 2)
        layout.addWidget(spin_box_scale_offset, row, 3)
        row += 1
        layout.addWidget(label_max_value, row, 0)
        layout.addWidget(spin_box_max_value, row, 1)
        layout.addWidget(label_min_value, row, 2)
        layout.addWidget(spin_box_min_value, row, 3)
        row += 1
        layout.addWidget(label_time_range_CLF, row, 0)
        layout.addWidget(box_time_range_CLF, row, 1)
        layout.addWidget(label_time_range_EMG, row, 2)
        layout.addWidget(box_time_range_EMG, row, 3)
        # row += 1
        # layout.addWidget(label_scale_step, row, 0)
        # layout.addWidget(spin_box_scale_step, row, 1)
        row += 1
        

        self.box_scale_settings.setLayout(layout)
    

    def create_filter_settings(self):
        self.box_filter_settings = QWidget()
        # self.box_filter_settings.setStyleSheet("QWidget""{""background : white;""}")
        layout = QGridLayout()

        # show tkeo and filtered emg
        self.check_box_show_emg = self.check_box(False, 'Show EMG signal?')
        self.check_box_show_tkeo_emg = self.check_box(True, 'Show EMG energy (TKEO)?')
        self.check_box_show_tkeo_emg.clicked.connect(self.update_plot_title)

        # 5-150 Hz Butterworth bandpass filter 
        label_butterworth = QLabel('Butterworth filter', self)
        label_order = QLabel('order', self)
        spin_box_order = self.spin_box(0, 20, self.butter_order)
        spin_box_order.valueChanged[int].connect(self.set_butter_order)
        self.check_box_butter = self.check_box(True, 'use filter?')
        label_lower_fr = QLabel('Lower cut-off frequency', self)
        box_lower_fr = self.spin_box_with_unit(unit='Hz', min=0, max=500, value=self.butter_lower_fr, function=self.set_butter_lower_fr)
        self.check_box_lower_fr = self.check_box(True, 'use?')
        label_upper_fr = QLabel('Upper cut-off frequency', self)
        box_upper_fr = self.spin_box_with_unit(unit='Hz', min=0, max=500, value=self.butter_upper_fr, function=self.set_butter_upper_fr)
        self.check_box_upper_fr = self.check_box(True, 'use?')

        # 50 Hz Notch filter
        label_notch = QLabel('Notch filter', self)
        label_notch_fr = QLabel('frequency', self)
        box_notch_fr = self.spin_box_with_unit(unit='Hz', min=0, max=500, value=self.notch_fr, function=self.set_notch_fr)
        self.check_box_notch = self.check_box(True, 'use?')
        label_notch_width = QLabel('width', self)
        box_notch_width = self.spin_box_with_unit(unit='Hz', min=0, max=500, value=self.notch_width, function=self.set_notch_width)

        row = 0
        layout.addWidget(self.check_box_show_emg, row, 0, 1, 3)
        row += 1
        layout.addWidget(self.check_box_show_tkeo_emg, row, 0, 1, 3)
        row += 1
        layout.addWidget(label_butterworth, row, 0, 1, 3, Qt.AlignCenter)
        row += 1
        layout.addWidget(label_order, row, 0)
        layout.addWidget(spin_box_order, row, 1)
        layout.addWidget(self.check_box_butter, row, 2)
        row += 1
        layout.addWidget(label_lower_fr, row, 0)
        layout.addWidget(box_lower_fr, row, 1)
        layout.addWidget(self.check_box_lower_fr, row, 2)
        row += 1
        layout.addWidget(label_upper_fr, row, 0)
        layout.addWidget(box_upper_fr, row, 1)
        layout.addWidget(self.check_box_upper_fr, row, 2)
        row += 1
        layout.addWidget(label_notch, row, 0, 1, 3, Qt.AlignCenter)
        row += 1
        layout.addWidget(label_notch_fr, row, 0)
        layout.addWidget(box_notch_fr, row, 1)
        layout.addWidget(self.check_box_notch, row, 2)
        row += 1
        layout.addWidget(label_notch_width, row, 0)
        layout.addWidget(box_notch_width, row, 1)
        
        self.box_filter_settings.setLayout(layout)


    def spin_box(self, min, max, value, data_type = 'int', step=1, decimals=4):
        if data_type == 'int':
            spin_box = QSpinBox(self)
        else:
            spin_box = QDoubleSpinBox(self)
            spin_box.setDecimals(decimals)
        spin_box.setRange(min, max)
        spin_box.setValue(value)
        spin_box.setSingleStep(step)
        return spin_box
    

    def spin_box_with_unit(self, unit, min, max, value, function=None):
        box = QWidget()
        layout = QGridLayout()
        spin_box = self.spin_box(min, max, value)
        if function is not None:
            spin_box.valueChanged[int].connect(function)
        label_time = QLabel(unit, self)
        layout.addWidget(spin_box, 0, 0, 1, 2)
        layout.addWidget(label_time, 0, 2, 1, 1)
        box.setLayout(layout)

        return box


    def check_box(self, state, text=''):
        check_box = QCheckBox(text, self)
        if state:
            check_box.toggle()
        return check_box



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
    

    def change_mode(self):
        if self.check_box_mode.isChecked():
            self.timer = QTimer()
            self.timer.setInterval(INTERVAL)
            self.timer.timeout.connect(self.update_emg_plot)
            self.timer.start()

            self.timer_proba = QTimer()
            self.timer_proba.setInterval(INTERVAL)
            self.timer_proba.timeout.connect(self.update_proba_plot)
            self.timer_proba.start()
        else:
            self.timer.stop()
            self.timer_proba.stop()