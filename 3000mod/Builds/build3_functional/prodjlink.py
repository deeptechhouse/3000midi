"""PRO DJ LINK input using functional composition."""
import socket
import struct
import threading
import time
import logging
from typing import Callable, Optional

from beat_types import Beat, make_beat

logger = logging.getLogger(__name__)

MULTICAST_GROUP = "239.252.0.1"
PACKET_MAGIC = b'Qspt1WmJOL'
BEAT_PACKET_TYPE = 0x28


def parse_prodjlink_packet(data: bytes) -> Optional[Beat]:
    """Pure function to parse PRO DJ LINK packet into Beat."""
    if len(data) < 40 or data[:10] != PACKET_MAGIC:
        return None

    if data[10] != BEAT_PACKET_TYPE:
        return None

    try:
        player = data[11]
        bpm_x100 = struct.unpack('>I', data[12:16])[0]
        pitch_x100k = struct.unpack('>i', data[16:20])[0]
        beat_pos = data[20]
        bar_pos = data[21]
        playing = data[22]
        master = data[23]
        track_ms = struct.unpack('>I', data[24:28])[0]

        return make_beat(
            timestamp=time.monotonic(),
            beat_pos=beat_pos,
            bar_pos=bar_pos,
            bpm=bpm_x100 / 100.0,
            pitch=pitch_x100k / 100000.0,
            player=player,
            is_master=(master == 1),
            is_playing=(playing == 1),
            track_ms=track_ms
        )
    except (struct.error, IndexError):
        return None


def create_udp_receiver(port: int, on_data: Callable[[bytes], None]):
    """
    Create UDP receiver.
    Returns (start, stop) functions for lifecycle control.
    """
    running = {'value': False}
    sock: Optional[socket.socket] = None
    thread: Optional[threading.Thread] = None

    def receive_loop():
        nonlocal sock
        while running['value']:
            try:
                data, _ = sock.recvfrom(512)
                on_data(data)
            except socket.timeout:
                continue
            except Exception as e:
                if running['value']:
                    logger.error(f"UDP error: {e}")

    def start():
        nonlocal sock, thread
        if running['value']:
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass

        sock.bind(('', port))
        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)

        running['value'] = True
        thread = threading.Thread(target=receive_loop, daemon=True)
        thread.start()
        logger.info(f"PRO DJ LINK receiver started on port {port}")

    def stop():
        nonlocal sock, thread
        running['value'] = False
        if thread:
            thread.join(timeout=2.0)
        if sock:
            sock.close()
        logger.info("PRO DJ LINK receiver stopped")

    return start, stop


def create_prodjlink_input(port: int, emit_beat: Callable[[Beat], None]):
    """
    Create PRO DJ LINK input pipeline.
    Composes UDP receiver with packet parser.
    Returns (start, stop) functions.
    """
    def on_packet(data: bytes):
        beat = parse_prodjlink_packet(data)
        if beat:
            emit_beat(beat)

    return create_udp_receiver(port, on_packet)


def create_mock_input(bpm: float, emit_beat: Callable[[Beat], None]):
    """Create mock input that generates beats at specified BPM."""
    running = {'value': False, 'bpm': bpm}
    thread: Optional[threading.Thread] = None

    def generate():
        beat_count = 0
        bar_count = 0

        while running['value']:
            beat_count += 1
            beat_pos = ((beat_count - 1) % 4) + 1
            if beat_pos == 1:
                bar_count += 1

            beat = make_beat(
                timestamp=time.monotonic(),
                beat_pos=beat_pos,
                bar_pos=bar_count,
                bpm=running['bpm'],
                is_playing=True,
                track_ms=int(beat_count * (60000 / running['bpm']))
            )
            emit_beat(beat)
            time.sleep(60.0 / running['bpm'])

    def start():
        nonlocal thread
        if running['value']:
            return
        running['value'] = True
        thread = threading.Thread(target=generate, daemon=True)
        thread.start()
        logger.info(f"Mock input started at {running['bpm']} BPM")

    def stop():
        running['value'] = False
        if thread:
            thread.join(timeout=2.0)
        logger.info("Mock input stopped")

    def set_bpm(new_bpm: float):
        running['bpm'] = new_bpm

    return start, stop, set_bpm
