"""Base strategy class for TopstepQuant trading strategies."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class StrategyBase(ABC):
    """
    Abstract base class for trading strategies in the TopstepQuant framework.
    Strategies define how to react to market data (ticks) and trade events.
    This class enforces the core interface that each strategy must implement.
    
    Attributes:
        instrument (str): The trading instrument (symbol) this strategy trades.
        max_daily_loss (float): Daily loss limit. If the net P&L falls below negative this value,
            the strategy should stop trading for the rest of the day (Topstep risk rule).
        flatten_time (time): Time of day (CT) to auto-flatten all positions (e.g., 15:55 CT).
        position (int): Current net position (positive for long, negative for short, 0 for flat).
        avg_entry_price (Optional[float]): Average entry price for the current position (None if flat).
        realized_pnl (float): Cumulative realized profit/loss for the current day.
        active (bool): Whether the strategy is currently active (will generate new trades). 
            Set to False after hitting risk limits or end of trading session.
        last_price (Optional[float]): Last seen market price (midpoint or last trade price).
    """
    def __init__(self, instrument: str, max_daily_loss: Optional[float] = None,
                 flatten_time: time = time(15, 55)) -> None:
        """
        Initialize the strategy with instrument and risk parameters.
        
        Args:
            instrument (str): Trading instrument symbol (should be a micro futures contract).
            max_daily_loss (float, optional): Max allowable loss for the day. If exceeded, strategy halts.
            flatten_time (datetime.time): Time of day to flatten all positions (Central Time).
        """
        self.instrument: str = instrument
        self.max_daily_loss: Optional[float] = max_daily_loss
        self.flatten_time: time = flatten_time
        self.position: int = 0
        self.avg_entry_price: Optional[float] = None
        self.realized_pnl: float = 0.0
        self.active: bool = True
        self.last_price: Optional[float] = None
        
        # Ensure instrument is a micro futures symbol if possible (Topstep constraint).
        if isinstance(instrument, str) and not instrument.startswith("M"):
            logger.warning("Instrument %s may not be a micro future (expected symbol starting with 'M').", instrument)
    
    @abstractmethod
    def on_tick(self, market_data: Dict[str, Any]) -> None:
        """
        Handle a new tick of market data. This method is called by the trading system for each tick update.
        Implement strategy-specific logic to possibly generate trading signals or modify orders.
        
        Args:
            market_data (dict): Latest market data containing keys such as 'bid', 'ask', 'last', 'timestamp', etc.
        """
        raise NotImplementedError("on_tick() must be implemented by Strategy subclasses.")
    
    @abstractmethod
    def on_trade(self, price: float, quantity: int, side: str, timestamp: datetime) -> None:
        """
        Handle a trade execution or fill event. This is called by the system when an order for this strategy is executed.
        The strategy should update its position and realized P&L here.
        
        Args:
            price (float): The fill price of the trade.
            quantity (int): The quantity filled. (Always positive; use side to infer direction.)
            side (str): 'BUY' for buy orders or 'SELL' for sell orders.
            timestamp (datetime): Timestamp when the trade occurred.
        """
        raise NotImplementedError("on_trade() must be implemented by Strategy subclasses.")
    
    @abstractmethod
    def generate_signal(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate trading signal(s) based on current market data.
        This could be in the form of target positions or specific orders to place.
        
        Returns:
            list: A list of trading signals or orders. Each signal could be represented as a dict 
                  (e.g., {'side': 'BUY', 'quantity': 1, 'price': None}) where 'price' is None for market orders.
                  An empty list or None indicates no action.
        """
        raise NotImplementedError("generate_signal() must be implemented by Strategy subclasses.")
    
    @abstractmethod
    def flatten(self) -> None:
        """
        Flatten (close out) any open positions immediately. This is typically called at the end of the trading session 
        (e.g., 15:55 CT) or when risk limits are breached. Implementations should send market orders to close positions 
        and cancel any pending orders.
        """
        raise NotImplementedError("flatten() must be implemented by Strategy subclasses.")
    
    def _update_market_state(self, market_data: Dict[str, Any]) -> None:
        """
        Update generic market state information such as the last price, for use in decision making and P&L calculation.
        """
        if 'last' in market_data and market_data['last'] is not None:
            self.last_price = float(market_data['last'])
        elif 'bid' in market_data and 'ask' in market_data:
            bid = float(market_data['bid'])
            ask = float(market_data['ask'])
            self.last_price = (bid + ask) / 2
    
    def _calculate_total_pnl(self) -> float:
        """
        Calculate the net P&L including unrealized gains/losses on open positions.
        
        Returns:
            float: The total P&L (realized + unrealized for current open position).
        """
        total_pnl = self.realized_pnl
        if self.position != 0 and self.avg_entry_price is not None and self.last_price is not None:
            if self.position > 0:
                total_pnl += (self.last_price - self.avg_entry_price) * self.position
            else:
                total_pnl += (self.avg_entry_price - self.last_price) * abs(self.position)
        return total_pnl
    
    def should_flatten(self, current_time: datetime) -> bool:
        """
        Check if it's time to auto-flatten positions based on the configured flatten_time.
        Returns True if current_time is at or beyond flatten_time (assuming current_time in CT).
        """
        if current_time.time() >= self.flatten_time:
            return True
        return False
    
    def check_risk_limit(self) -> bool:
        """
        Check if the strategy has exceeded its daily loss limit.
        If so, triggers flattening of position and deactivates further trading.
        
        Returns:
            bool: True if risk limit was exceeded and strategy was deactivated, False otherwise.
        """
        if self.max_daily_loss is None:
            return False
        total_pnl = self._calculate_total_pnl()
        if total_pnl <= -float(self.max_daily_loss):
            if self.position != 0:
                try:
                    self.flatten()
                except Exception as e:
                    logger.error("Error while flattening positions due to risk limit: %s", e)
            self.active = False
            logger.warning("%s: Daily loss limit reached. Stopping trading for the day.", self.__class__.__name__)
            return True
        return False
    
    def _update_position_on_fill(self, price: float, quantity: int, side: str) -> None:
        """Update position and realized P&L after a trade fill event."""
        # This helper should be called within on_trade implementations to handle position bookkeeping.
        side = side.upper()
        if side not in ('BUY', 'SELL'):
            logger.error("%s: Invalid trade side '%s' in on_trade", self.__class__.__name__, side)
            return
        fill_qty = quantity if side == 'BUY' else -quantity
        if self.position == 0:
            # Opening a new position
            self.position = fill_qty
            self.avg_entry_price = price
        elif self.position * fill_qty > 0:
            # Increasing an existing position (same direction)
            total_pos = self.position + fill_qty
            # Compute weighted average price for new position
            new_cost = (self.avg_entry_price * abs(self.position) + price * abs(fill_qty)) / abs(total_pos)
            self.position = total_pos
            self.avg_entry_price = new_cost
        else:
            # Reducing or closing an existing position
            if abs(fill_qty) < abs(self.position):
                # Partial close of position
                if self.position > 0:
                    # Existing long position, selling part of it
                    pnl = (price - self.avg_entry_price) * abs(fill_qty)
                else:
                    # Existing short position, buying part of it
                    pnl = (self.avg_entry_price - price) * abs(fill_qty)
                self.realized_pnl += pnl
                # Reduce the position by fill_qty (fill_qty is negative for sell, positive for buy)
                self.position += fill_qty
                # Position remains on the same side, avg_entry_price unchanged
            elif abs(fill_qty) == abs(self.position):
                # Closing the entire position
                if self.position > 0:
                    pnl = (price - self.avg_entry_price) * abs(self.position)
                else:
                    pnl = (self.avg_entry_price - price) * abs(self.position)
                self.realized_pnl += pnl
                self.position = 0
                self.avg_entry_price = None
            else:
                # Reversing position (over-closed into opposite direction)
                if self.position > 0:
                    pnl = (price - self.avg_entry_price) * abs(self.position)
                else:
                    pnl = (self.avg_entry_price - price) * abs(self.position)
                self.realized_pnl += pnl
                # Determine new position after reversal
                new_pos = self.position + fill_qty
                self.position = new_pos
                # Set new average entry price for the new position
                self.avg_entry_price = price