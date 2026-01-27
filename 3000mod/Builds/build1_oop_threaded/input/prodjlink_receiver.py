"""PRO DJ LINK UDP receiver for beat synchronization."""
import socket
import struct
import threading
import time
import logging
from typing import Callable, Optional, List

from core.interfaces import SyncInputDevice
from core.types import BeatInfo
from core.errors import SyncDeviceError

logger = logging.getLogger(__name__)


class ProDJLinkReceiver(SyncInputDevice):
    """
    Receives and parses PRO DJ LINK beat packets from CDJ-3000.
    Uses UDP multicast on 239.252.0.1:50001.
    """

    MULTICAST_GROUP = "239.252.0.1"
    DEFAULT_PORT = 50001
    PACKET_MAGIC = b'Qspt1WmJOL'
    BEAT_PACKET_TYPE = 0x28

    def __init__(
        self,
        interface: str = "eth0",
        port: int = DEFAULT_PORT,
        buffer_size: int = 512
    ):
        self.interface = interface
        self.port = port
        self.buffer_size = buffer_size

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[BeatInfo], None]] = []
        self._socket: Optional[socket.socket] = None

        self._packets_received = 0
        self._packets_invalid = 0

        logger.info(f"ProDJLinkReceiver initialized: {interface}:{port}")

    def start(self) -> None:
        with self._lock:
            if self._running:
                logger.warning("ProDJLinkReceiver already running")
                return

            try:
                self._socket = socket.socket(
                    socket.AF_INET,
                    socket.SOCK_DGRAM,
                    socket.IPPROTO_UDP
                )
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                try:
                    self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except AttributeError:
                    pass

                self._socket.bind(('', self.port))

                mreq = struct.pack(
                    "4sl",
                    socket.inet_aton(self.MULTICAST_GROUP),
                    socket.INADDR_ANY
                )
                self._socket.setsockopt(
                    socket.IPPROTO_IP,
                    socket.IP_ADD_MEMBERSHIP,
                    mreq
                )
                self._socket.settimeout(1.0)

                logger.info(f"Joined multicast group {self.MULTICAST_GROUP}")

            except Exception as e:
                raise SyncDeviceError(
                    "ProDJLinkReceiver",
                    f"Failed to create socket: {e}",
                    recoverable=False
                )

            self._running = True
            self._thread = threading.Thread(
                target=self._listen_loop,
                name="ProDJLink-Listener",
                daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        if self._socket:
            self._socket.close()
            self._socket = None

        logger.info(f"ProDJLinkReceiver stopped. Packets: {self._packets_received} valid, {self._packets_invalid} invalid")

    def register_callback(self, callback: Callable[[BeatInfo], None]) -> None:
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def _listen_loop(self) -> None:
        logger.info("ProDJLink listener thread started")

        while self._running:
            try:
                data, addr = self._socket.recvfrom(self.buffer_size)
                beat_info = self._parse_packet(data, addr[0])

                if beat_info is None:
                    self._packets_invalid += 1
                    continue

                self._packets_received += 1

                with self._lock:
                    callbacks = self._callbacks.copy()

                for callback in callbacks:
                    try:
                        callback(beat_info)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Listener error: {e}")

    def _parse_packet(self, data: bytes, source_ip: str) -> Optional[BeatInfo]:
        if len(data) < 40:
            return None

        if data[:10] != self.PACKET_MAGIC:
            return None

        packet_type = data[10]
        if packet_type != self.BEAT_PACKET_TYPE:
            return None

        try:
            player_number = data[11]
            bpm_x100 = struct.unpack('>I', data[12:16])[0]
            pitch_x100k = struct.unpack('>i', data[16:20])[0]
            beat_pos = data[20]
            bar_pos = data[21]
            playing = data[22]
            master = data[23]
            track_time_ms = struct.unpack('>I', data[24:28])[0]

            bpm = bpm_x100 / 100.0
            pitch_percent = pitch_x100k / 100000.0

            if not (20.0 <= bpm <= 300.0):
                return None

            return BeatInfo(
                timestamp=time.monotonic(),
                beat_position=max(1, min(4, beat_pos)),
                bar_position=bar_pos,
                bpm=bpm,
                pitch_percent=pitch_percent,
                player_number=max(1, min(4, player_number)),
                is_master=(master == 1),
                is_playing=(playing == 1),
                track_time_ms=track_time_ms
            )

        except (struct.error, IndexError) as e:
            logger.debug(f"Packet parse error: {e}")
            return None


class MockProDJLinkReceiver(SyncInputDevice):
    """Mock receiver for testing that generates synthetic beat events."""

    def __init__(self, bpm: float = 120.0):
        self.bpm = bpm
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[BeatInfo], None]] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        self._thread = threading.Thread(target=self._generate_beats, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def register_callback(self, callback: Callable[[BeatInfo], None]) -> None:
        with self._lock:
            self._callbacks.append(callback)

    def set_bpm(self, bpm: float) -> None:
        self.bpm = bpm

    def _generate_beats(self) -> None:
        beat_counter = 0
        bar_counter = 0

        while self._running:
            beat_counter += 1
            beat_pos = ((beat_counter - 1) % 4) + 1
            if beat_pos == 1:
                bar_counter += 1

            beat_info = BeatInfo(
                timestamp=time.monotonic(),
                beat_position=beat_pos,
                bar_position=bar_counter,
                bpm=self.bpm,
                pitch_percent=0.0,
                player_number=1,
                is_master=True,
                is_playing=True,
                track_time_ms=int(beat_counter * (60000 / self.bpm))
            )

            with self._lock:
                for cb in self._callbacks:
                    try:
                        cb(beat_info)
                    except Exception:
                        pass

            time.sleep(60.0 / self.bpm)
