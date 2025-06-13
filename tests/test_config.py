"""Test configuration loading and validation."""

import os
import pytest
import tempfile
import yaml
from pathlib import Path

from topstep_quant.infrastructure.config import TradingConfig


def test_trading_config_defaults():
    """Test that TradingConfig has sensible defaults."""
    config = TradingConfig()
    
    assert config.daily_loss_limit == 1000.0
    assert config.trailing_drawdown == 2000.0
    assert config.initial_balance == 50000.0
    assert config.broker_type == "dummy"
    assert config.tradovate_demo is True


def test_trading_config_custom_values():
    """Test TradingConfig with custom values."""
    config = TradingConfig(
        daily_loss_limit=500.0,
        trailing_drawdown=1000.0,
        broker_type="tradovate"
    )
    
    assert config.daily_loss_limit == 500.0
    assert config.trailing_drawdown == 1000.0
    assert config.broker_type == "tradovate"


def test_load_yaml_config():
    """Test loading configuration from YAML file."""
    config_data = {
        'topstep': {
            'account_type': 'Express 50K',
            'username': 'test_user',
            'password': 'test_pass'
        },
        'risk': {
            'max_daily_loss': 1000,
            'max_total_drawdown': 2000,
            'max_position_size': 5,
            'trade_limit_per_day': 10,
            'trade_limit_per_week': 50,
            'allowed_markets': ['ES', 'NQ', 'YM']
        },
        'strategies': [
            {
                'name': 'MomentumScalper',
                'enabled': True,
                'description': 'Scalping strategy'
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    try:
        # Test that the file can be loaded
        with open(temp_path, 'r') as f:
            loaded_data = yaml.safe_load(f)
        
        assert loaded_data['topstep']['username'] == 'test_user'
        assert loaded_data['risk']['max_daily_loss'] == 1000
        assert len(loaded_data['strategies']) == 1
        
    finally:
        os.unlink(temp_path)