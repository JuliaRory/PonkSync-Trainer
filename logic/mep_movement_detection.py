from dataclasses import asdict, dataclass
import json
import os

import h5py
import numpy as np
import pandas as pd
from scipy.signal import butter, find_peaks, iirnotch, sosfilt, tf2sos


@dataclass
class MovementDetectionSettings:
    fs: float = 5000
    trigger_bit: int = 0
    emg_channel: int = 0
    invert_emg: bool = True
    epoch_start_ms: float = -500
    epoch_end_ms: float = 300
    baseline_from_ms: float = -200
    baseline_to_ms: float = -50
    art_from_ms: float = -1.5
    art_to_ms: float = 8
    mep_from_ms: float = 15
    mep_to_ms: float = 75
    threshold_k: float = 4
    baseline_percentile: float = 95
    prominence_k: float = 2
    smooth_ms: float = 3
    min_width_ms: float = 1
    min_distance_ms: float = 10
    confirmation_window_ms: float = 4
    required_fraction: float = 0.15
    min_peak_area: float = 0.0
    min_emg_ptp_mV: float = 0.12
    emg_ptp_from_ms: float = 75
    emg_ptp_to_ms: float = 250
    better_candidate_area_ratio: float = 3.0
    better_candidate_min_separation_ms: float = 40
    pre_tms_ignore_after_ms: float = -8
    detect_pre_tms: bool = False
    early_delay_ms: float = -80
    late_delay_ms: float = 80
    plot_from_ms: float = -200
    plot_to_ms: float = 255
    plot_ymax_mV: float = 0.1
    notch_hz: float = 50
    notch_width_hz: float = 1
    bandpass_low_hz: float = 5
    bandpass_high_hz: float = 450

    def to_dict(self):
        return asdict(self)


def ms_to_samples(ms, fs):
    return int(round(ms * fs / 1000))


def get_trigger(data, bit):
    ttl = np.asarray(data, dtype=np.uint8)
    return ((ttl >> bit) & 0b1).astype(int)


def calculate_tkeo(x):
    x = np.asarray(x)
    tkeo = np.zeros_like(x)
    if x.size < 3:
        return tkeo
    tkeo[1:-1] = x[1:-1] ** 2 - x[:-2] * x[2:]
    tkeo[0] = tkeo[1]
    tkeo[-1] = tkeo[-2]
    return tkeo


def make_online_filters(settings, fs):
    notch_width = max(float(settings.notch_width_hz), np.finfo(float).eps)
    notch_hz = min(max(float(settings.notch_hz), 0.1), fs / 2 - 1)
    q = notch_hz / notch_width
    b_notch, a_notch = iirnotch(notch_hz, q, fs=fs)
    sos_notch = tf2sos(b_notch, a_notch)

    low = max(float(settings.bandpass_low_hz), 0.1)
    high = min(float(settings.bandpass_high_hz), fs / 2 - 1)
    if high <= low:
        high = min(low + 1, fs / 2 - 1)
    sos_butter = butter(4, (low, high), btype="bandpass", output="sos", fs=fs)
    return sos_notch, sos_butter


def robust_noise_level(x):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    if x.size == 0:
        raise ValueError("Baseline interval is empty")

    median = np.median(x)
    mad = np.median(np.abs(x - median))
    sigma = 1.4826 * mad
    if sigma <= np.finfo(float).eps:
        sigma = max(
            np.std(x),
            np.percentile(x, 75) - np.percentile(x, 25),
            np.finfo(float).eps,
        )
    return float(median), float(sigma)


def smooth_boxcar(x, time, window_ms):
    dt = np.median(np.diff(time))
    n_samples = max(1, int(round(window_ms / dt)))
    if n_samples <= 1:
        return x.copy()
    kernel = np.ones(n_samples) / n_samples
    return np.convolve(x, kernel, mode="same")


