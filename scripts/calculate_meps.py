import os

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


def calculate_mep_amp(filename_path, bit, seq):
    import h5py

    seq = _clean_sequence(seq)
    with h5py.File(filename_path, "r") as h5f:
        data = h5f["eeg/data"][:-1]

    emg = data[:, 0]
    trigger = data[:, -1]
    ttl = np.array(trigger, dtype=np.uint8)
    trigger = ((ttl >> bit) & 0b1).astype(int)
    trigger_diff = np.diff(trigger)
    events = np.where(trigger_diff == 1)[0]

    start = ms_to_samples(-20)
    end = ms_to_samples(60)
    time = np.linspace(-20, 60, end - start)
    valid_events = [timestamp for timestamp in events if timestamp + start >= 0 and timestamp + end <= emg.size]
    if seq.size:
        valid_events = valid_events[:seq.size]
        seq = seq[:len(valid_events)]
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
