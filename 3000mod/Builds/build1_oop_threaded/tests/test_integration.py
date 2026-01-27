"""Integration tests for full system."""
import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from input.prodjlink_receiver import MockProDJLinkReceiver
from output.midi_clock_output import MIDIClockOutput
from output.control_chain_output import ControlChainOutput
from sync.coordinator import SyncCoordinator


class TestFullIntegration:
    def test_mock_input_to_midi_output(self):
        mock_input = MockProDJLinkReceiver(bpm=120.0)
        midi_output = MIDIClockOutput()

        coord = SyncCoordinator(mock_input, [midi_output])
        coord.start()

        time.sleep(2.0)

        stats = coord.get_statistics()
        coord.stop()

        assert stats['beat_count'] >= 3
        assert 119.0 <= stats['current_bpm'] <= 121.0

    def test_tempo_change_propagation(self):
        mock_input = MockProDJLinkReceiver(bpm=120.0)
        midi_output = MIDIClockOutput()

        coord = SyncCoordinator(mock_input, [midi_output])
        coord.start()

        time.sleep(1.0)
        mock_input.set_bpm(140.0)
        time.sleep(1.0)

        stats = coord.get_statistics()
        coord.stop()

        assert 139.0 <= stats['current_bpm'] <= 141.0

    def test_multiple_outputs(self):
        mock_input = MockProDJLinkReceiver(bpm=128.0)
        midi_output = MIDIClockOutput()
        cc_output = ControlChainOutput()

        coord = SyncCoordinator(mock_input, [midi_output, cc_output])
        coord.start()

        time.sleep(1.5)

        midi_stats = midi_output.get_statistics()
        cc_stats = cc_output.get_statistics()
        coord.stop()

        assert midi_stats['current_bpm'] == 128.0
        assert cc_stats['last_bpm'] == 128.0

    def test_graceful_shutdown(self):
        mock_input = MockProDJLinkReceiver(bpm=120.0)
        midi_output = MIDIClockOutput()

        coord = SyncCoordinator(mock_input, [midi_output])
        coord.start()

        time.sleep(0.5)

        coord.stop()

        assert coord._running is False
        assert midi_output._running is False
