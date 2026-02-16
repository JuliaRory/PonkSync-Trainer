from PyQt5.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout, QFrame


from utils.ui_helpers import (
    create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox, create_lineedit
)
from utils.layout_utils import create_hbox, create_vbox
from utils.logic_helpers import are_equal



class FilterPanel(QFrame):
    
    """ Панель с настройками процессинга графика."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)

        # self.setObjectName("settings_panel")    # для привязки стиля
        # self.setMinimumWidth(150)

        self.settings = settings
        self._setup_ui()
        self._setup_layout()


    def _setup_ui(self):
        s = self.settings.processing_settings
        self.check_box_notch = create_check_box(s.do_notch, text="notch 50 Hz", parent=self)
        self.check_box_lowpass = create_check_box(s.do_lowpass, text="lowpass", parent=self)
        self.check_box_highpass = create_check_box(s.do_highpass, text="highpass", parent=self)
        self.spin_box_lower_freq = create_spin_box(0, 100, s.freq_low, parent=self)
        self.spin_box_upper_freq = create_spin_box(0, 5000, s.freq_high, parent=self)

    def _setup_layout(self):
        
        layout = QVBoxLayout(self)
        layout.addLayout(create_hbox([self.check_box_notch]))
        layout.addLayout(create_hbox([self.check_box_lowpass, self.spin_box_upper_freq, QLabel("Hz")]))
        layout.addLayout(create_hbox([self.check_box_highpass, self.spin_box_lower_freq, QLabel("Hz")]))

        layout.setContentsMargins(0, 0, 0, 0)  # убираем все внешние отступы
        layout.setSpacing(0)  # убираем промежутки между виджетами
        layout.addStretch()
    