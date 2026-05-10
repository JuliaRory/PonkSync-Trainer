import os

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from logic.mep_movement_detection import (
    MovementDetectionSettings,
    analyze_record_file,
    default_results_dir_for_record,
    save_analysis_outputs,
)
from utils.ui_helpers import create_button, create_spin_box


class MEPMovementDetectionWindow(QWidget):
    def __init__(self, record_path, app_settings=None, parent=None):
        super().__init__(parent)
        self.record_path = record_path
        self.settings = MovementDetectionSettings()
        self._apply_app_defaults(app_settings)
        self.result = None
        self.saved_figure_path = None
        self.saved_table_path = None
        self._plot_signal_mode = "TKEO"

        self.setWindowTitle("MEP movement delay detection")
        self.resize(1500, 850)

        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        if self.record_path:
            self.recalculate()

    def _apply_app_defaults(self, app_settings):
        if app_settings is None:
            return
        self.settings.fs = app_settings.Fs
        self.settings.notch_hz = app_settings.processing_settings.notch_fr
        self.settings.notch_width_hz = app_settings.processing_settings.notch_width
        self.settings.bandpass_high_hz = max(app_settings.processing_settings.freq_high, 450)

    def _setup_ui(self):
        self._settings_frame = QFrame(self)
        self._settings_scroll = QScrollArea(self)
        self._settings_scroll.setWidgetResizable(True)
        self._settings_scroll.setWidget(self._settings_frame)

        self._button_choose_record = create_button("Выбрать record", parent=self)
        self._button_recalculate = create_button("Рассчитать", parent=self)
        self._combo_plot_signal = QComboBox(self)
        self._combo_plot_signal.addItems(["TKEO", "EMG"])
        self._label_record = QLabel("", self)
        self._label_record.setWordWrap(True)
        self._label_summary = QLabel("", self)
        self._label_summary.setWordWrap(True)
        self._label_saved = QLabel("", self)
        self._label_saved.setWordWrap(True)

        self._spinboxes = {}
        self._checkboxes = {}
        self._create_settings_widgets()

        self.figure = Figure(figsize=(10, 7), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self._update_record_label()

    def _create_settings_widgets(self):
        specs = [
            ("fs", "Fs, Hz", 100, 100000, 100, 1),
            ("trigger_bit", "trigger bit", 0, 15, 1, 0),
            ("emg_channel", "EMG channel", 0, 256, 1, 0),
            ("epoch_start_ms", "epoch from, ms", -5000, 1000, 10, 1),
            ("epoch_end_ms", "epoch to, ms", -1000, 5000, 10, 1),
            ("baseline_from_ms", "baseline from, ms", -5000, 1000, 10, 1),
            ("baseline_to_ms", "baseline to, ms", -5000, 1000, 10, 1),
            ("art_from_ms", "artifact from, ms", -1000, 1000, 0.5, 2),
            ("art_to_ms", "artifact to, ms", -1000, 1000, 0.5, 2),
            ("mep_from_ms", "MEP from, ms", -1000, 1000, 1, 1),
            ("mep_to_ms", "MEP to, ms", -1000, 1000, 1, 1),
            ("threshold_k", "threshold k", 0, 1000, 0.5, 2),
            ("baseline_percentile", "baseline percentile", 0, 100, 0.1, 2),
            ("prominence_k", "prominence k", 0, 1000, 0.5, 2),
            ("smooth_ms", "smooth, ms", 0, 200, 0.5, 2),
            ("min_width_ms", "min width, ms", 0, 200, 0.5, 2),
            ("min_distance_ms", "min distance, ms", 0, 1000, 1, 1),
            ("confirmation_window_ms", "confirmation, ms", 0, 1000, 1, 1),
            ("required_fraction", "required fraction", 0, 1, 0.05, 3),
            ("min_peak_area", "min peak area", 0, 1e-7, 1e-10, 12),
            ("min_emg_ptp_mV", "min EMG ptp, mV", 0, 10, 0.01, 3),
            ("emg_ptp_from_ms", "EMG ptp from, ms", -1000, 5000, 1, 1),
            ("emg_ptp_to_ms", "EMG ptp to, ms", -1000, 5000, 1, 1),
            ("better_candidate_area_ratio", "better area ratio", 0, 1000, 0.5, 2),
            ("better_candidate_min_separation_ms", "better separation, ms", 0, 1000, 1, 1),
            ("pre_tms_ignore_after_ms", "pre-TMS ignore after, ms", -1000, 1000, 1, 1),
            ("early_delay_ms", "early <", -1000, 1000, 1, 1),
            ("late_delay_ms", "late >", -1000, 1000, 1, 1),
            ("plot_from_ms", "plot from, ms", -5000, 5000, 10, 1),
            ("plot_to_ms", "plot to, ms", -5000, 5000, 10, 1),
            ("plot_ymax_mV", "scale, mV", 0.01, 100, 0.1, 2),
            ("notch_hz", "notch, Hz", 1, 1000, 1, 1),
            ("notch_width_hz", "notch width, Hz", 0.1, 100, 0.1, 2),
            ("bandpass_low_hz", "bandpass low, Hz", 0.1, 2000, 1, 1),
            ("bandpass_high_hz", "bandpass high, Hz", 1, 3000, 1, 1),
        ]

        int_attrs = {"trigger_bit", "emg_channel"}
        for attr, label, minimum, maximum, step, decimals in specs:
            data_type = "int" if attr in int_attrs else "float"
            spinbox = create_spin_box(
                minimum,
                maximum,
                getattr(self.settings, attr),
                data_type=data_type,
                decimals=decimals,
                step=step,
                parent=self._settings_frame,
                w=90,
            )
            self._spinboxes[attr] = (label, spinbox)

        self._checkboxes["detect_pre_tms"] = QCheckBox("detect pre-TMS", self._settings_frame)
        self._checkboxes["detect_pre_tms"].setChecked(self.settings.detect_pre_tms)
        self._checkboxes["invert_emg"] = QCheckBox("invert EMG", self._settings_frame)
        self._checkboxes["invert_emg"].setChecked(self.settings.invert_emg)

    def _setup_layout(self):
        settings_layout = QVBoxLayout(self._settings_frame)
        settings_layout.addWidget(self._label_record)
        settings_layout.addWidget(self._button_choose_record)
        settings_layout.addWidget(self._button_recalculate)
        settings_layout.addWidget(QLabel("Plot signal", self._settings_frame))
        settings_layout.addWidget(self._combo_plot_signal)
        settings_layout.addWidget(self._label_summary)
        settings_layout.addWidget(self._label_saved)

        grid = QGridLayout()
        row = 0
        for attr, (label, spinbox) in self._spinboxes.items():
            grid.addWidget(QLabel(label, self._settings_frame), row, 0)
            grid.addWidget(spinbox, row, 1)
            row += 1
        grid.addWidget(self._checkboxes["detect_pre_tms"], row, 0, 1, 2)
        grid.addWidget(self._checkboxes["invert_emg"], row + 1, 0, 1, 2)
        settings_layout.addLayout(grid)
        settings_layout.addStretch()

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._settings_scroll)
        splitter.addWidget(self.canvas)
        splitter.setSizes([340, 1160])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _setup_connections(self):
        self._button_choose_record.clicked.connect(self._choose_record)
        self._button_recalculate.clicked.connect(self.recalculate)
        self._combo_plot_signal.currentTextChanged.connect(self._on_plot_signal_changed)

    def _choose_record(self):
        start_dir = os.path.dirname(self.record_path) if self.record_path else os.path.abspath("data")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose record",
            start_dir,
            "HDF files (*.hdf *.hdf5 *.h5);;All files (*.*)",
        )
        if not path:
            return
        self.record_path = path
        self._update_record_label()
        self.recalculate()

    def _update_record_label(self):
        text = os.path.basename(self.record_path) if self.record_path else "record: --"
        self._label_record.setText(text)

    def _sync_settings_from_ui(self):
        for attr, (_, spinbox) in self._spinboxes.items():
            value = spinbox.value()
            if attr in {"trigger_bit", "emg_channel"}:
                value = int(value)
            setattr(self.settings, attr, value)
        self.settings.detect_pre_tms = self._checkboxes["detect_pre_tms"].isChecked()
        self.settings.invert_emg = self._checkboxes["invert_emg"].isChecked()

    def _on_plot_signal_changed(self, mode):
        self._plot_signal_mode = mode
        if self.result is not None:
            self._plot_result()
            self._save_outputs()

    def recalculate(self):
        if not self.record_path or not os.path.exists(self.record_path):
            QMessageBox.warning(self, "MEP movement detection", "Record file was not found.")
            return

        self._sync_settings_from_ui()
        try:
            self.result = analyze_record_file(self.record_path, self.settings)
        except Exception as exc:
            QMessageBox.warning(self, "MEP movement detection", str(exc))
            return

        self._update_summary()
        self._plot_result()
        self._save_outputs()

    def _update_summary(self):
        n_epochs = len(self.result["rows"])
        movement = self.result["movement_count"]
        early = self.result["early_count"]
        late = self.result["late_count"]
        has_mep = "yes" if self.result["has_mep"] else "no"
        self._label_summary.setText(
            f"Epochs: {n_epochs}. Movements: {movement}. Too early: {early}. Too late: {late}. MEP: {has_mep}."
        )

    def _plot_result(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        time = self.result["time"]
        if self._plot_signal_mode == "TKEO":
            epochs = self.result["tkeo_epochs"]
            scale = self._tkeo_plot_scale(epochs)
            ylabel = "TKEO epochs"
        else:
            epochs = self.result["emg_epochs"]
            scale = max(float(self.settings.plot_ymax_mV), 1e-6)
            ylabel = "EMG epochs"
        delays = self.result["delays"]
        rows = self.result["rows"]
        plot_mask = (time >= self.settings.plot_from_ms) & (time <= self.settings.plot_to_ms)
        if not np.any(plot_mask):
            plot_mask = np.ones_like(time, dtype=bool)

        spacing = scale * 2.8

        for idx, epoch in enumerate(epochs):
            y0 = idx * spacing
            delay = delays[idx] if idx < len(delays) else np.nan
            color = "#2f6b9a"
            if np.isfinite(delay) and delay < self.settings.early_delay_ms:
                color = "#b85450"
            elif np.isfinite(delay) and delay > self.settings.late_delay_ms:
                color = "#7b5db8"

            ax.plot(time[plot_mask], epoch[plot_mask] + y0, lw=0.8, color=color, alpha=0.85)
            ax.text(
                self.settings.plot_from_ms,
                y0,
                str(idx + 1),
                va="center",
                ha="right",
                fontsize=8,
                color="#555555",
            )

            if np.isfinite(delay):
                delay_idx = int(np.argmin(np.abs(time - delay)))
                ax.plot(delay, epoch[delay_idx] + y0, marker="o", ms=3.5, color="red", zorder=5)
                if idx < len(rows) and np.isfinite(rows[idx]["peak_time"]):
                    peak_idx = int(np.argmin(np.abs(time - rows[idx]["peak_time"])))
                    ax.plot(rows[idx]["peak_time"], epoch[peak_idx] + y0, marker="|", ms=8, color="black", zorder=5)

            if idx < len(rows):
                mep_amp = rows[idx].get("mep_amplitude_mV", np.nan)
                emg_ptp = rows[idx].get("emg_ptp_mV", np.nan)
                label_parts = []
                if np.isfinite(mep_amp):
                    label_parts.append(f"MEP {mep_amp:.2f}")
                if np.isfinite(emg_ptp):
                    label_parts.append(f"ptp {emg_ptp:.2f}")
                if label_parts:
                    ax.text(
                        self.settings.plot_to_ms,
                        y0,
                        " | ".join(label_parts),
                        va="center",
                        ha="left",
                        fontsize=7,
                        color="#333333",
                    )

        ax.axvspan(self.settings.art_from_ms, self.settings.art_to_ms, color="0.85", alpha=0.7)
        ax.axvspan(self.settings.mep_from_ms, self.settings.mep_to_ms, color="0.9", alpha=0.6)
        ax.axvspan(self.settings.emg_ptp_from_ms, self.settings.emg_ptp_to_ms, color="#e7f0ff", alpha=0.22)
        ax.axvline(self.settings.early_delay_ms, color="#b85450", lw=1, ls="--")
        ax.axvline(self.settings.late_delay_ms, color="#7b5db8", lw=1, ls="--")
        ax.axvline(0, color="black", lw=0.8)

        ax.set_xlim(self.settings.plot_from_ms, self.settings.plot_to_ms)
        ax.set_ylim(-spacing, max(spacing, len(epochs) * spacing))
        ax.set_xlabel("time [ms]")
        ax.set_ylabel(ylabel)
        ax.set_yticks([])
        ax.set_title(
            f"{self.result['record_name']} | "
            f"{self._plot_signal_mode} | "
            f"movements: {self.result['movement_count']} | "
            f"too early: {self.result['early_count']} | "
            f"too late: {self.result['late_count']}"
        )
        self.figure.tight_layout()
        self.canvas.draw()

    def _tkeo_plot_scale(self, epochs):
        if len(epochs) == 0:
            return 1e-10
        data = np.asarray(epochs, dtype=float)
        finite = data[np.isfinite(data)]
        if finite.size == 0:
            return 1e-10
        return max(float(np.nanpercentile(finite, 99)), 1e-12)

    def _save_outputs(self):
        output_dir = default_results_dir_for_record(self.record_path)
        self.saved_table_path, _ = save_analysis_outputs(self.result, output_dir=output_dir)
        stem = os.path.splitext(os.path.basename(self.record_path))[0]
        self.saved_figure_path = os.path.join(
            output_dir,
            f"{stem}_movement_detection.png",
        )
        self.figure.savefig(self.saved_figure_path, dpi=160)
        self._label_saved.setText(
            f"CSV: {self.saved_table_path}\nPNG: {self.saved_figure_path}"
        )
