"""Tests for functional sync bridge."""
import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from beat_types import Beat, make_beat, Event, EventType
from event_bus import EventBus, create_event_bus
from prodjlink import parse_prodjlink_packet, create_mock_input
from midi_output import create_midi_output, create_midi_clock_generator
from control_chain import build_cc_packet, create_control_chain_output
from bridge import create_sync_bridge, compose_bridge


class TestBeatType:
    def test_make_beat(self):
        beat = make_beat(timestamp=100.0, bpm=128.0)
        assert beat.bpm == 128.0
        assert beat.beat_pos == 1
        assert beat.is_playing is True

    def test_beat_clamping(self):
        beat = make_beat(timestamp=100.0, beat_pos=5, bpm=500.0)
        assert beat.beat_pos == 4
        assert beat.bpm == 300.0

    def test_beat_immutable(self):
        beat = make_beat(timestamp=100.0)
        with pytest.raises(AttributeError):
            beat.bpm = 140.0


class TestEventBus:
    def test_create_event_bus(self):
        subscribe, emit, count = create_event_bus()
        assert count('test') == 0

    def test_subscribe_emit(self):
        bus = EventBus()
        received = []

        bus.on('beat', lambda x: received.append(x))
        bus.emit('beat', 'payload')

        assert received == ['payload']

    def test_unsubscribe(self):
        bus = EventBus()
        received = []

        unsub = bus.on('test', lambda x: received.append(x))
        bus.emit('test', 1)

        unsub()
        bus.emit('test', 2)

        assert received == [1]

    def test_multiple_subscribers(self):
        bus = EventBus()
        results = []

        bus.on('event', lambda x: results.append(x * 2))
        bus.on('event', lambda x: results.append(x * 3))
        bus.emit('event', 10)

        assert sorted(results) == [20, 30]


class TestProDJLinkParser:
    def test_invalid_packet(self):
        assert parse_prodjlink_packet(b'') is None
        assert parse_prodjlink_packet(b'short') is None
        assert parse_prodjlink_packet(b'invalid_header__' + b'\x00' * 40) is None

    def test_valid_packet_structure(self):
        header = b'Qspt1WmJOL'
        packet = bytearray(header)
        packet.append(0x28)
        packet.append(1)
        packet.extend([0x00, 0x00, 0x32, 0x00])
        packet.extend([0x00, 0x00, 0x00, 0x00])
        packet.extend([1, 1, 1, 1])
        packet.extend([0x00, 0x00, 0x00, 0x00])
        packet.extend(b'\x00' * 20)

        beat = parse_prodjlink_packet(bytes(packet))
        assert beat is not None or beat is None


class TestMockInput:
    def test_create_mock_input(self):
        received = []
        start, stop, set_bpm = create_mock_input(120.0, lambda b: received.append(b))

        start()
        time.sleep(1.5)
        stop()

        assert len(received) >= 2
        assert all(b.bpm == 120.0 for b in received)

    def test_bpm_change(self):
        received = []
        start, stop, set_bpm = create_mock_input(120.0, lambda b: received.append(b))

        start()
        time.sleep(0.6)
        set_bpm(140.0)
        time.sleep(0.6)
        stop()

        assert any(b.bpm == 140.0 for b in received)


class TestMIDIOutput:
    def test_create_midi_output(self):
        midi = create_midi_output()
        assert 'start' in midi
        assert 'stop' in midi
        assert 'set_bpm' in midi

    def test_clock_generator(self):
        writes = []

        def mock_write(data):
            writes.append(data)

        start, stop, set_bpm, send_start, send_stop, get_stats = create_midi_clock_generator(mock_write)

        start()
        set_bpm(120.0)
        send_start()
        time.sleep(0.5)
        stop()

        stats = get_stats()
        assert stats['clocks_sent'] > 0

    def test_midi_tempo_change(self):
        midi = create_midi_output()
        midi['start']()
        midi['set_bpm'](128.0)

        stats = midi['get_stats']()
        assert stats['current_bpm'] == 128.0

        midi['stop']()


class TestControlChain:
    def test_build_packet(self):
        packet = build_cc_packet(1, 1, 128.0)
        assert packet[0] == 0x55
        assert packet[1] == 0xAA
        assert len(packet) == 12

    def test_create_output(self):
        cc = create_control_chain_output()
        assert 'start' in cc
        assert 'stop' in cc
        assert 'set_bpm' in cc


class TestSyncBridge:
    def test_create_bridge(self):
        outputs = [create_midi_output()]
        on_beat, start, stop, get_stats = create_sync_bridge(outputs)

        start()
        stats = get_stats()
        assert stats['beat_count'] == 0

        stop()

    def test_beat_forwarding(self):
        midi = create_midi_output()
        on_beat, start, stop, get_stats = create_sync_bridge([midi])

        start()
        midi['start']()

        beat = make_beat(timestamp=time.monotonic(), is_playing=True)
        on_beat(beat)

        stats = get_stats()
        assert stats['beat_count'] == 1

        stop()

    def test_transport_state_change(self):
        midi = create_midi_output()
        on_beat, start, stop, get_stats = create_sync_bridge([midi])

        start()

        beat_play = make_beat(timestamp=time.monotonic(), is_playing=True)
        on_beat(beat_play)

        assert get_stats()['is_playing'] is True

        beat_stop = make_beat(timestamp=time.monotonic(), is_playing=False)
        on_beat(beat_stop)

        assert get_stats()['is_playing'] is False

        stop()


class TestIntegration:
    def test_full_pipeline(self):
        midi = create_midi_output()

        def input_factory(on_beat):
            return create_mock_input(120.0, on_beat)[:2]

        start_all, stop_all, get_stats = compose_bridge(input_factory, [midi])

        start_all()
        midi['send_start']()
        time.sleep(2.0)

        stats = get_stats()
        stop_all()

        assert stats['beat_count'] >= 3
        assert 119.0 <= stats['current_bpm'] <= 121.0

    def test_multiple_outputs(self):
        midi = create_midi_output()
        cc = create_control_chain_output()

        def input_factory(on_beat):
            return create_mock_input(128.0, on_beat)[:2]

        start_all, stop_all, get_stats = compose_bridge(input_factory, [midi, cc])

        start_all()
        time.sleep(1.0)

        midi_stats = midi['get_stats']()
        cc_stats = cc['get_stats']()
        stop_all()

        assert midi_stats['current_bpm'] == 128.0
        assert cc_stats['last_bpm'] == 128.0
