import os

import numpy as np
import pandas as pd

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import QSignalBlocker, Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.feedback_bar import get_text_color
from utils.layout_utils import create_hbox
from utils.ui_helpers import create_button, create_check_box, create_spin_box


PLOT_TITLE_FONTSIZE = 19
PLOT_LABEL_FONTSIZE = 16
PLOT_TICK_FONTSIZE = 13
PLOT_LEGEND_FONTSIZE = 12
PLOT_ANNOTATION_FONTSIZE = 14


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


def calculate_error_statistics(df):
    if df is None or "error" not in df:
        return {
            "n": 0,
            "mean": np.nan,
            "std": np.nan,
            "median": np.nan,
            "range": np.nan,
            "min": np.nan,
            "max": np.nan,
        }

    error = pd.to_numeric(df["error"], errors="coerce").to_numpy(dtype=float)
    finite_error = error[np.isfinite(error)]
    if finite_error.size == 0:
        return {
            "n": 0,
            "mean": np.nan,
            "std": np.nan,
            "median": np.nan,
            "range": np.nan,
            "min": np.nan,
            "max": np.nan,
        }

    return {
        "n": int(finite_error.size),
        "mean": float(np.mean(finite_error)),
        "std": float(np.std(finite_error, ddof=1)) if finite_error.size > 1 else 0.0,
        "median": float(np.median(finite_error)),
        "range": float(np.max(finite_error) - np.min(finite_error)),
        "min": float(np.min(finite_error)),
        "max": float(np.max(finite_error)),
    }


def format_error_statistics(stats):
    if not stats or stats.get("n", 0) <= 0:
        return "Результаты: нет обнаруженных ошибок"

    return (
        f"Средняя ошибка: {stats['mean']:.2f} мс | "
        f"Стандартное отклонение: {stats['std']:.2f} мс | "
        f"Медиана: {stats['median']:.2f} мс | "
        f"Разброс: {stats['range']:.2f} мс "
        f"({stats['min']:.2f}..{stats['max']:.2f}, n={stats['n']})"
    )


def _finite_error_values(df):
    if df is None or "error" not in df:
        return np.array([], dtype=float)
    error = pd.to_numeric(df["error"], errors="coerce").to_numpy(dtype=float)
    return error[np.isfinite(error)]


def _qcolor_to_hex(color):
    return "#{:02x}{:02x}{:02x}".format(color.red(), color.green(), color.blue())


def _feedback_color(value):
    return _qcolor_to_hex(get_text_color(value))


def _kde_curve(values, grid):
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return np.zeros_like(grid)

    if values.size == 1:
        bandwidth = 20.0
    else:
        std = float(np.std(values, ddof=1))
        value_range = float(np.max(values) - np.min(values))
        bandwidth = 1.06 * std * (values.size ** (-1 / 5))
        if not np.isfinite(bandwidth) or bandwidth <= 0:
            bandwidth = max(value_range / 20.0, 20.0)
    bandwidth = max(float(bandwidth), 5.0)

    z = (grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * z * z).sum(axis=1)
    density /= values.size * bandwidth * np.sqrt(2 * np.pi)
    return density