def detect_movement_in_epoch(time, emg_tkeo, settings):
    time = np.asarray(time)
    emg_tkeo = np.asarray(emg_tkeo)

    baseline_mask = (time >= settings.baseline_from_ms) & (time <= settings.baseline_to_ms)
    base = emg_tkeo[baseline_mask]
    noise_median, noise_sigma = robust_noise_level(base)

    threshold = max(
        noise_median + settings.threshold_k * noise_sigma,
        np.percentile(base, settings.baseline_percentile),
    )
    min_prominence = max(
        settings.prominence_k * noise_sigma,
        0.5 * (threshold - noise_median),
    )

    valid_mask = time > settings.mep_to_ms
    if settings.detect_pre_tms:
        valid_mask |= time < min(settings.art_from_ms, settings.pre_tms_ignore_after_ms)

    signal_smooth = smooth_boxcar(emg_tkeo, time, settings.smooth_ms)
    signal_for_peaks = signal_smooth.copy()
    signal_for_peaks[~valid_mask] = noise_median

    dt = np.median(np.diff(time))
    min_width_samples = max(1, int(round(settings.min_width_ms / dt)))
    min_distance_samples = max(1, int(round(settings.min_distance_ms / dt)))
    peaks, props = find_peaks(
        signal_for_peaks,
        height=threshold,
        prominence=min_prominence,
        width=min_width_samples,
        distance=min_distance_samples,
    )

    half_window = max(1, int(round((settings.confirmation_window_ms / 2) / dt)))
    accepted = []
    accepted_prop_idxs = []
    onset_by_peak = []
    area_by_peak = []
    fraction_by_peak = []

    trapezoid = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    for prop_idx, peak_idx in enumerate(peaks):
        lo = max(0, peak_idx - half_window)
        hi = min(len(signal_smooth), peak_idx + half_window + 1)
        local_idxs = np.arange(lo, hi)
        local_idxs = local_idxs[valid_mask[local_idxs]]
        if local_idxs.size == 0:
            continue

        fraction = np.mean(signal_smooth[local_idxs] > threshold)
        if fraction < settings.required_fraction:
            continue

        area_lo = max(0, peak_idx - 2 * half_window)
        area_hi = min(len(signal_smooth), peak_idx + 2 * half_window + 1)
        peak_area = trapezoid(
            np.maximum(signal_smooth[area_lo:area_hi] - threshold, 0),
            time[area_lo:area_hi],
        )
        if peak_area < settings.min_peak_area:
            continue

        onset_idx = peak_idx
        while (
            onset_idx > 0
            and valid_mask[onset_idx - 1]
            and signal_smooth[onset_idx - 1] > threshold
        ):
            onset_idx -= 1

        accepted.append(peak_idx)
        accepted_prop_idxs.append(prop_idx)
        onset_by_peak.append(onset_idx)
        area_by_peak.append(float(peak_area))
        fraction_by_peak.append(float(fraction))

    result = {
        "movement_found": False,
        "delay_ms": np.nan,
        "onset_time": np.nan,
        "peak_time": np.nan,
        "peak_amp": np.nan,
        "peak_prominence": np.nan,
        "peak_area": np.nan,
        "peak_times": json.dumps([]),
        "peak_onsets": json.dumps([]),
        "peak_amps": json.dumps([]),
        "peak_areas": json.dumps([]),
        "threshold": float(threshold),
        "noise_median": float(noise_median),
        "noise_sigma": float(noise_sigma),
        "fraction_max": 0.0,
        "n_peaks": 0,
    }
    if not accepted:
        return result

    selected_pos = 0
    for candidate_pos in range(1, len(accepted)):
        separated_enough = (
            time[accepted[candidate_pos]] - time[accepted[selected_pos]]
            >= settings.better_candidate_min_separation_ms
        )
        much_stronger = (
            area_by_peak[candidate_pos]
            >= area_by_peak[selected_pos] * settings.better_candidate_area_ratio
        )
        if separated_enough and much_stronger:
            selected_pos = candidate_pos
            break

    peak_idx = accepted[selected_pos]
    prop_idx = accepted_prop_idxs[selected_pos]
    onset_idx = onset_by_peak[selected_pos]
    result.update({
        "movement_found": True,
        "delay_ms": float(time[onset_idx]),
        "onset_time": float(time[onset_idx]),
        "peak_time": float(time[peak_idx]),
        "peak_amp": float(signal_smooth[peak_idx]),
        "peak_prominence": float(props["prominences"][prop_idx]),
        "peak_area": float(area_by_peak[selected_pos]),
        "peak_times": json.dumps(time[accepted].astype(float).tolist()),
        "peak_onsets": json.dumps(time[onset_by_peak].astype(float).tolist()),
        "peak_amps": json.dumps(signal_smooth[accepted].astype(float).tolist()),
        "peak_areas": json.dumps(area_by_peak),
        "fraction_max": float(np.max(fraction_by_peak)),
        "n_peaks": int(len(accepted)),
    })
    return result


