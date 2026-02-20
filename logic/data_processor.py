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
    peakIdx = pyqtSignal(int)

    delayValue = pyqtSignal(int)
    delayTripletValues = pyqtSignal(object)
 
    def __init__(self, settings):
        super().__init__()
        self.settings = settings    # settings

        # для хранения данных
        time_range_ms = self.settings.plot_settings.time_range_ms
        maxlen = int(time_range_ms * self.settings.Fs / 1000)
        zeros = [np.nan for _ in range(maxlen)]
        self.ts =  deque(np.arange(maxlen) * 1000 / self.settings.Fs, maxlen=maxlen)                             # стек с данными таймстемпов
        self.emg = deque(zeros, maxlen=maxlen)     # стек с данными EMG
        self.trigger = deque(zeros, maxlen=maxlen)     # стек с данными EMG

        self.timestamp = 0

        self._trigger = None

        self._ponk_count = 0
        self._delays = [[], [], []]
        self._triplets_counter = 0

        self._coef = 1000 / self.settings.Fs
        self._ms_to_sample = lambda x: int(x / 1000 * self.settings.Fs)                                  # функция для пересчёта мс в сэмплы

        self._init_state()
    
    def _init_state(self):
        self.create_filters()
        self._detect_on = False


    @pyqtSlot(object, float)
    def add_pack(self, pack, ts):
        """
        :param pack: New portion of data.       ndarray [n_channels, n_samples]
        :param ts: timestamp from resonance.

        Signals:
            newDataProcessed: новая pack добавлена.
        """
        # emg = np.diff(pack[:, self.settings.emg_channels_monopolar], axis=1).squeeze() 
        
        emg = self._process_new_pack(pack)
        self.emg.extend(emg)

        self.ts.extend(np.arange(self.timestamp, self.timestamp + emg.shape[0], 1) * self._coef)        # ms
        self.timestamp += emg.shape[0]  # idx

        self._process_trigger(pack)

        self.newDataProcessed.emit()        # --> plot_updater
        if (self._trigger is not None) and (self._ponk_count < 3) and self._detect_on:
            self.process_ponk()

    # === ponk detection ===
    def process_ponk(self):
        """
        Набирает данные для нахождения пика и обнаруживает его.
        """
        s = self.settings.detection_settings
        window = s.window_ms
        
        if self.ts[-1] >= self._trigger+window[1]: # если накопилось достаточно сэмплов

            mask = np.where((self.ts >= self._trigger+window[0]) & (self.ts <= self._trigger+window[1]))[0]
            x = np.array(self.emg)[mask]    # выделяем нужный кусок

            threshold = self._define_thr(x)
            crossings = np.where(x > threshold)[0]      # находим есть ли эмг выше порога
            delay = np.nan
            if len(crossings) > 0:
                onset_idx = crossings[0]
                self.peakIdx.emit(onset_idx+mask[0])    # --> plot_updater

                onset_time = self.ts[onset_idx+mask[0]] # момент времени
                delay = onset_time - self._trigger

                self.delayValue.emit(int(delay))        # --> to show immediate feedback

                print("DELAY {}".format(delay))
                
            else:
                print("NO PEAK HAS BEEN DETECTED")

            print("PONK COUNTER", self._ponk_count)
            self._delays[self._ponk_count].append(delay)        # --> triplets
            self._ponk_count += 1
            self._trigger = None 

    
    def _define_thr(self, x):
        s = self.settings.detection_settings
        if s.thr_adaptive:
            baseline = x[:self._ms_to_sample(s.baseline_ms)]
            threshold = np.mean(baseline) + s.n_sd * np.std(baseline)
        else:
            threshold = s.threshold * (10 ** self.settings.plot_settings.scale_factor)
        return threshold

    def activate_triplet_detection(self, status):
        # False - триплет окончен, True - триплет начался. 
        # print("TRIPLET HAS BEEN FINISHED?", not status)
        self._detect_on = status
        if not status:
            self._ponk_count = 0         # новый отсчёт поньков
            
            print(self._delays)
            # print(np.array(([np.array(delay) for delay in self._delays])))
            delays = np.array(([np.array(delay).T for delay in self._delays])).T
            # delays = np.array(self._delays).T     # для проведения манипуляций
            print(delays)
            
            s = self.settings.stimuli_settings
            if s.feedback_mode_curr == 0:   # после каждой попытки
                print("--> SHOW", delays[-1])
                self.delayTripletValues.emit(delays[-1])        # показать последнюю попытку
            elif s.feedback_mode_curr == 1:     # накапливать n штук
                self._triplets_counter += 1
                if self._triplets_counter >= s.feedback_n:
                    toshow = np.nanmean(delays[-s.feedback_n:], axis=0)
                    print("--> SHOW", toshow)
                    self.delayTripletValues.emit(toshow)        # показать среднее n попыток
                    self._triplets_counter = 0
            else:       # показывать если отклонение превышает заданные границы
                d1 = delays[-1][0]
                d2 = delays[-1][1]
                d3 = delays[-1][2]
                limits = s.delay_limit
                if (abs(d1) > limits[0]) or (abs(d2) > limits[1]) or (abs(d3) > limits[2]):
                    print("--> SHOW", delays[-1])
                    self.delayTripletValues.emit(delays[-1])        # показать последнюю попытку
    
    
    # === signal parsing === 
    def _process_trigger(self, pack):

        ttl = np.array(pack[:, -1], dtype=np.uint8)
        bit = self.settings.detection_settings.bit
        trigger = ((ttl>>bit) & 0b1).astype(int)
        self.trigger.extend(trigger*1E-3)

        trigger_diff = np.diff(trigger)
        event = np.where(trigger_diff == 1)[0]      # 0 -> 1
        if len(event) != 0:
            idx =-(len(trigger) - event[0])
            self.triggerIdx.emit(idx)
            self._trigger = self.ts[idx]       # для обработки поньков  [ms]
            
    def _process_new_pack(self, pack):
        emg = pack[:, self.settings.emg_channels_bipolar].squeeze() 
        s = self.settings.processing_settings
        if s.do_notch:
            emg = self.apply_notch(emg)
        if s.do_lowpass or s.do_highpass:
            emg = self.apply_butter(emg)

        if s.tkeo:
            emg = self.calculate_TKEO(emg)
        return emg

    # === filters creation === 
    def create_notch(self):
        s = self.settings.processing_settings

        Q = s.notch_fr / s.notch_width
        b_notch, a_notch = iirnotch(s.notch_fr, Q, fs=self.settings.Fs)

        self.sos_notch = tf2sos(b_notch, a_notch)
        zi_base = sosfilt_zi(self.sos_notch)
        self.zi_notch = zi_base
        # self.zi_notch = np.tile(zi_base[:, :, np.newaxis], (1, 1, n_ch))
    
    def create_butter(self):
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

    # === signal processing === 
    def apply_notch(self, emg):
        emg, self.zi_notch = sosfilt(self.sos_notch, emg, axis=0, zi=self.zi_notch)
        return emg
    
    def apply_butter(self, emg):
        emg, self.zi_butter = sosfilt(self.sos_butter, emg, axis=0, zi=self.zi_butter)
        return emg

    def calculate_TKEO(self, x):
        tkeo = np.zeros_like(x)
        tkeo[1:-1] = x[1:-1]**2 - x[:-2] * x[2:]

        tkeo[0] = tkeo[1]    
        tkeo[-1] = tkeo[-2] 
        return tkeo