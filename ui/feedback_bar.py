import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


ERROR_COLORS_10 = {
    0: QColor(0, 255, 0),
    1: QColor(80, 255, 0),
    2: QColor(140, 255, 0),
    3: QColor(200, 255, 0),
    4: QColor(255, 255, 0),
    5: QColor(255, 200, 0),
    6: QColor(255, 140, 0),
    7: QColor(255, 80, 0),
    8: QColor(255, 40, 0),
    9: QColor(255, 0, 0),
}


def get_text_color(value, max_error=350):
    ratio = min(abs(value) / max_error, 1.0)
    color_index = min(int(ratio * 10), 9)
    return ERROR_COLORS_10[color_index]


def get_error_color(value, max_error=350):
    ratio = min(abs(value) / max_error, 1.0)
    red = int(255 * ratio)
    green = int(255 * (1 - ratio))
    blue = int(120 * (1 - ratio))
    return QColor(red, green, blue), QColor(red, green, blue, 100)


class FeedbackBar(QWidget):
    def __init__(self, w, h, parent=None):
        super().__init__(parent)

        self.setFixedSize(w, h)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

        self._zero_offset_px = 210
        self._rect_width = 20
        self._rect_height = 100
        self._label_offset_y = 20

        self.vertex_x = 0
        self.triangle_color = get_error_color(0)
        self.text_color = get_text_color(0)

        self.show_triangle = True
        self.show_measure_line = True
        self.show_label = True

    def set_axis_range(self, value):
        self.update()

    def set_triangle_params(self, base_width=None, vertex_x=None):
        if vertex_x is not None:
            self.vertex_x = int(vertex_x)
            
            self.triangle_color = get_error_color(vertex_x)
            self.text_color = get_text_color(vertex_x)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.show_triangle:
            self.draw_bar(painter)
        if self.show_label:
            self.draw_label(painter)

        painter.end()

    def draw_bar(self, painter):
        coef = 0.5
        
        center_x = self.width() // 2 + self._zero_offset_px + int(coef * self.vertex_x)
        # print("DELAY:", self.vertex_x, ". VERTEX:",  int(coef * self.vertex_x))
        # print("RECT:", center_x)
        center_y = self.height() // 2

        rect_x = center_x - self._rect_width // 2
        rect_y = center_y - self._rect_height // 2

        painter.setPen(QPen(self.triangle_color[0], 2))
        painter.setBrush(QBrush(self.triangle_color[1]))
        painter.drawRect(rect_x, rect_y, self._rect_width, self._rect_height)

    def draw_label(self, painter):
        coef = 0.5
        center_x = self.width() // 2 + self._zero_offset_px + int(coef * self.vertex_x)-20
        center_y = self.height() // 2

        label = f"{self.vertex_x}"
        text_width = painter.fontMetrics().horizontalAdvance(label)
        text_x = center_x - text_width // 2
        text_y = center_y - self._rect_height // 2 - self._label_offset_y

        painter.setPen(self.text_color)
        painter.setFont(QFont("Arial", 30, QFont.Bold))
        painter.drawText(text_x, text_y, label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Feedback Bar Preview")
        self.setGeometry(100, 100, 800, 600)

        central = QWidget()
        central.setStyleSheet("background-color: lightblue;")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        container = QWidget()
        container_layout = QVBoxLayout(container)

        self.graphics = FeedbackBar(800, 400)
        self.graphics.setMinimumHeight(400)
        container_layout.addWidget(self.graphics)

        control_panel = QWidget()
        control_panel.setStyleSheet("background-color: white;")
        control_layout = QHBoxLayout(control_panel)

        control_layout.addWidget(QLabel("Delay:"))
        self.vertex_spin = QSpinBox()
        self.vertex_spin.setRange(-350, 350)
        self.vertex_spin.setValue(30)
        self.vertex_spin.valueChanged.connect(self.update_bar)
        control_layout.addWidget(self.vertex_spin)

        btn_toggle = QPushButton("Show/Hide Bar")
        btn_toggle.clicked.connect(self.toggle_bar)
        control_layout.addWidget(btn_toggle)

        container_layout.addWidget(control_panel)
        layout.addWidget(container)

        self.update_bar()

    def update_bar(self):
        self.graphics.set_triangle_params(vertex_x=self.vertex_spin.value())

    def toggle_bar(self):
        self.graphics.show_triangle = not self.graphics.show_triangle
        self.graphics.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
