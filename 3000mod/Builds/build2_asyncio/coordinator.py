"""Async coordinator orchestrating sync between devices."""
import asyncio
import logging
from typing import List, Optional
from dataclasses import dataclass, field

from core.types import BeatInfo

logger = logging.getLogger(__name__)


@dataclass
class CoordinatorStats:
    beat_count: int = 0
    current_bpm: float = 0.0
    is_playing: bool = False
    jitter_samples: List[float] = field(default_factory=list)


class AsyncSyncCoordinator:
    """
    Async coordinator using Python's Protocol typing for duck typing.
    No inheritance required - uses structural subtyping.
    """

    def __init__(self, input_device, output_devices: list):
        self.input = input_device
        self.outputs = output_devices
        self._running = False
        self._last_beat: Optional[BeatInfo] = None
        self._was_playing = False
        self._stats = CoordinatorStats()

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self.input.on_beat(self._handle_beat)

        start_tasks = [o.start() for o in self.outputs]
        await asyncio.gather(*start_tasks, return_exceptions=True)

        await self.input.start()
        logger.info("AsyncSyncCoordinator started")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        await self.input.stop()

        stop_tasks = []
        for o in self.outputs:
            stop_tasks.append(o.send_stop())
            stop_tasks.append(o.stop())

        await asyncio.gather(*stop_tasks, return_exceptions=True)
        logger.info("AsyncSyncCoordinator stopped")

    async def _handle_beat(self, beat: BeatInfo) -> None:
        if not self._running:
            return

        self._stats.beat_count += 1
        self._stats.current_bpm = beat.bpm

        if self._last_beat:
            expected = 60.0 / beat.bpm
            actual = beat.timestamp - self._last_beat.timestamp
            jitter = abs(actual - expected)
            self._stats.jitter_samples.append(jitter)
            if len(self._stats.jitter_samples) > 100:
                self._stats.jitter_samples.pop(0)

        if beat.is_playing and not self._was_playing:
            self._stats.is_playing = True
            await asyncio.gather(
                *[o.send_start() for o in self.outputs],
                return_exceptions=True
            )

        elif not beat.is_playing and self._was_playing:
            self._stats.is_playing = False
            await asyncio.gather(
                *[o.send_stop() for o in self.outputs],
                return_exceptions=True
            )

        self._was_playing = beat.is_playing

        tempo_tasks = [o.set_tempo(beat.bpm) for o in self.outputs]
        if beat.is_playing:
            tempo_tasks.extend([o.send_clock() for o in self.outputs])

        await asyncio.gather(*tempo_tasks, return_exceptions=True)
        self._last_beat = beat

    def get_statistics(self) -> dict:
        avg_jitter = (
            sum(self._stats.jitter_samples) / len(self._stats.jitter_samples)
            if self._stats.jitter_samples else 0.0
        )
        return {
            "beat_count": self._stats.beat_count,
            "current_bpm": self._stats.current_bpm,
            "is_playing": self._stats.is_playing,
            "average_jitter_ms": avg_jitter * 1000
        }
