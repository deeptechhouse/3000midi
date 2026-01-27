"""MIDI output using functional composition."""
import threading
import time
import logging
from typing import Callable, Optional, Dict, Any

logger = logging.getLogger(__name__)

MIDI_CLOCK = 0xF8
MIDI_START = 0xFA
MIDI_STOP = 0xFC


def create_serial_writer(device: str, baud: int):
    """
    Create serial writer.
    Returns (write, close) functions.
    """
    port = None

    def init():
        nonlocal port
        try:
            import serial
            port = serial.Serial(device, baud, bytesize=8, parity='N', stopbits=1)
            logger.info(f"MIDI serial opened: {device}")
        except ImportError:
            logger.warning("pyserial not available, using mock")
        except Exception as e:
            logger.warning(f"Could not open {device}: {e}")

    def write(data: bytes) -> None:
        if port:
            port.write(data)
        else:
            pass

    def close() -> None:
        if port:
            port.close()

    init()
    return write, close


def create_midi_clock_generator(
    write_fn: Callable[[bytes], None],
    ppqn: int = 24
):
    """
    Create MIDI clock generator.
    Returns (start, stop, set_bpm, send_start, send_stop, get_stats) functions.
    """
    state = {
        'running': False,
        'playing': False,
        'bpm': 120.0,
        'clocks_sent': 0,
        'jitter_samples': []
    }
    thread: Optional[threading.Thread] = None
    lock = threading.Lock()

    def clock_loop():
        next_time = time.monotonic()

        while state['running']:
            with lock:
                if not state['playing']:
                    pass
                else:
                    interval = 60.0 / (state['bpm'] * ppqn)
                    now = time.monotonic()

                    if next_time - now > 0.001:
                        lock.release()
                        time.sleep(next_time - now - 0.001)
                        lock.acquire()

                    while time.monotonic() < next_time:
                        pass

                    write_fn(bytes([MIDI_CLOCK]))
                    state['clocks_sent'] += 1

                    jitter = abs(time.monotonic() - next_time)
                    state['jitter_samples'].append(jitter)
                    if len(state['jitter_samples']) > 100:
                        state['jitter_samples'].pop(0)

                    next_time += interval
                    continue

            time.sleep(0.01)

    def start():
        nonlocal thread
        if state['running']:
            return
        state['running'] = True
        thread = threading.Thread(target=clock_loop, daemon=True)
        thread.start()
        logger.info("MIDI clock generator started")

    def stop():
        state['running'] = False
        if thread:
            thread.join(timeout=2.0)
        logger.info("MIDI clock generator stopped")

    def set_bpm(bpm: float):
        if 20.0 <= bpm <= 300.0:
            with lock:
                state['bpm'] = bpm

    def send_start():
        write_fn(bytes([MIDI_START]))
        with lock:
            state['playing'] = True
        logger.info("MIDI Start sent")

    def send_stop():
        write_fn(bytes([MIDI_STOP]))
        with lock:
            state['playing'] = False
        logger.info("MIDI Stop sent")

    def get_stats() -> Dict[str, Any]:
        with lock:
            avg = sum(state['jitter_samples']) / len(state['jitter_samples']) if state['jitter_samples'] else 0
            return {
                'clocks_sent': state['clocks_sent'],
                'current_bpm': state['bpm'],
                'is_playing': state['playing'],
                'average_jitter_ms': avg * 1000
            }

    return start, stop, set_bpm, send_start, send_stop, get_stats


def create_midi_output(device: str = "/dev/ttyAMA0", baud: int = 31250, ppqn: int = 24):
    """
    Create complete MIDI output pipeline.
    Returns dict of control functions.
    """
    write, close_serial = create_serial_writer(device, baud)
    start, stop_gen, set_bpm, send_start, send_stop, get_stats = create_midi_clock_generator(write, ppqn)

    def close_all():
        stop_gen()
        close_serial()

    return {
        'start': start,
        'stop': close_all,
        'set_bpm': set_bpm,
        'send_start': send_start,
        'send_stop': send_stop,
        'get_stats': get_stats
    }
