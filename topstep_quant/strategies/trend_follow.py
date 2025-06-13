# topstep_quant/strategies/trend_follow.py
import logging
from typing import Deque, Dict, Any
from datetime import datetime
from collections import deque
from .base import StrategyBase

logger = logging.getLogger(__name__)

class TrendFollowingStrategy(StrategyBase):
    """
    An intraday trend-following strategy.
    This strategy attempts to ride short-term momentum by using moving average crossovers.
    It enters long or short when a fast moving average crosses a slow moving average,
    indicating a trend change.
    """
    def __init__(self, instrument: str, max_daily_loss: float = None, 
                 flatten_time: datetime.time = datetime.time(15, 55),
                 short_window: int = 20, long_window: int = 60):
        """
        Initialize the trend-following strategy.
        
        Args:
            instrument (str): The futures contract symbol to trade.
            max_daily_loss (float, optional): Daily loss limit for risk management.
            flatten_time (datetime.time): Time of day to flatten all positions.
            short_window (int): Number of ticks for the short-term moving average.
            long_window (int): Number of ticks for the long-term moving average.
        """
        super().__init__(instrument, max_daily_loss, flatten_time)
        self.short_window = short_window
        self.long_window = long_window
        # Use deques to maintain recent prices for moving average calculations
        self.short_window_prices: Deque[float] = deque(maxlen=short_window)
        self.long_window_prices: Deque[float] = deque(maxlen=long_window)
    
    def on_tick(self, market_data: Dict[str, Any]) -> None:
        """Process market tick: update moving averages and possibly generate a trend-following signal."""
        if not self.active:
            return
        self._update_market_state(market_data)
        timestamp = market_data.get('timestamp', datetime.now())
        
        if self.check_risk_limit():
            return
        if self.should_flatten(timestamp):
            self.flatten()
            return
        
        # Determine current price
        price = market_data.get('last')
        if price is None:
            bid = market_data.get('bid')
            ask = market_data.get('ask')
            if bid is not None and ask is not None:
                price = (bid + ask) / 2
        if price is None:
            return
        price = float(price)
        
        # Update moving average windows
        self.short_window_prices.append(price)
        self.long_window_prices.append(price)
        if len(self.long_window_prices) < self.long_window:
            return  # wait until enough data for long MA
        
        short_ma = sum(self.short_window_prices) / len(self.short_window_prices)
        long_ma = sum(self.long_window_prices) / len(self.long_window_prices)
        signals = []
        
        # Determine trend signal based on moving averages
        if self.position == 0:
            # No position: enter if a crossover occurs
            if short_ma > long_ma:
                signals.append({'side': 'BUY', 'quantity': 1, 'price': None})
                logger.debug("Trend signal: short MA %.2f above long MA %.2f -> BUY", short_ma, long_ma)
            elif short_ma < long_ma:
                signals.append({'side': 'SELL', 'quantity': 1, 'price': None})
                logger.debug("Trend signal: short MA %.2f below long MA %.2f -> SELL", short_ma, long_ma)
        elif self.position > 0:
            # Long position open: if trend reverses down, flip to short
            if short_ma < long_ma:
                # Sell enough to not only close long but go short
                flip_qty = abs(self.position) + 1
                signals.append({'side': 'SELL', 'quantity': flip_qty, 'price': None})
                logger.debug("Trend reversal: switching from long to short (MA cross down)")
        elif self.position < 0:
            # Short position open: if trend reverses up, flip to long
            if short_ma > long_ma:
                flip_qty = abs(self.position) + 1
                signals.append({'side': 'BUY', 'quantity': flip_qty, 'price': None})
                logger.debug("Trend reversal: switching from short to long (MA cross up)")
        
        for order in signals:
            fill_price = price  # assume market order fills at current price
            self.on_trade(fill_price, order['quantity'], order['side'], timestamp)
    
    def on_trade(self, price: float, quantity: int, side: str, timestamp: datetime) -> None:
        """Update position and P&L on trade execution."""
        self._update_position_on_fill(price, quantity, side)
        logger.info("%s: Trade executed - %s %d @ %.2f", self.__class__.__name__, side, quantity, price)
    
    def generate_signal(self, market_data: Dict[str, Any]) -> list:
        """
        Generate trading signal(s) based on moving average crossover logic.
        
        Returns:
            list: An empty list, as this strategy executes trades in on_tick.
        """
        return []
    
    def flatten(self) -> None:
        """Close any open position by market order."""
        if self.position != 0:
            if self.last_price is not None:
                exit_price = self.last_price
                if self.position > 0:
                    self.realized_pnl += (exit_price - self.avg_entry_price) * self.position
                else:
                    self.realized_pnl += (self.avg_entry_price - exit_price) * abs(self.position)
                logger.info("%s: Flattening position at %.2f", self.__class__.__name__, exit_price)
            else:
                logger.warning("%s: Flatten called with no market price.", self.__class__.__name__)
            self.position = 0
            self.avg_entry_price = None
