import os

import numpy as np
import pandas as pd

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import QSignalBlocker, Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from utils.layout_utils import create_hbox
from utils.ui_helpers import create_button, create_check_box, create_spin_box


def calculate_mean(df, n=5):
    df = df.copy()
    df["error"] = pd.to_numeric(df["error"], errors="coerce")
    df["trial_number"] = pd.to_numeric(df["trial_number"], errors="coerce")
    df["plot_x"] = pd.to_numeric(df.get("plot_x", df["trial_number"]), errors="coerce")
    df = df.loc[np.isfinite(df["plot_x"])]
    if df.empty:
        return pd.DataFrame(columns=["t", "error"])

    df["bin"] = np.arange(df.shape[0]) // max(1, n)
    df_mean = (
        df.groupby("bin", as_index=False)
        .agg(t=("plot_x", "mean"), error=("error", "mean"))
    )
    df_mean = df_mean.loc[np.isfinite(df_mean["error"])]
    return df_mean


def plot_error(ax, df, n_mean=5, limits=None, title=None, ylim=None, yticks=None, xticks_step=None):
    ax.clear()

    df = df.copy()
    df["trial_number"] = pd.to_numeric(df["trial_number"], errors="coerce")
    df["error"] = pd.to_numeric(df["error"], errors="coerce")
    df["plot_x"] = pd.to_numeric(df.get("plot_x", df["trial_number"]), errors="coerce")
    df = df.loc[np.isfinite(df["plot_x"])]
    if df.empty:
        if title is not None:
            ax.set_title(title, fontsize=14, y=1.02)
        ax.text(0.5, 0.5, "No trials to plot", ha="center", va="center", transform=ax.transAxes)
        ax.grid(linewidth=0.5, color="lightgrey")
        ax.set_xlabel("Trial number", fontsize=12)
        ax.set_ylabel("Error [ms]", fontsize=12)
        return

    df_mean = calculate_mean(df, n=n_mean)
    x = df["plot_x"].to_numpy(dtype=float)
    error = df["error"].to_numpy(dtype=float)
    missing = ~np.isfinite(error)

    ax.axhline(0, linewidth=3, color="#9649ED")

    ax.plot(
        x,
        error,
        linewidth=1.5,
        marker="o",
        markersize=4,
        color="#280E7E",
        label="Error per trial",
    )
    if not df_mean.empty:
        ax.plot(
            df_mean["t"],
            df_mean["error"],
            linewidth=3,
            marker="o",
            markersize=5,
            color="#C90CA7",
            label=f"Binned mean error (n = {n_mean})",
        )

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

    if missing.any():
        ymin, ymax = ax.get_ylim()
        marker_y = ymin + (ymax - ymin) * 0.04
        ax.scatter(
            x[missing],
            np.full(missing.sum(), marker_y),
            marker="x",
            s=70,
            linewidths=2,
            color="#D62828",
            label="No detection",
            zorder=5,
        )
        ax.set_ylim(ymin, ymax)

    if xticks_step is not None and xticks_step > 0 and df.shape[0] > 0:
        xmin = np.nanmin(x)
        xmax = np.nanmax(x)
        ax.set_xticks(np.arange(xmin, xmax + 1, xticks_step))
    if x.size > 0:
        xmin = np.nanmin(x)
        xmax = np.nanmax(x)
        padding = max(0.5, (xmax - xmin) * 0.02)
        ax.set_xlim(xmin - padding, xmax + padding)
    if yticks is not None:
        ax.set_yticks(yticks)

    ax.grid(linewidth=0.5, color="lightgrey")
    ax.set_xlabel("№ попытки", fontsize=12)
    ax.set_ylabel("ошибка [мс]", fontsize=12)
    ax.set_xlabel("Trial number", fontsize=12)
    ax.set_ylabel("Error [ms]", fontsize=12)
    ax.legend(loc="lower left")


def prepare_results_df(df):
    df = df.copy()
    if "trial_number" not in df:
        df["trial_number"] = np.arange(1, df.shape[0] + 1)

    trial_number = pd.to_numeric(df["trial_number"], errors="coerce")
    is_usable_trial_axis = trial_number.notna().all() and trial_number.is_monotonic_increasing and trial_number.is_unique
    df["plot_x"] = trial_number if is_usable_trial_axis else np.arange(1, df.shape[0] + 1)
    df["n"] = df["plot_x"]
    return df


class ResultsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowTitle("Results")
        self.resize(900, 600)

        self._df = None
        self._csv_path = None
        self._subject = None
        self._title = None
        self._limits = None
        self._updating_controls = False

        self._button_refresh = create_button(text="refresh", parent=self)
        self._auto_ylim = create_check_box(True, "auto y", parent=self)
        self._spin_ymin = create_spin_box(-2000, 2000, -300, step=10, parent=self)
        self._spin_ymax = create_spin_box(-2000, 2000, 150, parent=self)
        self._spin_n_mean = create_spin_box(1, 100, 5, parent=self)
        self._spin_xticks = create_spin_box(1, 500, 5, parent=self)

        self._figure = Figure(figsize=(10, 6))
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.addLayout(
            create_hbox(
                [
                    self._button_refresh,
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

        self._button_refresh.clicked.connect(self.refresh_results)
        self._auto_ylim.stateChanged.connect(self._update_scale_controls)
        self._spin_ymin.valueChanged.connect(self._redraw_plot)
        self._spin_ymax.valueChanged.connect(self._redraw_plot)
        self._spin_n_mean.valueChanged.connect(self._redraw_plot)
        self._spin_xticks.valueChanged.connect(self._redraw_plot)

        self._update_scale_controls()

    def show_results(self, csv_path, subject, record_name, limits=None):
        self._csv_path = csv_path
        self._subject = subject
        self._title = f"{subject}: {record_name}"
        self._limits = limits
        self.refresh_results()

    def refresh_results(self):
        if self._csv_path is None:
            return

        df = pd.read_csv(self._csv_path)
        df["subject"] = self._subject
        df["feedback"] = "feedback" if "errorfeedback" not in os.path.basename(self._csv_path) else "error_feedback"
        df["filename"] = os.path.basename(self._csv_path)
        df = prepare_results_df(df)

        self._df = df
        self._set_initial_scale(df)
        self._redraw_plot()

    def _set_initial_scale(self, df):
        error = pd.to_numeric(df["error"], errors="coerce").to_numpy(dtype=float)
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
