"""Tests for sync coordinator module."""
import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import BeatInfo
from core.interfaces import SyncInputDevice, SyncOutputDevice
from sync.coordinator import SyncCoordinator, TimingConfig


class MockInput(SyncInputDevice):
    def __init__(self):
        self.callbacks = []
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def register_callback(self, cb):
        self.callbacks.append(cb)

    def emit_beat(self, beat):
        for cb in self.callbacks:
            cb(beat)


class MockOutput(SyncOutputDevice):
    def __init__(self):
        self.started = False
        self.tempo = 0.0
        self.clock_pulses = 0
        self.start_count = 0
        self.stop_count = 0

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def send_clock_pulse(self, ts):
        self.clock_pulses += 1

    def send_start(self):
        self.start_count += 1

    def send_stop(self):
        self.stop_count += 1

    def set_tempo(self, bpm):
        self.tempo = bpm


class TestSyncCoordinator:
    def test_initialization(self):
        mock_input = MockInput()
        mock_output = MockOutput()

        coord = SyncCoordinator(mock_input, [mock_output])
        assert len(coord.output_devices) == 1

    def test_start_stop(self):
        mock_input = MockInput()
        mock_output = MockOutput()

        coord = SyncCoordinator(mock_input, [mock_output])
        coord.start()

        assert mock_input.started is True
        assert mock_output.started is True

        coord.stop()
        assert mock_input.started is False

    def test_beat_forwarding(self):
        mock_input = MockInput()
        mock_output = MockOutput()

        coord = SyncCoordinator(mock_input, [mock_output])
        coord.start()

        beat = BeatInfo(
            timestamp=time.monotonic(),
            beat_position=1,
            bar_position=1,
            bpm=128.0,
            pitch_percent=0.0,
            player_number=1,
            is_master=True,
            is_playing=True,
            track_time_ms=0
        )
        mock_input.emit_beat(beat)

        assert mock_output.tempo == 128.0
        assert mock_output.start_count == 1
        assert mock_output.clock_pulses == 1

        coord.stop()

    def test_transport_state_changes(self):
        mock_input = MockInput()
        mock_output = MockOutput()

        coord = SyncCoordinator(mock_input, [mock_output])
        coord.start()

        beat_playing = BeatInfo(
            timestamp=time.monotonic(),
            beat_position=1,
            bar_position=1,
            bpm=128.0,
            pitch_percent=0.0,
            player_number=1,
            is_master=True,
            is_playing=True,
            track_time_ms=0
        )
        mock_input.emit_beat(beat_playing)
        assert mock_output.start_count == 1

        beat_stopped = BeatInfo(
            timestamp=time.monotonic(),
            beat_position=1,
            bar_position=1,
            bpm=128.0,
            pitch_percent=0.0,
            player_number=1,
            is_master=True,
            is_playing=False,
            track_time_ms=0
        )
        mock_input.emit_beat(beat_stopped)
        assert mock_output.stop_count == 1

        coord.stop()

    def test_statistics(self):
        mock_input = MockInput()
        mock_output = MockOutput()

        coord = SyncCoordinator(mock_input, [mock_output])
        coord.start()

        for i in range(5):
            beat = BeatInfo(
                timestamp=time.monotonic(),
                beat_position=(i % 4) + 1,
                bar_position=i // 4,
                bpm=120.0,
                pitch_percent=0.0,
                player_number=1,
                is_master=True,
                is_playing=True,
                track_time_ms=i * 500
            )
            mock_input.emit_beat(beat)
            time.sleep(0.01)

        stats = coord.get_statistics()
        assert stats['beat_count'] == 5
        assert stats['current_bpm'] == 120.0

        coord.stop()
