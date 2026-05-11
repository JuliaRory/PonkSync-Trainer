import json
import os
import re

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QLabel, QMessageBox, QVBoxLayout, QWidget

from scripts.calculate_meps import calculate_mep_amp, plot_all_epochs_ax
from utils.ui_helpers import create_button


class MEPAnalysisWindow(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("МВП")
        self.resize(1000, 650)

        self.settings = settings
        self._hdf_path = None
        self._subject = None
        self._record_name = None

        self._button_refresh = create_button("Обновить", parent=self)
        self._label_info = QLabel("МВП: --", self)
        self._figure = Figure(figsize=(9.5, 5.8))
        self._canvas = FigureCanvas(self._figure)

        layout = QVBoxLayout(self)
        layout.addWidget(self._button_refresh)
        layout.addWidget(self._label_info)
        layout.addWidget(self._canvas)

        self._button_refresh.clicked.connect(self.refresh_plot)

    def show_record(self, subject, record_name):
        self._subject = subject.strip()
        self._record_name = os.path.splitext(record_name.strip())[0]
        self._hdf_path = self._find_record_hdf(self._subject, self._record_name)
        if self._hdf_path is None:
            QMessageBox.warning(
                self,
                "МВП",
                f"Не найден HDF-файл для записи '{self._record_name}' в data/{self._subject}.",
            )
            return False

        self.refresh_plot()
        self.show()
        self.raise_()
        self.activateWindow()
        return True

    def refresh_plot(self):
        if not self._hdf_path:
            return

        bit = int(getattr(self.settings.mep_settings, "trigger_bit", 0))
        try:
            seq = self._load_sequence_for_record()
        except Exception:
            seq = None

        try:
            time, motor_epochs, rest_epochs, info = calculate_mep_amp(
                self._hdf_path,
                bit,
                seq,
                return_info=True,
            )
        except Exception as exc:
            QMessageBox.warning(self, "МВП", f"Не удалось построить МВП:\n{exc}")
            return

        for warning in info.get("warnings", []):
            QMessageBox.warning(self, "РњР’Рџ", warning)

        motor_mean = float(np.nanmean(_epoch_amplitudes(motor_epochs, time))) if motor_epochs.size else np.nan
        rest_mean = float(np.nanmean(_epoch_amplitudes(rest_epochs, time))) if rest_epochs.size else np.nan

        self._figure.clear()
        ax = self._figure.add_subplot(111)
        title = f"{self._subject}: motor vs rest, {self._record_name}"
        plot_all_epochs_ax(ax, time, motor_epochs, rest_epochs, "motor", "rest", title)
        self._figure.tight_layout()
        self._canvas.draw()

        self._label_info.setText(
            f"{os.path.basename(self._hdf_path)} | "
            f"{info.get('source', '--')} | bit {bit} | "
            f"motor: {motor_epochs.shape[0]} epochs, mean {motor_mean:.3f} mV | "
            f"rest: {rest_epochs.shape[0]} epochs, mean {rest_mean:.3f} mV"
        )

    def _find_record_hdf(self, subject, record_name):
        folder = os.path.join("data", subject)
        if not os.path.isdir(folder):
            return None

        exact_candidates = []
        if os.path.splitext(record_name)[1].lower() in [".hdf", ".hdf5"]:
            exact_candidates.append(os.path.join(folder, record_name))
        else:
            exact_candidates.extend([
                os.path.join(folder, f"{record_name}.hdf"),
                os.path.join(folder, f"{record_name}.hdf5"),
            ])
        for path in exact_candidates:
            if os.path.exists(path):
                return path

        prefix = f"{record_name}-"
        matches = [
            os.path.join(folder, filename)
            for filename in os.listdir(folder)
            if filename.lower().endswith((".hdf", ".hdf5")) and filename.startswith(prefix)
        ]
        if not matches:
            return None
        return max(matches, key=os.path.getmtime)

    def _load_sequence_for_record(self):
        sequence_name = self._sequence_name_from_record()
        data = self._load_saved_stimuli()
        sequence = data.get(sequence_name, {}) if isinstance(data, dict) else {}
        order = sequence.get("order")
        if order:
            return np.asarray(order, dtype=int)

        current_sequence = getattr(self.settings.stimuli_settings, "saved_stimuli_curr", "")
        sequence = data.get(current_sequence, {}) if isinstance(data, dict) else {}
        order = sequence.get("order")
        if order:
            return np.asarray(order, dtype=int)

        raise ValueError("Не найдена последовательность motor/rest для этой записи.")

    def _sequence_name_from_record(self):
        match = re.search(r"tms_(\d+)", self._record_name.lower())
        if match:
            return f"bar_10-30_rest_vs_motor_{match.group(1)}"
        return getattr(self.settings.stimuli_settings, "saved_stimuli_curr", "")

    def _load_saved_stimuli(self):
        filename = getattr(self.settings.stimuli_settings, "saved_stimuli_filename", r"resources/saved_stimuli.json")
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)


def _epoch_amplitudes(epochs, time, from_ms=15, upto_ms=40):
    if epochs.size == 0:
        return np.asarray([], dtype=float)
    mask = (time >= from_ms) & (time <= upto_ms)
    if not np.any(mask):
        return np.full(epochs.shape[0], np.nan)
    data = epochs[:, mask]
    return np.nanmax(data, axis=1) - np.nanmin(data, axis=1)
