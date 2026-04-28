import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt5.QtWidgets import QWidget


class FeedbackBarOverlay(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._values = np.array([], dtype=float)
        self._has_input = False
        self._zero_offset_px = 350
        self._line_width = 20
        self._line_height = 150
        self._label_step = 40

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
            painter.setPen(QPen(Qt.black, 1))
            painter.setFont(QFont("Arial", 28, QFont.Bold))
            painter.drawText(self.rect(), Qt.AlignCenter, "not detected")
            painter.end()
            return

        center_x = self.width() // 2
        center_y = self.height() // 2
        zero_x = center_x + self._zero_offset_px
        top_y = center_y - self._line_height // 2

        for idx, value in enumerate(self._values):
            x = int(np.clip(zero_x + value, 0, self.width() - self._line_width))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("black")))
            painter.drawRect(x - self._line_width // 2, top_y, self._line_width, self._line_height)

            label = f"{int(value)}"
            painter.setPen(QPen(Qt.black, 1))
            painter.setFont(QFont("Arial", 24, QFont.Bold))

            text_width = painter.fontMetrics().horizontalAdvance(label)
            text_x = max(0, min(x - text_width // 2, self.width() - text_width))
            text_y = max(30, top_y - 20 - idx * self._label_step)
            painter.drawText(text_x, text_y, label)

            print("DRAW")

        painter.end()
