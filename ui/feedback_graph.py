import sys
import math
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSpinBox, QLabel
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPolygonF, QPainterPath, QPixmap

import os

ERROR_COLORS = {
    0: QColor(0, 255, 0),        # Ярко-зеленый (идеально)
    1: QColor(144, 238, 144),    # Светло-зеленый (почти идеально)
    2: QColor(255, 255, 0),      # Желтый (среднее отклонение)
    3: QColor(255, 165, 0),      # Оранжевый (сильное отклонение)
    4: QColor(255, 0, 0)         # Ярко-красный (критическое отклонение)
}
# ERROR_COLORS = {
#     0: QColor(0, 255, 100),     # Ярко-зеленый с синим оттенком
#     1: QColor(150, 255, 100),   # Светло-зеленый
#     2: QColor(255, 255, 100),   # Желтый
#     3: QColor(255, 180, 100),   # Оранжевый
#     4: QColor(255, 100, 100)    # Розовато-красный
# }

# def get_text_color(value, max_error=350):
#     # Нормализуем значение от 0 до 1
#     ratio = min(abs(value) / max_error, 1.0)
    
#     # Определяем индекс цвета (0-4)
#     if ratio == 0:
#         color_index = 0
#     elif ratio <= 0.25:
#         color_index = 1
#     elif ratio <= 0.5:
#         color_index = 2
#     elif ratio <= 0.75:
#         color_index = 3
#     else:
#         color_index = 4
#     return ERROR_COLORS[color_index]

ERROR_COLORS_10 = {
    0: QColor(0, 255, 0),        # #00FF00 - ярко-зеленый (идеально)
    1: QColor(80, 255, 0),       # #50FF00 - зеленый с желтым оттенком
    2: QColor(140, 255, 0),      # #8CFF00 - желто-зеленый
    3: QColor(200, 255, 0),      # #C8FF00 - зеленовато-желтый
    4: QColor(255, 255, 0),      # #FFFF00 - желтый
    5: QColor(255, 200, 0),      # #FFC800 - желто-оранжевый
    6: QColor(255, 140, 0),      # #FF8C00 - оранжевый
    7: QColor(255, 80, 0),       # #FF5000 - красно-оранжевый
    8: QColor(255, 40, 0),       # #FF2800 - оранжево-красный
    9: QColor(255, 0, 0)         # #FF0000 - ярко-красный (критически)
}

def get_text_color(value, max_error=350):
    """Компактная версия с 10 цветами"""
    ratio = min(abs(value) / max_error, 1.0)
    color_index = min(int(ratio * 10), 9)  # 0-9
    return ERROR_COLORS_10[color_index]

def get_error_color(value, max_error=350):
    """
    Возвращает цвет от зеленого до красного в зависимости от значения
    value: текущее значение ошибки
    max_error: максимальное значение ошибки (при котором цвет красный)
    """

    ratio = min(abs(value) / max_error, 1.0)
    
    # RGB компоненты
    # Зеленый: (0, 255, 0) -> Красный: (255, 0, 0)
    # red = int(255 * ratio)
    # green = int(255 * (1 - ratio))
    # blue = 0

    # Добавляем синий компонент для яркости
    red = int(255 * ratio)
    green = int(255 * (1 - ratio))
    blue = int(120 * (1 - ratio))  # синий делает зеленый ярче на сером

    
    return QColor(red, green, blue), QColor(red, green, blue, 100)


