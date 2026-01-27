#!/usr/bin/env python3
"""
CDJ-3000 Sync Bridge - Build 3: Functional/Event-Driven
Main entry point using function composition.
"""
import sys
import signal
import time
import argparse
import logging
import yaml
from pathlib import Path

from prodjlink import create_prodjlink_input, create_mock_input
from midi_output import create_midi_output
from control_chain import create_control_chain_output
from bridge import compose_bridge


def setup_logging(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def load_config(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def main():
    parser = argparse.ArgumentParser(description="CDJ Sync Bridge (Functional)")
    parser.add_argument('--config', default='config.yaml', help='Config file')
    parser.add_argument('--mock', action='store_true', help='Use mock input')
    parser.add_argument('--bpm', type=float, default=120.0, help='Mock BPM')
    args = parser.parse_args()

    config = load_config(args.config)
    log_level = config.get('logging', {}).get('level', 'INFO')
    logger = setup_logging(log_level)
    logger.info("CDJ Sync Bridge (Build 3: Functional) starting...")

    pdj_config = config.get('input', {}).get('prodjlink', {})
    port = pdj_config.get('port', 50001)

    midi_config = config.get('output', {}).get('midi', {})
    midi_device = midi_config.get('device', '/dev/ttyAMA0')
    midi_baud = midi_config.get('baud_rate', 31250)
    midi_ppqn = midi_config.get('ppqn', 24)

    cc_config = config.get('output', {}).get('control_chain', {})
    cc_device = cc_config.get('device', '/dev/ttyUSB0')
    cc_baud = cc_config.get('baud_rate', 115200)
    cc_gpio = cc_config.get('gpio_de_pin', 27)

    outputs = []

    midi_out = create_midi_output(midi_device, midi_baud, midi_ppqn)
    outputs.append(midi_out)
    logger.info(f"MIDI output configured: {midi_device}")

    if cc_device:
        cc_out = create_control_chain_output(cc_device, cc_baud, cc_gpio)
        outputs.append(cc_out)
        logger.info(f"Control Chain output configured: {cc_device}")

    if args.mock:
        def input_factory(on_beat):
            start, stop, _ = create_mock_input(args.bpm, on_beat)
            return start, stop
        logger.info(f"Using mock input at {args.bpm} BPM")
    else:
        def input_factory(on_beat):
            return create_prodjlink_input(port, on_beat)

    start_all, stop_all, get_stats = compose_bridge(input_factory, outputs)

    running = {'value': True}

    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        running['value'] = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        start_all()
        logger.info("Synchronization active. Press Ctrl+C to stop.")

        while running['value']:
            time.sleep(5)
            stats = get_stats()
            logger.info(
                f"Stats: beats={stats['beat_count']}, "
                f"bpm={stats['current_bpm']:.1f}, "
                f"jitter={stats['average_jitter_ms']:.2f}ms"
            )

    finally:
        stop_all()


if __name__ == "__main__":
    main()
