from dataclasses import dataclass, field
from typing import List

@dataclass
class PlotSettings:
    ymax: int = 2
    ymin: int = -2
    scale_offset: int = 0
    scale_factor: int = -3
    time_range_ms: int = 6000  # ms
    

@dataclass
class ProcessingSettings:
    notch_fr: int = 50
    notch_width: int = 1
    butter_order: int = 4
    freq_low: int = 5
    freq_high: int = 150
    do_lowpass: bool = True
    do_highpass: bool = True
    do_butter: bool = True
    do_notch: bool = True
    
    extra_samples: int = 500

@dataclass
class Settings:
    data_source: str = "nvx136"  # "SPEED"
    emg_channels: List[int] = field(default_factory=lambda: [64, 65])

    Fs: int = 1000  # Hz
    bit_index: int = 0

    plot_settings: PlotSettings = field(default_factory=PlotSettings)
    processing_settings: ProcessingSettings = field(default_factory=ProcessingSettings)