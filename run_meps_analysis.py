from scripts.calculate_meps import run

import numpy as np

seq1 = np.asarray([1,1,1,1,2,1,2,1,2,1,1,2,1,1,1,2,1,1,1,1,1,1,1,2,1,1,1,2,1,1,1,1,2,1,1,2,1,1,2,1])
seq2 = np.asarray([1,2,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,2,1,1,1,1,1,2,1,1,1,1,2,1,1])
seq3 = np.asarray([1,1,1,1,1,2,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,1,2])
seq4 = np.asarray([1,2,1,1,1,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,1])

subject = "06TG"

to_analysis = [
    {"record": "08_06TG_tms_58MSO_real.hdf", "seq": seq1, "motor_label": "real", "power": "58MSO"},
    {"record": "09_06TG_tms_43MSO_real.hdf", "seq": seq2, "motor_label": "real", "power": "43MSO"},
    {"record": "10_06TG_tms_43MSO_MI.hdf", "seq": seq3, "motor_label": "MI", "power": "43MSO"},
    {"record": "11_06TG_tms_58MSO_MI.hdf", "seq": seq4, "motor_label": "MI", "power": "58MSO"},
]


if __name__ == "__main__":
    run(subject, to_analysis)
