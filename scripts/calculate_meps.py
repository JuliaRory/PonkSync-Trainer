import os
import json

import matplotlib.pyplot as plt
import numpy as np


Fs = 5000
ms_to_samples = lambda x: int(x / 1000 * Fs)

seq1 = np.asarray([1,1,1,1,2,1,2,1,2,1,1,2,1,1,1,2,1,1,1,1,1,1,1,2,1,1,1,2,1,1,1,1,2,1,1,2,1,1,2,1])
seq2 = np.asarray([1,2,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,2,1,1,1,1,1,2,1,1,1,1,2,1,1])
seq3 = np.asarray([1,1,1,1,1,2,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,1,2])
seq4 = np.asarray([1,2,1,1,1,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,1])


def _clean_sequence(seq):
    seq = np.asarray(seq, dtype=int)
    return seq[np.isin(seq, [1, 2])]


def plot_epochs_ax(ax, time, epochs, label, color):
    if epochs.size == 0:
        return
    mean_epoch = np.mean(epochs, axis=0)
    sem_epoch = np.std(epochs, axis=0) / np.sqrt(epochs.shape[0])
    mask = np.where((time >= 10) & (time <= 60))[0]
    ax.plot(time[mask], mean_epoch[mask], label=label, color=color)
    ax.fill_between(
        time[mask],
        mean_epoch[mask] - sem_epoch[mask],
        mean_epoch[mask] + sem_epoch[mask],
        alpha=0.3,
        color=color,
    )
    ax.set_ylim(-0.5, 2)
    ax.grid(color="lightgray", linewidth=0.5)


def plot_epochs(time, epochs, label, color):
    plot_epochs_ax(plt.gca(), time, epochs, label, color)


def plot_all_epochs_ax(ax, time, motor_epochs, rest_epochs, label_motor, label_rest, title):
    plot_epochs_ax(ax, time, -motor_epochs, label_motor, "#961CBB")
    plot_epochs_ax(ax, time, -rest_epochs, label_rest, "#4927C5")
    ax.tick_params(axis="x", labelsize=12)
    ax.tick_params(axis="y", labelsize=12)
    ax.set_xlabel("Время (мс)", fontsize=14)
    ax.set_ylabel("Амплитуда МВП (мВ)", fontsize=14)
    ax.legend(fontsize=18)
    ax.set_title(title, fontsize=20)


def plot_all_epochs(time, motor_epochs, rest_epochs, label_motor, label_rest, title, filename):
    plot_all_epochs_ax(plt.gca(), time, motor_epochs, rest_epochs, label_motor, label_rest, title)
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.clf()


def _calculate_mep(epoch, time, from_ms=15, upto_ms=40):
    mask = (time >= from_ms) & (time <= upto_ms)
    if not np.any(mask):
        return np.nan
    data = epoch[mask]
    if data.size == 0 or not np.any(np.isfinite(data)):
        return np.nan
    return float(np.nanmax(data) - np.nanmin(data))


def _baseline_correction(epochs, time, from_ms=-20, to_ms=-5):
    mask = np.where((time > from_ms) & (time < to_ms))[0]
    baseline_mean = np.mean(epochs[:, mask], axis=1)
    return epochs - baseline_mean.reshape((-1, 1))


def _decode_stimulus_message(message):
    if isinstance(message, bytes):
        message = message.decode("utf-8", errors="replace")
    try:
        data = json.loads(message)
    except (TypeError, json.JSONDecodeError):
        return None
    stimulus = data.get("stimulus") if isinstance(data, dict) else None
    return str(stimulus) if stimulus else None


def _trigger_events_and_block_timestamps(h5f, bit):
    data = h5f["eeg/data"][:-1]
    trigger = data[:, -1]
    ttl = np.array(trigger, dtype=np.uint8)
    trigger = ((ttl >> bit) & 0b1).astype(int)
    trigger_diff = np.diff(trigger)
    events = np.where(trigger_diff == 1)[0] + 1

    block_timestamps = np.full(events.shape, np.nan, dtype=float)
    if "eeg/blocks" in h5f and len(events):
        blocks = h5f["eeg/blocks"][:]
        if "samples" in blocks.dtype.names and "received" in blocks.dtype.names:
            cum_samples = np.cumsum(blocks["samples"].astype(np.int64))
            block_idxs = np.searchsorted(cum_samples, events, side="right")
            block_idxs = np.clip(block_idxs, 0, len(blocks) - 1)
            block_timestamps = blocks["received"][block_idxs].astype(float)

    return data, events, block_timestamps


