"""Test risk management functionality."""

import pytest
from topstep_quant.risk.risk_manager import RiskManager
from topstep_quant.risk.kill_switch import KillSwitch, RiskViolationError


def test_risk_manager_initialization():
    """Test RiskManager initialization with default values."""
    rm = RiskManager()
    
    assert rm._initial_balance == 50000.0
    assert rm._daily_loss_limit == 1000.0
    assert rm._trailing_drawdown == 2000.0
    assert rm._high_balance == 50000.0
    assert rm._trailing_threshold == 48000.0  # 50000 - 2000


def test_start_new_day():
    """Test starting a new trading day."""
    rm = RiskManager()
    rm.start_new_day(51000.0)  # Start with profit from previous day
    
    assert rm._start_of_day_balance == 51000.0


def test_daily_loss_limit_check():
    """Test daily loss limit enforcement."""
    rm = RiskManager(daily_loss_limit=100.0)
    rm.start_new_day(50000.0)
    
    # Test within limit
    rm.check_limits(49950.0, 0.0)  # $50 loss, should be OK
    
    # Test at limit - should trigger kill switch
    with pytest.raises(RiskViolationError):
        rm.check_limits(49900.0, 0.0)  # $100 loss, should trigger


def test_trailing_drawdown_check():
    """Test trailing drawdown limit enforcement."""
    rm = RiskManager(trailing_drawdown=100.0, initial_balance=1000.0)
    rm.start_new_day(1000.0)
    
    # Test within limit
    rm.check_limits(950.0, 0.0)  # $50 loss, should be OK (threshold is 900)
    
    # Test at limit - should trigger kill switch
    with pytest.raises(RiskViolationError):
        rm.check_limits(900.0, 0.0)  # At threshold, should trigger


def test_end_of_day_new_high():
    """Test end of day processing with new high balance."""
    rm = RiskManager(initial_balance=50000.0, trailing_drawdown=2000.0)
    rm.start_new_day(50000.0)
    
    # End day with profit
    rm.end_of_day(52000.0)
    
    assert rm._high_balance == 52000.0
    assert rm._trailing_threshold == 50000.0  # Should be capped at initial balance


def test_kill_switch_functionality():
    """Test kill switch activation and reset."""
    kill_switch = KillSwitch()
    
    assert not kill_switch.triggered
    assert kill_switch.reason == ""
    
    # Test activation
    with pytest.raises(RiskViolationError):
        kill_switch.activate("Test reason")
    
    assert kill_switch.triggered
    assert kill_switch.reason == "Test reason"
    
    # Test reset
    kill_switch.reset()
    assert not kill_switch.triggered
    assert kill_switch.reason == ""


def test_risk_manager_with_unrealized_pnl():
    """Test risk checks including unrealized P&L."""
    rm = RiskManager(daily_loss_limit=100.0)
    rm.start_new_day(50000.0)
    
    # Test with unrealized loss that pushes over limit
    with pytest.raises(RiskViolationError):
        rm.check_limits(49950.0, -60.0)  # $50 realized + $60 unrealized = $110 total loss