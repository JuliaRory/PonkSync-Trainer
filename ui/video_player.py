import sys, os

import vlc
import time
import numpy as np
import json

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QStackedWidget
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap

from ui.feedback_graph import FeedbackGraph
from ui.feedback_bar import FeedbackBar
import logging

# воспроизведение стимулов идёт через VLC плеер (https://www.videolan.org/vlc/) <-- он должен быть установлен на компьютер (!!!) 
# на питоне для этого устанавливается библиотека python-vlc (https://pypi.org/project/python-vlc/)
# его необходимо привязать к системному окну открываемого QWidget
# ┌─────────────────────────────────────────────┐
# │ StimuliPresentation : QWidget (fullscreen)  │
# │┌───────────────────────────────────────────┐│
# ││       VLC выводит сюда картинку           ││
# │└───────────────────────────────────────────┘│
# └─────────────────────────────────────────────┘
# сигнал об окончании видео и переключении на новое реализован через pyqtSignal(), чтобы вписывать событие в общий поток GUI:
#  ┌──────────────┐              ┌──────────────┐
#  │ VLC thread   │ --emit-->    │ Qt event loop│
#  │ end reached  │              │ (GUI thread) │
#  └──────────────┘              └──────────────┘
#                                   |
#                                   ↓
#                         _play_next_video()
# 
# закрытие окна (и остановка видео) происходит при нажатии на кнопку Escape или по окончании последовательности стимулов
# окончание последовательности стимулов вызывает сигнал stimuliFinished

