from scripts.calculate_meps import run

import numpy as np

seq1 = np.asarray([1,1,1,1,2,1,2,1,2,1,1,2,1,1,1,2,1,1,1,1,1,1,1,2,1,1,1,2,1,1,1,1,2,1,1,2,1,1,2,1])
seq2 = np.asarray([1,2,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,2,1,1,1,1,1,2,1,1,1,1,2,1,1])
seq3 = np.asarray([1,1,1,1,1,2,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,1,2])
seq4 = np.asarray([1,2,1,1,1,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,1])

subject = "05UB"
to_analysis = [
    {"record": "09_05UB_tms_41MSO_real.hdf", "seq": seq1, "motor_label": "real", "power": "41MSO"},
    {"record": "10_05UB_tms_33MSO_real.hdf", "seq": seq2, "motor_label": "real", "power": "33MSO"},
    {"record": "11_05UB_tms_41MSO_MI.hdf", "seq": seq3, "motor_label": "MI", "power": "33MSO"},
    {"record": "12_05UB_tms_33MSO_MI.hdf", "seq": seq4, "motor_label": "MI", "power": "41MSO"},
]


if __name__ == "__main__":
    run(subject, to_analysis)
