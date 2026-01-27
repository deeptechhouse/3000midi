"""MIDI Clock output using asyncio for timing."""
import asyncio
import time
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MIDI_CLOCK = 0xF8
MIDI_START = 0xFA
MIDI_CONTINUE = 0xFB
MIDI_STOP = 0xFC


@dataclass
class MIDIConfig:
    device: str = "/dev/ttyAMA0"
    baud_rate: int = 31250
    ppqn: int = 24
    min_bpm: float = 20.0
    max_bpm: float = 300.0


class AsyncMIDIOutput:
    """
    Async MIDI clock output.
    Uses asyncio.sleep for coarse timing, busy-wait for fine precision.
    """

    def __init__(self, config: Optional[MIDIConfig] = None):
        self.config = config or MIDIConfig()
        self._writer: Optional[asyncio.StreamWriter] = None
        self._current_bpm: float = 120.0
        self._is_playing: bool = False
        self._running: bool = False
        self._clock_task: Optional[asyncio.Task] = None

        self._clocks_sent = 0
        self._jitter_samples: list = []

        self._pll_correction = 0.0
        self._pll_gain = 0.1

        logger.info(f"AsyncMIDIOutput initialized: {self.config.device}")

    async def start(self) -> None:
        if self._running:
            return

        try:
            import serial_asyncio
            _, self._writer = await serial_asyncio.open_serial_connection(
                url=self.config.device,
                baudrate=self.config.baud_rate,
                bytesize=8,
                parity='N',
                stopbits=1
            )
            logger.info(f"MIDI serial opened: {self.config.device}")
        except ImportError:
            logger.warning("serial_asyncio not available, using mock")
            self._writer = MockAsyncWriter()
        except Exception as e:
            logger.warning(f"Could not open MIDI device: {e}, using mock")
            self._writer = MockAsyncWriter()

        self._running = True
        self._clock_task = asyncio.create_task(self._clock_loop())

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        if self._is_playing:
            await self._write_byte(MIDI_STOP)

        if self._clock_task:
            self._clock_task.cancel()
            try:
                await self._clock_task
            except asyncio.CancelledError:
                pass

        if self._writer and hasattr(self._writer, 'close'):
            self._writer.close()
            if hasattr(self._writer, 'wait_closed'):
                await self._writer.wait_closed()

        logger.info(f"AsyncMIDIOutput stopped. Sent {self._clocks_sent} clocks")

    async def send_start(self) -> None:
        await self._write_byte(MIDI_START)
        self._is_playing = True
        logger.info("MIDI Start sent")

    async def send_stop(self) -> None:
        if not self._is_playing:
            return
        await self._write_byte(MIDI_STOP)
        self._is_playing = False
        logger.info("MIDI Stop sent")

    async def send_clock(self) -> None:
        pass

    async def set_tempo(self, bpm: float) -> None:
        if not (self.config.min_bpm <= bpm <= self.config.max_bpm):
            return
        old_bpm = self._current_bpm
        self._current_bpm = bpm
        if abs(bpm - old_bpm) >= 0.1:
            logger.debug(f"Tempo: {old_bpm:.1f} -> {bpm:.1f} BPM")

    def apply_pll_correction(self, phase_error: float) -> None:
        self._pll_correction = phase_error * self._pll_gain

    async def _clock_loop(self) -> None:
        logger.info("Async MIDI clock loop started")
        next_time = time.monotonic()

        while self._running:
            if not self._is_playing:
                await asyncio.sleep(0.01)
                continue

            interval = 60.0 / (self._current_bpm * self.config.ppqn)
            interval += self._pll_correction
            self._pll_correction = 0.0

            now = time.monotonic()
            wait_time = next_time - now

            if wait_time > 0.002:
                await asyncio.sleep(wait_time - 0.001)

            while time.monotonic() < next_time:
                pass

            await self._write_byte(MIDI_CLOCK)
            self._clocks_sent += 1

            actual_time = time.monotonic()
            jitter = abs(actual_time - next_time)
            self._jitter_samples.append(jitter)
            if len(self._jitter_samples) > 100:
                self._jitter_samples.pop(0)

            next_time += interval

    async def _write_byte(self, byte_val: int) -> None:
        if self._writer:
            self._writer.write(bytes([byte_val]))
            if hasattr(self._writer, 'drain'):
                await self._writer.drain()

    def get_statistics(self) -> dict:
        avg_jitter = sum(self._jitter_samples) / len(self._jitter_samples) if self._jitter_samples else 0
        max_jitter = max(self._jitter_samples) if self._jitter_samples else 0
        return {
            "clocks_sent": self._clocks_sent,
            "average_jitter_ms": avg_jitter * 1000,
            "max_jitter_ms": max_jitter * 1000,
            "current_bpm": self._current_bpm,
            "is_playing": self._is_playing
        }


class MockAsyncWriter:
    """Mock async writer for testing."""

    def __init__(self):
        self.buffer = []

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass
