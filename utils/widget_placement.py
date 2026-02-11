from PyQt5.QtGui import QGuiApplication

def place_widget(widget, monitor=1, coordinates=(0, 0)):
    screens = QGuiApplication.screens()
    screen = screens[monitor-1]

    geo = screen.availableGeometry()
    x = geo.x() + coordinates[0]
    y = geo.y() + coordinates[1]

    widget.move(x, y)