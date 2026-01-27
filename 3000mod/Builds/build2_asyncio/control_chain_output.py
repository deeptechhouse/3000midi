"""Control Chain output using asyncio."""
import asyncio
import struct
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CC_SYNC1 = 0x55
CC_SYNC2 = 0xAA
CC_CMD_DATA_UPDATE = 0x05


@dataclass
class CCConfig:
    device: str = "/dev/ttyUSB0"
    baud_rate: int = 115200
    gpio_pin: Optional[int] = 27


class AsyncControlChainOutput:
    """Async Control Chain output for MOD Dwarf."""

    def __init__(self, config: Optional[CCConfig] = None):
        self.config = config or CCConfig()
        self._writer: Optional[asyncio.StreamWriter] = None
        self._device_id = 0x01
        self._bpm_actuator = 0x01
        self._transport_actuator = 0x02
        self._last_bpm = 0.0
        self._gpio_initialized = False

        logger.info(f"AsyncControlChainOutput initialized: {self.config.device}")

    async def start(self) -> None:
        self._init_gpio()

        try:
            import serial_asyncio
            _, self._writer = await serial_asyncio.open_serial_connection(
                url=self.config.device,
                baudrate=self.config.baud_rate,
                bytesize=8,
                parity='N',
                stopbits=1
            )
            logger.info(f"Control Chain serial opened: {self.config.device}")
        except ImportError:
            logger.warning("serial_asyncio not available, using mock")
            self._writer = MockAsyncWriter()
        except Exception as e:
            logger.warning(f"Could not open CC device: {e}, using mock")
            self._writer = MockAsyncWriter()

        self._set_receive_mode()

    async def stop(self) -> None:
        if self._writer and hasattr(self._writer, 'close'):
            self._writer.close()
            if hasattr(self._writer, 'wait_closed'):
                await self._writer.wait_closed()

        self._cleanup_gpio()
        logger.info("AsyncControlChainOutput stopped")

    async def send_start(self) -> None:
        await self._send_update(self._transport_actuator, 1.0)

    async def send_stop(self) -> None:
        await self._send_update(self._transport_actuator, 0.0)

    async def send_clock(self) -> None:
        pass

    async def set_tempo(self, bpm: float) -> None:
        if abs(bpm - self._last_bpm) < 0.1:
            return
        self._last_bpm = bpm
        await self._send_update(self._bpm_actuator, bpm)

    def _init_gpio(self) -> None:
        if self.config.gpio_pin is None:
            return
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.config.gpio_pin, GPIO.OUT)
            GPIO.output(self.config.gpio_pin, GPIO.LOW)
            self._gpio_initialized = True
        except ImportError:
            logger.warning("RPi.GPIO not available")
        except Exception as e:
            logger.warning(f"GPIO init failed: {e}")

    def _cleanup_gpio(self) -> None:
        if self._gpio_initialized:
            try:
                import RPi.GPIO as GPIO
                GPIO.cleanup(self.config.gpio_pin)
            except Exception:
                pass

    def _set_transmit_mode(self) -> None:
        if self._gpio_initialized:
            try:
                import RPi.GPIO as GPIO
                GPIO.output(self.config.gpio_pin, GPIO.HIGH)
            except Exception:
                pass

    def _set_receive_mode(self) -> None:
        if self._gpio_initialized:
            try:
                import RPi.GPIO as GPIO
                GPIO.output(self.config.gpio_pin, GPIO.LOW)
            except Exception:
                pass

    async def _send_update(self, actuator_id: int, value: float) -> None:
        if not self._writer:
            return

        packet = bytearray([CC_SYNC1, CC_SYNC2, self._device_id, CC_CMD_DATA_UPDATE])
        packet.extend(struct.pack('<H', 5))
        packet.append(actuator_id)
        packet.extend(struct.pack('<f', value))

        checksum = 0
        for b in packet:
            checksum ^= b
        packet.append(checksum)

        self._set_transmit_mode()
        self._writer.write(bytes(packet))
        if hasattr(self._writer, 'drain'):
            await self._writer.drain()
        self._set_receive_mode()

    def get_statistics(self) -> dict:
        return {"last_bpm": self._last_bpm, "device_id": self._device_id}


class MockAsyncWriter:
    """Mock writer for testing."""

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
