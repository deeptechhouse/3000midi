"""Data types for asyncio-based sync bridge."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class BeatInfo:
    """Immutable beat information from CDJ."""
    timestamp: float
    beat_position: int
    bar_position: int
    bpm: float
    pitch_percent: float
    player_number: int
    is_master: bool
    is_playing: bool
    track_time_ms: int


@dataclass
class SyncConfig:
    """Configuration for sync bridge."""
    prodjlink_interface: str = "eth0"
    prodjlink_port: int = 50001
    midi_device: str = "/dev/ttyAMA0"
    midi_baud: int = 31250
    midi_ppqn: int = 24
    cc_device: Optional[str] = "/dev/ttyUSB0"
    cc_baud: int = 115200
    cc_gpio_pin: int = 27
    enable_pll: bool = True
    jitter_threshold_ms: float = 2.0
    log_level: str = "INFO"
