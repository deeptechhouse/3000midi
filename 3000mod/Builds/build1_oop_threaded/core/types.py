"""Data classes and type definitions for CDJ Sync Bridge."""
from dataclasses import dataclass
from typing import Optional
from enum import Enum, auto


@dataclass(frozen=True)
class BeatInfo:
    """
    Represents a single beat event from CDJ-3000.
    Immutable dataclass ensures thread safety.
    """
    timestamp: float
    beat_position: int
    bar_position: int
    bpm: float
    pitch_percent: float
    player_number: int
    is_master: bool
    is_playing: bool
    track_time_ms: int

    def __post_init__(self):
        if not (1 <= self.beat_position <= 4):
            object.__setattr__(self, 'beat_position', max(1, min(4, self.beat_position)))
        if not (1 <= self.player_number <= 4):
            object.__setattr__(self, 'player_number', max(1, min(4, self.player_number)))


@dataclass
class SyncConfig:
    """Configuration parameters for sync system."""
    prodjlink_interface: str = "eth0"
    prodjlink_port: int = 50001
    midi_device: str = "/dev/ttyAMA0"
    midi_baud: int = 31250
    midi_ppqn: int = 24
    cc_device: Optional[str] = None
    cc_baud: int = 115200
    cc_gpio_de_pin: int = 27
    latency_compensation_ms: float = 5.0
    jitter_threshold_ms: float = 2.0
    enable_pll: bool = True
    log_level: str = "INFO"
    log_file: str = "/var/log/cdj_sync.log"
    log_beat_events: bool = False


class PlayerState(Enum):
    """CDJ player states."""
    STOPPED = auto()
    LOADING = auto()
    PAUSED = auto()
    PLAYING = auto()
    CUEING = auto()
    ERROR = auto()