def emg_ptp_in_window(time, emg_epoch, from_ms, to_ms):
    mask = (time >= from_ms) & (time <= to_ms)
    if not np.any(mask):
        return np.nan
    data = np.asarray(emg_epoch)[mask]
    data = data[np.isfinite(data)]
    if data.size == 0:
        return np.nan
    return float(np.nanmax(data) - np.nanmin(data))


def _read_fs(h5f, default_fs):
    try:
        value = h5f["eeg/streamInfo/samplingRate"][0]
        if np.isfinite(value) and value > 0:
            return float(value)
    except Exception:
        pass
    return float(default_fs)


def _extract_epochs(emg_mV, trigger, fs, settings):
    events = np.where(np.diff(trigger) == 1)[0] + 1
    start = ms_to_samples(settings.epoch_start_ms, fs)
    end = ms_to_samples(settings.epoch_end_ms, fs)
    n_samples = end - start
    if n_samples <= 0:
        raise ValueError("Epoch start must be earlier than epoch end")

    time = (np.arange(n_samples) + start) * 1000 / fs
    epochs = []
    trigger_samples = []
    for sample in events:
        lo = int(sample + start)
        hi = int(sample + end)
        if lo < 0 or hi > len(emg_mV):
            continue
        epochs.append(np.asarray(emg_mV[lo:hi], dtype=float))
        trigger_samples.append(int(sample))

    if not epochs:
        return time, np.empty((0, n_samples)), np.empty((0, n_samples)), np.asarray([], dtype=int)

    epochs = np.asarray(epochs)
    tkeo_epochs = np.asarray([calculate_tkeo(epoch * 1e-3) for epoch in epochs])
    return time, epochs, tkeo_epochs, np.asarray(trigger_samples, dtype=int)


def _read_mep_group(h5f):
    if "mep" not in h5f:
        return {}
    group = h5f["mep"]
    values = {}
    for name in ("amplitudes_mV", "baselines_mV", "trigger_samples", "trigger_times_ms"):
        if name in group:
            values[name] = group[name][:]
    return values


def _mep_value_for_epoch(mep_values, name, idx, trigger_sample):
    if name not in mep_values:
        return np.nan
    values = mep_values[name]
    if "trigger_samples" in mep_values:
        samples = np.asarray(mep_values["trigger_samples"], dtype=int)
        if samples.size:
            nearest = int(np.argmin(np.abs(samples - int(trigger_sample))))
            if abs(int(samples[nearest]) - int(trigger_sample)) <= 2:
                return float(values[nearest])
    if idx < len(values):
        return float(values[idx])
    return np.nan