class FeedbackGraph(QWidget):
    def __init__(self, w, h, parent=None):
        super().__init__(parent)

        self.setFixedSize(w, h)

        #Фон просто серый с фотодатчиком
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        # self.setStyleSheet("background:transparent;")

        # Размеры осей
        self.axis_range = 500
        self.axis_margin = 50  # Отступ от краёв виджета
        
        # Параметры треугольника
        self.base_width = 80  # Ширина нижней стороны (лежит на оси X)
        self.vertex_x = 30    # Положение вершины по оси X
        
        # Фиксированная высота вершины (0.9 от размера оси Y)
        self.vertex_y_ratio = 0.9

        # цвета
        self.triangle_color = get_error_color(0)
        self.text_color = get_text_color(0)
        
        # Флаги отображения
        self.show_triangle = True
        self.show_measure_line = True
        self.show_label = True
        
        # Для хранения преобразований координат
        self.transform = None

    
    def set_axis_range(self, value):
        """Устанавливает диапазон осей (от -value до +value)"""
        self.axis_range = abs(value)
        self.update()
    
    def set_triangle_params(self, base_width=None, vertex_x=None):
        """Устанавливает параметры треугольника"""
        if base_width is not None:
            self.base_width = base_width
        if vertex_x is not None:
            self.vertex_x = vertex_x
            self.triangle_color = get_error_color(abs(vertex_x))
            self.text_color = get_text_color(abs(vertex_x))
        self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        """Основной метод рисования"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Создаём преобразование мировых координат в координаты виджета
        self.setup_coordinate_transform()
        
        # Рисуем оси
        self.draw_axes(painter)
        
        # Рисуем треугольник
        if self.show_triangle:
            self.draw_triangle(painter)
        
        # Рисуем измерительную линию и надпись
        if self.show_measure_line:
            self.draw_measure_line(painter)
            if self.show_label:
                self.draw_label(painter)
        
        painter.end()
    
    def setup_coordinate_transform(self):
        """Настраивает преобразование координат"""
        w, h = self.width(), self.height()
        
        # Центр виджета
        center_x = w // 2
        center_y = h // 2
        
        # Масштаб: пикселей на единицу
        scale_x = (w - 2 * self.axis_margin) / (2 * self.axis_range)
        scale_y = (h - 2 * self.axis_margin) / (2 * self.axis_range)
        
        # Выбираем минимальный масштаб для сохранения пропорций
        self.scale = min(scale_x, scale_y)
        
        # Смещение для центрирования
        self.offset_x = center_x
        self.offset_y = center_y
        
        # Сохраняем преобразование для преобразования координат
        self.transform = lambda x, y: (
            int(self.offset_x + x * self.scale),
            int(self.offset_y - y * self.scale)  # Минус из-за того, что Y вниз в Qt
        )
    
    def world_to_widget(self, x, y):
        """Преобразует мировые координаты в координаты виджета"""
        return self.transform(x, y)
    
    def draw_axes(self, painter):
        """Рисует оси X и Y с центром в (0,0)"""
        painter.setPen(QPen(Qt.black, 2))
        
        w, h = self.width(), self.height()
        
        # Получаем границы в мировых координатах
        world_left = -self.axis_range
        world_right = self.axis_range
        world_bottom = -self.axis_range
        world_top = self.axis_range
        
        # Преобразуем в координаты виджета
        left_x, _ = self.world_to_widget(world_left, 0)
        right_x, _ = self.world_to_widget(world_right, 0)
        _, top_y = self.world_to_widget(0, world_top)
        _, bottom_y = self.world_to_widget(0, world_bottom)
        
        # Основная ось Y через центр
        center_x, _ = self.world_to_widget(0, 0)
        painter.drawLine(center_x, top_y, center_x, bottom_y)
        
        # Ось X (горизонтальная через центр)
        _, center_y = self.world_to_widget(0, 0)
        painter.drawLine(left_x, bottom_y, right_x, bottom_y)
        
        # Подписи осей
        # painter.setFont(QFont("Arial", 12, QFont.Bold))
        # painter.drawText(right_x - 20, center_y - 15, "X")
        # painter.drawText(center_x + 15, top_y + 20, "Y")
    
    def draw_triangle(self, painter):
        """Рисует треугольник с основанием на оси X"""
        painter.setPen(QPen(self.triangle_color[0], 2))
        painter.setBrush(QBrush(self.triangle_color[1]))  # Полупрозрачный
        
        # Вершина треугольника
        vertex_y = self.axis_range * self.vertex_y_ratio
        vertex = QPointF(*self.world_to_widget(self.vertex_x, vertex_y))
        
        # Основание треугольника (на оси Y=0)
        base_left = self.world_to_widget(self.vertex_x - self.base_width/2, -self.axis_range)
        base_right = self.world_to_widget(self.vertex_x + self.base_width/2, -self.axis_range)
        base_center = self.world_to_widget(self.vertex_x, 0)
        
        # Создаем треугольник
        triangle = QPolygonF([
            QPointF(base_left[0], base_left[1]),      # Левая точка основания
            QPointF(base_right[0], base_right[1]),    # Правая точка основания
            vertex                                      # Вершина
        ])
        
        painter.drawPolygon(triangle)
        
        # Рисуем маленький кружок на вершине
        painter.setBrush(QBrush(self.triangle_color[0]))
        painter.drawEllipse(vertex, 4, 4)
    
    def draw_measure_line(self, painter):
        """Рисует горизонтальную линию со стрелками от оси Y до вершины"""
        painter.setPen(QPen(Qt.blue, 2))
        
        # Получаем координаты
        vertex_y = self.axis_range * self.vertex_y_ratio
        vertex_widget = self.world_to_widget(self.vertex_x, vertex_y)
        axis_widget = self.world_to_widget(0, vertex_y)
        
        # Рисуем линию
        painter.drawLine(axis_widget[0], axis_widget[1], 
                        vertex_widget[0], vertex_widget[1])
        
        # Рисуем стрелки на концах
        self.draw_arrow(painter, axis_widget, vertex_widget)
        self.draw_arrow(painter, vertex_widget, axis_widget)
    
    def draw_arrow(self, painter, from_point, to_point):
        """Рисует стрелку на конце линии"""
        # Направление линии
        dx = to_point[0] - from_point[0]
        dy = to_point[1] - from_point[1]
        
        # Длина линии
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0:
            return
        
        # Нормализованное направление
        dx /= length
        dy /= length
        
        # Размер стрелки
        arrow_size = 10
        
        # Точка наконечника стрелки
        tip_x = to_point[0] - dx * arrow_size * 0.5
        tip_y = to_point[1] - dy * arrow_size * 0.5
        
        # Перпендикулярное направление
        perp_x = -dy
        perp_y = dx
        
        # Точки основания стрелки
        left_x = tip_x - dx * arrow_size + perp_x * arrow_size * 0.3
        left_y = tip_y - dy * arrow_size + perp_y * arrow_size * 0.3
        right_x = tip_x - dx * arrow_size - perp_x * arrow_size * 0.3
        right_y = tip_y - dy * arrow_size - perp_y * arrow_size * 0.3
        
        # Рисуем стрелку
        arrow_head = QPolygonF([
            QPointF(tip_x, tip_y),
            QPointF(left_x, left_y),
            QPointF(right_x, right_y)
        ])
        
        painter.setBrush(QBrush(QColor(52, 58, 64)))
        painter.drawPolygon(arrow_head)
    
    def draw_label(self, painter):
        """Рисует надпись с координатой вершины по X"""
        painter.setPen(self.text_color)
        painter.setFont(QFont("Arial", 24, QFont.Bold))
        
        vertex_y = self.axis_range #* self.vertex_y_ratio
        vertex_widget = self.world_to_widget(self.vertex_x, vertex_y)
        axis_widget = self.world_to_widget(0, vertex_y)
        
        # Размещаем надпись над линией
        label_x = (axis_widget[0] + vertex_widget[0]) // 2
        label_y = axis_widget[1] - 20
        
        painter.drawText(label_x - 40, label_y, 
                        f"{self.vertex_x}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Прозрачный виджет с треугольником")
        self.setGeometry(100, 100, 800, 600)
        
        # Центральный виджет с фоном для демонстрации прозрачности
        central = QWidget()
        central.setStyleSheet("background-color: lightblue;")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Создаём контейнер с прозрачным фоном
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # Наш прозрачный виджет
        self.graphics = FeedbackGraph()
        self.graphics.setMinimumHeight(400)
        container_layout.addWidget(self.graphics)
        
        # Панель управления
        control_panel = QWidget()
        control_panel.setStyleSheet("background-color: white;")
        control_layout = QHBoxLayout(control_panel)
        
        # SpinBox для ширины основания
        control_layout.addWidget(QLabel("Ширина основания:"))
        self.base_spin = QSpinBox()
        self.base_spin.setRange(10, 200)
        self.base_spin.setValue(100)
        self.base_spin.valueChanged.connect(self.update_triangle)
        control_layout.addWidget(self.base_spin)
        
        # SpinBox для позиции вершины по X
        control_layout.addWidget(QLabel("Позиция вершины X:"))
        self.vertex_spin = QSpinBox()
        self.vertex_spin.setRange(-100, 100)
        self.vertex_spin.setValue(30)
        self.vertex_spin.valueChanged.connect(self.update_triangle)
        control_layout.addWidget(self.vertex_spin)
        
        # SpinBox для диапазона осей
        control_layout.addWidget(QLabel("Диапазон осей:"))
        self.range_spin = QSpinBox()
        self.range_spin.setRange(50, 200)
        self.range_spin.setValue(100)
        self.range_spin.valueChanged.connect(self.graphics.set_axis_range)
        control_layout.addWidget(self.range_spin)
        
        # Кнопки для показа/скрытия элементов
        btn_toggle = QPushButton("Скрыть/показать треугольник")
        btn_toggle.clicked.connect(self.toggle_triangle)
        control_layout.addWidget(btn_toggle)
        
        container_layout.addWidget(control_panel)
        layout.addWidget(container)
        
    def update_triangle(self):
        self.graphics.set_triangle_params(
            self.base_spin.value(), 
            self.vertex_spin.value()
        )
    
    def toggle_triangle(self):
        self.graphics.show_triangle = not self.graphics.show_triangle
        self.graphics.update()

if __name__ == '__main__':
    from PyQt5.QtWidgets import QLabel
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())