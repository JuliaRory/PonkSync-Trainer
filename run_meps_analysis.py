from scripts.calculate_meps import run

import numpy as np

seq1 = np.asarray([1,1,1,1,2,1,2,1,2,1,1,2,1,1,1,2,1,1,1,1,1,1,1,2,1,1,1,2,1,1,1,1,2,1,1,2,1,1,2,1])
seq2 = np.asarray([1,2,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,2,1,1,1,1,1,2,1,1,1,1,2,1,1])
seq3 = np.asarray([1,1,1,1,1,2,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,1,2])
seq4 = np.asarray([1,2,1,1,1,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,1])

subject = "04KK"
to_analysis = [
    {"record": "08_04KK_tms_40MSO_real.hdf", "seq": seq1, "motor_label": "real", "power": "40MSO"},
    {"record": "09_04KK_tms_32MSO_real.hdf", "seq": seq1, "motor_label": "real", "power": "32MSO"},
    {"record": "10_04KK_tms_32MSO_MI.hdf", "seq": seq3, "motor_label": "MI", "power": "32MSO"},
    {"record": "11_04KK_tms_40MSO_MI.hdf", "seq": seq4, "motor_label": "MI", "power": "40MSO"},
]


if __name__ == "__main__":
    run(subject, to_analysis)
