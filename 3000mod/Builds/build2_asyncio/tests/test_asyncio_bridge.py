"""Tests for asyncio-based sync bridge."""
import pytest
import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import BeatInfo
from prodjlink_input import MockAsyncInput
from midi_output import AsyncMIDIOutput, MIDIConfig
from control_chain_output import AsyncControlChainOutput
from coordinator import AsyncSyncCoordinator


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class TestBeatInfo:
    def test_create_beat(self):
        beat = BeatInfo(
            timestamp=100.0,
            beat_position=1,
            bar_position=1,
            bpm=128.0,
            pitch_percent=0.0,
            player_number=1,
            is_master=True,
            is_playing=True,
            track_time_ms=0
        )
        assert beat.bpm == 128.0
        assert beat.is_master is True

    def test_beat_immutable(self):
        beat = BeatInfo(
            timestamp=100.0,
            beat_position=1,
            bar_position=1,
            bpm=128.0,
            pitch_percent=0.0,
            player_number=1,
            is_master=True,
            is_playing=True,
            track_time_ms=0
        )
        with pytest.raises(AttributeError):
            beat.bpm = 140.0


class TestMockAsyncInput:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        mock = MockAsyncInput(bpm=120.0)
        await mock.start()
        assert mock._running is True
        await mock.stop()
        assert mock._running is False

    @pytest.mark.asyncio
    async def test_beat_generation(self):
        mock = MockAsyncInput(bpm=120.0)
        beats = []

        async def collect_beat(beat):
            beats.append(beat)

        mock.on_beat(collect_beat)
        await mock.start()
        await asyncio.sleep(1.5)
        await mock.stop()

        assert len(beats) >= 2
        assert all(b.bpm == 120.0 for b in beats)

    @pytest.mark.asyncio
    async def test_bpm_change(self):
        mock = MockAsyncInput(bpm=120.0)
        mock.set_bpm(140.0)
        assert mock.bpm == 140.0


class TestAsyncMIDIOutput:
    @pytest.mark.asyncio
    async def test_initialization(self):
        config = MIDIConfig(device="/dev/test")
        midi = AsyncMIDIOutput(config)
        assert midi.config.device == "/dev/test"

    @pytest.mark.asyncio
    async def test_start_stop(self):
        midi = AsyncMIDIOutput()
        await midi.start()
        assert midi._running is True
        await midi.stop()
        assert midi._running is False

    @pytest.mark.asyncio
    async def test_tempo_setting(self):
        midi = AsyncMIDIOutput()
        await midi.start()
        await midi.set_tempo(128.0)
        assert midi._current_bpm == 128.0
        await midi.stop()

    @pytest.mark.asyncio
    async def test_clock_generation(self):
        midi = AsyncMIDIOutput()
        await midi.start()
        await midi.set_tempo(120.0)
        await midi.send_start()

        await asyncio.sleep(0.5)

        stats = midi.get_statistics()
        await midi.stop()

        expected = int(0.5 * 120.0 * 24 / 60)
        assert abs(stats['clocks_sent'] - expected) <= 3

    @pytest.mark.asyncio
    async def test_statistics(self):
        midi = AsyncMIDIOutput()
        midi._clocks_sent = 100
        midi._current_bpm = 128.0
        midi._jitter_samples = [0.001, 0.002]

        stats = midi.get_statistics()
        assert stats['clocks_sent'] == 100
        assert stats['current_bpm'] == 128.0


class TestAsyncControlChainOutput:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        cc = AsyncControlChainOutput()
        await cc.start()
        await cc.stop()

    @pytest.mark.asyncio
    async def test_tempo_update(self):
        cc = AsyncControlChainOutput()
        await cc.start()
        await cc.set_tempo(128.0)
        assert cc._last_bpm == 128.0
        await cc.stop()


class TestAsyncCoordinator:
    @pytest.mark.asyncio
    async def test_initialization(self):
        mock_input = MockAsyncInput()
        mock_output = AsyncMIDIOutput()
        coord = AsyncSyncCoordinator(mock_input, [mock_output])
        assert len(coord.outputs) == 1

    @pytest.mark.asyncio
    async def test_start_stop(self):
        mock_input = MockAsyncInput(bpm=120.0)
        mock_output = AsyncMIDIOutput()

        coord = AsyncSyncCoordinator(mock_input, [mock_output])
        await coord.start()
        assert coord._running is True

        await asyncio.sleep(0.5)
        await coord.stop()
        assert coord._running is False

    @pytest.mark.asyncio
    async def test_beat_forwarding(self):
        mock_input = MockAsyncInput(bpm=128.0)
        mock_output = AsyncMIDIOutput()

        coord = AsyncSyncCoordinator(mock_input, [mock_output])
        await coord.start()

        await asyncio.sleep(1.0)

        stats = coord.get_statistics()
        await coord.stop()

        assert stats['beat_count'] >= 1
        assert stats['current_bpm'] == 128.0

    @pytest.mark.asyncio
    async def test_multiple_outputs(self):
        mock_input = MockAsyncInput(bpm=120.0)
        midi_out = AsyncMIDIOutput()
        cc_out = AsyncControlChainOutput()

        coord = AsyncSyncCoordinator(mock_input, [midi_out, cc_out])
        await coord.start()

        await asyncio.sleep(1.0)

        midi_stats = midi_out.get_statistics()
        cc_stats = cc_out.get_statistics()
        await coord.stop()

        assert midi_stats['current_bpm'] == 120.0
        assert cc_stats['last_bpm'] == 120.0


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_flow(self):
        mock_input = MockAsyncInput(bpm=120.0)
        midi_out = AsyncMIDIOutput()

        coord = AsyncSyncCoordinator(mock_input, [midi_out])
        await coord.start()

        await asyncio.sleep(2.0)

        stats = coord.get_statistics()
        await coord.stop()

        assert stats['beat_count'] >= 3
        assert stats['is_playing'] is True

    @pytest.mark.asyncio
    async def test_tempo_change(self):
        mock_input = MockAsyncInput(bpm=120.0)
        midi_out = AsyncMIDIOutput()

        coord = AsyncSyncCoordinator(mock_input, [midi_out])
        await coord.start()

        await asyncio.sleep(0.5)
        mock_input.set_bpm(140.0)
        await asyncio.sleep(1.0)

        stats = coord.get_statistics()
        await coord.stop()

        assert 139.0 <= stats['current_bpm'] <= 141.0
