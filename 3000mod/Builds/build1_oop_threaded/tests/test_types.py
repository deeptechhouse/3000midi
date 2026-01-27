"""Tests for core types module."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import BeatInfo, SyncConfig, PlayerState


class TestBeatInfo:
    def test_create_valid_beat(self):
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
        assert beat.beat_position == 1
        assert beat.is_master is True

    def test_beat_is_immutable(self):
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

    def test_beat_position_clamping(self):
        beat = BeatInfo(
            timestamp=100.0,
            beat_position=5,
            bar_position=1,
            bpm=128.0,
            pitch_percent=0.0,
            player_number=1,
            is_master=True,
            is_playing=True,
            track_time_ms=0
        )
        assert beat.beat_position == 4


class TestSyncConfig:
    def test_default_values(self):
        config = SyncConfig()
        assert config.midi_baud == 31250
        assert config.midi_ppqn == 24
        assert config.prodjlink_port == 50001

    def test_custom_values(self):
        config = SyncConfig(midi_device="/dev/test", latency_compensation_ms=10.0)
        assert config.midi_device == "/dev/test"
        assert config.latency_compensation_ms == 10.0


class TestPlayerState:
    def test_states_exist(self):
        assert PlayerState.PLAYING.name == "PLAYING"
        assert PlayerState.STOPPED.name == "STOPPED"
        assert PlayerState.PAUSED.name == "PAUSED"
