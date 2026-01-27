"""Control Chain output for MOD Dwarf communication via RS485."""
import struct
import logging
from typing import Optional
from dataclasses import dataclass

from core.interfaces import SyncOutputDevice
from core.errors import SyncDeviceError

logger = logging.getLogger(__name__)

CC_CMD_HELLO_RESPONSE = 0x81
CC_CMD_DATA_UPDATE = 0x05
CC_SYNC1 = 0x55
CC_SYNC2 = 0xAA


@dataclass
class ControlChainConfig:
    device: str = "/dev/ttyUSB0"
    baud_rate: int = 115200
    timeout: float = 1.0
    gpio_de_pin: Optional[int] = 27


class ControlChainOutput(SyncOutputDevice):
    """Control Chain output for MOD Dwarf via RS485."""

    def __init__(self, config: Optional[ControlChainConfig] = None):
        self.config = config or ControlChainConfig()
        self._serial = None
        self._device_id: Optional[int] = None
        self._registered = False
        self._gpio_initialized = False

        self._bpm_actuator_id = 0x01
        self._transport_actuator_id = 0x02

        self._last_bpm = 0.0
        self._min_bpm_change = 0.1

        logger.info(f"ControlChainOutput initialized: {self.config.device}")

    def start(self) -> None:
        try:
            if self.config.gpio_de_pin is not None:
                self._init_gpio()

            try:
                import serial
                self._serial = serial.Serial(
                    port=self.config.device,
                    baudrate=self.config.baud_rate,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=self.config.timeout
                )
                logger.info(f"Control Chain serial opened: {self.config.device}")
            except ImportError:
                logger.warning("pyserial not available, using mock")
                self._serial = MockRS485Serial()
            except Exception as e:
                logger.warning(f"Could not open {self.config.device}: {e}, using mock")
                self._serial = MockRS485Serial()

            self._set_receive_mode()
            self._device_id = 0x01
            self._registered = True

        except Exception as e:
            raise SyncDeviceError(
                "ControlChainOutput",
                f"Failed to start: {e}",
                recoverable=False
            )

    def stop(self) -> None:
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

        self._cleanup_gpio()
        logger.info("ControlChainOutput stopped")

    def set_tempo(self, bpm: float) -> None:
        if abs(bpm - self._last_bpm) < self._min_bpm_change:
            return

        self._last_bpm = bpm
        self._send_update(self._bpm_actuator_id, bpm)

    def send_start(self) -> None:
        self._send_update(self._transport_actuator_id, 1.0)
        logger.debug("Control Chain: Transport Start")

    def send_stop(self) -> None:
        self._send_update(self._transport_actuator_id, 0.0)
        logger.debug("Control Chain: Transport Stop")

    def send_clock_pulse(self, timestamp: float) -> None:
        pass

    def _init_gpio(self) -> None:
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.config.gpio_de_pin, GPIO.OUT)
            GPIO.output(self.config.gpio_de_pin, GPIO.LOW)
            self._gpio_initialized = True
            logger.info(f"GPIO {self.config.gpio_de_pin} initialized for RS485 DE/RE")
        except ImportError:
            logger.warning("RPi.GPIO not available (not on Raspberry Pi)")
        except Exception as e:
            logger.warning(f"Could not initialize GPIO: {e}")

    def _cleanup_gpio(self) -> None:
        if self._gpio_initialized:
            try:
                import RPi.GPIO as GPIO
                GPIO.cleanup(self.config.gpio_de_pin)
            except Exception:
                pass

    def _set_transmit_mode(self) -> None:
        if self._gpio_initialized:
            try:
                import RPi.GPIO as GPIO
                GPIO.output(self.config.gpio_de_pin, GPIO.HIGH)
            except Exception:
                pass

    def _set_receive_mode(self) -> None:
        if self._gpio_initialized:
            try:
                import RPi.GPIO as GPIO
                GPIO.output(self.config.gpio_de_pin, GPIO.LOW)
            except Exception:
                pass

    def _send_update(self, actuator_id: int, value: float) -> None:
        if not self._serial or not self._registered:
            return

        packet = bytearray()
        packet.append(CC_SYNC1)
        packet.append(CC_SYNC2)
        packet.append(self._device_id or 0x00)
        packet.append(CC_CMD_DATA_UPDATE)
        packet.extend(struct.pack('<H', 5))
        packet.append(actuator_id)
        packet.extend(struct.pack('<f', value))

        checksum = 0
        for byte in packet:
            checksum ^= byte
        packet.append(checksum)

        self._set_transmit_mode()
        try:
            self._serial.write(packet)
            self._serial.flush()
        except Exception as e:
            logger.error(f"Control Chain write error: {e}")
        finally:
            self._set_receive_mode()

    def get_statistics(self) -> dict:
        return {
            "device_id": self._device_id,
            "registered": self._registered,
            "last_bpm": self._last_bpm
        }


class MockRS485Serial:
    """Mock RS485 serial for testing."""

    def __init__(self):
        self.tx_buffer = []
        self._is_open = True

    def write(self, data: bytes) -> int:
        self.tx_buffer.extend(data)
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open
