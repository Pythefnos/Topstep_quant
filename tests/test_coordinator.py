"""Test execution coordinator functionality."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, time

from topstep_quant.execution.coordinator import ExecutionCoordinator
from topstep_quant.infrastructure.config import TradingConfig
from topstep_quant.infrastructure.dummy_broker import DummyBroker


def test_coordinator_initialization():
    """Test ExecutionCoordinator initialization."""
    broker = DummyBroker()
    config = TradingConfig()
    
    coordinator = ExecutionCoordinator(broker, config)
    
    assert coordinator.broker is broker
    assert coordinator.config is config
    assert coordinator.daily_loss_limit == 1000.0
    assert coordinator.trailing_drawdown == 2000.0


def test_start_new_session():
    """Test starting a new trading session."""
    broker = DummyBroker(initial_balance=50000.0)
    broker.connect()
    config = TradingConfig()
    
    coordinator = ExecutionCoordinator(broker, config)
    coordinator.start_new_session()
    
    assert coordinator.day_start_balance == 50000.0
    assert coordinator.initial_balance == 50000.0
    assert not coordinator.daily_locked
    assert not coordinator.account_closed


def test_execute_order_success():
    """Test successful order execution."""
    broker = DummyBroker(initial_balance=50000.0)
    broker.connect()
    config = TradingConfig()
    
    coordinator = ExecutionCoordinator(broker, config)
    coordinator.start_new_session()
    
    # Update market price for the instrument
    broker.update_market_price("MES", 4500.0)
    
    order_id = coordinator.execute_order("MES", "BUY", 1, "MARKET", price=4500.0)
    
    assert order_id is not None
    positions = broker.get_open_positions()
    assert len(positions) == 1
    assert positions[0].quantity == 1


def test_execute_order_when_not_allowed():
    """Test order execution when trading is not allowed."""
    broker = DummyBroker()
    config = TradingConfig()
    
    coordinator = ExecutionCoordinator(broker, config)
    # Don't start session, so trading should not be allowed
    
    with pytest.raises(RuntimeError, match="Trading session not started"):
        coordinator.execute_order("MES", "BUY", 1, "MARKET")


@patch('topstep_quant.execution.coordinator.datetime')
def test_is_trading_allowed_time_check(mock_datetime):
    """Test trading allowed based on time."""
    # Mock current time to be within trading hours
    mock_now = MagicMock()
    mock_now.time.return_value = time(14, 0)  # 2:00 PM CT
    mock_datetime.now.return_value = mock_now
    
    broker = DummyBroker(initial_balance=50000.0)
    broker.connect()
    config = TradingConfig()
    
    coordinator = ExecutionCoordinator(broker, config)
    coordinator.start_new_session()
    
    assert coordinator.is_trading_allowed()


def test_daily_loss_limit_breach():
    """Test daily loss limit enforcement."""
    broker = DummyBroker(initial_balance=50000.0)
    broker.connect()
    config = TradingConfig(daily_loss_limit=100.0)  # Low limit for testing
    
    coordinator = ExecutionCoordinator(broker, config)
    coordinator.start_new_session()
    
    # Simulate a large loss by updating broker balance
    broker._balance = 49900.0  # $100 loss
    
    # This should trigger the daily loss limit
    coordinator._check_risk()
    
    assert coordinator.daily_locked