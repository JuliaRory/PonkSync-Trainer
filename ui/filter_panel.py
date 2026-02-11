from PyQt5.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QVBoxLayout


from utils.ui_helpers import (
    create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox, create_lineedit
)
from utils.layout_utils import create_hbox, create_vbox
from utils.logic_helpers import are_equal


class SettingsPanel(QFrame):
    
    """ Панель с настройками."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)

        # self.setObjectName("settings_panel")    # для привязки стиля
        # self.setMinimumWidth(150)

        self.settings = settings
        self._setup_ui()
        self._setup_layout()
    
    def _setup_ui(self):
        self.combobox_signal_type = create_combo_box(["EMG", "TKEO"], curr_item_idx=0, parent=self)  # show tkeo or filtered emg

        
    
    def create_filter_settings(self):

        # 5-150 Hz Butterworth bandpass filter 
        label_butterworth = QLabel('Butterworth filter', self)
        label_order = QLabel('order', self)
        spin_box_order = self.spin_box(0, 20, self.butter_order)
        spin_box_order.valueChanged[int].connect(self.set_butter_order)
        self.check_box_butter = self.check_box(True, 'use filter?')
        label_lower_fr = QLabel('Lower cut-off frequency', self)
        box_lower_fr = self.spin_box_with_unit(unit='Hz', min=0, max=500, value=self.butter_lower_fr, function=self.set_butter_lower_fr)
        self.check_box_lower_fr = self.check_box(True, 'use?')
        label_upper_fr = QLabel('Upper cut-off frequency', self)
        box_upper_fr = self.spin_box_with_unit(unit='Hz', min=0, max=500, value=self.butter_upper_fr, function=self.set_butter_upper_fr)
        self.check_box_upper_fr = self.check_box(True, 'use?')

        # 50 Hz Notch filter
        label_notch = QLabel('Notch filter', self)
        label_notch_fr = QLabel('frequency', self)
        box_notch_fr = self.spin_box_with_unit(unit='Hz', min=0, max=500, value=self.notch_fr, function=self.set_notch_fr)
        self.check_box_notch = self.check_box(True, 'use?')
        label_notch_width = QLabel('width', self)
        box_notch_width = self.spin_box_with_unit(unit='Hz', min=0, max=500, value=self.notch_width, function=self.set_notch_width)

        row = 0
        layout.addWidget(self.check_box_show_emg, row, 0, 1, 3)
        row += 1
        layout.addWidget(self.check_box_show_tkeo_emg, row, 0, 1, 3)
        row += 1
        layout.addWidget(label_butterworth, row, 0, 1, 3, Qt.AlignCenter)
        row += 1
        layout.addWidget(label_order, row, 0)
        layout.addWidget(spin_box_order, row, 1)
        layout.addWidget(self.check_box_butter, row, 2)
        row += 1
        layout.addWidget(label_lower_fr, row, 0)
        layout.addWidget(box_lower_fr, row, 1)
        layout.addWidget(self.check_box_lower_fr, row, 2)
        row += 1
        layout.addWidget(label_upper_fr, row, 0)
        layout.addWidget(box_upper_fr, row, 1)
        layout.addWidget(self.check_box_upper_fr, row, 2)
        row += 1
        layout.addWidget(label_notch, row, 0, 1, 3, Qt.AlignCenter)
        row += 1
        layout.addWidget(label_notch_fr, row, 0)
        layout.addWidget(box_notch_fr, row, 1)
        layout.addWidget(self.check_box_notch, row, 2)
        row += 1
        layout.addWidget(label_notch_width, row, 0)
        layout.addWidget(box_notch_width, row, 1)
        
        self.box_filter_settings.setLayout(layout)
