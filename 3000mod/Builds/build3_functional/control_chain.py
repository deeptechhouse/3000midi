"""Control Chain output using functional composition."""
import struct
import logging
from typing import Callable, Dict, Any, Optional

logger = logging.getLogger(__name__)

CC_SYNC1 = 0x55
CC_SYNC2 = 0xAA
CC_CMD_DATA_UPDATE = 0x05


def build_cc_packet(device_id: int, actuator_id: int, value: float) -> bytes:
    """Pure function to build Control Chain packet."""
    packet = bytearray([CC_SYNC1, CC_SYNC2, device_id, CC_CMD_DATA_UPDATE])
    packet.extend(struct.pack('<H', 5))
    packet.append(actuator_id)
    packet.extend(struct.pack('<f', value))

    checksum = 0
    for b in packet:
        checksum ^= b
    packet.append(checksum)

    return bytes(packet)


def create_gpio_controller(pin: Optional[int]):
    """Create GPIO controller for RS485 direction."""
    initialized = {'value': False}

    def init():
        if pin is None:
            return
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            initialized['value'] = True
        except ImportError:
            logger.warning("RPi.GPIO not available")
        except Exception as e:
            logger.warning(f"GPIO init failed: {e}")

    def set_transmit():
        if initialized['value']:
            try:
                import RPi.GPIO as GPIO
                GPIO.output(pin, GPIO.HIGH)
            except Exception:
                pass

    def set_receive():
        if initialized['value']:
            try:
                import RPi.GPIO as GPIO
                GPIO.output(pin, GPIO.LOW)
            except Exception:
                pass

    def cleanup():
        if initialized['value']:
            try:
                import RPi.GPIO as GPIO
                GPIO.cleanup(pin)
            except Exception:
                pass

    init()
    return set_transmit, set_receive, cleanup


def create_control_chain_output(
    device: str = "/dev/ttyUSB0",
    baud: int = 115200,
    gpio_pin: Optional[int] = 27
):
    """
    Create Control Chain output pipeline.
    Returns dict of control functions.
    """
    port = None
    device_id = 0x01
    bpm_actuator = 0x01
    transport_actuator = 0x02
    last_bpm = {'value': 0.0}

    set_tx, set_rx, cleanup_gpio = create_gpio_controller(gpio_pin)

    def init():
        nonlocal port
        try:
            import serial
            port = serial.Serial(device, baud, bytesize=8, parity='N', stopbits=1)
            logger.info(f"Control Chain serial opened: {device}")
        except ImportError:
            logger.warning("pyserial not available")
        except Exception as e:
            logger.warning(f"Could not open {device}: {e}")

    def send_update(actuator_id: int, value: float):
        if not port:
            return
        packet = build_cc_packet(device_id, actuator_id, value)
        set_tx()
        try:
            port.write(packet)
            port.flush()
        except Exception as e:
            logger.error(f"CC write error: {e}")
        finally:
            set_rx()

    def start():
        init()
        set_rx()
        logger.info("Control Chain output started")

    def stop():
        if port:
            port.close()
        cleanup_gpio()
        logger.info("Control Chain output stopped")

    def set_bpm(bpm: float):
        if abs(bpm - last_bpm['value']) < 0.1:
            return
        last_bpm['value'] = bpm
        send_update(bpm_actuator, bpm)

    def send_start():
        send_update(transport_actuator, 1.0)

    def send_stop():
        send_update(transport_actuator, 0.0)

    def get_stats() -> Dict[str, Any]:
        return {'last_bpm': last_bpm['value'], 'device_id': device_id}

    return {
        'start': start,
        'stop': stop,
        'set_bpm': set_bpm,
        'send_start': send_start,
        'send_stop': send_stop,
        'get_stats': get_stats
    }
