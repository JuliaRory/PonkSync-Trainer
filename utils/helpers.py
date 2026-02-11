

def get_time_ticks(max_time):   
    # max_time: [ms]
    # Returns: d_time [ms]
    if max_time >= 40:
        return 10
    elif max_time >=20:
        return 5
    else:
        return 2

def get_voltage_ticks(amp, n_tick=4):
    return amp / n_tick