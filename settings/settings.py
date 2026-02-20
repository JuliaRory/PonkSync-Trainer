from dataclasses import dataclass, field
from typing import List

@dataclass
class StimuliSettings:
    volume: int = 80
    monitor: int = 2
    record: bool = False
    cross_figure: str = "cross_image_white_photomark_left.png"
    triplet_video: str = "OffsetTriplet_+750_soa750_audio_30_freq440_dur50_trigWB_3ponk_trig_left.mkv"
    cross_ms: int = 2000
    show_feedback: int = 500
    feedback_ms: int = 3000
    feedback_mode: List[str] = field(default_factory=lambda: ["После каждой попытки", "После N попыток", "При превышении"])
    feedback_mode_curr: int = 0
    delay_limit: List[int] = field(default_factory=lambda: [50, 50, 50])
    feedback_n: int = 2


@dataclass
class PlotSettings:
    ymax: int = 10
    ymin: int = 0
    scale_offset: int = 0
    scale_factor: int = -10
    time_range_ms: int = 4000  # ms    
    

@dataclass
class ProcessingSettings:
    notch_fr: int = 50
    notch_width: int = 1
    butter_order: int = 4
    freq_low: int = 5
    freq_high: int = 75

    do_lowpass: bool = True
    do_highpass: bool = True
    do_butter: bool = True
    do_notch: bool = True
    
    tkeo: bool = True
    extra_samples: int = 500

@dataclass
class DetectionSettings:
    bit: int = 0
    window_ms:  List[int] = field(default_factory=lambda: [-300, 100])
    threshold: int = 1
    threshold_mv: float = 0.5
    thr_adaptive: bool = False
    baseline_ms: int = 250
    n_sd: int = 15


@dataclass
class Settings:
    data_source: str = "nvx136"  # "SPEED"
    emg_channels_monopolar: List[int] = field(default_factory=lambda: [64, 65])
    emg_channels_bipolar: List[int] = field(default_factory=lambda: [64])

    Fs: int = 5000  # Hz
    
    detection_settings: DetectionSettings = field(default_factory=DetectionSettings)
    plot_settings: PlotSettings = field(default_factory=PlotSettings)
    processing_settings: ProcessingSettings = field(default_factory=ProcessingSettings)
    stimuli_settings: StimuliSettings = field(default_factory=StimuliSettings)