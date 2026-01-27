#!/usr/bin/env python3
"""
CDJ-3000 Sync Bridge - Build 2: Asyncio Architecture
Main entry point using async/await patterns.
"""
import asyncio
import signal
import argparse
import logging
import yaml
from pathlib import Path

from core.types import SyncConfig
from prodjlink_input import AsyncProDJLinkInput, MockAsyncInput
from midi_output import AsyncMIDIOutput, MIDIConfig
from control_chain_output import AsyncControlChainOutput, CCConfig
from coordinator import AsyncSyncCoordinator


def setup_logging(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def load_config(path: str) -> SyncConfig:
    config_path = Path(path)
    if not config_path.exists():
        return SyncConfig()

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    config = SyncConfig()
    if 'input' in data and 'prodjlink' in data['input']:
        config.prodjlink_interface = data['input']['prodjlink'].get('interface', config.prodjlink_interface)
        config.prodjlink_port = data['input']['prodjlink'].get('port', config.prodjlink_port)

    if 'output' in data:
        if 'midi' in data['output']:
            config.midi_device = data['output']['midi'].get('device', config.midi_device)
        if 'control_chain' in data['output']:
            config.cc_device = data['output']['control_chain'].get('device', config.cc_device)

    if 'logging' in data:
        config.log_level = data['logging'].get('level', config.log_level)

    return config


async def main_async(args):
    config = load_config(args.config)
    logger = setup_logging(config.log_level)
    logger.info("CDJ Sync Bridge (Build 2: Asyncio) starting...")

    if args.mock:
        cdj_input = MockAsyncInput(bpm=args.bpm)
        logger.info(f"Using mock input at {args.bpm} BPM")
    else:
        cdj_input = AsyncProDJLinkInput(
            interface=config.prodjlink_interface,
            port=config.prodjlink_port
        )

    outputs = []

    midi_config = MIDIConfig(device=config.midi_device)
    midi_out = AsyncMIDIOutput(midi_config)
    outputs.append(midi_out)

    if config.cc_device:
        cc_config = CCConfig(device=config.cc_device)
        cc_out = AsyncControlChainOutput(cc_config)
        outputs.append(cc_out)

    coordinator = AsyncSyncCoordinator(cdj_input, outputs)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await coordinator.start()
        logger.info("Synchronization active. Press Ctrl+C to stop.")

        stats_task = asyncio.create_task(print_stats(coordinator, logger))

        await stop_event.wait()

        stats_task.cancel()
        try:
            await stats_task
        except asyncio.CancelledError:
            pass

    finally:
        await coordinator.stop()


async def print_stats(coordinator, logger):
    while True:
        await asyncio.sleep(5)
        stats = coordinator.get_statistics()
        logger.info(
            f"Stats: beats={stats['beat_count']}, "
            f"bpm={stats['current_bpm']:.1f}, "
            f"jitter={stats['average_jitter_ms']:.2f}ms"
        )


def main():
    parser = argparse.ArgumentParser(description="CDJ Sync Bridge (Asyncio)")
    parser.add_argument('--config', default='config.yaml', help='Config file')
    parser.add_argument('--mock', action='store_true', help='Use mock input')
    parser.add_argument('--bpm', type=float, default=120.0, help='Mock BPM')
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
