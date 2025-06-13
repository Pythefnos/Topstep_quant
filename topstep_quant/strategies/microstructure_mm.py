# topstep_quant/strategies/microstructure_mm.py
import logging
from typing import Dict, Any
from datetime import datetime
from .base import StrategyBase

logger = logging.getLogger(__name__)

class MicrostructureMarketMakingStrategy(StrategyBase):
    """
    A microstructure-based market making strategy.
    This strategy places passive buy and sell orders (quotes) around the current price 
    to capture the bid-ask spread.
    It manages a small inventory and attempts to profit from very short-term mean reversion in price (microstructure noise).
    """
    def __init__(self, instrument: str, max_daily_loss: float = None, 
                 flatten_time: datetime.time = datetime.time(15, 55),
                 min_spread: float = 0.25, order_size: int = 1, 
                 profit_target: float = None, stop_loss: float = None):
        """
        Initialize the market making strategy with specific parameters.
        
        Args:
            instrument (str): The micro futures symbol to trade.
            max_daily_loss (float, optional): Daily loss limit for risk management.
            flatten_time (datetime.time): Time of day to flatten all positions.
            min_spread (float): Minimum bid-ask spread (in price units) to engage in market making.
            order_size (int): Number of contracts for each quote order.
            profit_target (float, optional): Profit per contract to seek on each round trip. 
                Defaults to min_spread.
            stop_loss (float, optional): Stop loss per contract for adverse moves. 
                Defaults to 2 * profit_target.
        """
        super().__init__(instrument, max_daily_loss, flatten_time)
        self.min_spread = min_spread
        self.order_size = order_size
        self.profit_target = profit_target if profit_target is not None else min_spread
        self.stop_loss = stop_loss if stop_loss is not None else 2 * self.profit_target
        self.has_active_orders = False  # Whether there are currently quotes working in the market
    
    def on_tick(self, market_data: Dict[str, Any]) -> None:
        """Process a new tick: update quotes or manage inventory based on market data."""
        if not self.active:
            return  # Skip trading if strategy is inactive due to risk limits
        
        # Update market state (especially self.last_price) for use in decisions
        self._update_market_state(market_data)
        timestamp = market_data.get('timestamp', datetime.now())
        
        # Check risk limits and flatten if needed
        if self.check_risk_limit():
            return
        # Auto-flatten positions at end of session
        if self.should_flatten(timestamp):
            self.flatten()
            return
        
        # Determine current best bid and ask from market data
        bid = market_data.get('bid')
        ask = market_data.get('ask')
        if bid is None or ask is None:
            return  # If no bid/ask info, cannot place quotes
        
        spread = ask - bid
        signals = []  # orders or actions to take
        
        if self.position == 0:
            # No current position
            if not self.has_active_orders:
                # No orders currently working, so place new quotes if spread is sufficient
                if spread >= self.min_spread:
                    # Place passive buy at bid and sell at ask
                    signals.append({'side': 'BUY', 'quantity': self.order_size, 'price': bid})
                    signals.append({'side': 'SELL', 'quantity': self.order_size, 'price': ask})
                    self.has_active_orders = True
                    logger.debug("Placed initial quotes: BUY @ %.2f, SELL @ %.2f", bid, ask)
            else:
                # Orders are active but no fill yet;
                # update quotes if price moved or cancel if spread too low
                if spread < self.min_spread:
                    # Cancel working orders due to narrow spread
                    self.has_active_orders = False
                    logger.debug("Cancelled quotes due to low spread (%.2f)", spread)
                else:
                    # Update quote prices to the new best bid/ask
                    signals.append({'side': 'BUY', 'quantity': self.order_size, 'price': bid})
                    signals.append({'side': 'SELL', 'quantity': self.order_size, 'price': ask})
                    self.has_active_orders = True
                    logger.debug("Updated quotes to new bid/ask: BUY @ %.2f, SELL @ %.2f", bid, ask)
        else:
            # We have an open position; manage inventory
            if self.position > 0:
                # Long inventory: check for profit target or stop loss
                if bid - self.avg_entry_price >= self.profit_target:
                    # Take profit: sell at market (bid)
                    signals.append({'side': 'SELL', 'quantity': abs(self.position), 'price': None})
                    logger.debug("Taking profit on long position at bid %.2f", bid)
                elif self.avg_entry_price - bid >= self.stop_loss:
                    # Stop loss: sell at market to cut loss
                    signals.append({'side': 'SELL', 'quantity': abs(self.position), 'price': None})
                    logger.debug("Stopping out long position at bid %.2f", bid)
            elif self.position < 0:
                # Short inventory
                if self.avg_entry_price - ask >= self.profit_target:
                    # Take profit: buy to cover at market (ask)
                    signals.append({'side': 'BUY', 'quantity': abs(self.position), 'price': None})
                    logger.debug("Taking profit on short position at ask %.2f", ask)
                elif ask - self.avg_entry_price >= self.stop_loss:
                    # Stop loss: buy to cover to cut loss
                    signals.append({'side': 'BUY', 'quantity': abs(self.position), 'price': None})
                    logger.debug("Stopping out short position at ask %.2f", ask)
        
        # Execute market orders immediately and update state
        for order in signals:
            side = order['side']
            qty = order['quantity']
            price = order.get('price')
            if price is None:
                # Market order: assume fill at current last_price
                fill_price = self.last_price if self.last_price is not None else (ask if side == 'BUY' else bid)
                if fill_price is None:
                    fill_price = bid if side == 'BUY' else ask
                if fill_price is None:
                    continue  # cannot determine fill price
                self.on_trade(fill_price, qty, side, timestamp)
            else:
                # Limit order: placed in market (no immediate fill simulation here)
                pass
    
    def on_trade(self, price: float, quantity: int, side: str, timestamp: datetime) -> None:
        """Handle trade fills for this strategy (update position and P&L)."""
        # Update position and P&L using base helper
        self._update_position_on_fill(price, quantity, side)
        # If position was closed, mark that no active orders remain
        if self.position == 0:
            self.has_active_orders = False
        logger.info("%s: Trade executed - %s %d @ %.2f", self.__class__.__name__, side, quantity, price)
    
    def generate_signal(self, market_data: Dict[str, Any]) -> list:
        """
        Generate trading signals (order instructions) based on current market state.
        For market making, this method is not actively used because orders are updated continuously in on_tick.
        
        Returns:
            list: Returns an empty list as signals are handled in on_tick.
        """
        return []
    
    def flatten(self) -> None:
        """Flatten positions and cancel any pending quotes immediately."""
        # Cancel any working orders
        self.has_active_orders = False
        if self.position != 0:
            # Close open position at market using last_price
            if self.last_price is None:
                logger.warning("No market price available to flatten position.")
            else:
                exit_price = self.last_price
                if self.position > 0:
                    # Selling long position
                    self.realized_pnl += (exit_price - self.avg_entry_price) * self.position
                else:
                    # Covering short position
                    self.realized_pnl += (self.avg_entry_price - exit_price) * abs(self.position)
                logger.info("%s: Flattening position at %.2f", self.__class__.__name__, exit_price)
            self.position = 0
            self.avg_entry_price = None
