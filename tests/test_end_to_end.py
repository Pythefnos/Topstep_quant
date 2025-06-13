"""End-to-end integration tests."""

import pytest
from datetime import datetime
from topstep_quant.infrastructure.dummy_broker import DummyBroker
from topstep_quant.infrastructure.config import TradingConfig
from topstep_quant.execution.coordinator import ExecutionCoordinator
from topstep_quant.risk.risk_manager import RiskManager
from topstep_quant.strategies.microstructure_mm import MicrostructureMarketMakingStrategy


def test_full_trading_workflow():
    """Test complete trading workflow from strategy signal to execution."""
    # Setup components
    broker = DummyBroker(initial_balance=50000.0)
    broker.connect()
    config = TradingConfig()
    
    coordinator = ExecutionCoordinator(broker, config)
    coordinator.start_new_session()
    
    risk_manager = RiskManager(
        initial_balance=50000.0,
        daily_loss_limit=1000.0,
        trailing_drawdown=2000.0
    )
    risk_manager.start_new_day(50000.0)
    
    strategy = MicrostructureMarketMakingStrategy("MES", max_daily_loss=250.0)
    
    # Set market price
    broker.update_market_price("MES", 4500.0)
    
    # Execute a trade through coordinator
    order_id = coordinator.execute_order("MES", "BUY", 1, "MARKET", price=4500.0)
    
    assert order_id is not None
    
    # Check position was created
    positions = broker.get_open_positions()
    assert len(positions) == 1
    assert positions[0].instrument == "MES"
    assert positions[0].quantity == 1
    
    # Update strategy with trade
    strategy.on_trade(4500.0, 1, "BUY", datetime.now())
    assert strategy.position == 1
    assert strategy.avg_entry_price == 4500.0
    
    # Check risk limits are still OK
    current_balance = broker.get_account_balance()
    unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
    risk_manager.check_limits(current_balance, unrealized_pnl)
    
    # Simulate price movement and profit taking
    broker.update_market_price("MES", 4510.0)
    
    # Close position
    coordinator.execute_order("MES", "SELL", 1, "MARKET", price=4510.0)
    
    # Check position was closed
    positions = broker.get_open_positions()
    assert len(positions) == 0
    
    # Check profit was realized
    final_balance = broker.get_account_balance()
    assert final_balance > 50000.0  # Should have made profit


def test_risk_limit_enforcement():
    """Test that risk limits are properly enforced."""
    broker = DummyBroker(initial_balance=50000.0)
    broker.connect()
    config = TradingConfig(daily_loss_limit=100.0)  # Very low limit for testing
    
    coordinator = ExecutionCoordinator(broker, config)
    coordinator.start_new_session()
    
    # Set market price
    broker.update_market_price("MES", 4500.0)
    
    # Execute trade
    coordinator.execute_order("MES", "BUY", 1, "MARKET", price=4500.0)
    
    # Simulate large adverse price movement
    broker.update_market_price("MES", 4350.0)  # $150 loss per contract
    
    # Risk check should trigger daily loss limit
    coordinator._check_risk()
    
    assert coordinator.daily_locked is True


def test_session_management():
    """Test trading session start and end."""
    broker = DummyBroker(initial_balance=50000.0)
    broker.connect()
    config = TradingConfig()
    
    coordinator = ExecutionCoordinator(broker, config)
    
    # Start session
    coordinator.start_new_session()
    assert coordinator.day_start_balance == 50000.0
    assert not coordinator.daily_locked
    
    # Execute some trades
    broker.update_market_price("MES", 4500.0)
    coordinator.execute_order("MES", "BUY", 1, "MARKET", price=4500.0)
    
    # End session
    coordinator.end_session()
    assert coordinator.daily_locked is True
    
    # Check positions were flattened
    positions = broker.get_open_positions()
    assert len(positions) == 0