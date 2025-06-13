# File: tests/unit/test_config.py

import os
import pytest
from topstepquant import config

def test_load_config_success(tmp_path):
    """Loading a valid config file should produce the expected configuration dictionary."""
    # Create a sample YAML configuration file
    config_content = """\
broker:
  api_key: file_value
risk:
  max_daily_loss: 1000
  max_trade_size: 5
"""
    config_file = tmp_path / "sample_config.yaml"
    config_file.write_text(config_content)

    cfg = config.load_config(str(config_file))
    # The loaded config should be a dict with correct values from the file
    assert isinstance(cfg, dict)
    assert cfg["broker"]["api_key"] == "file_value"
    assert cfg["risk"]["max_daily_loss"] == 1000
    assert cfg["risk"]["max_trade_size"] == 5

def test_load_config_missing_required_section(tmp_path):
    """If a required section (e.g., 'risk') is missing in the config, an error should be raised."""
    bad_content = "broker:\n  api_key: abc\n"  # 'risk' section missing
    config_file = tmp_path / "incomplete_config.yaml"
    config_file.write_text(bad_content)

    # Expect load_config to raise an error due to missing 'risk' section
    with pytest.raises(KeyError):
        config.load_config(str(config_file))

def test_environment_overrides_config(monkeypatch, tmp_path):
    """Environment variables should override config file values for critical settings."""
    # Set an environment variable for broker API key to override the file value
    monkeypatch.setenv("BROKER_API_KEY", "env_value")
    config_content = "broker:\n  api_key: file_value\nrisk:\n  max_daily_loss: 500\n"
    config_file = tmp_path / "override_config.yaml"
    config_file.write_text(config_content)

    cfg = config.load_config(str(config_file))
    # The broker.api_key in config should be overridden by the environment variable
    assert cfg["broker"]["api_key"] == "env_value"
    # Other values remain as in the file
    assert cfg["risk"]["max_daily_loss"] == 500
