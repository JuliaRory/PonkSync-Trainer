from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot
import numpy as np
from collections import deque

from scipy.signal import iirnotch, tf2sos, butter, sosfilt, sosfilt_zi

from settings.settings import Settings

from utils.averaging_math import RollingMean, RollingMedian, RollingTrimMean

import logging
from datetime import datetime

# from utils.logging import ExperimentLogger

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
    delayValues = pyqtSignal(object)    # --> main_window --> stimuli_panel --> video_player
 
    def __init__(self, settings):
        super().__init__()
        self.settings = settings    # settings
        # self.logger = logging.getLogger(__name__)
        self.logger = ExperimentLogger(self.settings.stimuli_settings.filename)

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
        self._delays = []
        self._feedback_counter = 0  # для показа N усреднённого фидбэка

        self._coef = 1000 / self.settings.Fs
        self._ms_to_sample = lambda x: int(x / 1000 * self.settings.Fs)                                  # функция для пересчёта мс в сэмплы

        self._init_state()
    
    def _init_state(self):
        self.create_filters()
        self._detect_on = False

    def change_file(self):
        self.logger.close()
        self.logger = ExperimentLogger(self.settings.stimuli_settings.filename)

    @pyqtSlot(object, float)
    def add_pack(self, pack, ts):
        """
        :param pack: New portion of data.       ndarray [n_channels, n_samples]
        :param ts: timestamp from resonance.

        Signals:
            newDataProcessed: новая pack добавлена.
        """
        # emg = np.diff(pack[:, self.settings.emg_channels_monopolar], axis=1).squeeze() 
        
        self.res_timestamp = ts
        emg = self._process_new_pack(pack)
        self.emg.extend(emg* 1E3)

        self.ts.extend(np.arange(self.timestamp, self.timestamp + emg.shape[0], 1) * self._coef)        # ms
        self.timestamp += emg.shape[0]  # idx

        self._process_trigger(pack)

        self.newDataProcessed.emit()        # --> plot_updater
        if self._trigger is not None:
            self.process_ponk()

    def _define_thr(self, x):
        s = self.settings.detection_settings
        if s.thr_adaptive:
            baseline = x[:self._ms_to_sample(s.baseline_ms)]
            threshold = np.mean(baseline) + s.n_sd * np.std(baseline)
        else:
            threshold = s.threshold * (10 ** self.settings.plot_settings.scale_factor)
        return threshold
    
    # === ponk detection ===
    def process_ponk(self):
        """
        Набирает данные для нахождения пика и обнаруживает его.
        """
        s = self.settings.detection_settings
        window = s.window_ms
        
        if self.ts[-1] >= self._trigger+window[1]: # если накопилось достаточно сэмплов
            # self.logger.info(f"Trigger processed at {self.ts[-1]} ms.")

            mask = np.where((self.ts >= self._trigger+window[0]) & (self.ts <= self._trigger+window[1]))[0]
            x = np.array(self.emg)[mask]    # выделяем нужный кусок

            threshold = self._define_thr(x)
            # self.logger.info(f"Threshold is {threshold}.")

            crossings = np.where(x > threshold)[0]      # находим есть ли эмг выше порога
            
            delay = np.nan
            if len(crossings) > 0:
                onset_idx = crossings[0]
                self.peakIdx.emit(onset_idx+mask[0])    # --> plot_updater

                onset_time = self.ts[onset_idx+mask[0]] # момент времени
                delay = onset_time - self._trigger
                duration = len(crossings)

                amp = np.max(x[crossings])

                self.delayValue.emit(int(delay))        # --> to show immediate feedback

                data = {
                    'timestamp': datetime.now().isoformat(),
                    'res_timestamp': self.res_timestamp, 
                    'error': int(delay),
                    'duration': int(duration), 
                    'amplitude': amp
                }
                print("DELAY {}".format(delay))
                
            else:
                print("NO PEAK HAS BEEN DETECTED")
                data = {
                    'timestamp': datetime.now().isoformat(),
                    'res_timestamp': self.res_timestamp, 
                    'error': np.nan,
                    'duration': np.nan, 
                    'amplitude': np.nan
                }

            data["mode"] = "TKEO" if self.settings.processing_settings.tkeo else "EMG"
            data['threshold'] = threshold
            self.logger.log_trial(data)
            print("PONK COUNTER", self._ponk_count)
            self._delays.append(delay)       # накапливает все задержки  
            self._feedback_counter += 1  # для показа N-усреднённой обратной связи
            self._ponk_count += 1
            self._trigger = None 


    def get_delays(self):
        """
        после окончания стимульного ряда
        Signal: delayValues --> main_window --> stimuli_panel --> video_player
        """

        s = self.settings.stimuli_settings
        
        stimuli = s.stimuli_curr
        feedback = s.feedback_mode_curr
        
        if feedback == 3:
            return
        # if feedback == 0 or 2 (and if delays are above limit in case of feedback == 2)
        send_feedback = True
        feedack_values = np.array(self._delays[-3:]) if stimuli == 0 else np.array([self._delays[-1]])      # three or one last delays
        
        if feedback == 2: # показывать если отклонение превышает заданные границы
            limits = s.delay_limit
            send_feedback = any(abs(value) > limit for value, limit in zip(feedack_values, limits))  # False if all below limit
            print(send_feedback, [value > limit for value, limit in zip(feedack_values, limits)])

        elif feedback == 1:  # показывать после накопления N значений усреднённую версию
            send_feedback = self._feedback_counter >= s.feedback_n
            if send_feedback:
                n_ponk = 3 if stimuli == 0 else 1
                delays = np.array(self._delays[-s.feedback_n*n_ponk:]).reshape((s.feedback_n, n_ponk)) 
                feedack_values = np.nanmean(delays, axis=0)
                self._feedback_counter = 0  # начать отсчёт сначала

        if send_feedback:
            # self.logger.info(f"Delays: {feedack_values}.")
            self.delayValues.emit(feedack_values) 

    
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
            # self.logger.info(f"Trigger event at {self._trigger} ms.")
            
    def _process_new_pack(self, pack):
        emg = pack[:, self.settings.emg_channels_monopolar] 
        emg = np.diff(emg, axis=1).squeeze()
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