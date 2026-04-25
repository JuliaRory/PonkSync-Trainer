import os

import numpy as np
import pandas as pd
import seaborn as sns

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import QSignalBlocker, Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from utils.layout_utils import create_hbox
from utils.ui_helpers import create_check_box, create_spin_box


def calculate_mean(df, n=10):
    df_valid = df.loc[np.isfinite(df["error"])].copy()
    if df_valid.empty:
        return pd.DataFrame(columns=["t", "error"])

    df_valid["bin"] = np.arange(df_valid.shape[0]) // max(1, n)
    df_mean = (
        df_valid.groupby("bin", as_index=False)
        .agg(t=("n", "mean"), error=("error", "mean"))
    )
    return df_mean


def plot_error(ax, df, n_mean=10, limits=None, title=None, ylim=None, yticks=None, xticks_step=None):
    ax.clear()

    df_mean = calculate_mean(df, n=n_mean)

    ax.axhline(0, linewidth=3, color="#9649ED")

    sns.lineplot(data=df, x="n", y="error", ax=ax, linewidth=1.5, color="#280E7E", label="Error per trial")
    if not df_mean.empty:
        sns.lineplot(
            data=df_mean,
            x="t",
            y="error",
            ax=ax,
            linewidth=3,
            color="#C90CA7",
            label=f"Binned mean error (n = {n_mean})",
        )

    if xticks_step is not None and xticks_step > 0 and df.shape[0] > 0:
        ax.set_xticks(np.arange(0, df.shape[0], xticks_step))
    if yticks is not None:
        ax.set_yticks(yticks)
    if ylim is not None:
        ax.set_ylim(ylim)
    if title is not None:
        ax.set_title(title, fontsize=14, y=1.02)
    if limits is not None:
        xmin, xmax = ax.get_xlim()
        ax.fill_between(
            [xmin, xmax],
            y1=limits[0],
            y2=limits[1],
            alpha=0.2,
            color="#28076F",
            label=f"Acceptable range {limits} ms",
        )
        ax.set_xlim(xmin, xmax)

    ax.grid(linewidth=0.5, color="lightgrey")
    ax.set_xlabel("№ попытки", fontsize=12)
    ax.set_ylabel("ошибка [мс]", fontsize=12)
    ax.legend(loc="lower left")


class ResultsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowTitle("Results")
        self.resize(900, 600)

        self._df = None
        self._title = None
        self._limits = None
        self._updating_controls = False

        self._auto_ylim = create_check_box(True, "auto y", parent=self)
        self._spin_ymin = create_spin_box(-2000, 2000, -300, parent=self)
        self._spin_ymax = create_spin_box(-2000, 2000, 150, parent=self)
        self._spin_n_mean = create_spin_box(1, 100, 10, parent=self)
        self._spin_xticks = create_spin_box(1, 500, 10, parent=self)

        self._figure = Figure(figsize=(10, 6))
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.addLayout(
            create_hbox(
                [
                    QLabel("Scale:", self),
                    self._auto_ylim,
                    QLabel("ymin", self),
                    self._spin_ymin,
                    QLabel("ymax", self),
                    self._spin_ymax,
                    QLabel("mean n", self),
                    self._spin_n_mean,
                    QLabel("x step", self),
                    self._spin_xticks,
                ]
            )
        )
        layout.addWidget(self._canvas)

        self._auto_ylim.stateChanged.connect(self._update_scale_controls)
        self._spin_ymin.valueChanged.connect(self._redraw_plot)
        self._spin_ymax.valueChanged.connect(self._redraw_plot)
        self._spin_n_mean.valueChanged.connect(self._redraw_plot)
        self._spin_xticks.valueChanged.connect(self._redraw_plot)

        self._update_scale_controls()

    def show_results(self, csv_path, subject, record_name, limits=None):
        df = pd.read_csv(csv_path)
        df["subject"] = subject
        df["feedback"] = "feedback" if "errorfeedback" not in os.path.basename(csv_path) else "error_feedback"
        df["filename"] = os.path.basename(csv_path)
        df["n"] = np.arange(df.shape[0])

        self._df = df
        self._title = f"{subject}: {record_name}"
        self._limits = limits
        self._set_initial_scale(df)
        self._redraw_plot()

    def _set_initial_scale(self, df):
        error = df["error"].to_numpy(dtype=float)
        finite_error = error[np.isfinite(error)]
        if finite_error.size == 0:
            return

        ymin = int(np.floor(finite_error.min() / 25.0) * 25) - 25
        ymax = int(np.ceil(finite_error.max() / 25.0) * 25) + 25
        if ymin == ymax:
            ymin -= 25
            ymax += 25

        self._updating_controls = True
        try:
            with QSignalBlocker(self._spin_ymin):
                self._spin_ymin.setValue(ymin)
            with QSignalBlocker(self._spin_ymax):
                self._spin_ymax.setValue(ymax)
        finally:
            self._updating_controls = False

    def _update_scale_controls(self):
        if self._updating_controls:
            return
        auto = self._auto_ylim.isChecked()
        self._spin_ymin.setEnabled(not auto)
        self._spin_ymax.setEnabled(not auto)
        self._redraw_plot()

    def _redraw_plot(self):
        if self._df is None or self._updating_controls:
            return

        ylim = None
        if not self._auto_ylim.isChecked():
            ymin = self._spin_ymin.value()
            ymax = self._spin_ymax.value()
            if ymin == ymax:
                ymax = ymin + 1
            elif ymin > ymax:
                ymin, ymax = ymax, ymin
            ylim = (ymin, ymax)
        xticks_step = self._spin_xticks.value() if self._spin_xticks.value() > 0 else None

        plot_error(
            self._ax,
            df=self._df,
            n_mean=self._spin_n_mean.value(),
            limits=self._limits,
            title=self._title,
            ylim=ylim,
            xticks_step=xticks_step,
        )
        self._figure.tight_layout()
        self._canvas.draw()
