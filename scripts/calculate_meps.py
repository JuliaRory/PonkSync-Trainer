import h5py 
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os


Fs = 5000
ms_to_samples = lambda x: int(x / 1000 * Fs)

seq1 = np.asarray([1,1,1,1,2,1,2,1,2,1,1,2,1,1,1,2,1,1,1,1,1,1,1,2,1,1,1,2,1,1,1,1,2,1,1,2,1,1,2,1])
seq2 = np.asarray([1,2,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,2,1,1,1,1,1,2,1,1,1,1,2,1,1])
seq3 = np.asarray([1,1,1,1,1,2,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,1,2])
seq4 = np.asarray([1,2,1,1,1,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,1])

# subject = "02NS"
# to_analysis = [
#     {"record": "07_tms_68MSO_real.hdf", "seq": seq1, "motor_label": "real", "power": "68MSO"},
#     {"record": "08_tms_50MSO_real.hdf", "seq": seq2, "motor_label": "real", "power": "50MSO"},
#     {"record": "09_tms_68MSO_MI.hdf", "seq": seq3, "motor_label": "MI", "power": "68MSO"},
#     {"record": "10_tms_50MSO_MI.hdf", "seq": seq4, "motor_label": "MI", "power": "50MSO"},
# ]

def plot_epochs(time, epochs, label, color):
    mean_epoch = np.mean(epochs, axis=0)
    sem_epoch = np.std(epochs, axis=0) / np.sqrt(epochs.shape[0])
    mask = np.where((time >= 10) & (time <= 60))[0]
    plt.plot(time[mask], mean_epoch[mask], label=label, color=color)
    plt.fill_between(time[mask], mean_epoch[mask] - sem_epoch[mask], mean_epoch[mask] + sem_epoch[mask], alpha=0.3, color=color)
    amp = 2
    plt.ylim(-0.5, amp)
    plt.grid(color="lightgray", linewidth=0.5)

def plot_all_epochs(time, motor_epochs, rest_epochs, label_motor, label_rest, title, filename):
    plot_epochs(time, -motor_epochs, label_motor, "#961CBB")
    plot_epochs(time, -rest_epochs, label_rest, "#4927C5")
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    plt.xlabel("Время (мс)", fontsize=14)
    plt.ylabel("Амплитуда МВП (мВ)", fontsize=14)
    plt.legend(fontsize=24)
    plt.title(title, fontsize=24)
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.clf()

def calculate_mep_amp(filename_path, bit, seq):
    with h5py.File(filename_path, "r") as h5f:
        data = h5f["eeg/data"][:-1]
    emg = data[:, 0]
    trigger = data[:, -1]
    ttl = np.array(trigger, dtype=np.uint8)
    trigger = ((ttl>>bit) & 0b1).astype(int)
    trigger_diff = np.diff(trigger)
    events = np.where(trigger_diff == 1)[0]
    def cut_epoch(timepoint, data, start, end):
        return data[timepoint+start:timepoint+end]

    start = ms_to_samples(-20)
    end = ms_to_samples(60)
    time = np.linspace(-20, 60, end-start)
    epochs = np.asarray([cut_epoch(timestamp, emg, start, end) for timestamp in events])

    def calculate_mep(epoch, time, from_ms=15, upto_ms=40):
        mask = (time >= from_ms) & (time <= upto_ms)
        if not np.any(mask):
            return np.nan
        data = epoch[mask]
        if data.size == 0 or not np.any(np.isfinite(data)):
            return np.nan
        return float(np.nanmax(data) - np.nanmin(data)) 
    amps = np.asarray([calculate_mep(epoch, time) for epoch in epochs]) * 1e3

    motor_amps = amps[np.where(seq == 1)]
    rest_amps = amps[np.where(seq == 2)]

    print(f"Средняя амплитуда МВП в покое была {np.mean(rest_amps):.3f} мВ. Медиана: {np.median(rest_amps):.3f} мВ.")
    print(f"Средняя амплитуда МВП при движении была {np.mean(motor_amps):.3f} мВ. Медиана: {np.median(motor_amps):.3f} мВ.")

    def baseline_correction(epochs, time, from_ms=-20, to_ms=-5):
        mask = np.where((time > from_ms) & (time<to_ms))[0]
        baseline_mean = np.mean(epochs[:, mask], axis=1)
        return epochs - baseline_mean.reshape((-1, 1))

    bas_epochs = baseline_correction(epochs, time)

    bas_motor_epochs = bas_epochs[np.where(seq == 1)] * 1e3
    bas_rest_epochs = bas_epochs[np.where(seq == 2)] * 1e3

    return time, bas_motor_epochs, bas_rest_epochs


def run(subject, to_analysis):
    for record in to_analysis:
        filename_path = os.path.join(r"./data", subject, record["record"])
        print(f"-----Испытуемый {subject}, запись {record['record']}-----")
        time, motor_epochs, rest_epochs = calculate_mep_amp(filename_path, 2, record["seq"])

        plot_all_epochs(time, motor_epochs, rest_epochs, record["motor_label"], "rest", 
                        f"{subject}: {record["motor_label"]} vs rest, {record["power"]}",
                        os.path.join(r"data", subject, f"{record['record']}_mep_plot.png"))

# if __name__ == "__main__":
#     run(subject, to_analysis)

