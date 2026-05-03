from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot
import numpy as np
from collections import deque
import os
import h5py

from scipy.signal import iirnotch, tf2sos, butter, sosfilt, sosfilt_zi

from settings.settings import Settings

from utils.averaging_math import RollingMean, RollingMedian, RollingTrimMean

import logging
from datetime import datetime

from utils.logging import ExperimentLogger

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
    mepEpochReady = pyqtSignal(object)
    mepRecordingFinished = pyqtSignal(float, int, str)

    delayValue = pyqtSignal(int)
    delayValues = pyqtSignal(object)    # --> main_window --> stimuli_panel --> video_player
 
    def __init__(self, settings, output_stream_ponk):
        super().__init__()
        self.settings = settings    # settings
        # self.logger = logging.getLogger(__name__)
        self.logger = ExperimentLogger(self.settings.stimuli_settings.filename)
        self.logger.set_output_stream(output_stream_ponk)

        self.output_stream_ponk = output_stream_ponk

        # для хранения данных
        time_range_ms = self.settings.plot_settings.time_range_ms
        maxlen = int(time_range_ms * self.settings.Fs / 1000)
        zeros = [np.nan for _ in range(maxlen)]
        self.ts =  deque(np.arange(maxlen) * 1000 / self.settings.Fs, maxlen=maxlen)                             # стек с данными таймстемпов
        self.emg = deque(zeros, maxlen=maxlen)     # стек с данными EMG
        self.mep_emg = deque(zeros, maxlen=maxlen)
        self.trigger = deque(zeros, maxlen=maxlen)     # стек с данными EMG

        self.timestamp = 0

        self._trigger = None

        self._ponk_count = 0
        self._delays = []
        self._feedback_cursor = 0
        self._pending_feedback_requests = 0
        self._feedback_counter = 0  # для показа N усреднённого фидбэка

        self._pending_mep_triggers = []
        self._mep_recording = False
        self._mep_hdf_path = None
        self._mep_record_epochs = []
        self._mep_record_amps = []
        self._mep_record_baselines = []
        self._mep_record_trigger_samples = []
        self._mep_record_trigger_times = []

        self._coef = 1000 / self.settings.Fs
        self._ms_to_sample = lambda x: int(x / 1000 * self.settings.Fs)                                  # функция для пересчёта мс в сэмплы

        self._init_state()
    
    def _init_state(self):
        self.create_filters()
        self._detect_on = False

    def change_file(self, filename):
        # filename : full path
        self.logger.close()
        self.logger = ExperimentLogger(filename)
        self.logger.set_output_stream(self.output_stream_ponk)
        self._delays = []
        self._feedback_counter = 0
        self._feedback_cursor = 0
        self._pending_feedback_requests = 0
        self._trigger = None

    def start_mep_recording(self, hdf_path):
        self._mep_hdf_path = hdf_path
        self._mep_record_epochs = []
        self._mep_record_amps = []
        self._mep_record_baselines = []
        self._mep_record_trigger_samples = []
        self._mep_record_trigger_times = []
        self._pending_mep_triggers = []
        self._mep_recording = True

    def finish_mep_recording(self):
        if not self._mep_recording:
            return

        self._process_pending_mep_epochs(force=True)
        self._mep_recording = False

        amps = np.asarray(self._mep_record_amps, dtype=float)
        finite_amps = amps[np.isfinite(amps)]
        mean_amp = float(np.mean(finite_amps)) if finite_amps.size else np.nan
        n_epochs = int(len(self._mep_record_epochs))
        saved_path = self._save_mep_recording()
        self.mepRecordingFinished.emit(mean_amp, n_epochs, saved_path or "")

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
        self.mep_emg.extend(self._last_mep_emg * 1E3)
        self.emg.extend(emg* 1E3)

        self.ts.extend(np.arange(self.timestamp, self.timestamp + emg.shape[0], 1) * self._coef)        # ms
        self.timestamp += emg.shape[0]  # idx

        self._queue_mep_triggers_from_pack(pack)
        self._process_trigger(pack)
        self._process_pending_mep_epochs()

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
        mov_criterio = s.mov_detect_criterio #"max" or "onset"
        
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
                # max_value_idx = np.argmax(x)[0]

                idx = onset_idx # max_value_idx if mov_criterio == "max" else 
                self.peakIdx.emit(idx+mask[0])    # --> plot_updater

                onset_time = self.ts[idx+mask[0]] # момент времени
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
                print("DETECTED DELAY {}".format(delay))
                
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
            # print("PONK COUNTER", self._ponk_count)
            self._delays.append(delay)       # накапливает все задержки  
            self._feedback_counter += 1      # для показа N-усреднённой обратной связи
            self._ponk_count += 1
            self._trigger = None
            self._try_emit_feedback()


    def get_delays(self):
        """
        после окончания стимульного ряда
        Signal: delayValues --> main_window --> stimuli_panel --> video_player
        """

        s = self.settings.stimuli_settings

        if s.feedback_mode_curr == 3:
            self._feedback_cursor = len(self._delays)
            return

        self._pending_feedback_requests += 1
        self._try_emit_feedback()
        return

        
        if feedback == 3:   # если режим без ОС
            return
        
        
        if feedback == 2: # показывать если отклонение превышает заданные границы
            limits = s.delay_limit
            send_feedback = any(abs(value) > limit for value, limit in zip(feedack_values, limits))  # False if all below limit
            # print("TO SEND", send_feedback, [value > limit for value, limit in zip(feedack_values, limits)])

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
            print("TO SEND", feedack_values)

    def _ponks_per_stimulus(self):
        stimuli = self.settings.stimuli_settings.stimuli_curr
        return 3 if stimuli == 2 else 1

    def _try_emit_feedback(self):
        s = self.settings.stimuli_settings
        feedback = s.feedback_mode_curr

        if feedback == 3:
            self._pending_feedback_requests = 0
            self._feedback_cursor = len(self._delays)
            return

        n_ponk = self._ponks_per_stimulus()

        while self._pending_feedback_requests > 0:
            available = len(self._delays) - self._feedback_cursor

            if feedback == 1:
                required_requests = max(1, int(s.feedback_n))
                required_delays = required_requests * n_ponk
                if self._pending_feedback_requests < required_requests or available < required_delays:
                    return

                values = np.array(self._delays[self._feedback_cursor:self._feedback_cursor + required_delays])
                feedack_values = np.nanmean(values.reshape((required_requests, n_ponk)), axis=0)
                self._feedback_cursor += required_delays
                self._pending_feedback_requests -= required_requests
                self._feedback_counter = 0
                self.delayValues.emit(feedack_values)
                print("TO SEND", feedack_values)
                continue

            if available < n_ponk:
                return

            feedack_values = np.array(self._delays[self._feedback_cursor:self._feedback_cursor + n_ponk])
            self._feedback_cursor += n_ponk
            self._pending_feedback_requests -= 1

            send_feedback = True
            if feedback == 2:
                limits = s.delay_limit
                send_feedback = any(abs(value) > limit for value, limit in zip(feedack_values, limits))

            if send_feedback:
                self.delayValues.emit(feedack_values)
                print("TO SEND", feedack_values)

    
    # === signal parsing === 
    def _process_trigger(self, pack):

        ttl = np.array(pack[:, -1], dtype=np.uint8)
        bit = self.settings.detection_settings.bit
        trigger = ((ttl>>bit) & 0b1).astype(int)
            
        self.trigger.extend(trigger*1E-3)

        trigger_diff = np.diff(trigger)
        event = np.where(trigger_diff == 1)[0]      # 0 -> 1 
        if len(event) != 0:
            # print("EVENT SOUND", bit, event)
            idx =-(len(trigger) - event[0]-1)
            self.triggerIdx.emit(idx)
            self._trigger = self.ts[idx]       # для обработки поньков  [ms]
        
            
    def _queue_mep_triggers_from_pack(self, pack):
        ttl = np.array(pack[:, -1], dtype=np.uint8)
        bit = self.settings.detection_settings.bit
        trigger = ((ttl >> bit) & 0b1).astype(int)
        trigger_diff = np.diff(trigger)
        events = np.where(trigger_diff == 1)[0]

        for event in events:
            trigger_sample = self.timestamp - len(trigger) + int(event) + 1
            trigger_time = trigger_sample * self._coef
            self._pending_mep_triggers.append((trigger_sample, trigger_time))

    def _process_pending_mep_epochs(self, force=False):
        if not self._pending_mep_triggers:
            return

        processed = []
        first_sample = self.timestamp - len(self.mep_emg)
        emg = np.asarray(self.mep_emg, dtype=float)

        for trigger_sample, trigger_time in self._pending_mep_triggers:
            mep = self._try_extract_mep_epoch(trigger_sample, trigger_time, first_sample, emg, force=force)
            if mep is None:
                continue

            processed.append((trigger_sample, trigger_time))
            self.mepEpochReady.emit(mep)

            if self._mep_recording:
                self._mep_record_epochs.append(mep["epoch_mV"])
                self._mep_record_amps.append(mep["amplitude_mV"])
                self._mep_record_baselines.append(mep["baseline_mV"])
                self._mep_record_trigger_samples.append(trigger_sample)
                self._mep_record_trigger_times.append(trigger_time)

        if processed:
            processed_set = set(processed)
            self._pending_mep_triggers = [
                item for item in self._pending_mep_triggers
                if item not in processed_set
            ]

        if force:
            self._pending_mep_triggers = []

    def _try_extract_mep_epoch(self, trigger_sample, trigger_time, first_sample, emg, force=False):
        s = self.settings.mep_settings
        start_sample = trigger_sample + self._ms_to_sample(s.epoch_start_ms)
        end_sample = trigger_sample + self._ms_to_sample(s.epoch_end_ms)

        if self.timestamp <= end_sample and not force:
            return None
        if start_sample < first_sample:
            return None
        if end_sample > self.timestamp:
            return None

        start = int(start_sample - first_sample)
        end = int(end_sample - first_sample)
        epoch = np.asarray(emg[start:end], dtype=float)
        if epoch.size == 0:
            return None

        time_ms = (np.arange(epoch.size) + self._ms_to_sample(s.epoch_start_ms)) * self._coef
        baseline = self._calculate_mep_baseline(epoch, time_ms)
        if np.isfinite(baseline):
            epoch = epoch - baseline
        amplitude = self._calculate_mep_amplitude(epoch, time_ms)

        return {
            "epoch_mV": epoch,
            "time_ms": time_ms,
            "amplitude_mV": amplitude,
            "baseline_mV": baseline,
            "trigger_sample": int(trigger_sample),
            "trigger_time_ms": float(trigger_time),
        }

    def _calculate_mep_baseline(self, epoch, time_ms):
        s = self.settings.mep_settings
        mask = (time_ms >= s.baseline_start_ms) & (time_ms <= s.baseline_end_ms)
        if not np.any(mask):
            return np.nan
        data = epoch[mask]
        if data.size == 0 or not np.any(np.isfinite(data)):
            return np.nan
        return float(np.nanmean(data))

    def _calculate_mep_amplitude(self, epoch, time_ms):
        s = self.settings.mep_settings
        mask = (time_ms >= s.plot_start_ms) & (time_ms <= s.plot_end_ms)
        if not np.any(mask):
            return np.nan
        data = epoch[mask]
        if data.size == 0 or not np.any(np.isfinite(data)):
            return np.nan
        return float(np.nanmax(data) - np.nanmin(data))

    def _save_mep_recording(self):
        if not self._mep_hdf_path or len(self._mep_record_epochs) == 0:
            return self._mep_hdf_path

        path = self._mep_hdf_path
        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            return self._write_mep_hdf(path)
        except OSError:
            base, _ = os.path.splitext(path)
            fallback_path = f"{base}_mep.hdf5"
            return self._write_mep_hdf(fallback_path)

    def _write_mep_hdf(self, path):
        epochs = np.asarray(self._mep_record_epochs, dtype=np.float32)
        amps = np.asarray(self._mep_record_amps, dtype=np.float32)
        baselines = np.asarray(self._mep_record_baselines, dtype=np.float32)
        trigger_samples = np.asarray(self._mep_record_trigger_samples, dtype=np.int64)
        trigger_times = np.asarray(self._mep_record_trigger_times, dtype=np.float64)
        s = self.settings.mep_settings

        with h5py.File(path, "a") as hdf:
            if "mep" in hdf:
                del hdf["mep"]
            group = hdf.create_group("mep")
            group.create_dataset("epochs_mV", data=epochs)
            group.create_dataset("time_ms", data=self._mep_time_axis_for_record(), dtype=np.float32)
            group.create_dataset("amplitudes_mV", data=amps)
            group.create_dataset("baselines_mV", data=baselines)
            group.create_dataset("trigger_samples", data=trigger_samples)
            group.create_dataset("trigger_times_ms", data=trigger_times)
            group.attrs["Fs"] = self.settings.Fs
            group.attrs["epoch_start_ms"] = s.epoch_start_ms
            group.attrs["epoch_end_ms"] = s.epoch_end_ms
            group.attrs["baseline_start_ms"] = s.baseline_start_ms
            group.attrs["baseline_end_ms"] = s.baseline_end_ms
            group.attrs["plot_start_ms"] = s.plot_start_ms
            group.attrs["plot_end_ms"] = s.plot_end_ms
            group.attrs["amp_threshold_mV"] = s.amp_threshold_mv
            finite_amps = amps[np.isfinite(amps)]
            group.attrs["mean_amplitude_mV"] = float(np.mean(finite_amps)) if finite_amps.size else np.nan

        return path

    def _mep_time_axis_for_record(self):
        if len(self._mep_record_epochs) == 0:
            return np.asarray([], dtype=np.float32)
        s = self.settings.mep_settings
        n = len(self._mep_record_epochs[0])
        return (np.arange(n) + self._ms_to_sample(s.epoch_start_ms)) * self._coef

    def _process_new_pack(self, pack):
        s = self.settings.processing_settings

        # montage
        if s.montage == 1:  # monopolar
            emg = pack[:, s.emg_channels_monopolar].squeeze()
        else:   # bipolar
            emg = pack[:, s.emg_channels_bipolar] 
            emg = np.diff(emg, axis=1).squeeze()

        
        if s.do_notch:
            emg = self.apply_notch(emg)
        if s.do_lowpass or s.do_highpass:
            emg = self.apply_butter(emg)

        self._last_mep_emg = np.asarray(emg, dtype=float).copy()

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
