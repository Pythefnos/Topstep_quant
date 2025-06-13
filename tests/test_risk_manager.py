# File: tests/unit/test_risk_manager.py

import pytest
from topstepquant.risk_manager import RiskManager
from tests.conftest import TradeSignal

def test_allows_trade_within_limits():
    """RiskManager should allow a trade that does not violate any risk limits."""
    rm = RiskManager(max_daily_loss=1000, max_trade_size=5, max_open_positions=3)
    rm.current_loss = 500      # current loss below daily limit
    rm.current_open_positions = 1  # below max open positions
    signal = TradeSignal("ES", "BUY", 1)  # quantity within max_trade_size
    allowed = rm.validate_signal(signal)
    assert allowed is True, "Trade within all limits should be allowed"

def test_blocks_trade_exceeding_size_limit():
    """RiskManager should block a trade that exceeds the maximum allowed trade size."""
    rm = RiskManager(max_trade_size=5)
    signal = TradeSignal("ES", "BUY", 10)  # quantity 10 > max_trade_size 5
    allowed = rm.validate_signal(signal)
    assert allowed is False, "Trade larger than max_trade_size should be blocked"

def test_blocks_trade_after_daily_loss_limit():
    """RiskManager should block new trades once the daily loss limit is reached or exceeded."""
    rm = RiskManager(max_daily_loss=100)
    rm.current_loss = 100  # at daily loss limit
    signal = TradeSignal("ES", "BUY", 1)
    allowed = rm.validate_signal(signal)
    assert allowed is False, "No trades should be allowed after reaching daily loss limit"

def test_blocks_trade_when_max_open_reached():
    """RiskManager should block a trade if the maximum number of open positions is reached."""
    rm = RiskManager(max_open_positions=2)
    rm.current_open_positions = 2  # at max allowed open positions
    signal = TradeSignal("ES", "BUY", 1)
    allowed = rm.validate_signal(signal)
    assert allowed is False, "No new trade allowed when max open positions reached"

def test_allows_trade_when_below_risk_limits():
    """RiskManager should allow trades when current risk exposure is below all limits."""
    rm = RiskManager(max_daily_loss=500, max_trade_size=5, max_open_positions=3)
    rm.current_loss = 0       # no loss so far
    rm.current_open_positions = 0  # no open trades currently
    signal = TradeSignal("ES", "BUY", 5)  # quantity equal to max_trade_size
    allowed = rm.validate_signal(signal)
    assert allowed is True, "Trade should be allowed when under all risk thresholds"