def plot_error_distribution(
    ax,
    df,
    title="Задержка попадания",
    acceptable_limit=200,
    outlier_limit=200,
    transparent=False,
):
    ax.clear()
    text_color = "white" if transparent else "#222222"
    grid_color = "#FFFFFF" if transparent else "lightgrey"
    spine_color = "#E8E8FF" if transparent else "#333333"

    if transparent:
        ax.set_facecolor("none")

    values = _finite_error_values(df)
    if values.size == 0:
        ax.set_title(title, fontsize=PLOT_TITLE_FONTSIZE, color=text_color)
        ax.text(
            0.5,
            0.5,
            "Нет данных",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=text_color,
            fontsize=PLOT_LABEL_FONTSIZE,
        )
        ax.set_xlabel("Ошибка [мс]", color=text_color, fontsize=PLOT_LABEL_FONTSIZE)
        ax.set_yticks([])
        ax.tick_params(colors=text_color, labelsize=PLOT_TICK_FONTSIZE)
        ax.grid(linewidth=0.5, color=grid_color, axis="x", alpha=0.7)
        return

    acceptable_limit = abs(float(acceptable_limit))
    outlier_limit = abs(float(outlier_limit))
    xmin = min(float(np.min(values)), -outlier_limit, -acceptable_limit) - 40
    xmax = max(float(np.max(values)), outlier_limit, acceptable_limit) + 40
    if np.isclose(xmin, xmax):
        xmin -= 50
        xmax += 50
    grid = np.linspace(xmin, xmax, 400)
    density = _kde_curve(values, grid)

    bins = 20
    hist_color = "#B9C7E6" if not transparent else "#C0D2FA"
    kde_fill = "#8fb7ff" if not transparent else "#86B5FF"
    kde_line = "#2452A6" if not transparent else "#F3F8FF"
    ax.hist(values, bins=bins, density=True, color=hist_color, alpha=0.24 if transparent else 0.35, edgecolor="white")
    ax.fill_between(grid, density, color=kde_fill, alpha=0.22 if transparent else 0.35) #, label="KDE")
    ax.plot(grid, density, color=kde_line, linewidth=2.8)
    ax.axvspan(
        -acceptable_limit,
        acceptable_limit,
        color="#0C7E19",
        alpha=0.50 if transparent else 0.30,
        label="Целевая область",
    )
    # ax.axvline(-outlier_limit, color="#777777", linestyle="--", linewidth=1)
    # ax.axvline(outlier_limit, color="#777777", linestyle="--", linewidth=1)

    ymax = float(np.max(density)) if np.max(density) > 0 else 1.0
    kde_at_values = np.interp(values, grid, density)
    fractions = 0.18 + 0.76 * ((np.arange(values.size) * 0.61803398875) % 1.0)
    kde_top = np.maximum(kde_at_values, ymax * 0.06)
    point_y = fractions * kde_top
    inlier_mask = (values >= -outlier_limit) & (values <= outlier_limit)
    colors = [_feedback_color(value) for value in values]

    if inlier_mask.any():
        ax.scatter(
            values[inlier_mask],
            point_y[inlier_mask],
            c=[colors[i] for i in np.where(inlier_mask)[0]],
            marker="o",
            s=52,
            edgecolors="#F7F7F7" if transparent else "#222222",
            linewidths=0.6,
            zorder=5,
            label="Измерения",
        )
    if (~inlier_mask).any():
        ax.scatter(
            values[~inlier_mask],
            point_y[~inlier_mask],
            c=[colors[i] for i in np.where(~inlier_mask)[0]],
            marker="x",
            s=95,
            linewidths=2.2,
            zorder=6,
            label="Слишком много",
        )

    mean_value = float(np.mean(values))
    mean_y = float(np.interp(mean_value, grid, density))
    ax.annotate(
        "среднее",
        xy=(mean_value, mean_y),
        xytext=(mean_value, ymax * 1.15),
        ha="center",
        color="#FFFFFF" if transparent else "#3E2660",
        fontsize=PLOT_ANNOTATION_FONTSIZE,
        arrowprops={"arrowstyle": "->", "color": "#A985F9" if transparent else "#4F2C7F", "linewidth": 1.8},
    )

    ax.set_title(title, fontsize=PLOT_TITLE_FONTSIZE, color=text_color)
    ax.set_xlabel("Ошибка [мс]", color=text_color, fontsize=PLOT_LABEL_FONTSIZE)
    ax.set_ylabel("Плотность", color=text_color, fontsize=PLOT_LABEL_FONTSIZE)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(0, ymax * 1.28)
    ax.tick_params(colors=text_color, labelsize=PLOT_TICK_FONTSIZE)
    for spine in ax.spines.values():
        spine.set_color(spine_color)
    ax.grid(linewidth=0.5, color=grid_color, axis="x", alpha=0.65)
    legend = ax.legend(loc="upper right", fontsize=PLOT_LEGEND_FONTSIZE)
    if legend is not None and transparent:
        legend.get_frame().set_alpha(0.15)
        legend.get_frame().set_facecolor("#000000")
        for text in legend.get_texts():
            text.set_color(text_color)


def save_error_distribution_plot(df, output_path, title="Задержка попадания", acceptable_limit=200, transparent=False):
    figure = Figure(figsize=(9.5, 5.2), dpi=150)
    if transparent:
        figure.patch.set_alpha(0.0)
    ax = figure.add_subplot(111)
    plot_error_distribution(ax, df, title=title, acceptable_limit=acceptable_limit, transparent=transparent)
    figure.tight_layout()
    figure.savefig(output_path, facecolor="none" if transparent else "white", transparent=transparent, bbox_inches="tight")
    return output_path


