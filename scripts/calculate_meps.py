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


def _epoch_amp_stats(epochs, time):
    if epochs.size == 0:
        return np.nan, np.nan
    amps = np.asarray([_calculate_mep(epoch, time) for epoch in epochs], dtype=float)
    return float(np.nanmean(amps)), float(np.nanstd(amps, ddof=1 if amps.size > 1 else 0))


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


def _stimulus_label_from_name(stimulus):
    name = os.path.basename(str(stimulus)).lower()
    if "rest" in name:
        return 2
    if "countdown" in name or "cross" in name:
        return None
    return 1


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
    ignored_count = 0
    for row in messages:
        stimulus = _decode_stimulus_message(row["message"])
        if stimulus is None:
            continue
        label = _stimulus_label_from_name(stimulus)
        if label is None:
            ignored_count += 1
            continue
        stimuli.append({
            "received": float(row["received"]),
            "stimulus": stimulus,
            "label": label,
        })

    n_events = len(events)
    n_messages = len(messages)
    n_trial_stimuli = len(stimuli)
    if n_trial_stimuli == n_events + 1:
        stimuli = stimuli[1:]
    elif n_trial_stimuli != n_events:
        warnings.append(
            f"Trial stimuli count ({n_trial_stimuli}) does not match trigger events ({n_events}) on the selected bit."
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
        "stimuli_count": n_trial_stimuli,
        "stimuli_message_count": n_messages,
        "ignored_stimuli_count": ignored_count,
        "trigger_count": n_events,
        "matched_stimuli": matched_stimuli,
        "warnings": warnings,
    }, warnings


def _sequence_from_source(seq, stream_info, sequence_source):
    source_key = str(sequence_source or "auto").lower()
    if source_key not in {"auto", "stimuli", "stream", "seq", "sequence"}:
        raise ValueError(f"Unknown MEP sequence source: {sequence_source!r}.")

    if source_key in {"stimuli", "stream"}:
        if stream_info is None:
            raise ValueError("Stimuli stream was requested, but no usable stimuli stream was found in HDF.")
        return stream_info["seq"], stream_info["source"], [], True

    if source_key in {"seq", "sequence"}:
        if seq is None:
            raise ValueError("Manual sequence was requested, but no seq was provided.")
        return _clean_sequence(seq), "manual seq", [], False

    if stream_info is not None:
        return stream_info["seq"], stream_info["source"], [], True

    if seq is None:
        raise ValueError("No usable stimuli stream was found, and no fallback sequence was provided.")
    return _clean_sequence(seq), "manual seq fallback", [
        "No usable stimuli stream was found in HDF. Falling back to the provided sequence."
    ], False


def calculate_mep_amp(filename_path, bit, seq=None, return_info=False, sequence_source="auto"):
    import h5py

    with h5py.File(filename_path, "r") as h5f:
        data, events, event_timestamps = _trigger_events_and_block_timestamps(h5f, bit)
        stream_info, stream_warnings = _stimulus_labels_from_stream(h5f, events, event_timestamps)

    emg = data[:, 0]
    seq, source, source_warnings, uses_stream = _sequence_from_source(seq, stream_info, sequence_source)
    warnings = list(stream_warnings) if uses_stream else []
    warnings.extend(source_warnings)

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
        "stimuli_message_count": None if stream_info is None else int(stream_info["stimuli_message_count"]),
        "ignored_stimuli_count": None if stream_info is None else int(stream_info["ignored_stimuli_count"]),
        "motor_count": int(bas_motor_epochs.shape[0]),
        "rest_count": int(bas_rest_epochs.shape[0]),
    }
    if return_info:
        return time, bas_motor_epochs, bas_rest_epochs, info
    return time, bas_motor_epochs, bas_rest_epochs


def run(subject, to_analysis, bit=2, sequence_source="auto"):
    for record in to_analysis:
        filename_path = os.path.join("./data", subject, record["record"])
        print(f"-----Испытуемый {subject}, запись {record['record']}-----")
        record_bit = int(record.get("bit", bit))
        record_sequence_source = record.get("sequence_source", sequence_source)
        time, motor_epochs, rest_epochs, info = calculate_mep_amp(
            filename_path,
            record_bit,
            record.get("seq"),
            return_info=True,
            sequence_source=record_sequence_source,
        )
        print(
            f"Источник разметки: {info['source']}; bit {record_bit}; "
            f"motor: {info['motor_count']}, rest: {info['rest_count']}."
        )
        for warning in info.get("warnings", []):
            print(f"WARNING: {warning}")
        motor_mean_amp, motor_std_amp = _epoch_amp_stats(motor_epochs, time)
        rest_mean_amp, rest_std_amp = _epoch_amp_stats(rest_epochs, time)

        plot_all_epochs(
            time,
            motor_epochs,
            rest_epochs,
            record["motor_label"],
            "rest",
            (
                f"{subject}, {record['power']}\n"
                f"motor: {motor_mean_amp:.2f} ± {motor_std_amp:.2f} mV; "
                f"rest: {rest_mean_amp:.2f} ± {rest_std_amp:.2f} mV"
            ),
            os.path.join("data", subject, f"{record['record']}_mep_plot.png"),
        )


# if __name__ == "__main__":
#     run(subject, to_analysis)
