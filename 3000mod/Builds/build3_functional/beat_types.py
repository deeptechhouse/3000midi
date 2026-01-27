"""Immutable types using NamedTuple for functional style."""
from typing import NamedTuple, Callable, List, Dict, Any
from enum import Enum, auto


class Beat(NamedTuple):
    """Immutable beat event."""
    timestamp: float
    beat_pos: int
    bar_pos: int
    bpm: float
    pitch: float
    player: int
    is_master: bool
    is_playing: bool
    track_ms: int


class Event(NamedTuple):
    """Generic event with type and payload."""
    type: str
    payload: Any
    timestamp: float


class EventType(Enum):
    """Event types for the sync bridge."""
    BEAT = auto()
    TEMPO_CHANGE = auto()
    TRANSPORT_START = auto()
    TRANSPORT_STOP = auto()
    CLOCK_TICK = auto()
    ERROR = auto()


EventHandler = Callable[[Event], None]


def make_beat(
    timestamp: float,
    beat_pos: int = 1,
    bar_pos: int = 1,
    bpm: float = 120.0,
    pitch: float = 0.0,
    player: int = 1,
    is_master: bool = True,
    is_playing: bool = True,
    track_ms: int = 0
) -> Beat:
    """Factory function for Beat creation with defaults."""
    return Beat(
        timestamp=timestamp,
        beat_pos=max(1, min(4, beat_pos)),
        bar_pos=bar_pos,
        bpm=max(20.0, min(300.0, bpm)),
        pitch=pitch,
        player=max(1, min(4, player)),
        is_master=is_master,
        is_playing=is_playing,
        track_ms=track_ms
    )


def beat_to_event(beat: Beat) -> Event:
    """Convert Beat to Event."""
    import time
    return Event(
        type=EventType.BEAT.name,
        payload=beat,
        timestamp=time.monotonic()
    )
