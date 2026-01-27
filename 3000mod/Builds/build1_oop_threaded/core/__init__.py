"""Core module containing types, interfaces, and errors."""
from .types import BeatInfo, SyncConfig, PlayerState
from .interfaces import SyncInputDevice, SyncOutputDevice
from .errors import SyncDeviceError

__all__ = [
    'BeatInfo', 'SyncConfig', 'PlayerState',
    'SyncInputDevice', 'SyncOutputDevice',
    'SyncDeviceError'
]
