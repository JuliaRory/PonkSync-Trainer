from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QShortcut, QMessageBox
from PyQt5.QtCore import  pyqtSignal, Qt
from PyQt5.QtGui import QKeySequence

import json
import os
import numpy as np

from utils.ui_helpers import create_button, create_spin_box, create_check_box, create_combo_box, create_shortcut, create_lineedit
from utils.layout_utils import create_hbox, create_vbox

from .results_window import (
    ResultsWindow,
    calculate_error_statistics,
    format_error_statistics,
    prepare_results_df,
    save_error_distribution_plot,
)
from .video_player import StimuliPresentation_one_by_one

PLAY_LABEL = "▶"
STOP_LABEL = "⏸"

 # ▶  ⏸

class StimuliControlPanel(QFrame):
    """ --- UI для контроля за стимулами --- """

    stimuliPresentation = pyqtSignal(bool)      # -> stimuli presentation is on
    stimuliEnded = pyqtSignal()
    changeFile = pyqtSignal(str)
    recordingStarted = pyqtSignal(str)
    recordingFinished = pyqtSignal()

    def __init__(self, settings, resonance, output_stream=None, parent=None):
        super().__init__(parent)
        self.parent = parent
        # self.setObjectName("settings_panel")    # для привязки стиля
        self.setMinimumWidth(200)

        self.settings = settings.stimuli_settings
        self.resonance = resonance                      # для управления резонансными модулями
        self.output_stream = output_stream
        self._service = self.resonance.getService("nvx136")     # Берем сервис                     

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._finilize()

    def _init_state(self):
        self._restart_stimuli = False
        self._player_window = None
        self._results_windows = []
        self._current_results_csv_path = None

    # =======================
    # =====     UI      =====
    # =======================
    def _setup_ui(self):
        
        self._settings_panel = QFrame(self)
        
        self.line_edit_subject = create_lineedit(parent=self)
        self.line_edit_subject.setText(self.settings.subject)

        self.line_edit_filename = create_lineedit(parent=self)
        self.line_edit_filename.setText(self.settings.filename)
        self.button_stimuli = create_button(text='Открыть стимулы', disabled=False, parent=self, w=100)
        self.button_stimuli_pause = create_button(text=PLAY_LABEL, disabled=True, parent=self)
        self.button_stimuli_restart = create_button(text='start again', disabled=True, parent=self)
        self.button_show_results = create_button(text='show results', disabled=False, parent=self)
        self.label_results_stats = QLabel("Результаты: --", self)
        self.label_results_stats.setWordWrap(True)

        self.combo_box_stimuli = create_combo_box(self.settings.stimuli, curr_item_idx=self.settings.stimuli_curr, parent=self)
        self.combo_box_stimuli_type = create_combo_box(self.settings.stimuli_type, curr_item_idx=self.settings.stimuli_type_curr, parent=self)
        self.combo_box_fps = create_combo_box(self.settings.fps, curr_item_idx=self.settings.fps_curr, parent=self)
        saved_stimuli_names = self._load_saved_stimuli_names()
        if saved_stimuli_names and self.settings.saved_stimuli_curr not in saved_stimuli_names:
            self.settings.saved_stimuli_curr = saved_stimuli_names[0]
        self.combo_box_saved_stimuli = create_combo_box(saved_stimuli_names, curr_item=self.settings.saved_stimuli_curr, parent=self)
        self.check_box_stimuli_sequence_mode = create_check_box(self.settings.sequence_mode, 'Режим записи', parent=self)
        
        
        self.spin_box_stimuli_n = create_spin_box(0, 100, self.settings.stimuli_n, parent=self)
        self.check_box_stimuli_inf = create_check_box(self.settings.stimuli_inf, '∞', parent=self)
        self.spin_box_isi_min = create_spin_box(0, 60, self.settings.isi_min_s, data_type="float", decimals=1, step=0.1, parent=self, w=60)
        self.spin_box_isi_max = create_spin_box(0, 60, self.settings.isi_max_s, data_type="float", decimals=1, step=0.1, parent=self, w=60)

        self.spin_box_monitor = create_spin_box(1, 3, self.settings.monitor, parent=self)
        self.check_box_stimuli_record = create_check_box(self.settings.record, 'Запись NVX', parent=self)

        self.combo_box_feedback_mode = create_combo_box(self.settings.feedback_mode, curr_item_idx=self.settings.feedback_mode_curr, parent=self)
        self.combo_box_feedback_form = create_combo_box(self.settings.feedback_form, curr_item_idx=self.settings.feedback_form_curr, parent=self)
        self.spin_box_feedback_n = create_spin_box(0, 30, self.settings.feedback_n, parent=self)
        
        self.check_box_sham_feedback = create_check_box(self.settings.sham_feedback, 'sham', parent=self)
        
        delay_limit = self.settings.delay_limit
        self.spin_box_limit1 = create_spin_box(0, 1000, delay_limit[0], parent=self)
        self.spin_box_limit2 = create_spin_box(0, 1000, delay_limit[1], parent=self)
        self.spin_box_limit3 = create_spin_box(0, 1000, delay_limit[2], parent=self)

        self.label_stimuli_idx = QLabel("", self)
        self.label_stimuli_idx.setObjectName("label_stimulus_idx")

    # =======================
    # =====   LAYOUT    =====
    # =======================
    def _setup_layout(self):        
        
        layout_filename = create_hbox([QLabel("Subject:", self), self.line_edit_subject, QLabel("Record:", self), self.line_edit_filename])
        layout_start = create_hbox([self.button_stimuli, self.button_stimuli_pause, self.check_box_stimuli_record])
        layout_stimuli = create_hbox([self.combo_box_stimuli, QLabel("fps:"), self.combo_box_fps, self.button_stimuli_restart])
        layout_stimuli_type = create_hbox([QLabel("Тип стимулов:"), self.combo_box_stimuli_type])
        layout_saved_stimuli = create_hbox([self.check_box_stimuli_sequence_mode, self.combo_box_saved_stimuli])
        
        layout_number = create_hbox([QLabel("монитор", self), self.spin_box_monitor, QLabel("N:", self), self.spin_box_stimuli_n, QLabel("или", self), self.check_box_stimuli_inf])
        layout_isi = create_hbox([QLabel("ISI:", self), QLabel("min", self), self.spin_box_isi_min, QLabel("max", self), self.spin_box_isi_max, QLabel("s", self)])

        layout_feedback_mode = create_hbox([QLabel("Режим ОС", self), self.combo_box_feedback_mode])
        layout_feedback_form = create_hbox([QLabel("Форма ОС", self), self.combo_box_feedback_form])
        layout_feedback_n = create_hbox([QLabel("N эпох", self), self.spin_box_feedback_n])
        layout_delay_limit1 = create_hbox([QLabel("поньк #1:", self), self.spin_box_limit1, QLabel("мс", self)])
        layout_delay_limit2 = create_hbox([QLabel("поньк #2:", self), self.spin_box_limit2, QLabel("мс", self)])
        layout_delay_limit3 = create_hbox([QLabel("поньк #3:", self), self.spin_box_limit3, QLabel("мс", self)])
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.button_show_results)
        layout.addWidget(self.label_results_stats)
        layout.addLayout(layout_filename)
        layout.addLayout(layout_start)
        layout.addLayout(layout_stimuli)
        layout.addLayout(layout_stimuli_type)
        layout.addLayout(layout_saved_stimuli)
        layout.addLayout(layout_number)
        layout.addLayout(layout_isi)
        
        layout.addWidget(self.label_stimuli_idx)
        layout.addLayout(layout_feedback_mode)
        layout.addLayout(layout_feedback_form)
        layout.addWidget(self.check_box_sham_feedback)
        layout.addLayout(layout_feedback_n)
        layout.addLayout(layout_delay_limit1)
        layout.addLayout(layout_delay_limit2)
        layout.addLayout(layout_delay_limit3)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # =======================
    # =====   Сигналы    ====
    # =======================
    def _setup_connections(self):
        self.button_stimuli.clicked.connect(self._on_stimuli_button_click)                      # Открыть окно для показа стимулов
        self.button_stimuli_pause.clicked.connect(self._on_pause_stimuli_button_click)
        self.button_stimuli_restart.clicked.connect(self._on_restart_stimuli_presentation)
        self.button_show_results.clicked.connect(self._on_show_results)
        self.check_box_stimuli_sequence_mode.stateChanged.connect(self._update_recording_mode_widgets)
        self.line_edit_subject.textChanged.connect(self._update_results_stats)
        self.line_edit_filename.textChanged.connect(self._update_results_stats)

    
    def _update_connections(self):
        """установление связей после открытия окна с презентацией стимулов"""
        self._player_window.stimuliStarted.connect(self._on_start_stimuli)
        self._player_window.stimuliPaused.connect(self._change_button_pause_stimuli_text)
        self._player_window.stimuliFinished.connect(self._on_finish_stimuli)    

        self._player_window.currIdxChanged.connect(self._on_stimuli_idx_changed)
        self._player_window.stimulus.connect(self._on_stimuli_order_changed)

        self._player_window.volumeChanged.connect(self._on_player_volume_changed)
        self._player_window.playerIsMuted.connect(self._on_player_muted)

        self._player_window.stimuliEnded.connect(lambda: self.stimuliEnded.emit())

    # =======================
    # =====   Логика    =====
    # =======================

    def _load_saved_stimuli_names(self):
        try:
            with open(self.settings.saved_stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return list(data.keys())

    def _update_recording_mode_widgets(self):
        sequence_mode = self.check_box_stimuli_sequence_mode.isChecked()
        self.combo_box_saved_stimuli.setEnabled(sequence_mode)
        self.combo_box_stimuli.setEnabled(not sequence_mode)
        self.combo_box_stimuli_type.setEnabled(not sequence_mode)
        self.combo_box_fps.setEnabled(not sequence_mode)
        self.spin_box_stimuli_n.setEnabled(not sequence_mode)
        self.check_box_stimuli_inf.setEnabled(not sequence_mode)

    def _on_stimuli_button_click(self):
        # если стимул-презентейшн уже открыт -> хотим закрыть
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden() and not self._restart_stimuli:
            self.button_stimuli.setText("Открыть окно")               # опять можно начать презентацию
            self._player_window.finish()            # like Escape
                                         
        # если не открыт -> хотим начать презентацию и возможно запись nvx
        else:
            if not self._restart_stimuli:   # если первый запуск окна с показом стимулов -> создаём окно
                self._player_window = StimuliPresentation_one_by_one(self.settings)
                self._player_window.apply_sequence_settings()
                self._player_window.show()
                self._player_window.raise_()

                self._update_connections()      # устанавливаем связи с новым окном

            self.button_stimuli_pause.setEnabled(True)                  # кнопка пауза доступна
            self.button_stimuli_pause.setText(PLAY_LABEL)
            self.button_stimuli_restart.setEnabled(True)
            self.button_stimuli.setText("Закрыть окно")                 # меняем надпись на кнопке "старт"

            self._restart_stimuli = False                           
    
    # == NVX control ==
    
    
    def _start_nvx(self, filename):
        self._service.sendTransition('start', stream="eeg", filename=filename)
    
    def _stop_nvx(self):
        self._service.sendTransition('stop')

    def _stop_recording_if_needed(self):
        if self.check_box_stimuli_record.isChecked():
            self.stimuliPresentation.emit(False)
            self._stop_nvx()
            self.recordingFinished.emit()
        self.check_box_stimuli_record.setEnabled(True)

    # == show delay === 
    def show_delay(self, delay):
        values = np.atleast_1d(np.asarray(delay, dtype=float))
        if self.settings.sham_feedback:
            values = np.random.randint(-200, 201, size=values.shape).astype(float)
        print("--> show delay", values)
        self._player_window.show_feedback(values)

    # === изменения состояния кнопок === 
    def _change_button_pause_stimuli_text(self):
        status = PLAY_LABEL if self._player_window.is_paused else STOP_LABEL
        self.button_stimuli_pause.setText(status)

    def _on_pause_stimuli_button_click(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget):
            self._player_window.pause_video()
            self._change_button_pause_stimuli_text()
       
    def _on_restart_stimuli_presentation(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._stop_recording_if_needed()
            self._player_window.restart_sequence()
            self.button_stimuli_pause.setText(PLAY_LABEL)

    def _on_finish_stimuli(self):
        # запись nvx136
        self._stop_recording_if_needed()

        self.check_box_stimuli_record.setEnabled(True) # разрешить возможность поменять статус записи nvx

        self.label_stimuli_idx.setText(f"")
        self.button_stimuli_pause.setText(PLAY_LABEL)
        self.button_stimuli_restart.setEnabled(False)
        self._update_current_recording_stats()


    def _find_results_csv_path(self):
        subject = self.line_edit_subject.text().strip()
        record_name = self.line_edit_filename.text().strip()
        folder = os.path.abspath(os.path.join("data", subject))
        exact_path = os.path.join(folder, f"{record_name}.csv")

        if os.path.exists(exact_path):
            return exact_path

        if not os.path.isdir(folder):
            return None

        prefix = f"{record_name}-"
        matches = [
            os.path.join(folder, filename)
            for filename in os.listdir(folder)
            if filename.endswith(".csv") and (filename == f"{record_name}.csv" or filename.startswith(prefix))
        ]
        if not matches:
            return None
        return max(matches, key=os.path.getmtime)

    def _load_results_stats(self, csv_path=None):
        df = self._load_results_df(csv_path)
        if df is None:
            return None
        return calculate_error_statistics(df)

    def _load_results_df(self, csv_path=None):
        if csv_path is None:
            csv_path = self._find_results_csv_path()
        if csv_path is None or not os.path.exists(csv_path):
            return None

        try:
            import pandas as pd

            return prepare_results_df(pd.read_csv(csv_path))
        except Exception as exc:
            print(f"Could not load results from {csv_path}: {exc}")
            return None

    def _save_current_distribution_plot(self):
        csv_path = self._current_results_csv_path if self._current_results_csv_path else self._find_results_csv_path()
        df = self._load_results_df(csv_path)
        if df is None:
            return None

        output_dir = os.path.dirname(os.path.abspath(csv_path)) if csv_path else os.path.abspath("data")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "_error_distribution.png")
        try:
            acceptable_limit = abs(self.settings.delay_limit[0]) if self.settings.delay_limit else 200
            return save_error_distribution_plot(
                df,
                output_path,
                acceptable_limit=acceptable_limit,
                transparent=True,
            )
        except Exception as exc:
            print(f"Could not save error distribution plot: {exc}")
            return None

    def _update_results_stats(self):
        stats = self._load_results_stats()
        self.label_results_stats.setText(format_error_statistics(stats) if stats is not None else "Результаты: --")

    def _update_current_recording_stats(self):
        stats = self._load_results_stats(self._current_results_csv_path)
        self.label_results_stats.setText(format_error_statistics(stats) if stats is not None else "Результаты: --")

    def get_current_results_stats(self):
        stats = self._load_results_stats(self._current_results_csv_path)
        if stats is None:
            stats = self._load_results_stats()
        return stats

    def show_mean_error_on_player(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden() and pw.is_mean_error_visible():
            pw.hide_mean_error()
            return True

        stats = self.get_current_results_stats()
        if stats is None or stats.get("n", 0) <= 0 or not np.isfinite(stats.get("mean", np.nan)):
            self.label_results_stats.setText("Результаты: --")
            return False

        self.label_results_stats.setText(format_error_statistics(stats))
        if not isinstance(pw, QWidget) or pw.isHidden():
            return False
        pw.show_mean_error(stats["mean"], plot_path=self._save_current_distribution_plot())
        return True

    def _get_results_limits(self):
        if not self.settings.delay_limit:
            return None
        limit = abs(self.settings.delay_limit[0])
        return (-limit, limit)

    def _on_show_results(self):
        csv_path = self._find_results_csv_path()
        if csv_path is None:
            QMessageBox.warning(
                self,
                "Results Not Found",
                "Could not find the CSV results file for the selected subject and record name.",
            )
            return

        self._update_results_stats()

        results_window = ResultsWindow()
        self._results_windows.append(results_window)
        results_window.destroyed.connect(
            lambda _=None, window=results_window: self._results_windows.remove(window) if window in self._results_windows else None
        )

        results_window.show_results(
            csv_path=csv_path,
            subject=self.line_edit_subject.text().strip(),
            record_name=self.line_edit_filename.text().strip(),
            limits=self._get_results_limits(),
        )
        results_window.show()
        results_window.raise_()
        results_window.activateWindow()

    def _on_start_stimuli(self):
        folder = os.path.join(r"data", self.line_edit_subject.text())
        os.makedirs(folder, exist_ok=True)
        
        filename = self.line_edit_filename.text()

        # запись nvx136
        if self.check_box_stimuli_record.isChecked():
            self.stimuliPresentation.emit(True)
            filename_hdf = filename + ".hdf"
            full_path_hdf = os.path.join(folder, filename_hdf)
            
            if os.path.exists(full_path_hdf):
                full_path_hdf = full_path_hdf[:-4] +"-$$$.hdf5"
            full_path_hdf = os.path.abspath(full_path_hdf)
            self.recordingStarted.emit(full_path_hdf)
            self._start_nvx(full_path_hdf)

        filename_csv = filename + ".csv"
        full_path_csv = os.path.join(folder, filename_csv)
        if os.path.exists(full_path_csv):
            full_path_csv = full_path_csv[:-4] +"-$$$.csv"
        self._current_results_csv_path = full_path_csv
        self.changeFile.emit(full_path_csv) # start csv file -> data processor
        # self.check_box_stimuli_record.setDisabled(True) # сделать недоступной возможность поменять статус записи nvx

        self.button_stimuli_pause.setText(STOP_LABEL)
    
    # === отметки о текущем стимуле === 
    def _on_stimuli_idx_changed(self, idx):
        self.label_stimuli_idx.setText(f"#{idx}")

    def _on_stimuli_order_changed(self, filename):
        message = {"stimulus": filename}
        print(message)
        if self.output_stream is not None:
            self.output_stream(json.dumps(message))

    
    # === изменения звука === 
    def _on_player_volume_changed(self, value):
        """изменения от горячих клавиш стрелок вверх-вниз"""
        self.stimuli_volume_slider.slider.setValue(value)
    
    def _on_player_muted(self):
        cur_volume = self.stimuli_volume_slider.slider.value()
        volume = self._player_window.get_last_volume() if cur_volume == 0 else 0
        self.stimuli_volume_slider.slider.setValue(volume)

    def _on_change_stimuli_volume(self, value):
        """изменения от положения слайдера"""
        # если открыто окно со стимулами, поменять там громкость !!! не работает :( !!!
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._player_window.update_volume(value)
    
    def _on_change_noise_volume(self, value):
        """изменения от положения слайдера"""
        # если открыто окно со стимулами, поменять там громкость !!! не работает :( !!!
        self._audio_player.set_volume(value)
    
    # -- for
    def _up_noise_volume(self):
        new_value = min(100, self._audio_player.volume + 5)
        self.noise_volume_slider.setValue(new_value)
        self._on_change_noise_volume(new_value)
    
    def _down_noise_volume(self):
        new_value = max(0, self._audio_player.volume - 5)
        self.noise_volume_slider.setValue(new_value)
        self._on_change_noise_volume(new_value)
    
    def _up_stimuli_volume(self):
        new_value = min(100, self._player_window.get_last_volume() + 5)
        self.stimuli_volume_slider.setValue(new_value)
        self._on_change_stimuli_volume(new_value)
    
    def _down_stimuli_volume(self):
        new_value = max(0, self._player_window.get_last_volume() - 5)
        self.stimuli_volume_slider.setValue(new_value)
        self._on_change_stimuli_volume(new_value)


    # === получение последовательности стимулов === 
    def _get_sequence(self, seq_name):
        if not seq_name:
                return
        try:
            with open(self.settings.stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        return data.get(seq_name)

    def _update_combo_box_stimuli(self):
        self.combo_box_stimuli.clear()
        try:
            with open(self.settings.stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.combo_box_stimuli.addItems(data.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            print("файл пока пустой")
        
    def _finilize(self):
        # self._update_combo_box_stimuli()
        self._update_recording_mode_widgets()
        self._update_results_stats()
        print('that is it')
    

    # === events ===

    # def keyPressEvent(self, event):
    #     if event.key() == Qt.Key_Up+Qt.Key_N:                  # -- volume up
    #         new_value = min(100, self._audio_player.volume + 5)
    #         self._on_change_noise_volume(new_value)   
        
    #     # elif event.key() == Qt.Key_Down:                # -- volume down
    #     #     new_value = max(0, self._volume - 1)
    #     #     self.update_volume(new_value)

    #     # elif event.key() == Qt.Key_M:                   # -- mute
    #     #     self._player.audio_toggle_mute()
    #     #     self.playerIsMuted.emit()

    #     else:
    #         super().keyPressEvent(event)
