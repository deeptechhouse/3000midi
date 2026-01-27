#!/usr/bin/env python3
"""
CDJ-3000 Sync Bridge - Build 1: Traditional OOP with Threading
Main entry point with dependency injection.
"""
import sys
import signal
import time
import argparse
import logging

from utils.config_parser import load_config
from utils.logger import setup_logging
from input.prodjlink_receiver import ProDJLinkReceiver, MockProDJLinkReceiver
from output.midi_clock_output import MIDIClockOutput, MIDIClockConfig
from output.control_chain_output import ControlChainOutput, ControlChainConfig
from sync.coordinator import SyncCoordinator, TimingConfig


def main():
    parser = argparse.ArgumentParser(description="CDJ-3000 Sync Bridge")
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--mock', action='store_true', help='Use mock input for testing')
    parser.add_argument('--bpm', type=float, default=120.0, help='Mock BPM')
    args = parser.parse_args()

    config = load_config(args.config)
    logger = setup_logging(config.log_level)
    logger.info("CDJ Sync Bridge (Build 1: OOP/Threading) starting...")

    if args.mock:
        cdj_input = MockProDJLinkReceiver(bpm=args.bpm)
        logger.info(f"Using mock input at {args.bpm} BPM")
    else:
        cdj_input = ProDJLinkReceiver(
            interface=config.prodjlink_interface,
            port=config.prodjlink_port
        )

    outputs = []

    midi_config = MIDIClockConfig(
        device=config.midi_device,
        baud_rate=config.midi_baud,
        ppqn=config.midi_ppqn,
        latency_compensation_ms=config.latency_compensation_ms
    )
    midi_out = MIDIClockOutput(midi_config)
    outputs.append(midi_out)
    logger.info(f"MIDI output configured: {config.midi_device}")

    if config.cc_device:
        cc_config = ControlChainConfig(
            device=config.cc_device,
            baud_rate=config.cc_baud,
            gpio_de_pin=config.cc_gpio_de_pin
        )
        cc_out = ControlChainOutput(cc_config)
        outputs.append(cc_out)
        logger.info(f"Control Chain output configured: {config.cc_device}")

    timing_config = TimingConfig(
        enable_pll=config.enable_pll,
        jitter_threshold_ms=config.jitter_threshold_ms
    )

    coordinator = SyncCoordinator(
        input_device=cdj_input,
        output_devices=outputs,
        timing_config=timing_config
    )

    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        coordinator.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        coordinator.start()
        logger.info("Synchronization active. Press Ctrl+C to stop.")

        while True:
            time.sleep(5)
            stats = coordinator.get_statistics()
            logger.info(
                f"Stats: beats={stats['beat_count']}, "
                f"bpm={stats['current_bpm']:.1f}, "
                f"jitter={stats['average_jitter_ms']:.2f}ms"
            )

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
