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
    triggerIdx = pyqtSignal(int)
 
    def __init__(self, settings):
        super().__init__()
        self.settings = settings    # settings

        # для хранения данных
        time_range_ms = self.settings.plot_settings.time_range_ms
        maxlen = int(time_range_ms * self.settings.Fs / 1000)
        zeros = [0 for _ in range(maxlen)]
        self.ts =  deque(np.arange(maxlen) * 1000 / self.settings.Fs, maxlen=maxlen)                             # стек с данными таймстемпов
        self.emg = deque(zeros, maxlen=maxlen)     # стек с данными EMG
        self.trigger = deque(zeros, maxlen=maxlen)     # стек с данными EMG

        self.timestamp = 0

        # функции-трансформации
        self._baseline = lambda x: x
        self._lowpass_filter = lambda x: x
        self._transform = lambda x: x

        self._coef = 1000 / self.settings.Fs
        self._ms_to_sample = lambda x: int(x / 1000 * self.settings.Fs)                                  # функция для пересчёта мс в сэмплы

        self._init_state()
    
    def _init_state(self):
        self.create_filters()


    @pyqtSlot(object, float)
    def add_pack(self, pack, ts):
        """
        :param pack: New portion of data.       ndarray [n_channels, n_samples]
        :param ts: timestamp from resonance.

        Signals:
            newDataProcessed: новая pack добавлена.
        """
        emg = np.diff(pack[:, self.settings.emg_channels], axis=1).squeeze() 

        s = self.settings.processing_settings
        if s.do_notch:
            emg = self.apply_notch(emg)
        if s.do_lowpass or s.do_highpass:
            emg = self.apply_butter(emg)

        self.emg.extend(emg)

        self.ts.extend(np.arange(self.timestamp, self.timestamp + emg.shape[0], 1) * self._coef)
        self.timestamp += emg.shape[0]

        ttl = np.array(pack[:, -1], dtype=np.uint8)
        trigger = ((ttl>>self.settings.bit_index) & 0b1).astype(int)
        self.trigger.extend(trigger*100)

        trigger_diff = np.diff(trigger)
        event = np.where(trigger_diff == 1)[0] 
        if len(event) != 0:
            self.triggerIdx.emit(event[0])

        self.newDataProcessed.emit()        # --> plot_updater


    def create_notch(self):
        n_ch = len(self.settings.emg_channels) // 2

        s = self.settings.processing_settings

        Q = s.notch_fr / s.notch_width
        b_notch, a_notch = iirnotch(s.notch_fr, Q, fs=self.settings.Fs)

        self.sos_notch = tf2sos(b_notch, a_notch)
        zi_base = sosfilt_zi(self.sos_notch)
        self.zi_notch = zi_base
        # self.zi_notch = np.tile(zi_base[:, :, np.newaxis], (1, 1, n_ch))
    
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
            self.zi_butter = zi_base
            # self.zi_butter = np.tile(zi_base[:, :, np.newaxis], (1, 1, n_ch))

    def create_filters(self):
        self.create_notch()     # 50 Hz Notch filter
        self.create_butter()        # butterworth filter

    def calculate_TKEO(self, x):
        tkeo = x[1:-1]**2 - x[:-2] * x[2:]
        return np.vstack([tkeo[0], tkeo, tkeo[-1]])   # добавление крайних соседей для сохранения длины
    
    def apply_notch(self, emg):
        emg, self.zi_notch = sosfilt(self.sos_notch, emg, axis=0, zi=self.zi_notch)
        return emg
    
    def apply_butter(self, emg):
        emg, self.zi_butter = sosfilt(self.sos_butter, emg, axis=0, zi=self.zi_butter)
        return emg