"""Abstract base classes defining sync device interfaces."""
from abc import ABC, abstractmethod
from typing import Callable, List
from .types import BeatInfo


class SyncInputDevice(ABC):
    """Abstract base class for sync input devices."""

    @abstractmethod
    def start(self) -> None:
        """Start listening for sync signals."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop listening and clean up resources."""
        pass

    @abstractmethod
    def register_callback(self, callback: Callable[[BeatInfo], None]) -> None:
        """Register callback for beat events."""
        pass


class SyncOutputDevice(ABC):
    """Abstract base class for sync output devices."""

    @abstractmethod
    def start(self) -> None:
        """Initialize and start the output device."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop and clean up the output device."""
        pass

    @abstractmethod
    def send_clock_pulse(self, timestamp: float) -> None:
        """Send a timing clock pulse."""
        pass

    @abstractmethod
    def send_start(self) -> None:
        """Send transport start command."""
        pass

    @abstractmethod
    def send_stop(self) -> None:
        """Send transport stop command."""
        pass

    @abstractmethod
    def set_tempo(self, bpm: float) -> None:
        """Update tempo setting."""
        pass
