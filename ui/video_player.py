import sys, os

import vlc
import time

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap


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
    _videoEnded = pyqtSignal()
    tripletStarted = pyqtSignal(bool)       # --> data_processor

    stimulus = pyqtSignal(str)
    
    def __init__(self, settings=None):
        super().__init__()  

        self._volume = settings.volume
        self.settings = settings 
        self.show_delay = False

        # Настройка экрана
        screens = QApplication.instance().screens()
        target_monitor = screens[self.settings.monitor - 1].geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()

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
        
        self._cross_figure_path = os.path.join(r"resources\stimuli", self.settings.cross_figure)
        self._triplet_video_path = os.path.join(r"resources\stimuli", self.settings.triplet_video)
        # final_fig_files = os.listdir(r"resources\final_fig")
        # self.final_pic_path = os.path.join(r"resources\final_fig", random.choice(final_fig_files))

        self._configure_player()
               
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

        # === Видео виджет ===
        self._configure_video_widget()
        
        # === Placeholder widget поверх всего ===
        self._configure_placeholder_widget()

        self._configure_feedback_widget()

        # === Подготовка последовательности ===
        self.media = self._instance.media_new(self._triplet_video_path)
        self.media.add_option(':start-time=1.56')
        self.media.parse_async()  # preload
        
    def _configure_video_widget(self):
        
        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self._video_widget)

        winid = int(self._video_widget.winId())
        self._player.set_hwnd(winid)

    def _configure_placeholder_widget(self):
        self._placeholder_widget = QLabel(self)

        self._main_cross_pic = QPixmap(self._cross_figure_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        self._placeholder_widget.setPixmap(self._main_cross_pic)
        
        self._placeholder_widget.setGeometry(self.rect())
        self._placeholder_widget.setAlignment(Qt.AlignCenter)
        self._placeholder_widget.setStyleSheet("background-color: black;")
        self._placeholder_widget.show()

        self._cross_dur_ms = self.settings.cross_ms      # проигрвать крест 

        # первый стимул
        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)

        print('[VLC player]: press Space to start.')

    def _configure_feedback_widget(self):
        self._feedback_widget = QLabel(self)
        self._feedback_widget.setStyleSheet("""
            font-size: 40px;
            font-weight: bold;
            color: blue;
        """)

        x = int(self.width() // 2 - 250)
        y = int(0.2 * self.height())
        width = 500
        height = 100

        self._feedback_widget.setGeometry(x, y, width, height)
        self._feedback_widget.setAlignment(Qt.AlignCenter)

        self._feedback_ms = self.settings.feedback_ms      # проигрвать крест 
        self._show_feedback_ms = self.settings.show_feedback 
        

    # ===============================
    # === цикл проигрывания видео ===
    # ===============================

    def _play_next_video(self):
        if self._stopped:
            print('[VLC player]: stimuli presentation has been stopped.')
            return

        self._placeholder_widget.show()
        
        # запустить следующее видео
        self._player.set_media(self.media)
        self._player.audio_set_volume(self._volume)

        self.tripletStarted.emit(True)
        self._player.play()

        # подготовить следующее видео
        self._current_index += 1
        self.currIdxChanged.emit(self._current_index)

        self._is_paused = False

        # Скрываем placeholder через 50ms после старта VLC
        delay = 50
        QTimer.singleShot(delay, self._placeholder_widget.hide)

        # Проверяем окончание видео каждые 50ms
        QTimer.singleShot(50, self._check_video_end)
    
    def _check_video_end(self):
        if self._stopped:
            return  # больше ничего не делаем
        if self._player.get_state() == vlc.State.Ended:
            # Сразу показываем placeholder перед следующим видео
            self._placeholder_widget.show()
            self.tripletStarted.emit(False)
            if self.show_delay:
                QTimer.singleShot(self._show_feedback_ms, self._check_feedback)
            else:
                QTimer.singleShot(self._cross_dur_ms, self._play_next_video)
        else:
            QTimer.singleShot(50, self._check_video_end)
    
    def _check_feedback(self):
        self._feedback_widget.setText(f"Delay: {self.delay_value} ms.")
        self._feedback_widget.show()
        self.show_delay = False
        QTimer.singleShot(self._feedback_ms, self._show_cross)

    
    def _show_cross(self):
        self._feedback_widget.hide()
        self._feedback_widget.repaint()
        self._placeholder_widget.show()
        QTimer.singleShot(self._cross_dur_ms, self._play_next_video)
        

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

    def show_feedback(self, delay):
        self.show_delay = True
        self.delay_value = delay

    # === показ стимулов ===
    def _on_space_pressed(self):
        # Последовательность ещё не запускалась -> начать показ стимулов
        if not self._sequence_started:
            print("[VLC player]: start the stimuli presentation.")
            self._sequence_started = True
            self.stimuliStarted.emit()
            self._is_paused = False
            self._play_next_video()
            return

        # Последовательность идёт -> остановить показ стимулов
        if not self._is_paused:
            print("[VLC player]: pause the stimuli presentation.")
            self._player.pause()
            self._is_paused = True
            self.stimuliPaused.emit()
            return

        # Показ стимулов на паузе -> продолжить
        if self._is_paused:
            print("[VLC player]: continue the stimuli presentation.")
            self._player.play()
            self._is_paused = False
            self.stimuliPaused.emit()

    def pause_video(self):
        # управление внешней кнопкой 
        self._on_space_pressed()

    def restart_sequence(self):
        print("[VLC player]: restart stimuli presentation.")
        self._player.stop()

        self._is_paused = False
        self._sequence_started = False
        self._stopped = False
        self._finished = False

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)
        self.stimulus.emit(self.video_names[self.order[self._current_index]-1])

        self._prepare_next_video()
        self._placeholder_widget.show()
    
    def finish(self):
        print("[VLC player]: finish the stimuli presentation and close the player.")
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
        
        QTimer.singleShot(0, self._videoEnded.emit)
        
    # === управление звуком === 
    def update_volume(self, value):
        self._volume = value
        self._player.audio_set_volume(self._volume)
        self.volumeChanged.emit(self._volume)
        print("Volume:", self._volume)
    
    def get_last_volume(self):
        return self._volume

    

    
