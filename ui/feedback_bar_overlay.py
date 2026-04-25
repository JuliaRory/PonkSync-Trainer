import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPainter, QPen
from PyQt5.QtWidgets import QWidget

from ui.feedback_graph import get_error_color, get_text_color


class FeedbackBarOverlay(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._values = np.array([], dtype=float)
        self._has_input = False
        self._zero_offset_px = 350
        self._line_width = 6
        self._label_step = 40

        #self.hide()

    def set_values(self, values):
        arr = np.atleast_1d(np.asarray(values, dtype=float))
        self._has_input = arr.size > 0
        self._values = arr[np.isfinite(arr)]
        self.setVisible(self._has_input)
        self.update()

    def clear(self):
        self._values = np.array([], dtype=float)
        self._has_input = False
        self.hide()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._has_input:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._values.size == 0:
            painter.setPen(QPen(get_text_color(self.settings.feedback_bar_scale_ms), 1))
            painter.setFont(QFont("Arial", 28, QFont.Bold))
            painter.drawText(self.rect(), Qt.AlignCenter, "not detected")
            painter.end()
            return

        center_x = self.width() // 2
        center_y = self.height() // 2
        zero_x = center_x + self._zero_offset_px
        line_height = self.settings.feedback_bar_height_px
        top_y = center_y - line_height // 2
        bottom_y = center_y + line_height // 2
        px_per_ms = self._get_px_per_ms()

        for idx, value in enumerate(self._values):
            x = int(np.clip(zero_x + value * px_per_ms, 0, self.width() - 1))
            color = get_error_color(abs(value))[0]
            text_color = get_text_color(abs(value))

            painter.setPen(QPen(color, self._line_width))
            painter.drawLine(x, top_y, x, bottom_y)

            label = f"{int(value)}"
            painter.setPen(text_color)
            painter.setFont(QFont("Arial", 24, QFont.Bold))

            text_width = painter.fontMetrics().horizontalAdvance(label)
            text_x = max(0, min(x - text_width // 2, self.width() - text_width))
            text_y = max(30, top_y - 20 - idx * self._label_step)
            painter.drawText(text_x, text_y, label)

        painter.end()

    def _get_px_per_ms(self):
        scale_ms = self.settings.feedback_bar_scale_ms
        if scale_ms == 0:
            return 0.0
        return self.settings.feedback_bar_scale_px / scale_ms