def _stimulus_labels_from_stream(h5f, events, event_timestamps):
    warnings = []
    if "stimuli/messages" not in h5f:
        return None, warnings

    messages = h5f["stimuli/messages"][:]
    stimuli = []
    for row in messages:
        stimulus = _decode_stimulus_message(row["message"])
        if stimulus is None:
            continue
        stimuli.append({
            "received": float(row["received"]),
            "stimulus": stimulus,
            "label": 2 if "rest" in stimulus.lower() else 1,
        })

    n_events = len(events)
    n_stimuli_original = len(stimuli)
    if n_stimuli_original == n_events + 1:
        stimuli = stimuli[1:]
    elif n_stimuli_original != n_events:
        warnings.append(
            f"Stimuli count ({n_stimuli_original}) does not match trigger events ({n_events}) on the selected bit."
        )

    if not stimuli:
        warnings.append("Stimuli stream exists, but no stimulus messages were decoded.")
        return None, warnings

    stimulus_timestamps = np.asarray([item["received"] for item in stimuli], dtype=float)
    labels = []
    matched_stimuli = []
    for timestamp in event_timestamps:
        if np.isfinite(timestamp):
            idx = int(np.argmin(np.abs(stimulus_timestamps - timestamp)))
        else:
            idx = min(len(labels), len(stimuli) - 1)
        labels.append(stimuli[idx]["label"])
        matched_stimuli.append(stimuli[idx]["stimulus"])

    return {
        "seq": np.asarray(labels, dtype=int),
        "source": "stimuli stream",
        "stimuli_count": n_stimuli_original,
        "trigger_count": n_events,
        "matched_stimuli": matched_stimuli,
        "warnings": warnings,
    }, warnings


def calculate_mep_amp(filename_path, bit, seq=None, return_info=False):
    import h5py

    with h5py.File(filename_path, "r") as h5f:
        data, events, event_timestamps = _trigger_events_and_block_timestamps(h5f, bit)
        stream_info, stream_warnings = _stimulus_labels_from_stream(h5f, events, event_timestamps)

    emg = data[:, 0]
    warnings = list(stream_warnings)
    if stream_info is not None:
        seq = stream_info["seq"]
        source = stream_info["source"]
    else:
        if seq is None:
            raise ValueError("No stimuli stream was found, and no fallback sequence was provided.")
        warnings.append("No stimuli stream was found in HDF. Falling back to the selected saved sequence.")
        seq = _clean_sequence(seq)
        source = "saved sequence fallback"

    start = ms_to_samples(-20)
    end = ms_to_samples(60)
    time = np.linspace(-20, 60, end - start)

    event_labels = np.asarray(seq, dtype=int)
    valid_pairs = [
        (timestamp, label)
        for timestamp, label in zip(events, event_labels)
        if timestamp + start >= 0 and timestamp + end <= emg.size
    ]
    if not valid_pairs:
        valid_events = []
        seq = np.asarray([], dtype=int)
    else:
        valid_events = [timestamp for timestamp, _ in valid_pairs]
        seq = np.asarray([label for _, label in valid_pairs], dtype=int)

    epochs = np.asarray([emg[timestamp + start:timestamp + end] for timestamp in valid_events])
    if epochs.size == 0:
        raise ValueError("No valid MEP epochs found in the selected record.")
    if seq.size != epochs.shape[0]:
        raise ValueError(f"Sequence length ({seq.size}) does not match extracted epochs ({epochs.shape[0]}).")

    amps = np.asarray([_calculate_mep(epoch, time) for epoch in epochs]) * 1e3
    motor_amps = amps[np.where(seq == 1)]
    rest_amps = amps[np.where(seq == 2)]

    print(f"Средняя амплитуда МВП в покое была {np.mean(rest_amps):.3f} мВ. Медиана: {np.median(rest_amps):.3f} мВ.")
    print(f"Средняя амплитуда МВП при движении была {np.mean(motor_amps):.3f} мВ. Медиана: {np.median(motor_amps):.3f} мВ.")

    bas_epochs = _baseline_correction(epochs, time)
    bas_motor_epochs = bas_epochs[np.where(seq == 1)] * 1e3
    bas_rest_epochs = bas_epochs[np.where(seq == 2)] * 1e3

    info = {
        "source": source,
        "warnings": warnings,
        "trigger_count": int(len(events)),
        "stimuli_count": None if stream_info is None else int(stream_info["stimuli_count"]),
        "motor_count": int(bas_motor_epochs.shape[0]),
        "rest_count": int(bas_rest_epochs.shape[0]),
    }
    if return_info:
        return time, bas_motor_epochs, bas_rest_epochs, info
    return time, bas_motor_epochs, bas_rest_epochs


def run(subject, to_analysis):
    for record in to_analysis:
        filename_path = os.path.join("./data", subject, record["record"])
        print(f"-----Испытуемый {subject}, запись {record['record']}-----")
        time, motor_epochs, rest_epochs = calculate_mep_amp(filename_path, 2, record["seq"])

        plot_all_epochs(
            time,
            motor_epochs,
            rest_epochs,
            record["motor_label"],
            "rest",
            f"{subject}: {record['motor_label']} vs rest, {record['power']}",
            os.path.join("data", subject, f"{record['record']}_mep_plot.png"),
        )


# if __name__ == "__main__":
#     run(subject, to_analysis)