class StimuliPresentation_one_by_one(QWidget):
    stimuliStarted = pyqtSignal()
    stimuliFinished = pyqtSignal()
    stimuliPaused = pyqtSignal()
    volumeChanged = pyqtSignal(int)
    playerIsMuted = pyqtSignal()
    currIdxChanged = pyqtSignal(int)
    _videoEnded = pyqtSignal(int, int)
    _mediaPlaying = pyqtSignal(int, int)
    stimuliEnded = pyqtSignal()       # --> stimuli_control_panel --> main_window --> data_processor

    stimulus = pyqtSignal(str)
    BAR_FEEDBACK_MS = 2000
    FEEDBACK_WAIT_MS = 400
    VIDEO_READY_HIDE_MS = 300
    LAST_FRAME_CAPTURE_MS = 300
    LAST_FRAME_POLL_MS = 40
    MARKER_STIMULUS = "audio_countdown_3.mkv"
    
    def __init__(self, settings=None):
        super().__init__()  

        # self.logger = logging.getLogger(__name__)
        self._volume = settings.volume
        self.settings = settings 
        self.show_delay = False
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._feedback_trial_id = None
        self._feedback_rendering_trial_id = None
        self._marker_visible_during_current_video = False
        self._video_playback_active = False
        self._last_frame_ready = False
        self._last_frame_pixmap = QPixmap()
        self._awaiting_first_frame = False
        self._last_frame_path = os.path.abspath(os.path.join("data", "_stimulus_last_frame.png"))

        self._init_state()
    
    # ==================================
    # === предварительная подготовка ===
    # ==================================
    def _init_state(self):
        self._stopped = False               # остановлен через esc и сейчас закроется
        self._finished = False               # остановлен т.к. закончилась последовательность
        self._sequence_started = False      # последовательность началась
        self._is_paused = False             # и не на паузе

        self._counter = 0
        self._run_id = 0
        self._active_trial_id = 0
        self._saved_sequence_order = []
        self._saved_sequence_set = {}
        self._saved_sequence_cross_filename = None
        self._saved_sequence_cross_ms = None
        self._showing_final_image = False
        self._final_image_path = None
        self._marker_visible_during_current_video = False
        self._video_playback_active = False
        self.n = None
        self.apply_sequence_settings()
        self._awaiting_first_frame = False
        self._apply_cross_settings()
        
        # final_fig_files = os.listdir(r"resources\final_fig")
        # self.final_pic_path = os.path.join(r"resources\final_fig", random.choice(final_fig_files))

        self.set_monitor()
        self._configure_player()
    
    def set_monitor(self):
        # Настройка экрана
        screens = QApplication.instance().screens()
        if not screens:
            raise RuntimeError("No Qt screens are available for stimuli presentation.")
        monitor_index = min(max(self.settings.monitor - 1, 0), len(screens) - 1)
        target_monitor = screens[monitor_index].geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()

    def _sequence_mode_enabled(self):
        return bool(getattr(self.settings, "sequence_mode", False))

    def _load_saved_sequence(self):
        filename = getattr(self.settings, "saved_stimuli_filename", r"resources/saved_stimuli.json")
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        sequence_name = getattr(self.settings, "saved_stimuli_curr", "")
        if sequence_name not in data:
            if not data:
                raise ValueError("No saved stimulus sequences were found.")
            sequence_name = next(iter(data))
            self.settings.saved_stimuli_curr = sequence_name

        sequence = data[sequence_name]
        self._saved_sequence_set = {str(k): v for k, v in sequence.get("set", {}).items()}
        self._saved_sequence_order = [str(item) for item in sequence.get("order", [])]

        cross = sequence.get("cross", {})
        self._saved_sequence_cross_filename = cross.get("filename", self.settings.cross_figure)
        self._saved_sequence_cross_ms = int(cross.get("dur_ms", self.settings.cross_ms))

    def _current_cross_filename(self):
        if self._sequence_mode_enabled() and self._saved_sequence_cross_filename:
            return self._saved_sequence_cross_filename
        return self.settings.cross_figure

    def _current_cross_duration_ms(self):
        return self._next_cross_duration_ms()

    def _next_cross_duration_ms(self):
        min_s = float(getattr(self.settings, "isi_min_s", self.settings.cross_ms / 1000))
        max_s = float(getattr(self.settings, "isi_max_s", min_s))
        if max_s < min_s:
            min_s, max_s = max_s, min_s
        if np.isclose(min_s, max_s):
            return int(round(min_s * 1000))
        isi = int(round(np.random.uniform(min_s, max_s) * 1000))
        print("ISI: ", isi)
        return isi

    def _apply_cross_settings(self):
        self._showing_final_image = False
        self._cross_figure_path = os.path.join(r"resources\stimuli", self._current_cross_filename())
        self._cross_dur_ms = self._current_cross_duration_ms()

        if "_cross_label" not in self.__dict__:
            return

        self._main_cross_pic = QPixmap(self._cross_figure_path).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._cross_label.setPixmap(self._main_cross_pic)
        self._cross_label.setGeometry(self.rect())

        if "_video_placeholder" in self.__dict__:
            self._video_placeholder.setPixmap(self._main_cross_pic)
            self._video_placeholder.setGeometry(self.rect())

    def _set_media_from_filename(self, filename):
        if not filename:
            raise ValueError("Empty stimulus video filename.")

        self._video_path = os.path.join(r"resources\stimuli", filename)
        if not os.path.exists(self._video_path):
            raise FileNotFoundError(f"Stimulus video not found: {self._video_path}")

        self._current_stimulus_filename = filename
        self.media = self._instance.media_new(self._video_path)
        self._player.set_media(self.media)
        self.media.parse_async()

    def _set_sequence_video_path(self, sequence_index):
        if not self._saved_sequence_order:
            self._load_saved_sequence()

        key = self._saved_sequence_order[sequence_index]
        filename = self._saved_sequence_set.get(key)
        if filename is None:
            raise ValueError(f"Stimulus code {key!r} is not present in saved sequence set.")
        self._set_media_from_filename(filename)

    def set_video_path(self):
        if self._sequence_mode_enabled():
            if not self._saved_sequence_order:
                self._load_saved_sequence()
            if self._saved_sequence_order:
                sequence_index = min(self._counter, len(self._saved_sequence_order) - 1)
                self._set_sequence_video_path(sequence_index)
            self._apply_cross_settings()
            return

        stimuli = self.settings.stimuli_curr
        stimuli_type = self.settings.stimuli_type_curr
        fps = self.settings.fps_curr

        # Загружаем данные
        with open(r'resources/stimuli_path.json', 'r') as f:
            data = json.load(f)

        def get_selected_path(data, combo1_value, combo2_value, combo3_value=None):
            key = {
                "Одиночные": "single",
                "Одиночные SST": "single_SST",
                "Триплеты": "triplets",
                "Триплеты SST": "triplets_SST",
                "Круг": "circle",
                "Вертикальный бар": "vbar",
                "Горизонтальный бар": "bar",
            }
            if combo1_value not in key:
                raise ValueError(f"Unknown stimuli mode: {combo1_value!r}")
            if combo2_value not in key:
                raise ValueError(f"Unknown stimuli type: {combo2_value!r}")
            combo1_value = key[combo1_value]
            combo2_value = key[combo2_value]
            if combo1_value == "single":
                try:
                    return data["single"][combo2_value][combo3_value]
                except KeyError as exc:
                    raise ValueError(
                        f"No single stimulus video for type={combo2_value!r}, fps={combo3_value!r}"
                    ) from exc
            elif combo1_value == "single_SST":
                return getattr(self.settings, "SST_video", None)
            elif combo1_value == "triplets":
                return data.get("triplets", {}).get(combo2_value) or getattr(self.settings, "triplet_video", None)
            elif combo1_value == "triplets_SST":
                return getattr(self.settings, "SRT_video", None)
            return None

        path = get_selected_path(data, 
                                 self.settings.stimuli[stimuli],
                                 self.settings.stimuli_type[stimuli_type],
                                 self.settings.fps[fps])
        print(path)
        # if stimuli == 0: # single
        #     if stimuli_type == 0: # circle
        #         elif stimuli == 1: # single SST
        
        #         elif stimuli == 2: # triplets
            
        #     elif stimuli_type == 1: # bar
            
        #     elif stimuli_type == 2: # vbar

        # elif stimuli == 1: # single SST
        
        # elif stimuli == 2: # triplets

        # elif stimuli == 3: # triplest SST


        # if stimuli == 0:
        #     video = self.settings.triplet_video
        # elif stimuli == 1:
        #     video = self.settings.single_video
        # elif stimuli == 2:
        #     video = self.settings.SRT_video

        if not path:
            raise ValueError("Could not resolve a stimulus video path from the current settings.")

        self._set_media_from_filename(path)

    def set_number(self, n=None):
        self.n = None if n is None else max(0, int(n))

    def apply_sequence_settings(self):
        if self._sequence_mode_enabled():
            self._load_saved_sequence()
            self.set_number(len(self._saved_sequence_order))
        elif self.settings.stimuli_inf:
            self.set_number(None)
        else:
            self.set_number(self.settings.stimuli_n)
        self._apply_cross_settings()

    def _current_run(self, run_id):
        return not self._stopped and run_id == self._run_id

    def _current_trial(self, run_id, trial_id):
        return self._current_run(run_id) and trial_id == self._active_trial_id

    def _schedule(self, delay_ms, callback, run_id=None, trial_id=None):
        run_id = self._run_id if run_id is None else run_id

        def guarded_callback():
            if trial_id is None:
                if not self._current_run(run_id):
                    return
            elif not self._current_trial(run_id, trial_id):
                return
            callback()

        QTimer.singleShot(delay_ms, guarded_callback)

    def _pick_final_image_path(self):
        final_dir = os.path.join("resources", "stimuli", "final_fig")
        if not os.path.isdir(final_dir):
            return None

        allowed_ext = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        filenames = [
            filename for filename in os.listdir(final_dir)
            if os.path.splitext(filename)[1].lower() in allowed_ext
        ]
        if not filenames:
            return None

        filename = str(np.random.choice(filenames))
        return os.path.join(final_dir, filename)

    def _set_fullscreen_pixmap(self, label, pixmap):
        label.setPixmap(pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        label.setGeometry(self.rect())

    def _configure_marker_widget(self):
        self._marker_widget = QLabel(self)
        self._marker_widget.setGeometry(max(0, self.width() - 80), 0, 80, 80)
        self._marker_widget.setStyleSheet("background-color: white;")
        self._marker_widget.show()
        self._marker_widget.raise_()

    def _configure_mean_error_label(self):
        self._mean_error_label = QLabel(self)
        self._mean_error_label.setAlignment(Qt.AlignCenter)
        self._mean_error_label.setWordWrap(True)
        self._mean_error_label.setStyleSheet(
            "QLabel {"
            "color: white;"
            "background-color: rgba(0, 0, 0, 180);"
            "font-size: 64px;"
            "font-weight: 700;"
            "padding: 18px;"
            "border-radius: 8px;"
            "}"
        )
        self._update_mean_error_label_geometry()
        self._mean_error_label.hide()

        self._results_plot_label = QLabel(self)
        self._results_plot_label.setAlignment(Qt.AlignCenter)
        self._results_plot_label.setStyleSheet(
            "QLabel {"
            "background-color: transparent;"
            "padding: 0px;"
            "border: none;"
            "}"
        )
        self._results_plot_path = None
        self._update_results_plot_label_geometry()
        self._results_plot_label.hide()

    def _update_mean_error_label_geometry(self):
        if "_mean_error_label" not in self.__dict__:
            return
        width = int(self.width() * 0.82)
        height = 130
        x = int((self.width() - width) / 2)
        y = int(self.height() * 0.18)
        self._mean_error_label.setGeometry(x, y, width, height)

    def _update_results_plot_label_geometry(self):
        if "_results_plot_label" not in self.__dict__:
            return
        width = int(self.width() * 0.84)
        height = int(self.height() * 0.52)
        x = int((self.width() - width) / 2)
        y = int(self.height() * 0.34)
        self._results_plot_label.setGeometry(x, y, width, height)

    def is_mean_error_visible(self):
        return "_mean_error_label" in self.__dict__ and self._mean_error_label.isVisible()

    def hide_mean_error(self):
        if "_mean_error_label" in self.__dict__:
            self._mean_error_label.hide()
        if "_results_plot_label" in self.__dict__:
            self._results_plot_label.hide()
        self._results_plot_path = None

    def show_mean_error(self, mean_error, plot_path=None, duration_ms=None):
        if "_mean_error_label" not in self.__dict__:
            return
        if np.isfinite(mean_error):
            text = f"Средняя ошибка: {mean_error:.2f} мс"
        else:
            text = "Средняя ошибка: --"
        self._mean_error_label.setText(text)
        self._update_mean_error_label_geometry()
        self._mean_error_label.show()
        self._mean_error_label.raise_()
        if plot_path and os.path.exists(plot_path) and "_results_plot_label" in self.__dict__:
            self._results_plot_path = plot_path
            pixmap = QPixmap(plot_path)
            if not pixmap.isNull():
                self._update_results_plot_label_geometry()
                self._results_plot_label.setPixmap(
                    pixmap.scaled(
                        self._results_plot_label.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                self._results_plot_label.show()
                self._results_plot_label.raise_()
        elif "_results_plot_label" in self.__dict__:
            self._results_plot_path = None
            self._results_plot_label.hide()
        if "_marker_widget" in self.__dict__ and self._marker_widget.isVisible():
            self._marker_widget.raise_()
        if duration_ms and duration_ms > 0:
            QTimer.singleShot(int(duration_ms), self.hide_mean_error)

    def _show_marker(self):
        if "_marker_widget" not in self.__dict__:
            return
        self._marker_widget.show()
        self._marker_widget.raise_()

    def _hide_marker(self):
        if "_marker_widget" not in self.__dict__:
            return
        self._marker_widget.hide()

    def _should_show_marker_for_stimulus(self, filename):
        return os.path.basename(filename) == self.MARKER_STIMULUS

    def _attach_video_output(self):
        if getattr(self, "_video_output_attached", False):
            return
        self._player.set_hwnd(self._video_hwnd)
        self._video_output_attached = True

    def _detach_video_output(self):
        if not getattr(self, "_video_output_attached", False):
            return
        try:
            self._player.set_hwnd(0)
        finally:
            self._video_output_attached = False

    def _show_final_image(self):
        self._detach_video_output()
        self._video_widget.hide()
        self._final_image_path = self._pick_final_image_path()
        self._showing_final_image = bool(self._final_image_path)

        if self._showing_final_image:
            pixmap = QPixmap(self._final_image_path)
            if not pixmap.isNull():
                self._set_fullscreen_pixmap(self._cross_label, pixmap)

        self._hide_feedback_bar_mode()
        self._stacked.setCurrentIndex(2)
        self._cross_label.show()
        self._show_marker()

    def _finish_sequence(self):
        self._player.stop()
        self._video_playback_active = False
        self._detach_video_output()
        self._awaiting_first_frame = False
        self._is_paused = False
        self._sequence_started = False
        self.show_delay = False
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._feedback_trial_id = None
        self._feedback_rendering_trial_id = None
        self._finished = True
        self._show_final_image()
        self.stimuliFinished.emit()

    def _configure_player(self):
        # ===  VLC player === 
        self._instance = vlc.Instance(
            '--file-caching=100',
            '--no-video-title-show',
            '--no-osd',
            '--quiet',
            '--no-sub-autodetect-file', 
            '--no-spu'
            )


        self._player = self._instance.media_player_new()

        # Привязка событий
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)
        events.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_media_playing)
        self._videoEnded.connect(self._handle_video_end)
        self._mediaPlaying.connect(self._handle_media_playing)

        # === background === 

        # === Видео виджет ===
        self._configure_video_widget()
        self._configure_background_label()
        
        # === Виджет с крестом ===
        self._configure_cross_label()

        # === Feedback widget === 
        self._configure_feedback_widget()

        # === Bar feedback widget ===
        self._configure_bar_feedback_widget()

        # === setup layout === 
        self._setup_layout()
        self._configure_marker_widget()
        self._configure_mean_error_label()

        # === Установить видос === 
        self.set_video_path()
        
    def _setup_layout(self):
        self._stacked = QStackedWidget()      # позволяет просто переключаться между виджетами
        self._stacked.setAttribute(Qt.WA_TranslucentBackground, True)
        self._stacked.setAttribute(Qt.WA_NoSystemBackground, True)
        self._stacked.setStyleSheet("background: transparent;")

        self._stacked.addWidget(self._video_widget)      # индекс 0
        self._stacked.addWidget(self._feedback_widget)   # индекс 1
        self._stacked.addWidget(self._cross_widget)      # индекс 2
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)

        layout.addWidget(self._stacked)
        self._background_label.lower()
        self._stacked.raise_()

        self._stacked.setCurrentIndex(2)
        # self._video_widget.hide()

    def _configure_background_label(self):
        background_path = os.path.join(r"resources\stimuli", self.settings.background_figure)
        self._background_label = QLabel(self)
        self._background = QPixmap(background_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        self._background_label.setPixmap(self._background)
        self._background_label.setGeometry(self.rect())
        self._background_label.setAlignment(Qt.AlignCenter)
        self._background_label.setStyleSheet("background-color: black;")
        self._background_label.hide()
        self._background_label.lower()

    def _configure_video_widget(self):
        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        video_placeholder_pixmap = QPixmap(self._cross_figure_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        self._video_placeholder = QLabel(self)
        self._video_placeholder.setPixmap(video_placeholder_pixmap)
        self._video_placeholder.setGeometry(self.rect())
        self._video_placeholder.setAlignment(Qt.AlignCenter)
        self._video_placeholder.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._video_placeholder.setStyleSheet("background-color: black;")
        
        self._player.audio_set_volume(self._volume)
        self._video_placeholder.hide()
        self._video_placeholder.raise_()

        self._last_frame_label = QLabel(self)
        self._last_frame_label.setGeometry(self.rect())
        self._last_frame_label.setAlignment(Qt.AlignCenter)
        self._last_frame_label.setStyleSheet("background-color: black;")
        self._last_frame_label.hide()

        # layout = QVBoxLayout(self)
        # layout.setContentsMargins(0,0,0,0)
        # layout.addWidget(self._video_widget)

        self._video_hwnd = int(self._video_widget.winId())
        self._player.set_hwnd(self._video_hwnd)
        # self._video_output_attached = False

        # self._attach_video_output()


    def _configure_cross_label(self):
        self._cross_widget = QWidget(self)
        self._cross_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self._cross_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._cross_label = QLabel(self._cross_widget)

        self._main_cross_pic = QPixmap(self._cross_figure_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        self._cross_label.setPixmap(self._main_cross_pic)
        
        self._cross_label.setGeometry(self.rect())
        self._cross_label.setAlignment(Qt.AlignCenter)
        self._cross_label.setStyleSheet("background:transparent;")

        self._cross_dur_ms = self._current_cross_duration_ms()

        # первый стимул
        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)
        
        print('[VLC player]: press Space to start.')

    def _configure_feedback_widget(self):
        self._feedback_widget = QWidget(self)
        self._feedback_widget.setStyleSheet("background:transparent;")

        w, h = self.settings.feedback_w, self.settings.feedback_h

        self._feedback_graphs = [FeedbackGraph(w, h, self._feedback_widget), FeedbackGraph(w, h, self._feedback_widget), FeedbackGraph(w, h, self._feedback_widget)]
        center_y = self.height() // 2 - h // 2
        center_x = self.width() // 2 - w // 2
        self._feedback_graphs[0].move(center_x-w, center_y)
        self._feedback_graphs[1].move(center_x, center_y)
        self._feedback_graphs[2].move(center_x+w, center_y)

        center_x, center_y = self.width() // 2 - w // 2, self.height() // 2 - h // 2
        w, h = int(1.1 * w), int(1.1 * h)
        self._feedback_graph = FeedbackGraph(w, h, self._feedback_widget)
        self._feedback_graph.move(center_x, center_y)

        self.change_stimuli()
        # self._feedback_graph.setGeometry(x, y, width, height)

        self._feedback_ms = self.settings.feedback_ms
        self._show_feedback_ms = self.settings.show_feedback

    def _configure_bar_feedback_widget(self):
        self._feedback_bar = FeedbackBar(w=self.width(), h=self.height(), 
                                         parent=self)
        self._feedback_bar.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._feedback_bar.move(0, 0)
        self._feedback_bar.hide()

    def change_stimuli(self):
        if self.settings.stimuli_curr == 2:
            self._feedback_graph.hide()
            for graph in self._feedback_graphs:
                graph.show()
        elif self.settings.stimuli_curr == 0:
            for graph in self._feedback_graphs:
                graph.hide()
            self._feedback_graph.show()
        
        stimuli_mode = self.settings.stimuli[self.settings.stimuli_curr]
        # self.logger.info(f"Stimuli mode: {stimuli_mode}")

    def _hide_feedback_plot_widgets(self):
        self._feedback_graph.hide()
        for graph in self._feedback_graphs:
            graph.hide()

    def _clear_last_frame_background(self, remove_file=False):
        self._last_frame_ready = False
        self._last_frame_pixmap = QPixmap()
        if hasattr(self, "_last_frame_label"):
            self._last_frame_label.clear()
            self._last_frame_label.hide()
        if remove_file and os.path.exists(self._last_frame_path):
            try:
                os.remove(self._last_frame_path)
            except OSError:
                pass

    def _capture_last_frame_from_screen(self):
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return False

        geometry = self.geometry()
        pixmap = screen.grabWindow(0, geometry.x(), geometry.y(), geometry.width(), geometry.height())
        if pixmap.isNull():
            return False

        self._last_frame_pixmap = pixmap
        self._last_frame_ready = True
        return True

    def _show_last_frame_background(self):
        if not self._last_frame_ready:
            return False

        pixmap = self._last_frame_pixmap
        if pixmap.isNull() and os.path.exists(self._last_frame_path):
            pixmap = QPixmap(self._last_frame_path)
        if pixmap.isNull():
            return False

        self._last_frame_label.setPixmap(
            pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        )
        self._last_frame_label.setGeometry(self.rect())
        self._last_frame_label.show()
        self._last_frame_label.raise_()
        if hasattr(self, "_background_label"):
            self._background_label.hide()
            self._background_label.lower()
        return True

    def _show_feedback_plot_mode(self):
        #self._video_widget.hide()
        self._background_label.show()
        self._background_label.lower()
        self._last_frame_label.hide()
        self._feedback_bar.hide()
        if hasattr(self, "_video_placeholder"):
            self._video_placeholder.hide()
        self.change_stimuli()
        if self.settings.stimuli_curr == 2:
            for graph in self._feedback_graphs:
                graph.raise_()
        else:
            self._feedback_graph.raise_()
        self._show_marker()

    def _show_feedback_bar_mode(self):
        self._background_label.hide()
        self._hide_feedback_plot_widgets()

        if hasattr(self, "_video_placeholder"):
            self._video_placeholder.hide()

        # self._video_widget.show()
        self._video_widget.hide()          # VLC больше не фон
        self._stacked.setCurrentIndex(0)

        shown = self._show_last_frame_background()

        if not shown:
            # fallback лучше крест/placeholder, чем черный фон
            self._video_placeholder.setPixmap(self._main_cross_pic)
            self._video_placeholder.setGeometry(self.rect())
            self._video_placeholder.show()
            self._video_placeholder.raise_()

        self._feedback_bar.setFixedSize(self.size())
        self._feedback_bar.move(0, 0)
        self._feedback_bar.show()
        self._feedback_bar.raise_()
        self._feedback_bar.update()

        # if self._last_frame_ready:
        #     pixmap = self._last_frame_pixmap
        #     if pixmap.isNull() and os.path.exists(self._last_frame_path):
        #         pixmap = QPixmap(self._last_frame_path)

        #     if not pixmap.isNull():
        #         self._last_frame_label.setPixmap(
        #             pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        #         )
        #         self._last_frame_label.setGeometry(self.rect())
        #         self._last_frame_label.show()
        #         self._last_frame_label.raise_()

        # self._feedback_bar.setFixedSize(self.size())
        # self._feedback_bar.move(0, 0)
        # self._feedback_bar.show()
        # self._feedback_bar.raise_()
        # self._feedback_bar.update()
    
    # ===============================
    # === цикл проигрывания видео ===
    # ===============================

    def _play_next_video(self):
        if self._stopped or self._is_paused:
            print('[VLC player]: stimuli presentation has been stopped.')
            return
        run_id = self._run_id
        self._showing_final_image = False
        
        if self.n is not None and self._counter >= self.n:
            self._finish_sequence()
            return

        sequence_index = self._counter
        if self._sequence_mode_enabled():
            self._set_sequence_video_path(sequence_index)

        self._counter += 1
        self._active_trial_id += 1
        trial_id = self._active_trial_id
        self.show_delay = False
        self._last_frame_ready = False
        self._clear_last_frame_background(remove_file=True)
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._feedback_trial_id = None
        self._feedback_rendering_trial_id = None

        # запустить следующее видео
        self._marker_visible_during_current_video = self._should_show_marker_for_stimulus(self._current_stimulus_filename)
        # self._attach_video_output()
        self._video_widget.show()
        self._video_placeholder.setPixmap(self._main_cross_pic)
        self._video_placeholder.setGeometry(self.rect())
        self._video_placeholder.show()
        self._video_placeholder.raise_()
        self._show_marker()

        self._stacked.setCurrentIndex(0)
        self._awaiting_first_frame = True
        self._player.stop()
        self._player.set_media(self.media)
        self._player.set_position(0)
        self.stimulus.emit(self._current_stimulus_filename)
        self._video_playback_active = True
        self._player.play()
        self._schedule(self.LAST_FRAME_POLL_MS, lambda: self._capture_last_frame_loop(run_id, trial_id), run_id, trial_id)

        self._background_label.hide()
        self._hide_feedback_bar_mode()
        self._cross_label.hide()
        if self._marker_visible_during_current_video:
            self._show_marker()
        else:
            self._hide_marker()
        

        # подготовить следующее видео
        self._current_index += 1
        self.currIdxChanged.emit(self._current_index)

        self._is_paused = False

        # Скрываем placeholder через 50ms после старта VLC
        # delay = 50
        # QTimer.singleShot(delay, self._cross_label.hide)
        # Проверяем окончание видео каждые 50ms

    def _show_video_widget(self):
        if self._stopped or not self._video_playback_active or not self._awaiting_first_frame:
            return
        self._clear_last_frame_background()
        self._video_widget.show()
        self._stacked.setCurrentIndex(0)
        if hasattr(self, "_video_placeholder"):
            self._video_placeholder.hide()
        if self._marker_visible_during_current_video:
            self._show_marker()
        else:
            self._hide_marker()
        self._awaiting_first_frame = False

    # def _capture_last_frame_loop(self, run_id, trial_id):
    #     if self._last_frame_ready or not self._video_playback_active or not self._current_trial(run_id, trial_id):
    #         return

    #     length = self._player.get_length()
    #     current = self._player.get_time()
    #     if length > 0 and current >= 0 and 0 <= length - current <= self.LAST_FRAME_CAPTURE_MS:
    #         os.makedirs(os.path.dirname(self._last_frame_path), exist_ok=True)
    #         if self._player.video_take_snapshot(0, self._last_frame_path, self.width(), self.height()) == 0:
    #             self._last_frame_pixmap = QPixmap(self._last_frame_path)
    #             self._last_frame_ready = True
    #         return

    #     self._schedule(self.LAST_FRAME_POLL_MS, lambda: self._capture_last_frame_loop(run_id, trial_id), run_id, trial_id)

    def _capture_last_frame_loop(self, run_id, trial_id):
        if self._last_frame_ready or not self._video_playback_active or not self._current_trial(run_id, trial_id):
            return

        length = self._player.get_length()
        current = self._player.get_time()

        if length > 0 and current >= 0 and 0 <= length - current <= self.LAST_FRAME_CAPTURE_MS:
            os.makedirs(os.path.dirname(self._last_frame_path), exist_ok=True)

            # ok = self._player.video_take_snapshot(
            #     0,
            #     self._last_frame_path,
            #     self.width(),
            #     self.height()
            # ) == 0

            # if ok and os.path.exists(self._last_frame_path) and os.path.getsize(self._last_frame_path) > 0:
            #     pixmap = QPixmap(self._last_frame_path)
            #     if not pixmap.isNull():
            #         self._last_frame_pixmap = pixmap
            #         self._last_frame_ready = True
            #         return
            if self._player.video_take_snapshot(0, self._last_frame_path, self.width(), self.height()) == 0:
                self._last_frame_ready = True
                self._last_frame_pixmap = QPixmap(self._last_frame_path)
                return

        self._schedule(
            self.LAST_FRAME_POLL_MS,
            lambda: self._capture_last_frame_loop(run_id, trial_id),
            run_id,
            trial_id
        )

    def _handle_video_end(self, run_id=None, trial_id=None):
        run_id = self._run_id if run_id is None else run_id
        trial_id = self._active_trial_id if trial_id is None else trial_id
        if not self._current_trial(run_id, trial_id):
            return  # больше ничего не делаем
        # if not self._last_frame_ready:
        #     self._capture_last_frame_from_screen()
        self._awaiting_first_frame = False
        self._video_playback_active = False
        self._player.pause()  # или не stop; главное не давать VLC очистить окно

        # if self._last_frame_ready:
        #     self._show_last_frame_background()
            
        # self._hide_feedback_plot_widgets()
        # if hasattr(self, "_video_placeholder"):
        #     self._video_placeholder.hide()

        # self._stacked.setCurrentIndex(0)
        # self._cross_label.hide()
        # self._cross_label.show()
        
            # Сразу показываем placeholder перед следующим видео
            
        # self._show_marker() #what is it?? 

        self._awaiting_feedback = True
        self._awaiting_feedback_trial_id = trial_id
        self.stimuliEnded.emit()    # --> stimuli_control_panel --> main_window --> data_processor

        if self.settings.sham_feedback and not self.show_delay:
            self.show_feedback(self._generate_sham_delay(), trial_id=trial_id)
        
        if self.show_delay and self._feedback_trial_id == trial_id:
            self._check_feedback()
            print("show without waiting", self.delay_value)
        else:
            self._awaiting_feedback = True
            self._awaiting_feedback_trial_id = trial_id
            self._schedule(
                self.FEEDBACK_WAIT_MS,
                lambda: self._show_cross_if_no_feedback(run_id, trial_id),
                run_id,
                trial_id,
            )

    def _show_cross_if_no_feedback(self, run_id=None, trial_id=None):
        print("waiting feedback")
        run_id = self._run_id if run_id is None else run_id
        trial_id = self._active_trial_id if trial_id is None else trial_id
        if not self._current_trial(run_id, trial_id) or self._is_paused:
            return
        if self._feedback_rendering_trial_id == trial_id:
            return
        if self._feedback_trial_id == trial_id:
            print("show after waiting", self.delay_value, trial_id)
            self._check_feedback()
            return
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._show_cross()

    def _update_feedback_graph(self, graph, value):
        if np.isfinite(value):
            status = True
            graph.set_triangle_params(vertex_x=value)
        else:
            status = False
        graph.show_triangle = status
        graph.show_measure_line = status
        graph.show_label = status
    
    def _update_feedback_bar(self, graph, value):
        if np.isfinite(value):
            status = True
            graph.set_triangle_params(vertex_x=value)
        else:
            status = False
        graph.show_triangle = status
        graph.show_measure_line = status
        graph.show_label = status


    def _hide_feedback_bar_mode(self):
        self._background_label.hide()
        self._feedback_bar.hide()
        if hasattr(self, "_last_frame_label"):
            self._last_frame_label.hide()
        

    def _check_feedback(self):
        trial_id = self._feedback_trial_id
        run_id = self._run_id
        if trial_id is None or not self._current_trial(run_id, trial_id):
            return
        self._feedback_rendering_trial_id = trial_id
        
        if self.settings.feedback_form_curr == 0:
            if self.settings.stimuli_curr == 2: # triplets
                d1 = int(self.delay_value[0]) if np.isfinite(self.delay_value[0]) else np.nan
                d2 = int(self.delay_value[1]) if np.isfinite(self.delay_value[1]) else np.nan
                d3 = int(self.delay_value[2]) if np.isfinite(self.delay_value[2]) else np.nan
                for i, d in enumerate([d1, d2, d3]):
                    graph = self._feedback_graphs[i]
                    self._update_feedback_graph(graph, d)
            else:
                d = int(self.delay_value[0]) if np.isfinite(self.delay_value[0]) else np.nan
                self._update_feedback_graph(self._feedback_graph, d)
            self._show_feedback_plot_mode()
            self._stacked.setCurrentIndex(1)        # switch to feedback widget
        else:
            self._update_feedback_bar(self._feedback_bar, self.delay_value[0])
            self._show_feedback_bar_mode()
        print("SHOW FEEDBACK ", self.delay_value)
        # QTimer.singleShot(50, self._cross_label.hide)
    
        self.show_delay = False
        feedback_duration_ms = self._feedback_ms
        if not self._is_paused:
            self._feedback_trial_id = None
            self._schedule(feedback_duration_ms, lambda: self._finish_feedback(run_id, trial_id), run_id, trial_id)
        else:
            self._schedule(250, self._check_feedback, run_id, trial_id)

    def _finish_feedback(self, run_id, trial_id):
        if not self._current_trial(run_id, trial_id):
            return
        self._feedback_rendering_trial_id = None
        self._show_cross()

    
    def _show_cross(self):
        if self._stopped:
            return
        run_id = self._run_id
        trial_id = self._active_trial_id
        # self._video_widget.hide()
        if hasattr(self, "_video_placeholder"):
            self._video_placeholder.hide()
        self._hide_feedback_bar_mode()
        self._hide_feedback_plot_widgets()
        self._stacked.setCurrentIndex(2)
        self._cross_label.show()
        self._show_marker()
        if not self._is_paused:
            self._cross_dur_ms = self._next_cross_duration_ms()
            self._schedule(self._cross_dur_ms, self._play_next_video, run_id, trial_id)
        else:
            self._schedule(250, self._show_cross, run_id, trial_id)

    # =======================
    # ===     события     ===
    # =======================
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:         # start|stop regulation
            self._on_space_pressed()
        
        elif event.key() == Qt.Key_Escape:      # closing
            self.finish()
                    
        elif event.key() == Qt.Key_R:           # restart
            self.restart_sequence()             
                                                 # volume regulation

        elif event.key() == Qt.Key_Up:                  # -- volume up
            new_value = min(100, self._volume + 1)
            self.update_volume(new_value)   
        
        elif event.key() == Qt.Key_Down:                # -- volume down
            new_value = max(0, self._volume - 1)
            self.update_volume(new_value)

        elif event.key() == Qt.Key_M:                   # -- mute
            self._player.audio_toggle_mute()
            self.playerIsMuted.emit()

        else:
            super().keyPressEvent(event)

    # ====================
    # ===    логика    ===
    # ====================

    def show_feedback(self, delay, trial_id=None):
        if trial_id is None:
            trial_id = self._awaiting_feedback_trial_id
        if trial_id is None and self._sequence_started:
            trial_id = self._active_trial_id
        if trial_id is None or not self._current_trial(self._run_id, trial_id):
            return
        self.show_delay = True
        self._feedback_trial_id = trial_id
        print("trial ID {}, delay {}". format(trial_id, delay))
        self.delay_value = np.atleast_1d(np.asarray(delay, dtype=float))
        if self._awaiting_feedback and self._awaiting_feedback_trial_id == trial_id:
            self._awaiting_feedback = False
            self._awaiting_feedback_trial_id = None
            QTimer.singleShot(0, self._check_feedback)

    def _generate_sham_delay(self):
        n_values = 3 if self.settings.stimuli_curr == 2 else 1
        return 0#np.random.randint(-200, 201, size=n_values).astype(float)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "_background_label"):
            self._background = QPixmap(os.path.join(r"resources\stimuli", self.settings.background_figure)).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._background_label.setPixmap(self._background)
            self._last_frame_label.setGeometry(self.rect())

        if hasattr(self, "_cross_label"):
            if self._showing_final_image and self._final_image_path:
                pixmap = QPixmap(self._final_image_path)
                if not pixmap.isNull():
                    self._set_fullscreen_pixmap(self._cross_label, pixmap)
            else:
                self._main_cross_pic = QPixmap(self._cross_figure_path).scaled(
                    self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self._cross_label.setPixmap(self._main_cross_pic)
            self._cross_label.setGeometry(self.rect())

        if hasattr(self, "_video_placeholder"):
            self._video_placeholder.setPixmap(self._main_cross_pic)
            self._video_placeholder.setGeometry(self.rect())

        if hasattr(self, "_last_frame_label"):
            self._last_frame_label.setGeometry(self.rect())
            if self._last_frame_label.isVisible():
                self._show_last_frame_background()

        if hasattr(self, "_feedback_bar"):
            self._feedback_bar.setFixedSize(self.size())
            self._feedback_bar.move(0, 0)

        if "_marker_widget" in self.__dict__:
            self._marker_widget.setGeometry(max(0, self.width() - 80), 0, 80, 80)
            self._marker_widget.raise_()

        self._update_mean_error_label_geometry()
        self._update_results_plot_label_geometry()
        if (
            "_results_plot_label" in self.__dict__
            and self._results_plot_label.isVisible()
            and self._results_plot_path
            and os.path.exists(self._results_plot_path)
        ):
            pixmap = QPixmap(self._results_plot_path)
            if not pixmap.isNull():
                self._results_plot_label.setPixmap(
                    pixmap.scaled(
                        self._results_plot_label.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                self._results_plot_label.raise_()
        if "_mean_error_label" in self.__dict__ and self._mean_error_label.isVisible():
            self._mean_error_label.raise_()
    

    # === показ стимулов ===
    def _on_space_pressed(self):
        # Последовательность ещё не запускалась -> начать показ стимулов
        if not self._sequence_started:
            print("[VLC player]: start the stimuli presentation.")
            self._run_id += 1
            self._active_trial_id = 0
            self._awaiting_feedback = False
            self._awaiting_feedback_trial_id = None
            self._feedback_trial_id = None
            self._feedback_rendering_trial_id = None
            self._sequence_started = True
            self.stimuliStarted.emit()
            self._is_paused = False
            self._play_next_video()
            return

        # Последовательность идёт -> остановить показ стимулов
        if not self._is_paused:
            print("[VLC player]: pause the stimuli presentation.")
            if self._player.get_state() in (vlc.State.Opening, vlc.State.Buffering, vlc.State.Playing):
                self._player.pause()
            self._is_paused = True
            self.stimuliPaused.emit()
            return

        # Показ стимулов на паузе -> продолжить
        if self._is_paused:
            print("[VLC player]: continue the stimuli presentation.")
            if self._player.get_state() == vlc.State.Paused:
                self._player.play()
            self._is_paused = False
            self.stimuliPaused.emit()

    def pause_video(self):
        # управление внешней кнопкой 
        self._on_space_pressed()

    def restart_sequence(self):
        print("[VLC player]: restart stimuli presentation.")
        self._run_id += 1
        self._player.stop()
        self._video_playback_active = False
        self._detach_video_output()

        self._is_paused = False
        self._sequence_started = False
        self._stopped = False
        self._finished = False
        self._counter = 0
        self._active_trial_id = 0
        self._showing_final_image = False
        self._final_image_path = None
        self.show_delay = False
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._feedback_trial_id = None
        self._feedback_rendering_trial_id = None
        self.apply_sequence_settings()

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)
        self._video_widget.hide()
        self._stacked.setCurrentIndex(2)
        self._cross_label.show()
        self.hide_mean_error()
        self._show_marker()
    
    def finish(self):
        print("[VLC player]: finish the stimuli presentation and close the player.")
        self._run_id += 1
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._feedback_trial_id = None
        self._feedback_rendering_trial_id = None
        self._stopped = True           # ставим флаг остановки
        self._player.stop()
        self._video_playback_active = False
        self._detach_video_output()
        self._player.release()
        self._instance.release()
        if not self._finished:
            self.stimuliFinished.emit()
        self.close()
    
    @property
    def is_paused(self):
        return self._is_paused

    def _on_end_reached(self, event):
        if self._is_paused:
            return  # если вдруг pause совпал с концом
        
        self._videoEnded.emit(self._run_id, self._active_trial_id)
        
    # === управление звуком === 
    def _on_media_playing(self, event):
        self._mediaPlaying.emit(self._run_id, self._active_trial_id)

    def _handle_media_playing(self, run_id, trial_id):
        if not self._video_playback_active or not self._current_trial(run_id, trial_id) or not self._awaiting_first_frame:
            return
        self._schedule(self.VIDEO_READY_HIDE_MS, self._show_video_widget, run_id, trial_id)

    def update_volume(self, value):
        self._volume = value
        self._player.audio_set_volume(self._volume)
        self.volumeChanged.emit(self._volume)
        print("Volume:", self._volume)
    
    def get_last_volume(self):
        return self._volume

    

    


