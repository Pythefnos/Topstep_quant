"""Test trading strategy implementations."""

import pytest
from datetime import datetime, time
from topstep_quant.strategies.microstructure_mm import MicrostructureMarketMakingStrategy
from topstep_quant.strategies.intraday_mean_revert import IntradayMeanReversionStrategy
from topstep_quant.strategies.trend_follow import TrendFollowingStrategy
from topstep_quant.strategies.tail_hedge import TailHedgeStrategy


def test_microstructure_mm_strategy():
    """Test microstructure market making strategy."""
    strategy = MicrostructureMarketMakingStrategy("MES", max_daily_loss=1000.0)
    
    assert strategy.instrument == "MES"
    assert strategy.max_daily_loss == 1000.0
    assert strategy.position == 0
    assert strategy.active is True


def test_mean_reversion_strategy():
    """Test mean reversion strategy."""
    strategy = IntradayMeanReversionStrategy("MES", max_daily_loss=1000.0)
    
    assert strategy.instrument == "MES"
    assert strategy.lookback == 50
    assert len(strategy.prices) == 0


def test_trend_following_strategy():
    """Test trend following strategy."""
    strategy = TrendFollowingStrategy("MES", max_daily_loss=1000.0)
    
    assert strategy.instrument == "MES"
    assert strategy.short_window == 20
    assert strategy.long_window == 60


def test_tail_hedge_strategy():
    """Test tail hedge strategy."""
    strategy = TailHedgeStrategy("MES", max_daily_loss=1000.0)
    
    assert strategy.instrument == "MES"
    assert strategy.tail_threshold == 0.02
    assert strategy.day_high is None


def test_strategy_position_update():
    """Test strategy position update on trade."""
    strategy = MicrostructureMarketMakingStrategy("MES")
    
    # Test opening position
    strategy.on_trade(4500.0, 1, "BUY", datetime.now())
    assert strategy.position == 1
    assert strategy.avg_entry_price == 4500.0
    
    # Test closing position
    strategy.on_trade(4510.0, 1, "SELL", datetime.now())
    assert strategy.position == 0
    assert strategy.avg_entry_price is None
    assert strategy.realized_pnl == 10.0  # $10 profit


def test_strategy_risk_limit():
    """Test strategy risk limit enforcement."""
    strategy = MicrostructureMarketMakingStrategy("MES", max_daily_loss=100.0)
    
    # Simulate a losing trade
    strategy.on_trade(4500.0, 1, "BUY", datetime.now())
    strategy.last_price = 4400.0  # $100 unrealized loss
    
    # Check risk limit
    risk_hit = strategy.check_risk_limit()
    assert risk_hit is True
    assert strategy.active is False


def test_strategy_flatten():
    """Test strategy position flattening."""
    strategy = MicrostructureMarketMakingStrategy("MES")
    
    # Open position
    strategy.on_trade(4500.0, 2, "BUY", datetime.now())
    strategy.last_price = 4510.0
    
    # Flatten
    strategy.flatten()
    
    assert strategy.position == 0
    assert strategy.avg_entry_price is None
    assert strategy.realized_pnl == 20.0  # $10 per contract profit


def test_mean_reversion_signal_generation():
    """Test mean reversion strategy signal generation."""
    strategy = IntradayMeanReversionStrategy("MES", lookback=5, threshold=0.01)
    
    # Add some price data
    prices = [4500.0, 4502.0, 4498.0, 4501.0, 4499.0]
    for price in prices:
        strategy.prices.append(price)
    
    # Test with price above threshold
    market_data = {
        'last': 4520.0,  # Well above mean
        'timestamp': datetime.now()
    }
    
    strategy.on_tick(market_data)
    # Should have generated a sell signal and executed it
    assert strategy.position == -1  # Short position from mean reversion