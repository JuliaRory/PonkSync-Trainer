from dataclasses import dataclass, field
from typing import List

@dataclass
class StimuliSettings:
    volume: int = 80
    monitor: int = 3
    record: bool = False
    cross_figure: str = "cross_image_white_photomark.png"
    triplet_video: str = "OffsetTriplet_0__soa750_audio-30_freq440_dur50_trigWB.mkv"
    cross_ms: int = 3000

@dataclass
class PlotSettings:
    ymax: int = 2
    ymin: int = 0
    scale_offset: int = 0
    scale_factor: int = -10
    time_range_ms: int = 4000  # ms    
    

@dataclass
class ProcessingSettings:
    notch_fr: int = 50
    notch_width: int = 1
    butter_order: int = 4
    freq_low: int = 30
    freq_high: int = 500

    do_lowpass: bool = True
    do_highpass: bool = True
    do_butter: bool = True
    do_notch: bool = True
    
    tkeo: bool = True
    extra_samples: int = 500

@dataclass
class DetectionSettings:
    window_ms:  List[int] = field(default_factory=lambda: [-500, 500])
    threshold: int = 10
    threshold_mv: float = 0.5
    thr_adaptive: bool = False
    baseline_ms: int = 250
    n_sd: int = 15


@dataclass
class Settings:
    data_source: str = "nvx136"  # "SPEED"
    emg_channels: List[int] = field(default_factory=lambda: [64, 65])

    Fs: int = 5000  # Hz
    bit_index: int = 0
    
    detection_settings: DetectionSettings = field(default_factory=DetectionSettings)
    plot_settings: PlotSettings = field(default_factory=PlotSettings)
    processing_settings: ProcessingSettings = field(default_factory=ProcessingSettings)
    stimuli_settings: StimuliSettings = field(default_factory=StimuliSettings)