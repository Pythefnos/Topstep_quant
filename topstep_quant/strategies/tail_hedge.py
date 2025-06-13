# topstep_quant/strategies/tail_hedge.py
import logging
from typing import Dict, Any
from datetime import datetime
from .base import StrategyBase

logger = logging.getLogger(__name__)

class TailHedgeStrategy(StrategyBase):
    """
    A tail-risk hedging strategy.
    This strategy protects against rare, extreme market moves (tail events)
    by taking positions that profit from such moves.
    It typically stays out of the market or in a small position during normal conditions,
    and enters aggressive positions when large moves are detected.
    """
    def __init__(self, instrument: str, max_daily_loss: float = None, 
                 flatten_time: datetime.time = datetime.time(15, 55),
                 tail_threshold: float = 0.02):
        """
        Initialize the tail hedge strategy.
        
        Args:
            instrument (str): The futures contract symbol to trade.
            max_daily_loss (float, optional): Daily loss limit for risk management.
            flatten_time (datetime.time): Time of day to flatten all positions.
            tail_threshold (float): Percentage drop from intraday high to trigger a tail-risk hedge 
            (e.g., 0.02 for 2%).
        """
        super().__init__(instrument, max_daily_loss, flatten_time)
        self.tail_threshold = tail_threshold
        self.day_high: float = None
        self.current_day = None
    
    def on_tick(self, market_data: Dict[str, Any]) -> None:
        """Process a tick: monitor for tail events and adjust hedge position accordingly."""
        if not self.active:
            return
        self._update_market_state(market_data)
        timestamp = market_data.get('timestamp', datetime.now())
        
        if self.check_risk_limit():
            return
        if self.should_flatten(timestamp):
            self.flatten()
            return
        
        price = market_data.get('last')
        if price is None:
            bid = market_data.get('bid')
            ask = market_data.get('ask')
            if bid is not None and ask is not None:
                price = (bid + ask) / 2
        if price is None:
            return
        price = float(price)
        
        # Reset daily high at start of a new trading day
        day = timestamp.date()
        if self.current_day is None or day != self.current_day:
            self.current_day = day
            self.day_high = price
        
        # Update intraday high price
        if self.day_high is None or price > self.day_high:
            self.day_high = price
        
        signals = []
        # If no position, check for tail event trigger (price drop from high exceeds threshold)
        if self.position == 0:
            if self.day_high is not None and price < self.day_high * (1 - self.tail_threshold):
                # Significant drop detected: enter a short position to hedge tail risk
                signals.append({'side': 'SELL', 'quantity': 1, 'price': None})
                logger.debug("Tail hedge triggered: price %.2f dropped >%.1f%% from high %.2f, entering short", 
                             price, self.tail_threshold*100, self.day_high)
        elif self.position < 0:
            # Already in a short hedge position; exit if market recovers significantly
            if price >= self.day_high * (1 - self.tail_threshold/2):
                # Price recovered half the drop -> cover short
                signals.append({'side': 'BUY', 'quantity': abs(self.position), 'price': None})
                logger.debug("Tail hedge exit: price %.2f rebounded, covering short position", 
                             price)
        elif self.position > 0:
            # Tail hedge should not maintain long positions normally, flatten any longs
            signals.append({'side': 'SELL', 'quantity': abs(self.position), 'price': None})
            logger.warning("%s: Unexpected long position detected; flattening.", self.__class__.__name__)
        
        for order in signals:
            fill_price = price
            self.on_trade(fill_price, order['quantity'], order['side'], timestamp)
    
    def on_trade(self, price: float, quantity: int, side: str, timestamp: datetime) -> None:
        """Handle trade fill by updating position and realized P&L for tail hedge strategy."""
        self._update_position_on_fill(price, quantity, side)
        logger.info("%s: Trade executed - %s %d @ %.2f", self.__class__.__name__, side, quantity, price)
    
    def generate_signal(self, market_data: Dict[str, Any]) -> list:
        """
        Generate trading signals based on extreme move detection.
        
        Returns:
            list: An empty list, as signals are executed directly in on_tick.
        """
        return []
    
    def flatten(self) -> None:
        """Flatten any open hedge position immediately."""
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
