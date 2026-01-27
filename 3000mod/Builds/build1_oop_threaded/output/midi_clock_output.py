"""MIDI Clock output with precise timing using threading."""
import threading
import time
import logging
from typing import Optional
from dataclasses import dataclass

from core.interfaces import SyncOutputDevice
from core.errors import SyncDeviceError

logger = logging.getLogger(__name__)

MIDI_CLOCK = 0xF8
MIDI_START = 0xFA
MIDI_CONTINUE = 0xFB
MIDI_STOP = 0xFC


@dataclass
class MIDIClockConfig:
    device: str = "/dev/ttyAMA0"
    baud_rate: int = 31250
    ppqn: int = 24
    latency_compensation_ms: float = 3.0
    min_bpm: float = 20.0
    max_bpm: float = 300.0


class MIDIClockOutput(SyncOutputDevice):
    """
    MIDI Clock output device using dedicated timing thread.
    Uses busy-wait for sub-millisecond precision.
    """

    def __init__(self, config: Optional[MIDIClockConfig] = None):
        self.config = config or MIDIClockConfig()
        self._serial = None
        self._current_bpm: float = 120.0
        self._clock_interval: float = self._calculate_interval(120.0)
        self._next_clock_time: float = 0.0
        self._is_playing: bool = False
        self._running: bool = False

        self._clock_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._clocks_sent = 0
        self._jitter_sum = 0.0
        self._max_jitter = 0.0

        self._pll_enabled = True
        self._pll_phase_error = 0.0
        self._pll_gain = 0.1

        logger.info(f"MIDIClockOutput initialized: {self.config.device}")

    def start(self) -> None:
        with self._lock:
            if self._running:
                return

            try:
                import serial
                self._serial = serial.Serial(
                    port=self.config.device,
                    baudrate=self.config.baud_rate,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=None,
                    write_timeout=0.1
                )
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()
                logger.info(f"MIDI serial port opened: {self.config.device}")

            except ImportError:
                logger.warning("pyserial not available, using mock serial")
                self._serial = MockSerial()
            except Exception as e:
                logger.warning(f"Could not open {self.config.device}: {e}, using mock")
                self._serial = MockSerial()

            self._running = True
            self._clock_thread = threading.Thread(
                target=self._clock_loop,
                name="MIDI-Clock-Generator",
                daemon=True
            )
            self._clock_thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return

            if self._is_playing:
                try:
                    self._send_byte(MIDI_STOP)
                except Exception:
                    pass

            self._running = False

        if self._clock_thread and self._clock_thread.is_alive():
            self._clock_thread.join(timeout=2.0)

        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

        logger.info(f"MIDIClockOutput stopped. Sent {self._clocks_sent} clocks")

    def send_start(self) -> None:
        with self._lock:
            if not self._serial:
                return
            self._send_byte(MIDI_START)
            self._is_playing = True
            self._next_clock_time = time.monotonic()
            logger.info("MIDI Start sent")

    def send_stop(self) -> None:
        with self._lock:
            if not self._is_playing:
                return
            self._send_byte(MIDI_STOP)
            self._is_playing = False
            logger.info("MIDI Stop sent")

    def send_continue(self) -> None:
        with self._lock:
            self._send_byte(MIDI_CONTINUE)
            self._is_playing = True
            self._next_clock_time = time.monotonic()

    def set_tempo(self, bpm: float) -> None:
        if not (self.config.min_bpm <= bpm <= self.config.max_bpm):
            return

        with self._lock:
            old_bpm = self._current_bpm
            self._current_bpm = bpm
            self._clock_interval = self._calculate_interval(bpm)

            if abs(bpm - old_bpm) >= 0.1:
                logger.debug(f"Tempo: {old_bpm:.1f} -> {bpm:.1f} BPM")

    def send_clock_pulse(self, timestamp: float) -> None:
        with self._lock:
            if not self._is_playing or not self._pll_enabled:
                return

            expected_time = self._next_clock_time
            actual_time = time.monotonic()
            phase_error = expected_time - actual_time

            correction = phase_error * self._pll_gain
            self._next_clock_time += correction

    def _clock_loop(self) -> None:
        logger.info("MIDI clock thread started")
        self._next_clock_time = time.monotonic()

        while self._running:
            with self._lock:
                if not self._is_playing:
                    pass
                else:
                    interval = self._clock_interval
                    next_time = self._next_clock_time

                    now = time.monotonic()
                    time_until_next = next_time - now

                    if time_until_next > 0.001:
                        self._lock.release()
                        time.sleep(time_until_next - 0.001)
                        self._lock.acquire()

                    while time.monotonic() < next_time:
                        pass

                    self._send_byte(MIDI_CLOCK)
                    self._clocks_sent += 1

                    actual_time = time.monotonic()
                    jitter = abs(actual_time - next_time)
                    self._jitter_sum += jitter
                    self._max_jitter = max(self._max_jitter, jitter)

                    self._next_clock_time = next_time + interval
                    continue

            time.sleep(0.01)

    def _send_byte(self, byte_val: int) -> None:
        if self._serial:
            self._serial.write(bytes([byte_val]))

    def _calculate_interval(self, bpm: float) -> float:
        return 60.0 / (bpm * self.config.ppqn)

    def get_statistics(self) -> dict:
        with self._lock:
            avg_jitter = (self._jitter_sum / self._clocks_sent) if self._clocks_sent > 0 else 0.0
            return {
                "clocks_sent": self._clocks_sent,
                "average_jitter_ms": avg_jitter * 1000,
                "max_jitter_ms": self._max_jitter * 1000,
                "current_bpm": self._current_bpm,
                "is_playing": self._is_playing
            }


class MockSerial:
    """Mock serial port for testing without hardware."""

    def __init__(self):
        self.buffer = []
        self._is_open = True

    def write(self, data: bytes) -> int:
        self.buffer.extend(data)
        return len(data)

    def close(self) -> None:
        self._is_open = False

    def reset_input_buffer(self) -> None:
        pass

    def reset_output_buffer(self) -> None:
        self.buffer.clear()

    @property
    def is_open(self) -> bool:
        return self._is_open
