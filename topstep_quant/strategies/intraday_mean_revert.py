# topstep_quant/strategies/intraday_mean_revert.py
import logging
from typing import Deque, Dict, Any
from datetime import datetime
from collections import deque
from .base import StrategyBase

logger = logging.getLogger(__name__)

class IntradayMeanReversionStrategy(StrategyBase):
    """
    An intraday mean-reversion strategy.
    This strategy assumes that price extremes during the day will revert toward the mean.
    It monitors short-term price deviations and enters counter-trend positions expecting reversion.
    """
    def __init__(self, instrument: str, max_daily_loss: float = None, 
                 flatten_time: datetime.time = datetime.time(15, 55),
                 lookback: int = 50, threshold: float = 0.005):
        """
        Initialize the mean reversion strategy.
        
        Args:
            instrument (str): The futures contract symbol to trade.
            max_daily_loss (float, optional): Daily loss limit for risk management.
            flatten_time (datetime.time): Time of day to flatten all positions.
            lookback (int): Number of recent price points to consider for mean calculation.
            threshold (float): Fractional deviation from the mean (e.g., 0.005 for 0.5%) 
            to trigger a trade.
        """
        super().__init__(instrument, max_daily_loss, flatten_time)
        self.lookback = lookback
        self.prices: Deque[float] = deque(maxlen=lookback)
        self.threshold = threshold
    
    def on_tick(self, market_data: Dict[str, Any]) -> None:
        """Process a market tick: decide if a mean reversion trade should be made."""
        if not self.active:
            return
        # Update last price and other state
        self._update_market_state(market_data)
        timestamp = market_data.get('timestamp', datetime.now())
        
        # Risk management and session management
        if self.check_risk_limit():
            return
        if self.should_flatten(timestamp):
            self.flatten()
            return
        
        # Get current price (use last trade price or mid if available)
        price = market_data.get('last')
        if price is None:
            bid = market_data.get('bid')
            ask = market_data.get('ask')
            if bid is not None and ask is not None:
                price = (bid + ask) / 2
        if price is None:
            return
        price = float(price)
        
        # Update price history
        self.prices.append(price)
        if len(self.prices) < max(5, self.lookback // 5):
            # Not enough data points yet to establish a reliable mean
            return
        
        # Calculate intraday mean price
        avg_price = sum(self.prices) / len(self.prices)
        signals = []
        
        if self.position == 0:
            # No open position: look for reversion entry
            if price > avg_price * (1 + self.threshold):
                # Price above threshold -> sell expecting reversion down
                signals.append({'side': 'SELL', 'quantity': 1, 'price': None})
                logger.debug("Reversion signal: price %.2f above mean %.2f, SELL", price, avg_price)
            elif price < avg_price * (1 - self.threshold):
                # Price below threshold -> buy expecting reversion up
                signals.append({'side': 'BUY', 'quantity': 1, 'price': None})
                logger.debug("Reversion signal: price %.2f below mean %.2f, BUY", price, avg_price)
        elif self.position > 0:
            # Long position open: exit when price reverts up to or above mean
            if price >= avg_price:
                signals.append({'side': 'SELL', 'quantity': abs(self.position), 'price': None})
                logger.debug("Exiting long position as price %.2f reverted to mean %.2f", price, avg_price)
        elif self.position < 0:
            # Short position open: exit when price reverts down to or below mean
            if price <= avg_price:
                signals.append({'side': 'BUY', 'quantity': abs(self.position), 'price': None})
                logger.debug("Exiting short position as price %.2f reverted to mean %.2f", price, avg_price)
        
        # Execute market orders immediately
        for order in signals:
            fill_price = float(price)  # use current price as fill
            self.on_trade(fill_price, order['quantity'], order['side'], timestamp)
    
    def on_trade(self, price: float, quantity: int, side: str, timestamp: datetime) -> None:
        """Handle trade execution by updating position and P&L for mean reversion strategy."""
        self._update_position_on_fill(price, quantity, side)
        logger.info("%s: Executed %s %d @ %.2f", self.__class__.__name__, side, quantity, price)
    
    def generate_signal(self, market_data: Dict[str, Any]) -> list:
        """
        Generate signals based on price vs. mean. 
        (Not used in this strategy since trades are executed in on_tick.)
        
        Returns:
            list: An empty list (signals are generated and executed in on_tick).
        """
        return []
    
    def flatten(self) -> None:
        """Close any open position immediately."""
        if self.position != 0:
            if self.last_price is not None:
                exit_price = self.last_price
                if self.position > 0:
                    self.realized_pnl += (exit_price - self.avg_entry_price) * self.position
                else:
                    self.realized_pnl += (self.avg_entry_price - exit_price) * abs(self.position)
                logger.info("%s: Flattening position at %.2f", self.__class__.__name__, exit_price)
            else:
                logger.warning("%s: Flatten called with no price data.", self.__class__.__name__)
            self.position = 0
            self.avg_entry_price = None
