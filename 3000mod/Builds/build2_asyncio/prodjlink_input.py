"""PRO DJ LINK input using asyncio UDP protocol."""
import asyncio
import struct
import time
import logging
from typing import Callable, Awaitable, Optional, List

from core.types import BeatInfo

logger = logging.getLogger(__name__)

MULTICAST_GROUP = "239.252.0.1"
PACKET_MAGIC = b'Qspt1WmJOL'
BEAT_PACKET_TYPE = 0x28


class ProDJLinkProtocol(asyncio.DatagramProtocol):
    """Asyncio datagram protocol for PRO DJ LINK."""

    def __init__(self, on_beat: Callable[[BeatInfo], Awaitable[None]]):
        self._on_beat = on_beat
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._packets_received = 0
        self._packets_invalid = 0

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport
        logger.info("PRO DJ LINK protocol connected")

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        beat = self._parse_packet(data)
        if beat:
            self._packets_received += 1
            asyncio.create_task(self._on_beat(beat))
        else:
            self._packets_invalid += 1

    def error_received(self, exc: Exception) -> None:
        logger.error(f"UDP error: {exc}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        logger.info("PRO DJ LINK protocol disconnected")

    def _parse_packet(self, data: bytes) -> Optional[BeatInfo]:
        if len(data) < 40 or data[:10] != PACKET_MAGIC:
            return None

        if data[10] != BEAT_PACKET_TYPE:
            return None

        try:
            player_number = data[11]
            bpm_x100 = struct.unpack('>I', data[12:16])[0]
            pitch_x100k = struct.unpack('>i', data[16:20])[0]
            beat_pos = max(1, min(4, data[20]))
            bar_pos = data[21]
            playing = data[22]
            master = data[23]
            track_time_ms = struct.unpack('>I', data[24:28])[0]

            bpm = bpm_x100 / 100.0
            if not (20.0 <= bpm <= 300.0):
                return None

            return BeatInfo(
                timestamp=time.monotonic(),
                beat_position=beat_pos,
                bar_position=bar_pos,
                bpm=bpm,
                pitch_percent=pitch_x100k / 100000.0,
                player_number=max(1, min(4, player_number)),
                is_master=(master == 1),
                is_playing=(playing == 1),
                track_time_ms=track_time_ms
            )
        except (struct.error, IndexError):
            return None


class AsyncProDJLinkInput:
    """Async PRO DJ LINK receiver."""

    def __init__(self, interface: str = "eth0", port: int = 50001):
        self.interface = interface
        self.port = port
        self._callbacks: List[Callable[[BeatInfo], Awaitable[None]]] = []
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[ProDJLinkProtocol] = None

    def on_beat(self, callback: Callable[[BeatInfo], Awaitable[None]]) -> None:
        self._callbacks.append(callback)

    async def _dispatch_beat(self, beat: BeatInfo) -> None:
        await asyncio.gather(
            *[cb(beat) for cb in self._callbacks],
            return_exceptions=True
        )

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass
        sock.bind(('', self.port))

        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)

        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: ProDJLinkProtocol(self._dispatch_beat),
            sock=sock
        )
        logger.info(f"Async PRO DJ LINK started on port {self.port}")

    async def stop(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None
        logger.info("Async PRO DJ LINK stopped")


class MockAsyncInput:
    """Mock input that generates beats asynchronously."""

    def __init__(self, bpm: float = 120.0):
        self.bpm = bpm
        self._callbacks: List[Callable[[BeatInfo], Awaitable[None]]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def on_beat(self, callback: Callable[[BeatInfo], Awaitable[None]]) -> None:
        self._callbacks.append(callback)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._generate_beats())
        logger.info(f"Mock input started at {self.bpm} BPM")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Mock input stopped")

    def set_bpm(self, bpm: float) -> None:
        self.bpm = bpm

    async def _generate_beats(self) -> None:
        beat_counter = 0
        bar_counter = 0

        while self._running:
            beat_counter += 1
            beat_pos = ((beat_counter - 1) % 4) + 1
            if beat_pos == 1:
                bar_counter += 1

            beat = BeatInfo(
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

            await asyncio.gather(
                *[cb(beat) for cb in self._callbacks],
                return_exceptions=True
            )

            await asyncio.sleep(60.0 / self.bpm)
