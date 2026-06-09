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

        self.spin_box_threshold_mv = create_spin_box(0, 100, s.threshold_mv, step=0.01, data_type="float")
        self.spin_box_threshold_curr = create_spin_box(0, 100000, s.threshold, data_type="float", step=0.25)

        self.label_units = QLabel("...")
        self.check_box_relax = create_check_box(s.relax, "relax", parent=self)
        self.check_box_show_relax_mean = create_check_box(s.show_relax_mean, "среднее relax", parent=self)
        self.check_box_relax_gate = create_check_box(s.relax_gate_enabled, "ждать напр.", parent=self)
        self.spin_box_relax_window_ms = create_spin_box(1, 1000, s.relax_window_ms, parent=self)
        self.spin_box_relax_gate_window_ms = create_spin_box(1, 2000, s.relax_gate_window_ms, parent=self)
        self._update_relax_widgets()
        self.check_box_relax.stateChanged.connect(lambda _: self._update_relax_widgets())
        self.check_box_relax_gate.stateChanged.connect(lambda _: self._update_relax_widgets())

        self.spin_box_bit = create_spin_box(0, 8, s.bit, parent=self)
        # self.spin_box_min_value = create_spin_box(-100, 100, s.ymin, parent=self)
        # self.spin_box_scale_offset = create_spin_box(-100, 100, s.scale_offset, parent=self)
        # self.spin_box_time_range = create_spin_box(1, 20, int(s.time_range_ms//1000), parent=self)

        # self.combobox_signal_type = create_combo_box(["EMG", "TKEO"], curr_item_idx=0, parent=self)  # show tkeo or filtered emg
    
    def _setup_layout(self):
        
        layout = QVBoxLayout(self)
        layout.addLayout(create_hbox([QLabel("Окно детекции")]))
        layout.addLayout(create_hbox([QLabel("от"), self.spin_box_window_from, QLabel("до"), self.spin_box_window_until, QLabel("мс")]))
        layout.addLayout(create_hbox([QLabel("Порог"), self.spin_box_threshold_curr, self.label_units]))
        layout.addWidget(self.check_box_relax)
        layout.addLayout(create_hbox([QLabel("Окно relax"), self.spin_box_relax_window_ms, QLabel("мс")]))
        layout.addWidget(self.check_box_show_relax_mean)
        layout.addWidget(self.check_box_relax_gate)
        layout.addLayout(create_hbox([QLabel("Окно напр."), self.spin_box_relax_gate_window_ms, QLabel("мс")]))

        layout.addLayout(create_hbox([QLabel("Бит"), self.spin_box_bit]))

        # layout.addLayout(create_hbox([QLabel("Time range:"), self.spin_box_time_range, QLabel("s")]))
        # layout.addLayout(create_hbox([QLabel("Signal:"), self.combobox_signal_type]))

        layout.setContentsMargins(0, 0, 0, 0)  # убираем все внешние отступы
        layout.setSpacing(0)  # убираем промежутки между виджетами
        layout.addStretch()

    def _update_relax_widgets(self):
        relax_enabled = self.check_box_relax.isChecked()
        gate_enabled = relax_enabled and self.check_box_relax_gate.isChecked()
        self.spin_box_relax_window_ms.setEnabled(relax_enabled)
        self.check_box_show_relax_mean.setEnabled(relax_enabled)
        self.check_box_relax_gate.setEnabled(relax_enabled)
        self.spin_box_relax_gate_window_ms.setEnabled(gate_enabled)
