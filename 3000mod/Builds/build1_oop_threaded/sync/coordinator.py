"""Synchronization coordinator orchestrating input and output devices."""
import threading
import logging
from typing import List, Optional
from dataclasses import dataclass

from core.interfaces import SyncInputDevice, SyncOutputDevice
from core.types import BeatInfo

logger = logging.getLogger(__name__)


@dataclass
class TimingConfig:
    enable_pll: bool = True
    jitter_threshold_ms: float = 2.0
    latency_compensation_ms: float = 3.0


class SyncCoordinator:
    """
    Central coordinator for beat synchronization.
    Follows Dependency Inversion Principle - depends on abstractions.
    """

    def __init__(
        self,
        input_device: SyncInputDevice,
        output_devices: List[SyncOutputDevice],
        timing_config: Optional[TimingConfig] = None
    ):
        self.input_device = input_device
        self.output_devices = output_devices
        self.timing_config = timing_config or TimingConfig()

        self._running = False
        self._lock = threading.Lock()

        self._last_beat: Optional[BeatInfo] = None
        self._beat_count = 0
        self._was_playing = False

        self._jitter_samples: List[float] = []
        self._max_samples = 100

        logger.info(f"SyncCoordinator initialized with {len(output_devices)} outputs")

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        self.input_device.register_callback(self._on_beat_received)

        for output in self.output_devices:
            try:
                output.start()
            except Exception as e:
                logger.error(f"Failed to start output: {e}")

        self.input_device.start()
        logger.info("SyncCoordinator started")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False

        self.input_device.stop()

        for output in self.output_devices:
            try:
                output.send_stop()
                output.stop()
            except Exception as e:
                logger.error(f"Failed to stop output: {e}")

        logger.info("SyncCoordinator stopped")

    def _on_beat_received(self, beat: BeatInfo) -> None:
        with self._lock:
            if not self._running:
                return

            self._beat_count += 1

            if self._last_beat:
                expected_interval = 60.0 / beat.bpm
                actual_interval = beat.timestamp - self._last_beat.timestamp
                jitter = abs(actual_interval - expected_interval)
                self._jitter_samples.append(jitter)
                if len(self._jitter_samples) > self._max_samples:
                    self._jitter_samples.pop(0)

            if beat.is_playing and not self._was_playing:
                for output in self.output_devices:
                    try:
                        output.send_start()
                    except Exception as e:
                        logger.error(f"Error sending start: {e}")

            elif not beat.is_playing and self._was_playing:
                for output in self.output_devices:
                    try:
                        output.send_stop()
                    except Exception as e:
                        logger.error(f"Error sending stop: {e}")

            self._was_playing = beat.is_playing

            for output in self.output_devices:
                try:
                    output.set_tempo(beat.bpm)
                    if beat.is_playing:
                        output.send_clock_pulse(beat.timestamp)
                except Exception as e:
                    logger.error(f"Error updating output: {e}")

            self._last_beat = beat

    def get_statistics(self) -> dict:
        with self._lock:
            avg_jitter = (
                sum(self._jitter_samples) / len(self._jitter_samples)
                if self._jitter_samples else 0.0
            )
            max_jitter = max(self._jitter_samples) if self._jitter_samples else 0.0

            return {
                "beat_count": self._beat_count,
                "average_jitter_ms": avg_jitter * 1000,
                "max_jitter_ms": max_jitter * 1000,
                "is_playing": self._was_playing,
                "current_bpm": self._last_beat.bpm if self._last_beat else 0.0
            }
