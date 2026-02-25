from dataclasses import dataclass, field
from typing import List

@dataclass
class StimuliSettings:
    volume: int = 80
    monitor: int = 3
    record: bool = False
    cross_figure: str = "cross_image_white_photomark.png"
    background_figure: str = "background_white_photomark.png"
    triplet_video: str = "PS__animatedTriplet_750.mkv"
    single_video: str = "PS__animatedSingle_750.mkv"
    SRT_video: str = "PS__SRT.mkv" 
    stimuli: List[str] = field(default_factory=lambda: ["Триплеты", "Одиночные", "SRT"])
    stimuli_curr: int = 1
    stimuli_n: int = 10
    stimuli_inf: bool = True
    cross_ms: int = 2000
    show_feedback: int = 500
    feedback_ms: int = 3000
    feedback_mode: List[str] = field(default_factory=lambda: ["После каждой попытки", "После N попыток", "При превышении", "Без обратной связи"])
    feedback_mode_curr: int = 0
    delay_limit: List[int] = field(default_factory=lambda: [50, 50, 50])
    feedback_n: int = 2
    feedback_w: int = 460
    feedback_h: int = 460
    filename: str = r"00SS_triplets_NoFB.csv"


@dataclass
class PlotSettings:
    ymax: int = 10
    ymin: int = -10
    scale_offset: int = 0
    scale_factor: int = -5
    time_range_ms: int = 4000  # ms    
    

@dataclass
class ProcessingSettings:
    notch_fr: int = 50
    notch_width: int = 1
    butter_order: int = 4
    freq_low: int = 5
    freq_high: int = 40

    do_lowpass: bool = True
    do_highpass: bool = True
    do_butter: bool = True
    do_notch: bool = True
    
    tkeo: bool = False
    extra_samples: int = 500

@dataclass
class DetectionSettings:
    bit: int = 2
    window_ms:  List[int] = field(default_factory=lambda: [-375, 375])
    threshold: int = 4
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