from PyQt5.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout, QFrame


from utils.ui_helpers import (
    create_button, create_spin_box, create_check_box, create_combo_box, create_lineedit
)
from utils.layout_utils import create_hbox, create_vbox
from utils.logic_helpers import are_equal


class PeakDetectionPanel(QFrame):
    
    """ Панель с настройками выявления пиков."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)

        # self.setObjectName("settings_panel")    # для привязки стиля
        # self.setMinimumWidth(150)

        self.settings = settings
        self._setup_ui()
        self._setup_layout()

   
    def _setup_ui(self):

        s = self.settings.detection_settings

        self.spin_box_window_from = create_spin_box(-2000, 0, s.window_ms[0], parent=self)
        self.spin_box_window_until = create_spin_box(0, 2000, s.window_ms[1], parent=self)

        self.spin_box_threshold_mv = create_spin_box(0, 20, s.threshold_mv, step=0.01, data_type="float", parent=self)
        self.spin_box_threshold_curr = create_spin_box(0, 100000, s.threshold, parent=self)

        self.label_units = QLabel("...")
        # self.spin_box_min_value = create_spin_box(-100, 100, s.ymin, parent=self)
        # self.spin_box_scale_offset = create_spin_box(-100, 100, s.scale_offset, parent=self)
        # self.spin_box_time_range = create_spin_box(1, 20, int(s.time_range_ms//1000), parent=self)

        # self.combobox_signal_type = create_combo_box(["EMG", "TKEO"], curr_item_idx=0, parent=self)  # show tkeo or filtered emg
    
    def _setup_layout(self):
        
        layout = QVBoxLayout(self)
        layout.addLayout(create_hbox([QLabel("Окно детекции")]))
        layout.addLayout(create_hbox([QLabel("от"), self.spin_box_window_from, QLabel("до"), self.spin_box_window_until, QLabel("мс")]))
        layout.addLayout(create_hbox([QLabel("Порог"), self.spin_box_threshold_curr, self.label_units, QLabel("<==>"), self.spin_box_threshold_mv, QLabel("мВ")]))

        # layout.addLayout(create_hbox([QLabel("Time range:"), self.spin_box_time_range, QLabel("s")]))
        # layout.addLayout(create_hbox([QLabel("Signal:"), self.combobox_signal_type]))

        layout.setContentsMargins(0, 0, 0, 0)  # убираем все внешние отступы
        layout.setSpacing(0)  # убираем промежутки между виджетами
        layout.addStretch()


