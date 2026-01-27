"""Configuration parser for YAML config files."""
import yaml
import logging
from typing import Any, Dict, Optional
from pathlib import Path

from core.types import SyncConfig
from core.errors import ConfigurationError

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> SyncConfig:
    """Load configuration from YAML file."""
    path = Path(config_path)

    if not path.exists():
        logger.warning(f"Config file {config_path} not found, using defaults")
        return SyncConfig()

    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {config_path}: {e}")

    if not data:
        return SyncConfig()

    config = SyncConfig()

    if 'input' in data and 'prodjlink' in data['input']:
        pdj = data['input']['prodjlink']
        config.prodjlink_interface = pdj.get('interface', config.prodjlink_interface)
        config.prodjlink_port = pdj.get('port', config.prodjlink_port)

    if 'output' in data:
        if 'midi' in data['output']:
            midi = data['output']['midi']
            config.midi_device = midi.get('device', config.midi_device)
            config.midi_baud = midi.get('baud_rate', config.midi_baud)
            config.midi_ppqn = midi.get('ppqn', config.midi_ppqn)
            config.latency_compensation_ms = midi.get(
                'latency_compensation_ms', config.latency_compensation_ms
            )

        if 'control_chain' in data['output']:
            cc = data['output']['control_chain']
            config.cc_device = cc.get('device', config.cc_device)
            config.cc_baud = cc.get('baud_rate', config.cc_baud)
            config.cc_gpio_de_pin = cc.get('gpio_de_pin', config.cc_gpio_de_pin)

    if 'timing' in data:
        config.enable_pll = data['timing'].get('enable_pll', config.enable_pll)
        config.jitter_threshold_ms = data['timing'].get(
            'jitter_threshold_ms', config.jitter_threshold_ms
        )

    if 'logging' in data:
        config.log_level = data['logging'].get('level', config.log_level)
        config.log_file = data['logging'].get('file', config.log_file)
        config.log_beat_events = data['logging'].get(
            'log_beat_events', config.log_beat_events
        )

    logger.info(f"Configuration loaded from {config_path}")
    return config
