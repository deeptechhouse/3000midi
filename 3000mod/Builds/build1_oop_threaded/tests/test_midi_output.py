"""Tests for MIDI clock output module."""
import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from output.midi_clock_output import MIDIClockOutput, MIDIClockConfig, MockSerial


class TestMIDIClockOutput:
    def test_initialization(self):
        config = MIDIClockConfig(device="/dev/test")
        midi = MIDIClockOutput(config)
        assert midi.config.device == "/dev/test"
        assert midi.config.baud_rate == 31250

    def test_interval_calculation(self):
        midi = MIDIClockOutput()
        interval_120 = midi._calculate_interval(120.0)
        assert abs(interval_120 - 0.0208333) < 0.0001

        interval_128 = midi._calculate_interval(128.0)
        assert abs(interval_128 - 0.0195312) < 0.0001

    def test_tempo_validation(self):
        config = MIDIClockConfig(min_bpm=20.0, max_bpm=300.0)
        midi = MIDIClockOutput(config)
        midi._serial = MockSerial()
        midi._running = True

        midi.set_tempo(128.0)
        assert midi._current_bpm == 128.0

        midi.set_tempo(10.0)
        assert midi._current_bpm == 128.0

        midi.set_tempo(400.0)
        assert midi._current_bpm == 128.0

    def test_start_stop(self):
        midi = MIDIClockOutput()
        midi.start()
        assert midi._running is True

        midi.stop()
        assert midi._running is False

    def test_mock_serial_write(self):
        mock = MockSerial()
        mock.write(bytes([0xF8]))
        assert 0xF8 in mock.buffer

    def test_statistics(self):
        midi = MIDIClockOutput()
        midi._clocks_sent = 100
        midi._jitter_sum = 0.01
        midi._max_jitter = 0.002
        midi._current_bpm = 128.0

        stats = midi.get_statistics()
        assert stats['clocks_sent'] == 100
        assert stats['current_bpm'] == 128.0
        assert stats['average_jitter_ms'] == 0.1


class TestMIDIClockTiming:
    def test_clock_generation_timing(self):
        midi = MIDIClockOutput()
        midi.start()
        midi.set_tempo(120.0)
        midi.send_start()

        time.sleep(0.5)

        stats = midi.get_statistics()
        midi.stop()

        expected_clocks = int(0.5 * 120.0 * 24 / 60)
        actual_clocks = stats['clocks_sent']
        assert abs(actual_clocks - expected_clocks) <= 2
