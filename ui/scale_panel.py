from PyQt5.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout, QFrame


from utils.ui_helpers import (
    create_button, create_spin_box, create_check_box, create_combo_box, create_lineedit
)
from utils.layout_utils import create_hbox, create_vbox
from utils.logic_helpers import are_equal


class ScalePanel(QFrame):
    
    """ Панель с настройками отображения графика."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)

        # self.setObjectName("settings_panel")    # для привязки стиля
        # self.setMinimumWidth(150)

        self.settings = settings
        self._setup_ui()
        self._setup_layout()

   
    def _setup_ui(self):

        s = self.settings.plot_settings
        self.spin_box_scale = create_spin_box(-20, 20, s.scale_factor, parent=self)
        self.spin_box_max_value = create_spin_box(-100, 100, s.ymax, parent=self)
        self.spin_box_min_value = create_spin_box(-100, 100, s.ymin, parent=self)
        self.spin_box_scale_offset = create_spin_box(-100, 100, s.scale_offset)
        self.spin_box_time_range = create_spin_box(1, 20, int(s.time_range_ms//1000))

        s = self.settings.processing_settings
        idx = 1 if s.tkeo else 0
        self.combobox_signal_type = create_combo_box(["EMG", "TKEO"], curr_item_idx=idx, parent=self)  # show tkeo or filtered emg
        self.combobox_montage = create_combo_box(s.montage_list, curr_item_idx=s.montage, parent=self)  # bipolar or monopolar montage
        self.spin_box_monopolar = create_spin_box(0, 100, s.emg_channels_monopolar)
        self.spin_box_bipolar_1 = create_spin_box(0, 100, s.emg_channels_bipolar[0])
        self.spin_box_bipolar_2 = create_spin_box(0, 100, s.emg_channels_bipolar[1])

    def _setup_layout(self):
        
        layout = QVBoxLayout(self)
        layout.addLayout(create_hbox([QLabel("Scale factor:"), self.spin_box_scale]))
        # layout.addLayout(create_hbox([QLabel("y offset:"), self.spin_box_scale_offset]))
        layout.addLayout(create_hbox([QLabel("ymin:"), self.spin_box_min_value, QLabel("ymax:"), self.spin_box_max_value]))
        layout.addLayout(create_hbox([QLabel("Time range:"), self.spin_box_time_range, QLabel("s")]))

        layout.addLayout(create_hbox([QLabel("Signal:"), self.combobox_signal_type]))
        layout.addLayout(create_hbox([QLabel("Montage:"), self.combobox_montage]))
        layout.addLayout(create_hbox([QLabel("Monopolar:"), self.spin_box_monopolar]))
        layout.addLayout(create_hbox([QLabel("Bipolar:"), self.spin_box_bipolar_1, self.spin_box_bipolar_2]))

        layout.setContentsMargins(0, 0, 0, 0)  # убираем все внешние отступы
        layout.setSpacing(0)  # убираем промежутки между виджетами
        layout.addStretch()