def plot_error(ax, df, n_mean=5, limits=None, title=None, ylim=None, yticks=None, xticks_step=None):
    ax.clear()

    df = df.copy()
    df["trial_number"] = pd.to_numeric(df["trial_number"], errors="coerce")
    df["error"] = pd.to_numeric(df["error"], errors="coerce")
    df["plot_x"] = pd.to_numeric(df.get("plot_x", df["trial_number"]), errors="coerce")
    df = df.loc[np.isfinite(df["plot_x"])]
    if df.empty:
        if title is not None:
            ax.set_title(title, fontsize=PLOT_TITLE_FONTSIZE, y=1.02)
        ax.text(
            0.5,
            0.5,
            "No trials to plot",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=PLOT_LABEL_FONTSIZE,
        )
        ax.grid(linewidth=0.5, color="lightgrey")
        ax.set_xlabel("Trial number", fontsize=PLOT_LABEL_FONTSIZE)
        ax.set_ylabel("Error [ms]", fontsize=PLOT_LABEL_FONTSIZE)
        ax.tick_params(labelsize=PLOT_TICK_FONTSIZE)
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
        ax.set_title(title, fontsize=PLOT_TITLE_FONTSIZE, y=1.02)
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
    ax.set_xlabel("№ попытки", fontsize=PLOT_LABEL_FONTSIZE)
    ax.set_ylabel("ошибка [мс]", fontsize=PLOT_LABEL_FONTSIZE)
    ax.set_xlabel("Trial number", fontsize=PLOT_LABEL_FONTSIZE)
    ax.set_ylabel("Error [ms]", fontsize=PLOT_LABEL_FONTSIZE)
    ax.tick_params(labelsize=PLOT_TICK_FONTSIZE)
    ax.legend(loc="lower left", fontsize=PLOT_LEGEND_FONTSIZE)


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
        self.resize(1200, 650)

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
        self._show_trials_plot = create_check_box(True, "trials", parent=self)
        self._show_distribution_plot = create_check_box(True, "distribution", parent=self)

        self._figure = Figure(figsize=(12, 5.8))
        self._canvas = FigureCanvas(self._figure)
        self._ax = None
        self._density_ax = None
        self._label_statistics = QLabel("Результаты: --", self)
        self._label_statistics.setAlignment(Qt.AlignCenter)

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
                    QLabel("show:", self),
                    self._show_trials_plot,
                    self._show_distribution_plot,
                ]
            )
        )
        layout.addWidget(self._label_statistics)
        layout.addWidget(self._canvas)

        self._button_refresh.clicked.connect(self.refresh_results)
        self._auto_ylim.stateChanged.connect(self._update_scale_controls)
        self._spin_ymin.valueChanged.connect(self._redraw_plot)
        self._spin_ymax.valueChanged.connect(self._redraw_plot)
        self._spin_n_mean.valueChanged.connect(self._redraw_plot)
        self._spin_xticks.valueChanged.connect(self._redraw_plot)
        self._show_trials_plot.stateChanged.connect(self._redraw_plot)
        self._show_distribution_plot.stateChanged.connect(self._redraw_plot)

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
        self._label_statistics.setText(format_error_statistics(calculate_error_statistics(df)))
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

        show_trials = self._show_trials_plot.isChecked()
        show_distribution = self._show_distribution_plot.isChecked()
        if not show_trials and not show_distribution:
            with QSignalBlocker(self._show_distribution_plot):
                self._show_distribution_plot.setChecked(True)
            show_distribution = True

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

        self._figure.clear()
        if show_trials and show_distribution:
            self._ax = self._figure.add_subplot(121)
            self._density_ax = self._figure.add_subplot(122)
        elif show_trials:
            self._ax = self._figure.add_subplot(111)
            self._density_ax = None
        else:
            self._ax = None
            self._density_ax = self._figure.add_subplot(111)

        if self._ax is not None:
            plot_error(
                self._ax,
                df=self._df,
                n_mean=self._spin_n_mean.value(),
                limits=self._limits,
                title=self._title,
                ylim=ylim,
                xticks_step=xticks_step,
            )
        if self._density_ax is not None:
            acceptable_limit = abs(self._limits[1]) if self._limits is not None else 200
            plot_error_distribution(self._density_ax, self._df, acceptable_limit=acceptable_limit)
        self._figure.tight_layout()
        self._canvas.draw()
