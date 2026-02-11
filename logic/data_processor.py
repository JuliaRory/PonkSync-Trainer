from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot
import numpy as np
from collections import deque

from scipy.signal import iirnotch, tf2sos, butter, sosfilt, sosfilt_zi

from settings.settings import Settings

from utils.averaging_math import RollingMean, RollingMedian, RollingTrimMean


class DataProcessor(QObject):
    """
    Базовый класс для источника данных.

    Args:
        settings(Settings): класс для хранения настроек для обработки данных.

    Attributes: 
        data (list): [max_n_samples x n_channels]
        timestamps (list): время прихода пакета (от резонанса) --> для сохранения эпох only [n_epoch]

    Signals:
        newDataProcessed: обработка данных завершена.
        
    """
    newDataProcessed = pyqtSignal()
 
    def __init__(self, settings):
        super().__init__()
        self.settings = settings    # settings

        # для хранения данных
        maxlen = int(self.settings.plot_settings.time_range_ms * self.settings.Fs / 1000)
        zeros = [0 for _ in range(maxlen)]
        self.ts =  deque(range(0, self.settings.plot_settings.time_range_ms, int(1000/self.settings.Fs)), maxlen=maxlen)                             # стек с данными таймстемпов
        self.emg = deque(zeros, maxlen=maxlen)     # стек с данными EMG

        self.timestamp = 0

        # функции-трансформации
        self._baseline = lambda x: x
        self._lowpass_filter = lambda x: x
        self._transform = lambda x: x

        self._ms_to_sample = lambda x: int(x / 1000 * self.settings.Fs)                                  # функция для пересчёта мс в сэмплы

        self._init_state()
    
    def _init_state(self):
        self.create_filters()


    @pyqtSlot(object, float)
    def add_epoch(self, pack, ts):
        """
        :param pack: New portion of data.       ndarray [n_channels, n_samples]
        :param ts: timestamp from resonance.

        Signals:
            newDataProcessed: новая pack добавлена.
        """
        emg = np.diff(pack[:, self.settings.emg_channels], axis=1).squeeze() * 1E3
        self.emg.extend(emg)

        time = int(emg.shape[0] * 1000 / self.settings.Fs)
        self.ts.extend(np.arange(self.timestamp, self.timestamp + time, 1000//self.settings.Fs))
        self.timestamp += time

        self.newDataProcessed.emit()        # --> plot_updater


    def create_notch(self):
        n_ch = len(self.settings.emg_channels) // 2

        s = self.settings.processing_settings

        Q = s.notch_fr / s.notch_width
        b_notch, a_notch = iirnotch(s.notch_fr, Q, fs=self.settings.Fs)

        self.sos_notch = tf2sos(b_notch, a_notch)
        zi_base = sosfilt_zi(self.sos_notch)

        self.zi_notch = np.tile(zi_base[:, :, np.newaxis], (1, 1, n_ch))
    
    def create_butter(self):
        n_ch = len(self.settings.emg_channels) // 2
        s = self.settings.processing_settings
        butter_type = None
        if s.do_lowpass and s.do_highpass:
            butter_type = "bandpass"
            freqs = [s.freq_low, s.freq_high]
        elif s.do_lowpass:
            butter_type = "lowpass"
            freqs = s.freq_high
        elif s.do_highpass:
            butter_type = "highpass"
            freqs = s.freq_low

        if butter_type is not None:
            self.sos_butter = butter(N=s.butter_order, Wn=freqs, btype=butter_type, output='sos', fs=self.settings.Fs)
            zi_base = sosfilt_zi(self.sos_butter)
            self.zi_butter = np.tile(zi_base[:, :, np.newaxis], (1, 1, n_ch))

    def create_filters(self):
        self.create_notch()     # 50 Hz Notch filter
        self.create_butter()        # butterworth filter

    def calculate_TKEO(self, x):
        tkeo = x[1:-1]**2 - x[:-2] * x[2:]
        return np.vstack([tkeo[0], tkeo, tkeo[-1]])   # добавление крайних соседей для сохранения длины
    
    def apply_notch(self):
        emg, self.zi_notch = sosfilt(self.sos_notch, np.array(self.emg), axis=0, zi=self.zi_notch)
        return emg
    
    def apply_butter(self):
        emg, self.zi_butter = sosfilt(self.sos_butter, np.array(self.emg), axis=0, zi=self.zi_butter)
        return emg

    # --- Сброс сессий ---

    def reset_sessions(self):
        self._epochs = []
        self._timestamps = []
        
        self._n_epoch = 0
        self.updateCounter.emit(self._n_epoch)

        self.average_functions = []
        self.average_functions_mep = []