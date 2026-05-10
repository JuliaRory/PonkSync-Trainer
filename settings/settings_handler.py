
from dataclasses import fields, is_dataclass
import json
import os
from dataclasses import asdict

from PyQt5.QtCore import QSignalBlocker
from PyQt5.QtWidgets import QWidget
from numpy import sqrt

class SettingsHandler:
    """
    «Связующее звено» между UI и логикой processing:
    -- Слушает изменения в UI.
    -- Обновляет соответствующие поля в Settings.
    -- Вызывает методы DataProcessor, PlotUpdater или других классов, чтобы применить новые настройки

    Args:
        settings(Settings): 
        data_processor(DataProcessor):
        plot_updater(PlotUpdater):
        ui(QWidget):

    """
    def __init__(self, settings, data_processor, plot_updater, ui):
        self.data_processor = data_processor
        self.settings = settings
        self.plot_updater = plot_updater
        self.ui = ui

        self._init_state()
        self._setup_connections()
    
    def _init_state(self):
        self._filter_panel = self.ui._filter_panel
        self._scale_panel = self.ui._scale_panel
        self._peak_panel = self.ui._peak_panel
        self._graph = self.ui._figure_panel
        self._stimuli_panel = self.ui._stimuli_panel

        self._setup_units()
        self._update_thr()


    def _setup_connections(self):
        self._scale_panel.spin_box_scale.valueChanged[int].connect(self._update_scale)
        self._scale_panel.spin_box_max_value.valueChanged[int].connect(self._update_ymax)
        self._scale_panel.spin_box_min_value.valueChanged[int].connect(self._update_ymin)
        self._scale_panel.spin_box_scale_offset.valueChanged[int].connect(self._update_offset)
        self._scale_panel.spin_box_time_range.valueChanged[int].connect(self._update_timerange)
        self._scale_panel.combobox_signal_type.currentIndexChanged[int].connect(self._update_tkeo)
        self._scale_panel.combobox_montage.currentIndexChanged[int].connect(self._update_montage)
        self._scale_panel.spin_box_monopolar.valueChanged[int].connect(self._update_monopolar_montage)
        self._scale_panel.spin_box_bipolar_1.valueChanged[int].connect(self._update_bipolar_1_montage)
        self._scale_panel.spin_box_bipolar_2.valueChanged[int].connect(self._update_bipolar_2_montage)

        self._filter_panel.spin_box_lower_freq.valueChanged[int].connect(self._update_low_freq)
        self._filter_panel.spin_box_upper_freq.valueChanged[int].connect(self._update_high_freq)
        self._filter_panel.check_box_notch.stateChanged.connect(self._update_notch)
        self._filter_panel.check_box_lowpass.stateChanged.connect(self._update_lowpass)
        self._filter_panel.check_box_highpass.stateChanged.connect(self._update_highpass)

        self._peak_panel.spin_box_threshold_curr.valueChanged[float].connect(self._update_threshold)
        self._peak_panel.spin_box_threshold_mv.valueChanged[float].connect(self._update_threshold_mv)
        self._peak_panel.spin_box_bit.valueChanged[int].connect(self._update_bit)


        self._stimuli_panel.combo_box_stimuli.currentIndexChanged[int].connect(self._update_stimuli)
        self._stimuli_panel.combo_box_settings_preset.currentTextChanged.connect(self._apply_settings_preset)
        self._stimuli_panel.combo_box_stimuli_type.currentIndexChanged[int].connect(self._update_stimuli_type)
        self._stimuli_panel.combo_box_fps.currentIndexChanged[int].connect(self._update_fps)
        
        self._stimuli_panel.spin_box_stimuli_n.valueChanged[int].connect(self._update_stimuli_n)
        self._stimuli_panel.check_box_stimuli_inf.stateChanged.connect(self._update_stimuli_inf)
        self._stimuli_panel.spin_box_isi_min.valueChanged[float].connect(self._update_isi_min)
        self._stimuli_panel.spin_box_isi_max.valueChanged[float].connect(self._update_isi_max)
        self._stimuli_panel.check_box_stimuli_sequence_mode.stateChanged.connect(self._update_sequence_mode)
        self._stimuli_panel.combo_box_saved_stimuli.currentTextChanged.connect(self._update_saved_stimuli)
        self._stimuli_panel.spin_box_monitor.valueChanged[int].connect(self._update_monitor)
        self._stimuli_panel.check_box_stimuli_record.stateChanged.connect(self._update_record_status)
        self._stimuli_panel.combo_box_feedback_mode.currentIndexChanged[int].connect(self._update_feedback_mode)
        self._stimuli_panel.combo_box_feedback_form.currentIndexChanged[int].connect(self._update_feedback_form)
        self._stimuli_panel.spin_box_feedback_n.valueChanged[int].connect(self._update_feedback_n)
        self._stimuli_panel.check_box_sham_feedback.stateChanged.connect(self._update_sham_feedback)
        self._stimuli_panel.spin_box_limit1.valueChanged[int].connect(self._update_limit1)
        self._stimuli_panel.spin_box_limit2.valueChanged[int].connect(self._update_limit2)
        self._stimuli_panel.spin_box_limit3.valueChanged[int].connect(self._update_limit3)
        self._stimuli_panel.line_edit_subject.textChanged.connect(self._update_subject)
        self._stimuli_panel.line_edit_filename.textChanged.connect(self._update_filename)


    # === plot settings === 
    # == montage ==
    def _update_montage(self, idx):
        self.settings.processing_settings.montage = idx
    
    def _update_monopolar_montage(self, channel):
        self.settings.processing_settings.emg_channels_monopolar = channel
    
    def _update_bipolar_1_montage(self, channel):
        self.settings.processing_settings.emg_channels_bipolar[0] = channel
    
    def _update_bipolar_2_montage(self, channel):
        self.settings.processing_settings.emg_channels_bipolar[1] = channel

    def _update_threshold(self, thr):
        print("tkeo", thr)
        self.settings.detection_settings.threshold = thr
        # -> mv
        # mv = sqrt(thr) / 1E3
        # self._peak_panel.spin_box_threshold_mv.setValue(mv)
        # self.settings.detection_settings.threshold_mv = mv
        self._update_thr()

    def _update_bit(self, bit):
        self.settings.detection_settings.bit = bit

    def _update_threshold_mv(self, thr):
        print("mv", thr)
        self.settings.detection_settings.threshold_mv = thr
        # -> tkeo units
        # tkeo_thr = (thr ** 2) * ((1/1000) ** 2) 
        # scale = 10 ** (self.settings.plot_settings.scale_factor)
        # coef = tkeo_thr / scale
        # self._peak_panel.spin_box_threshold_curr.setValue(int(coef))
        # self.settings.detection_settings.threshold = int(coef)
        self._update_thr()
    
    def _update_thr(self):
        thr = self.settings.detection_settings.threshold * (10 ** (self.settings.plot_settings.scale_factor))
        print(thr)
        self.plot_updater.change_thr_line(thr)

    def _update_scale(self, scale):
        self.settings.plot_settings.scale_factor = scale

        self._graph.update_yrange()
        self._setup_units()
        self._update_thr()
    
    def _update_ymax(self, value):
        self.settings.plot_settings.ymax = value
        self._graph.update_yrange()
    
    def _update_ymin(self, value):
        self.settings.plot_settings.ymin = value
        self._graph.update_yrange()
    
    def _update_offset(self, value):
        self.settings.plot_settings.scale_offset = value
        print("DOES NOT WORK YET")
    
    def _update_timerange(self, value):
        self.settings.plot_settings.time_range_ms = value * 1000
        print("DOES NOT WORK YET")

    def _setup_units(self):
        factor = self.settings.plot_settings.scale_factor
        text = f"<span style='font-size: 14pt;'>&times; 10<sup>{factor}</sup></span>"
        self._peak_panel.label_units.setText(text)
    
    def _update_tkeo(self, index):
        status = True if index == 1 else False
        self.settings.processing_settings.tkeo = status

    # === stimuli settings === 
    def _apply_settings_preset(self, preset_name):
        if not preset_name:
            return

        filename = self.settings.stimuli_settings.settings_presets_filename
        try:
            with open(filename, "r", encoding="utf-8") as f:
                presets = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"Could not load settings presets from {filename}: {exc}")
            return

        preset = presets.get(preset_name)
        if not isinstance(preset, dict):
            print(f"Settings preset '{preset_name}' is missing or is not an object.")
            return

        has_filename = self._preset_has_key(preset, "filename")
        self._apply_settings_dict(self.settings, preset)
        if not has_filename:
            self.settings.stimuli_settings.filename = self._build_record_name_for_preset(preset_name)
        self._sync_ui_from_settings()
        self._refresh_runtime_after_preset()

    def _preset_has_key(self, preset, key):
        if key in preset:
            return True
        return any(isinstance(value, dict) and key in value for value in preset.values())

    def _build_record_name_for_preset(self, preset_name):
        s = self.settings.stimuli_settings
        subject = s.subject.strip() or "subject"
        suffix = self._record_suffix_from_preset(preset_name, s)
        number = self._next_record_number(subject)
        return f"{number:02d}_{subject}_{suffix}"

    def _record_suffix_from_preset(self, preset_name, stimuli_settings):
        name = preset_name.lower()
        if "error feedback" in name:
            return "efb"
        if "no feedback" in name:
            return "nofb_test"
        if "feedback" in name:
            return "fb"
        if "tms" in name:
            sequence = getattr(stimuli_settings, "saved_stimuli_curr", "")
            if sequence:
                tail = sequence.rsplit("_", 1)[-1]
                return f"tms_{tail}"
            return name.replace(" ", "_")
        return "_".join(name.split())

    def _next_record_number(self, subject):
        folder = os.path.join("data", subject)
        if not os.path.isdir(folder):
            return 1

        numbers = []
        for filename in os.listdir(folder):
            prefix = filename.split("_", 1)[0]
            if prefix.isdigit():
                numbers.append(int(prefix))
        return max(numbers, default=0) + 1

    def _apply_settings_dict(self, target, values):
        if not isinstance(values, dict):
            return

        dataclass_fields = {field.name for field in fields(target)} if is_dataclass(target) else set()

        for key, value in values.items():
            if key in dataclass_fields:
                current_value = getattr(target, key)
                if is_dataclass(current_value) and isinstance(value, dict):
                    self._apply_settings_dict(current_value, value)
                else:
                    setattr(target, key, value)
                continue

            nested_target = self._find_nested_settings(target, key)
            if nested_target is not None:
                setattr(nested_target, key, value)
            else:
                print(f"Unknown setting in preset: {key}")

    def _find_nested_settings(self, target, key):
        if not is_dataclass(target):
            return None

        for field in fields(target):
            value = getattr(target, field.name)
            if is_dataclass(value) and hasattr(value, key):
                return value
        return None

    def _sync_ui_from_settings(self):
        self._sync_scale_ui_from_settings()
        self._sync_filter_ui_from_settings()
        self._sync_peak_ui_from_settings()
        self._sync_stimuli_ui_from_settings()

    def _set_widget_value(self, widget, value):
        blocker = QSignalBlocker(widget)
        if hasattr(widget, "setChecked"):
            widget.setChecked(bool(value))
        elif hasattr(widget, "setCurrentIndex") and isinstance(value, int):
            widget.setCurrentIndex(value)
        elif hasattr(widget, "setCurrentText"):
            widget.setCurrentText(str(value))
        elif hasattr(widget, "setValue"):
            widget.setValue(value)
        elif hasattr(widget, "setText"):
            widget.setText(str(value))
        del blocker

    def _sync_scale_ui_from_settings(self):
        plot = self.settings.plot_settings
        processing = self.settings.processing_settings
        widget_values = [
            (self._scale_panel.spin_box_scale, plot.scale_factor),
            (self._scale_panel.spin_box_max_value, plot.ymax),
            (self._scale_panel.spin_box_min_value, plot.ymin),
            (self._scale_panel.spin_box_scale_offset, plot.scale_offset),
            (self._scale_panel.spin_box_time_range, int(plot.time_range_ms // 1000)),
            (self._scale_panel.combobox_signal_type, 1 if processing.tkeo else 0),
            (self._scale_panel.combobox_montage, processing.montage),
            (self._scale_panel.spin_box_monopolar, processing.emg_channels_monopolar),
            (self._scale_panel.spin_box_bipolar_1, processing.emg_channels_bipolar[0]),
            (self._scale_panel.spin_box_bipolar_2, processing.emg_channels_bipolar[1]),
        ]
        for widget, value in widget_values:
            self._set_widget_value(widget, value)

    def _sync_filter_ui_from_settings(self):
        s = self.settings.processing_settings
        widget_values = [
            (self._filter_panel.check_box_notch, s.do_notch),
            (self._filter_panel.check_box_lowpass, s.do_lowpass),
            (self._filter_panel.check_box_highpass, s.do_highpass),
            (self._filter_panel.spin_box_lower_freq, s.freq_low),
            (self._filter_panel.spin_box_upper_freq, s.freq_high),
        ]
        for widget, value in widget_values:
            self._set_widget_value(widget, value)

    def _sync_peak_ui_from_settings(self):
        s = self.settings.detection_settings
        window_ms = list(s.window_ms) if s.window_ms else [0, 0]
        while len(window_ms) < 2:
            window_ms.append(0)
        widget_values = [
            (self._peak_panel.spin_box_window_from, window_ms[0]),
            (self._peak_panel.spin_box_window_until, window_ms[1]),
            (self._peak_panel.spin_box_threshold_mv, s.threshold_mv),
            (self._peak_panel.spin_box_threshold_curr, s.threshold),
            (self._peak_panel.spin_box_bit, s.bit),
        ]
        for widget, value in widget_values:
            self._set_widget_value(widget, value)

    def _sync_stimuli_ui_from_settings(self):
        s = self.settings.stimuli_settings
        widget_values = [
            (self._stimuli_panel.combo_box_stimuli, s.stimuli_curr),
            (self._stimuli_panel.combo_box_stimuli_type, s.stimuli_type_curr),
            (self._stimuli_panel.combo_box_fps, s.fps_curr),
            (self._stimuli_panel.combo_box_saved_stimuli, s.saved_stimuli_curr),
            (self._stimuli_panel.combo_box_feedback_mode, s.feedback_mode_curr),
            (self._stimuli_panel.combo_box_feedback_form, s.feedback_form_curr),
            (self._stimuli_panel.spin_box_stimuli_n, s.stimuli_n),
            (self._stimuli_panel.check_box_stimuli_inf, s.stimuli_inf),
            (self._stimuli_panel.spin_box_isi_min, s.isi_min_s),
            (self._stimuli_panel.spin_box_isi_max, s.isi_max_s),
            (self._stimuli_panel.check_box_stimuli_sequence_mode, s.sequence_mode),
            (self._stimuli_panel.spin_box_monitor, s.monitor),
            (self._stimuli_panel.check_box_stimuli_record, s.record),
            (self._stimuli_panel.spin_box_feedback_n, s.feedback_n),
            (self._stimuli_panel.check_box_sham_feedback, s.sham_feedback),
            (self._stimuli_panel.line_edit_subject, s.subject),
            (self._stimuli_panel.line_edit_filename, s.filename),
        ]

        for widget, value in widget_values:
            self._set_widget_value(widget, value)

        delay_limit = list(s.delay_limit) if s.delay_limit else [0, 0, 0]
        while len(delay_limit) < 3:
            delay_limit.append(0)
        for spin_box, value in [
            (self._stimuli_panel.spin_box_limit1, delay_limit[0]),
            (self._stimuli_panel.spin_box_limit2, delay_limit[1]),
            (self._stimuli_panel.spin_box_limit3, delay_limit[2]),
        ]:
            self._set_widget_value(spin_box, value)

        self._stimuli_panel._update_recording_mode_widgets()
        self._stimuli_panel._update_results_stats()

    def _refresh_runtime_after_preset(self):
        self.data_processor.create_butter()
        self.data_processor.create_notch()
        self._graph.update_yrange()
        self._setup_units()
        self._update_thr()
        self._refresh_player_sequence()

        pw = getattr(self.ui._stimuli_panel, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            pw.set_monitor()
            pw.set_video_path()
            pw.change_stimuli()

    def _update_subject(self, subject):
        self.settings.stimuli_settings.subject = subject
        self._save_last_subject(subject)

    def _save_last_subject(self, subject):
        subject = subject.strip()
        if not subject:
            return

        filename = self.settings.stimuli_settings.last_subject_filename
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({"subject": subject}, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            print(f"Could not save last subject to {filename}: {exc}")

    def _update_filename(self, filename):
        self.settings.stimuli_settings.filename = filename

    def _update_stimuli(self, index):
        self.settings.stimuli_settings.stimuli_curr = index
        pw = getattr(self.ui._stimuli_panel, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self.ui._stimuli_panel._player_window.set_video_path()
            self.ui._stimuli_panel._player_window.change_stimuli()
    
    def _update_stimuli_type(self, index):
        self.settings.stimuli_settings.stimuli_type_curr = index
        pw = getattr(self.ui._stimuli_panel, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self.ui._stimuli_panel._player_window.set_video_path()
            self.ui._stimuli_panel._player_window.change_stimuli()

    def _update_fps(self, index):
        self.settings.stimuli_settings.fps_curr = index
        pw = getattr(self.ui._stimuli_panel, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self.ui._stimuli_panel._player_window.set_video_path()
            self.ui._stimuli_panel._player_window.change_stimuli()
    
    def _update_stimuli_n(self, n): # DOES NOT INPLEMENTED AT ALL
        self.settings.stimuli_settings.stimuli_n = n
        pw = getattr(self.ui._stimuli_panel, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self.ui._stimuli_panel._player_window.apply_sequence_settings()
    
    def _update_stimuli_inf(self, status):
        self.settings.stimuli_settings.stimuli_inf = bool(status)
        pw = getattr(self.ui._stimuli_panel, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self.ui._stimuli_panel._player_window.apply_sequence_settings()

    def _update_isi_min(self, value):
        self.settings.stimuli_settings.isi_min_s = float(value)

    def _update_isi_max(self, value):
        self.settings.stimuli_settings.isi_max_s = float(value)

    def _update_sequence_mode(self, status):
        self.settings.stimuli_settings.sequence_mode = bool(status)
        self._refresh_player_sequence()

    def _update_saved_stimuli(self, sequence_name):
        self.settings.stimuli_settings.saved_stimuli_curr = sequence_name
        self._refresh_player_sequence()

    def _refresh_player_sequence(self):
        pw = getattr(self.ui._stimuli_panel, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self.ui._stimuli_panel._player_window.apply_sequence_settings()
            self.ui._stimuli_panel._player_window.set_video_path()
    
    def _update_monitor(self, n):
        self.settings.stimuli_settings.monitor = n
        pw = getattr(self.ui._stimuli_panel, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self.ui._stimuli_panel._player_window.set_monitor()
        
    def _update_record_status(self, status): # DOESNOT INPLEMENTED AT ALL
        self.settings.stimuli_settings.record = status
        # --> signal to change record status DOESNOT INPLEMENTED AT ALL

    def _update_feedback_mode(self, index):
        self.settings.stimuli_settings.feedback_mode_curr = index
        # --> signal to change feedback mode in video_player

    def _update_feedback_form(self, index):
        self.settings.stimuli_settings.feedback_form_curr = index
    
    def _update_feedback_n(self, n):
        self.settings.stimuli_settings.feedback_n = n

    def _update_sham_feedback(self, status):
        self.settings.stimuli_settings.sham_feedback = bool(status)
    
    def _update_limit1(self, value):
        self.settings.stimuli_settings.delay_limit[0] = value
    
    def _update_limit2(self, value):
        self.settings.stimuli_settings.delay_limit[1] = value
    
    def _update_limit3(self, value):
        self.settings.stimuli_settings.delay_limit[2] = value

    # === filter settings === 
    def _update_low_freq(self, value):
        self.settings.processing_settings.freq_low = value
        self.data_processor.create_butter()
    
    def _update_high_freq(self, value):
        self.settings.processing_settings.freq_high = value
        self.data_processor.create_butter()
    
    def _update_notch(self, status):
        self.settings.processing_settings.do_notch = status
        self.data_processor.create_notch()
    
    def _update_lowpass(self, status):
        self.settings.processing_settings.do_lowpass = status
        self.data_processor.create_butter()
    
    def _update_highpass(self, status):
        self.settings.processing_settings.do_highpass = status
        self.data_processor.create_butter()
