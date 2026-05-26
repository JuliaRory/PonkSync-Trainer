from scripts.calculate_meps import run

import numpy as np

seq1 = np.asarray([1,1,1,1,2,1,2,1,2,1,1,2,1,1,1,2,1,1,1,1,1,1,1,2,1,1,1,2,1,1,1,1,2,1,1,2,1,1,2,1])
seq2 = np.asarray([1,2,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,2,1,1,1,1,1,2,1,1,1,1,2,1,1])
seq3 = np.asarray([1,1,1,1,1,2,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,1,1,2,1,1,2,1,1,2,1,1,1,1,1,2])
seq4 = np.asarray([1,2,1,1,1,1,1,1,2,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,2,1,1,2,1,1,1,1,2,1,2,1,1,1,1])

subject = "15SZ"
power_quasi = 43
power_supthr = 52

def get_numbers(number=1):
    if number < 10:
        return f"0{number}"
    return str(number)

first_number = 6
trigger_bit = 0

# Source of motor/rest labels:
# "auto"    - use the HDF stimuli stream when it exists, otherwise fall back to seq.
# "stimuli" - force labels from the HDF stimuli/messages stream.
# "seq"     - force the manually specified seq in to_analysis.
sequence_source = "auto"

to_analysis = [
    {"record": f"{get_numbers(first_number)}_{subject}_tms_{power_supthr}MSO_real.hdf", "seq": seq1, "motor_label": "real", "power": f"{power_supthr}MSO"},
    {"record": f"{get_numbers(first_number + 1)}_{subject}_tms_{power_quasi}MSO_real.hdf", "seq": seq2, "motor_label": "real", "power": f"{power_quasi}MSO"},
    {"record": f"{get_numbers(first_number + 2)}_{subject}_tms_{power_quasi}MSO_MI.hdf", "seq": seq3, "motor_label": "MI", "power": f"{power_quasi}MSO"},
    {"record": f"{get_numbers(first_number + 3)}_{subject}_tms_{power_supthr}MSO_MI.hdf", "seq": seq4, "motor_label": "MI", "power": f"{power_supthr}MSO"},
]


if __name__ == "__main__":
    run(subject, to_analysis, bit=trigger_bit, sequence_source=sequence_source)
