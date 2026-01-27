"""Protocol definitions using Python Protocol for structural typing."""
from typing import Protocol, Callable, Awaitable
from .types import BeatInfo


class SyncInput(Protocol):
    """Protocol for sync input devices."""

    async def start(self) -> None:
        """Start receiving sync signals."""
        ...

    async def stop(self) -> None:
        """Stop receiving and cleanup."""
        ...

    def on_beat(self, callback: Callable[[BeatInfo], Awaitable[None]]) -> None:
        """Register async callback for beat events."""
        ...


class SyncOutput(Protocol):
    """Protocol for sync output devices."""

    async def start(self) -> None:
        """Initialize output device."""
        ...

    async def stop(self) -> None:
        """Stop and cleanup."""
        ...

    async def send_clock(self) -> None:
        """Send clock pulse."""
        ...

    async def send_start(self) -> None:
        """Send transport start."""
        ...

    async def send_stop(self) -> None:
        """Send transport stop."""
        ...

    async def set_tempo(self, bpm: float) -> None:
        """Update tempo."""
        ...
