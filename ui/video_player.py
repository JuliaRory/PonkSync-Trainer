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
from ui.feedback_bar_overlay import FeedbackBarOverlay
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
    FEEDBACK_WAIT_MS = 200
    VIDEO_READY_HIDE_MS = 300
    
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
        self._awaiting_first_frame = False

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
        self.n = None
        self.apply_sequence_settings()
        self._awaiting_first_frame = False
        
        self._cross_figure_path = os.path.join(r"resources\stimuli", self.settings.cross_figure)
        self._bar_figure_path = os.path.join(r"resources\stimuli", self.settings.bar_figure)
        
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

    def set_video_path(self):
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

        self._video_path = os.path.join(r"resources\stimuli", path)
        if not os.path.exists(self._video_path):
            raise FileNotFoundError(f"Stimulus video not found: {self._video_path}")

        # === Подготовка последовательности ===
        self.media = self._instance.media_new(self._video_path)
        self._player.set_media(self.media)
        # self.media.add_option(':start-time=1.56')
        self.media.parse_async()  # preload

    def set_number(self, n=None):
        self.n = None if n is None else max(0, int(n))

    def apply_sequence_settings(self):
        if self.settings.stimuli_inf:
            self.set_number(None)
        else:
            self.set_number(self.settings.stimuli_n)

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

    def _finish_sequence(self):
        self._player.stop()
        self._awaiting_first_frame = False
        self._is_paused = False
        self._sequence_started = False
        self.show_delay = False
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._feedback_trial_id = None
        self._feedback_rendering_trial_id = None
        self._finished = True
        self._stacked.setCurrentIndex(2)
        self._cross_label.show()
        self.stimuliFinished.emit()

    def _configure_player(self):
        # ===  VLC player === 
        self._instance = vlc.Instance(
            '--file-caching=100',
            '--no-video-title-show',
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
        self._stacked.addWidget(self._bar_feedback_widget)  # index 3  

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)

        layout.addWidget(self._stacked)
        self._background_label.lower()
        self._stacked.raise_()

        self._stacked.setCurrentIndex(2)

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
        # layout = QVBoxLayout(self)
        # layout.setContentsMargins(0,0,0,0)
        # layout.addWidget(self._video_widget)

        winid = int(self._video_widget.winId())
        self._player.set_hwnd(winid)


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

        self._cross_dur_ms = self.settings.cross_ms      # проигрвать крест 

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
        self._bar_feedback_widget = QWidget(self)
        # self._bar_feedback_widget.setAttribute(Qt.WA_TranslucentBackground, True)
        # self._bar_feedback_widget.setAttribute(Qt.WA_NoSystemBackground, True)
        # self._bar_feedback_widget.setAutoFillBackground(False)
        self._bar_feedback_widget.setStyleSheet("background-color: black;")

        # layout = QVBoxLayout(self._bar_feedback_widget)
        # layout.setContentsMargins(0, 0, 0, 0)
        self._feedback_bar_background = QLabel(self._bar_feedback_widget)
        self._bar_figure_pixmap = QPixmap(self._bar_figure_path)
        self._feedback_bar_background.setPixmap(self._bar_figure_pixmap)

        self._feedback_bar_background.setGeometry(self.rect())
        self._feedback_bar_background.setAlignment(Qt.AlignCenter)
        self._feedback_bar_background.setStyleSheet("background-color: black;")
        self._feedback_bar_background.setAttribute(Qt.WA_TranslucentBackground, True)
        
        self._feedback_bar_background.setScaledContents(True)

        self._feedback_bar = FeedbackBar(w=self.width(), h=self.height(), 
                                         parent=self._bar_feedback_widget)
        self._feedback_bar.move(0, 0)
        self._feedback_bar.raise_()

        self._feedback_bar_overlay = FeedbackBarOverlay(self.settings, self._bar_feedback_widget)
        self._feedback_bar_overlay.setGeometry(self._bar_feedback_widget.rect())
        self._feedback_bar_overlay.raise_()

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

    def _show_feedback_plot_mode(self):
        self._background_label.show()
        self._background_label.lower()
        self._feedback_bar_background.hide()
        self._feedback_bar_overlay.clear()
        self.change_stimuli()

    def _show_feedback_bar_mode(self):
        self._background_label.hide()
        self._feedback_graph.hide()
        for graph in self._feedback_graphs:
            graph.hide()
        self._feedback_bar.show()
        self._feedback_bar_background.show()
        self._feedback_bar_background.raise_()
        self._feedback_bar.raise_()
        self._feedback_bar_overlay.raise_()
    
    # ===============================
    # === цикл проигрывания видео ===
    # ===============================

    def _play_next_video(self):
        if self._stopped or self._is_paused:
            print('[VLC player]: stimuli presentation has been stopped.')
            return
        run_id = self._run_id
        
        if self.n is not None and self._counter >= self.n:
            self._finish_sequence()
            return

        self._counter += 1
        self._active_trial_id += 1
        trial_id = self._active_trial_id
        self.show_delay = False
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._feedback_trial_id = None
        self._feedback_rendering_trial_id = None

        # запустить следующее видео
        self._video_placeholder.setPixmap(self._main_cross_pic)
        self._video_placeholder.setGeometry(self.rect())
        self._video_placeholder.show()
        self._video_placeholder.raise_()

        self._stacked.setCurrentIndex(0)
        self._awaiting_first_frame = True
        self._player.stop()
        self._player.set_media(self.media)
        self._player.set_position(0)
        self._player.play()

        self._background_label.hide()
        self._hide_feedback_bar_mode()
        self._cross_label.hide()
        

        # подготовить следующее видео
        self._current_index += 1
        self.currIdxChanged.emit(self._current_index)

        self._is_paused = False

        # Скрываем placeholder через 50ms после старта VLC
        # delay = 50
        # QTimer.singleShot(delay, self._cross_label.hide)
        # Проверяем окончание видео каждые 50ms

    def _show_video_widget(self):
        if self._stopped:
            return
        self._stacked.setCurrentIndex(0)
        if hasattr(self, "_video_placeholder"):
            self._video_placeholder.hide()
        self._awaiting_first_frame = False

    def _handle_video_end(self, run_id=None, trial_id=None):
        run_id = self._run_id if run_id is None else run_id
        trial_id = self._active_trial_id if trial_id is None else trial_id
        if not self._current_trial(run_id, trial_id):
            return  # больше ничего не делаем
        self._awaiting_first_frame = False
        if hasattr(self, "_video_placeholder"):
            self._video_placeholder.hide()
        self._stacked.setCurrentIndex(0)
        
            # Сразу показываем placeholder перед следующим видео
            
        self._awaiting_feedback = True
        self._awaiting_feedback_trial_id = trial_id
        self.stimuliEnded.emit()    # --> stimuli_control_panel --> main_window --> data_processor

        if self.settings.sham_feedback and not self.show_delay:
            self.show_feedback(self._generate_sham_delay(), trial_id=trial_id)
        
        if self.show_delay and self._feedback_trial_id == trial_id:
            self._check_feedback()
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
        run_id = self._run_id if run_id is None else run_id
        trial_id = self._active_trial_id if trial_id is None else trial_id
        if not self._current_trial(run_id, trial_id) or self._is_paused:
            return
        if self._feedback_rendering_trial_id == trial_id:
            return
        if self._feedback_trial_id == trial_id:
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
        self._feedback_bar_background.hide()
        self._feedback_bar_overlay.clear()

    def _check_feedback(self):

        trial_id = self._feedback_trial_id
        run_id = self._run_id
        if trial_id is None or not self._current_trial(run_id, trial_id):
            return
        self._feedback_rendering_trial_id = trial_id
        

        print("TO SHOW", self.delay_value)
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
            self._stacked.setCurrentIndex(3)
            
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
        if hasattr(self, "_video_placeholder"):
            self._video_placeholder.hide()
        self._hide_feedback_bar_mode()
        self._stacked.setCurrentIndex(2)
        self._cross_label.show()
        if not self._is_paused:
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
        trial_id = self._awaiting_feedback_trial_id if trial_id is None else trial_id
        if trial_id is None or not self._current_trial(self._run_id, trial_id):
            return
        self.show_delay = True
        self._feedback_trial_id = trial_id
        self.delay_value = np.atleast_1d(np.asarray(delay, dtype=float))
        if self._awaiting_feedback and self._awaiting_feedback_trial_id == trial_id:
            self._awaiting_feedback = False
            self._awaiting_feedback_trial_id = None
            QTimer.singleShot(0, self._check_feedback)

    def _generate_sham_delay(self):
        n_values = 3 if self.settings.stimuli_curr == 2 else 1
        return np.random.randint(-200, 201, size=n_values).astype(float)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "_background_label"):
            self._background = QPixmap(os.path.join(r"resources\stimuli", self.settings.background_figure)).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._background_label.setPixmap(self._background)
            self._background_label.setGeometry(self.rect())

        if hasattr(self, "_cross_label"):
            self._main_cross_pic = QPixmap(self._cross_figure_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._cross_label.setPixmap(self._main_cross_pic)
            self._cross_label.setGeometry(self.rect())

        if hasattr(self, "_video_placeholder"):
            self._video_placeholder.setPixmap(self._main_cross_pic)
            self._video_placeholder.setGeometry(self.rect())

        if hasattr(self, "_feedback_bar_background"):
            self._feedback_bar_background.setGeometry(self._bar_feedback_widget.rect())
            self._update_bar_background_pixmap()

        if hasattr(self, "_feedback_bar_overlay"):
            self._feedback_bar_overlay.setGeometry(self._bar_feedback_widget.rect())
    

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

        self._is_paused = False
        self._sequence_started = False
        self._stopped = False
        self._finished = False
        self._counter = 0
        self._active_trial_id = 0
        self.show_delay = False
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._feedback_trial_id = None
        self._feedback_rendering_trial_id = None
        self.apply_sequence_settings()

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)
        self._stacked.setCurrentIndex(2)
        self._cross_label.show()
    
    def finish(self):
        print("[VLC player]: finish the stimuli presentation and close the player.")
        self._run_id += 1
        self._awaiting_feedback = False
        self._awaiting_feedback_trial_id = None
        self._feedback_trial_id = None
        self._feedback_rendering_trial_id = None
        self._stopped = True           # ставим флаг остановки
        self._player.stop()
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
        if not self._current_trial(run_id, trial_id) or not self._awaiting_first_frame:
            return
        self._schedule(self.VIDEO_READY_HIDE_MS, self._show_video_widget, run_id, trial_id)

    def update_volume(self, value):
        self._volume = value
        self._player.audio_set_volume(self._volume)
        self.volumeChanged.emit(self._volume)
        print("Volume:", self._volume)
    
    def get_last_volume(self):
        return self._volume

    

    


