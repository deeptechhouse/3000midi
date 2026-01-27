"""Bridge coordinator using functional composition."""
import logging
from typing import Dict, Any, List, Callable

from beat_types import Beat
from event_bus import EventBus

logger = logging.getLogger(__name__)


def create_sync_bridge(outputs: List[Dict[str, Callable]]):
    """
    Create sync bridge that coordinates input events to outputs.
    Uses event bus for decoupled communication.
    Returns (on_beat, start, stop, get_stats) functions.
    """
    bus = EventBus()
    state = {
        'beat_count': 0,
        'was_playing': False,
        'last_bpm': 0.0,
        'jitter_samples': []
    }
    last_timestamp = {'value': 0.0}

    def handle_beat(beat: Beat):
        state['beat_count'] += 1
        state['last_bpm'] = beat.bpm

        if last_timestamp['value'] > 0:
            expected = 60.0 / beat.bpm
            actual = beat.timestamp - last_timestamp['value']
            jitter = abs(actual - expected)
            state['jitter_samples'].append(jitter)
            if len(state['jitter_samples']) > 100:
                state['jitter_samples'].pop(0)
        last_timestamp['value'] = beat.timestamp

        if beat.is_playing and not state['was_playing']:
            for out in outputs:
                try:
                    out['send_start']()
                except Exception as e:
                    logger.error(f"Error sending start: {e}")

        elif not beat.is_playing and state['was_playing']:
            for out in outputs:
                try:
                    out['send_stop']()
                except Exception as e:
                    logger.error(f"Error sending stop: {e}")

        state['was_playing'] = beat.is_playing

        for out in outputs:
            try:
                out['set_bpm'](beat.bpm)
            except Exception as e:
                logger.error(f"Error setting tempo: {e}")

    bus.on('beat', handle_beat)

    def on_beat(beat: Beat):
        bus.emit('beat', beat)

    def start():
        for out in outputs:
            try:
                out['start']()
            except Exception as e:
                logger.error(f"Error starting output: {e}")
        logger.info("Sync bridge started")

    def stop():
        for out in outputs:
            try:
                out['send_stop']()
                out['stop']()
            except Exception as e:
                logger.error(f"Error stopping output: {e}")
        logger.info("Sync bridge stopped")

    def get_stats() -> Dict[str, Any]:
        avg_jitter = sum(state['jitter_samples']) / len(state['jitter_samples']) if state['jitter_samples'] else 0
        return {
            'beat_count': state['beat_count'],
            'current_bpm': state['last_bpm'],
            'is_playing': state['was_playing'],
            'average_jitter_ms': avg_jitter * 1000
        }

    return on_beat, start, stop, get_stats


def compose_bridge(input_fn, outputs: List[Dict]):
    """
    Compose complete bridge with input and outputs.
    Returns (start_all, stop_all, get_stats) functions.
    """
    on_beat, start_bridge, stop_bridge, get_stats = create_sync_bridge(outputs)
    start_input, stop_input = input_fn(on_beat)

    def start_all():
        start_bridge()
        start_input()

    def stop_all():
        stop_input()
        stop_bridge()

    return start_all, stop_all, get_stats
