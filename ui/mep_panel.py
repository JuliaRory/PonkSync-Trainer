from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from utils.layout_utils import create_hbox
from utils.ui_helpers import create_button, create_spin_box


class MEPPlotsWindow(QWidget):
    settingsChanged = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MEP plots")
        self.resize(1400, 650)

        self.settings = settings.mep_settings
        self._epochs = deque(maxlen=self.settings.n_plots)
        self._amps = deque(maxlen=self.settings.n_plots)

        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._rebuild_plots()

    def _setup_ui(self):
        self._controls = QFrame(self)

        self.spin_n_plots = create_spin_box(1, 20, self.settings.n_plots, parent=self._controls, w=60)
        self.spin_epoch_start = create_spin_box(-1000, 0, self.settings.epoch_start_ms, parent=self._controls, w=70)
        self.spin_epoch_end = create_spin_box(1, 2000, self.settings.epoch_end_ms, parent=self._controls, w=70)
        self.spin_plot_start = create_spin_box(-1000, 1000, self.settings.plot_start_ms, parent=self._controls, w=70)
        self.spin_plot_end = create_spin_box(-1000, 2000, self.settings.plot_end_ms, parent=self._controls, w=70)
        self.spin_amp_thr = create_spin_box(
            0,
            100,
            self.settings.amp_threshold_mv,
            data_type="float",
            decimals=2,
            step=0.05,
            parent=self._controls,
            w=70,
        )
        self.spin_ymax = create_spin_box(
            0.1,
            100,
            self.settings.max_amp_mV,
            data_type="float",
            decimals=1,
            step=0.5,
            parent=self._controls,
            w=70,
        )
        self.button_apply = create_button("Apply", parent=self._controls, w=90)

        self.label_above_thr = QLabel("", self)
        self.label_mean_amp = QLabel("Mean MEP amp: -- mV", self)

        self._plot_area = pg.GraphicsLayoutWidget(self)
        self._plot_area.setBackground("w")
        self._plot_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _setup_layout(self):
        controls_layout = QVBoxLayout(self._controls)
        controls_layout.addLayout(create_hbox([QLabel("N:"), self.spin_n_plots]))
        controls_layout.addLayout(create_hbox([QLabel("Epoch:"), self.spin_epoch_start, QLabel("to"), self.spin_epoch_end, QLabel("ms")]))
        controls_layout.addLayout(create_hbox([QLabel("Plot:"), self.spin_plot_start, QLabel("to"), self.spin_plot_end, QLabel("ms")]))
        controls_layout.addLayout(create_hbox([QLabel("Amp thr:"), self.spin_amp_thr, QLabel("mV")]))
        controls_layout.addLayout(create_hbox([QLabel("Y max:"), self.spin_ymax, QLabel("mV")]))
        controls_layout.addWidget(self.button_apply)
        controls_layout.addWidget(self.label_above_thr)
        controls_layout.addWidget(self.label_mean_amp)
        controls_layout.addStretch()

        layout = QGridLayout(self)
        layout.addWidget(self._controls, 0, 0, 1, 1)
        layout.addWidget(self._plot_area, 0, 1, 1, 5)
        layout.setColumnStretch(1, 1)

    def _setup_connections(self):
        self.button_apply.clicked.connect(self.apply_settings)

    def apply_settings(self):
        self.settings.n_plots = int(self.spin_n_plots.value())
        self.settings.epoch_start_ms = int(self.spin_epoch_start.value())
        self.settings.epoch_end_ms = int(self.spin_epoch_end.value())
        self.settings.plot_start_ms = int(self.spin_plot_start.value())
        self.settings.plot_end_ms = int(self.spin_plot_end.value())
        self.settings.amp_threshold_mv = float(self.spin_amp_thr.value())
        self.settings.max_amp_mV = float(self.spin_ymax.value())

        if self.settings.epoch_start_ms >= self.settings.epoch_end_ms:
            self.settings.epoch_end_ms = self.settings.epoch_start_ms + 1
            self.spin_epoch_end.setValue(self.settings.epoch_end_ms)
        if self.settings.plot_start_ms >= self.settings.plot_end_ms:
            self.settings.plot_end_ms = self.settings.plot_start_ms + 1
            self.spin_plot_end.setValue(self.settings.plot_end_ms)

        old_epochs = list(self._epochs)[: self.settings.n_plots]
        old_amps = list(self._amps)[: self.settings.n_plots]
        self._epochs = deque(old_epochs, maxlen=self.settings.n_plots)
        self._amps = deque(old_amps, maxlen=self.settings.n_plots)
        self._rebuild_plots()
        self._redraw_all()
        self.settingsChanged.emit()

    def _rebuild_plots(self):
        self._plot_area.clear()
        self._plots = []
        self._curves = []

        n_cols = min(5, self.settings.n_plots)
        for i in range(self.settings.n_plots):
            row = i // n_cols
            col = i % n_cols
            plot = self._plot_area.addPlot(row=row, col=col)
            plot.showGrid(x=True, y=True, alpha=0.35)
            plot.setLabel("bottom", "ms")
            if col == 0:
                plot.setLabel("left", "mV")
            plot.setYRange(-self.settings.max_amp_mV, self.settings.max_amp_mV)
            plot.setXRange(self.settings.plot_start_ms, self.settings.plot_end_ms)
            plot.setTitle(f"#{i + 1}")
            curve = plot.plot([], [], pen=pg.mkPen((20, 90, 220), width=2))
            self._plots.append(plot)
            self._curves.append(curve)

        self._update_counter_label()

    def add_mep(self, mep):
        self._epochs.appendleft(mep)
        self._amps.appendleft(self._amplitude_for_plot_window(mep))
        self._redraw_all()

    def set_record_mean(self, mean_amp, n_epochs, saved_path=None):
        if n_epochs <= 0 or not np.isfinite(mean_amp):
            self.label_mean_amp.setText("Mean MEP amp: -- mV")
            return
        self.label_mean_amp.setText(f"Mean MEP amp: {mean_amp:.2f} mV (n={n_epochs})")

    def _redraw_all(self):
        for i, curve in enumerate(self._curves):
            if i >= len(self._epochs):
                curve.setData([], [])
                self._plots[i].setTitle(f"#{i + 1}")
                continue

            mep = self._epochs[i]
            time_ms = mep["time_ms"]
            epoch = mep["epoch_mV"]
            mask = (time_ms >= self.settings.plot_start_ms) & (time_ms <= self.settings.plot_end_ms)
            curve.setData(time_ms[mask], epoch[mask])

            amp = self._amps[i]
            title = f"#{i + 1}"
            if np.isfinite(amp):
                title = f"{title}: {amp:.2f} mV"
            self._plots[i].setTitle(title)
            self._plots[i].setYRange(-self.settings.max_amp_mV, self.settings.max_amp_mV)
            self._plots[i].setXRange(self.settings.plot_start_ms, self.settings.plot_end_ms)

        self._update_counter_label()

    def _amplitude_for_plot_window(self, mep):
        time_ms = mep["time_ms"]
        epoch = mep["epoch_mV"]
        mask = (time_ms >= self.settings.plot_start_ms) & (time_ms <= self.settings.plot_end_ms)
        if not np.any(mask):
            return np.nan
        data = epoch[mask]
        if data.size == 0 or not np.any(np.isfinite(data)):
            return np.nan
        return float(np.nanmax(data) - np.nanmin(data))

    def _update_counter_label(self):
        amps = np.asarray(list(self._amps), dtype=float)
        count = int(np.sum(amps[np.isfinite(amps)] > self.settings.amp_threshold_mv))
        self.label_above_thr.setText(f"Above {self.settings.amp_threshold_mv:.2f} mV: {count}/{self.settings.n_plots}")