def analyze_record_file(path, settings):
    path = os.path.abspath(path)
    with h5py.File(path, "r") as h5f:
        if "eeg/data" not in h5f:
            raise KeyError("HDF file does not contain eeg/data")
        data = h5f["eeg/data"][:-1]
        fs = _read_fs(h5f, settings.fs)
        mep_values = _read_mep_group(h5f)

    settings.fs = fs
    if settings.emg_channel < 0 or settings.emg_channel >= data.shape[1] - 1:
        raise ValueError(
            f"EMG channel {settings.emg_channel} is outside eeg/data columns 0..{data.shape[1] - 2}"
        )

    emg = np.asarray(data[:, settings.emg_channel], dtype=float)
    if settings.invert_emg:
        emg = -emg
    trigger = get_trigger(data[:, -1], settings.trigger_bit)

    sos_notch, sos_butter = make_online_filters(settings, fs)
    emg_filtered = sosfilt(sos_notch, emg, axis=0)
    emg_filtered = sosfilt(sos_butter, emg_filtered, axis=0)
    emg_mV = emg_filtered * 1e3

    time, emg_epochs, tkeo_epochs, trigger_samples = _extract_epochs(
        emg_mV,
        trigger,
        fs,
        settings,
    )

    rows = []
    for idx, (emg_epoch, tkeo_epoch) in enumerate(zip(emg_epochs, tkeo_epochs)):
        row = detect_movement_in_epoch(time, tkeo_epoch, settings)
        row["emg_ptp_mV"] = emg_ptp_in_window(
            time,
            emg_epoch,
            settings.emg_ptp_from_ms,
            settings.emg_ptp_to_ms,
        )
        if (
            row["movement_found"]
            and np.isfinite(row["emg_ptp_mV"])
            and row["emg_ptp_mV"] < settings.min_emg_ptp_mV
        ):
            row["movement_found"] = False
            row["delay_ms"] = np.nan
            row["onset_time"] = np.nan
            row["peak_time"] = np.nan
            row["peak_amp"] = np.nan
            row["peak_prominence"] = np.nan
            row["peak_area"] = np.nan
            row["peak_times"] = json.dumps([])
            row["peak_onsets"] = json.dumps([])
            row["peak_amps"] = json.dumps([])
            row["peak_areas"] = json.dumps([])
            row["fraction_max"] = 0.0
            row["n_peaks"] = 0
        row["record"] = os.path.basename(path)
        row["n_epoch"] = idx + 1
        row["trigger_sample"] = int(trigger_samples[idx])
        row["trigger_time_ms"] = float(trigger_samples[idx] * 1000 / fs)
        row["mep_amplitude_mV"] = _mep_value_for_epoch(mep_values, "amplitudes_mV", idx, trigger_samples[idx])
        row["mep_baseline_mV"] = _mep_value_for_epoch(mep_values, "baselines_mV", idx, trigger_samples[idx])
        rows.append(row)

    delays = np.asarray([row["delay_ms"] for row in rows], dtype=float)
    early_count = int(np.sum(np.isfinite(delays) & (delays < settings.early_delay_ms)))
    late_count = int(np.sum(np.isfinite(delays) & (delays > settings.late_delay_ms)))
    movement_count = int(np.sum(np.isfinite(delays)))

    df = pd.DataFrame(rows)
    if not df.empty:
        first_cols = [
            "record",
            "n_epoch",
            "movement_found",
            "delay_ms",
            "onset_time",
            "peak_time",
            "mep_amplitude_mV",
            "trigger_sample",
            "trigger_time_ms",
        ]
        rest_cols = [col for col in df.columns if col not in first_cols]
        df = df[first_cols + rest_cols]

    return {
        "record_path": path,
        "record_name": os.path.basename(path),
        "time": time,
        "emg_epochs": emg_epochs,
        "tkeo_epochs": tkeo_epochs,
        "rows": rows,
        "table": df,
        "delays": delays,
        "early_count": early_count,
        "late_count": late_count,
        "movement_count": movement_count,
        "fs": fs,
        "settings": settings.to_dict(),
        "has_mep": bool(mep_values),
    }


def default_results_dir_for_record(record_path):
    record_path = os.path.abspath(record_path)
    parent = os.path.basename(os.path.dirname(record_path))
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(record_path)))
    if parent and grandparent == "data":
        return os.path.abspath(os.path.join("results", parent))
    if parent:
        return os.path.abspath(os.path.join("results", parent))
    return os.path.abspath("results")


def save_analysis_outputs(result, output_dir=None):
    record_path = result["record_path"]
    if output_dir is None:
        output_dir = default_results_dir_for_record(record_path)
    os.makedirs(output_dir, exist_ok=True)

    stem = os.path.splitext(os.path.basename(record_path))[0]
    table_path = os.path.join(output_dir, f"{stem}_movement_detection.csv")
    settings_path = os.path.join(output_dir, f"{stem}_movement_detection_settings.json")
    result["table"].to_csv(table_path, index=False)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(result["settings"], f, indent=2)
    return table_path, settings_path
