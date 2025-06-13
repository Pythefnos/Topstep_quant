# File: tests/unit/test_strategies.py

import pytest
from topstepquant.strategies import MeanReversionStrategy, BreakoutStrategy

def test_mean_reversion_strategy_sell_signal():
    """MeanReversionStrategy should signal SELL when price is above the average (overbought)."""
    strategy = MeanReversionStrategy(window=5)  # assume window parameter for moving average
    prices = [100, 102, 98, 99, 110]  # Last price 110 is well above the average (~102)
    signals = strategy.generate_signals(prices)
    assert signals, "Expected a trade signal for overbought condition"
    signal = signals[0]
    assert signal.action == "SELL", "Should issue SELL signal when price is above the mean"

def test_mean_reversion_strategy_buy_signal():
    """MeanReversionStrategy should signal BUY when price is below the average (oversold)."""
    strategy = MeanReversionStrategy(window=5)
    prices = [100, 102, 98, 101, 90]  # Last price 90 is well below the average (~100)
    signals = strategy.generate_signals(prices)
    assert signals, "Expected a trade signal for oversold condition"
    signal = signals[0]
    assert signal.action == "BUY", "Should issue BUY signal when price is below the mean"

def test_mean_reversion_strategy_no_signal():
    """MeanReversionStrategy should produce no signal when price is near the average."""
    strategy = MeanReversionStrategy(window=3)
    prices = [100, 102, 98]  # Last price ~100, near the average of previous values
    signals = strategy.generate_signals(prices)
    # Expect no signals (None or empty list) when there's no significant divergence
    assert signals is None or len(signals) == 0, "No signal should be generated for minimal divergence"

def test_breakout_strategy_buy_signal():
    """BreakoutStrategy should signal BUY when price breaks above recent high."""
    strategy = BreakoutStrategy(lookback=3)
    prices = [100, 105, 102, 108]  # Prev 3 high = 105, last = 108 breaks above high
    signals = strategy.generate_signals(prices)
    assert signals, "Expected a breakout BUY signal"
    signal = signals[0]
    assert signal.action == "BUY", "Should issue BUY on breakout above the recent high"

def test_breakout_strategy_sell_signal():
    """BreakoutStrategy should signal SELL when price breaks below recent low."""
    strategy = BreakoutStrategy(lookback=3)
    prices = [100, 95, 98, 90]  # Prev 3 low = 95, last = 90 breaks below low
    signals = strategy.generate_signals(prices)
    assert signals, "Expected a breakout SELL signal"
    signal = signals[0]
    assert signal.action == "SELL", "Should issue SELL on breakout below the recent low"

def test_breakout_strategy_no_signal_in_range():
    """BreakoutStrategy should produce no signal if price stays within the recent range."""
    strategy = BreakoutStrategy(lookback=3)
    prices = [100, 105, 102, 103]  # High=105, Low=100, last=103 is within range
    signals = strategy.generate_signals(prices)
    assert signals is None or len(signals) == 0, "No signal expected when price remains in range"

def test_breakout_strategy_insufficient_data():
    """BreakoutStrategy should handle insufficient data by not generating any signal."""
    strategy = BreakoutStrategy(lookback=5)
    prices = [100, 102]  # Not enough data points for the lookback window
    signals = strategy.generate_signals(prices)
    # With insufficient data, strategy should return no signals (rather than throw an error)
    assert signals is None or len(signals) == 0, "No signal expected with insufficient data"
