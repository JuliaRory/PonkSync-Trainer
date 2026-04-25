from dataclasses import dataclass, field
from typing import List

@dataclass
class StimuliSettings:
    volume: int = 80
    monitor: int = 2
    record: bool = False
    cross_figure: str = "cross_image_white_photomark.png"
    background_figure: str = "background_white_photomark.png"
    # triplet_video: str = "PS__animatedTriplet_750_L.mkv"
    # single_video: str = "PS__animatedSingle_750_L.mkv"
    triplet_video: str = "animatedTriplet_tms3_0ms_allsounds.mkv"
    single_video: str = "animatedSingle1500_tms_0ms_nosounds.mkv"
    SRT_video: str = "PS__SRT.mkv" 
    SST_video: str = "animatedSingle1500_stop-200ms_tms_0ms_nosounds.mkv"
    
    stimuli: List[str] = field(default_factory=lambda: ["Одиночные", "Одиночные SST", "Триплеты", "Триплеты SST"])
    stimuli_type: List[str] = field(default_factory=lambda: ["Круг", "Вертикальный бар", "Горизонтальный бар"])
    fps: List[str] = field(default_factory=lambda: ['60', '120'])
    
    stimuli_curr: int = 0
    stimuli_type_curr: int = 2
    fps_curr: int = 1

    stimuli_n: int = 10
    stimuli_inf: bool = True
    cross_ms: int = 2000
    show_feedback: int = 1000
    feedback_ms: int = 1500
    feedback_mode: List[str] = field(default_factory=lambda: ["После каждой попытки", "После N попыток", "При превышении", "Без обратной связи"])
    feedback_mode_curr: int = 0
    feedback_form: List[str] = field(default_factory=lambda: ["Plot", "On the bar"])
    feedback_form_curr: int = 0
    delay_limit: List[int] = field(default_factory=lambda: [50, 50, 50])
    feedback_n: int = 2
    feedback_w: int = 460
    feedback_h: int = 460
    feedback_bar_height_px: int = 150
    feedback_bar_scale_px: int = 610
    feedback_bar_scale_ms: int = 1500

    subject: str = r"00SS"
    filename: str = r"test"


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
    freq_high: int = 90

    do_lowpass: bool = True
    do_highpass: bool = True
    do_butter: bool = True
    do_notch: bool = True
    
    tkeo: bool = True
    extra_samples: int = 500
    montage_list: List[str] = field(default_factory=lambda: ["bipolar", "monopolar"])
    montage: str = 0
    emg_channels_bipolar: List[int] = field(default_factory=lambda: [64, 65])
    emg_channels_monopolar: int = 0

    freq: int = 5000 # Hz

@dataclass
class DetectionSettings:
    bit: int = 4
    window_ms:  List[int] = field(default_factory=lambda: [-375, 375])
    threshold: int = 4
    threshold_mv: float = 0.5
    thr_adaptive: bool = False
    baseline_ms: int = 250
    n_sd: int = 15
    mov_detect_criterio: str = "max"



@dataclass
class Settings:
    data_source: str = "nvx136"  # "SPEED"
    

    Fs: int = 5000  # Hz
    
    detection_settings: DetectionSettings = field(default_factory=DetectionSettings)
    plot_settings: PlotSettings = field(default_factory=PlotSettings)
    processing_settings: ProcessingSettings = field(default_factory=ProcessingSettings)
    stimuli_settings: StimuliSettings = field(default_factory=StimuliSettings)

    activate_bat: bool = True
    bat_file: str = "D:\Resonance\dist_2025\control_ponk.bat"
    bat_file_home: str = "C:/Users/hodor/Documents/lab-MSU/Works/2025.10_TMS/dist_2024_11_13_imp/control.bat"
