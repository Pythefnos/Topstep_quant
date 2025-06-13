"""Abstract broker interface for trading execution.

Defines a Broker base class that outlines the required methods for any trading backend.
This abstraction allows the execution system to interact with Tradovate, Rithmic, or a dummy simulator uniformly.
The Broker should handle connecting to the trading platform, placing orders, and retrieving account info.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Position:
    """Represents an open position in an instrument."""
    instrument: str
    quantity: int  # positive for long, negative for short, 0 if flat
    entry_price: float  # average entry price of the position
    current_price: float  # current market price of the instrument
    unrealized_pnl: float  # unrealized P&L for this position

class Broker(ABC):
    """Abstract base class defining the interface for broker implementations."""
    def __init__(self):
        # Connection status flag
        self._connected: bool = False

    @abstractmethod
    def connect(self) -> None:
        """Connect to the broker's trading API (e.g., authenticate). Raises on failure."""
        raise NotImplementedError

    @abstractmethod
    def get_account_balance(self) -> float:
        """Return the current account balance (excluding unrealized P&L)."""
        raise NotImplementedError

    @abstractmethod
    def get_account_equity(self) -> float:
        """Return the current account equity (including unrealized P&L)."""
        raise NotImplementedError

    @abstractmethod
    def place_order(self, instrument: str, quantity: int, order_type: str, side: str,
                    price: Optional[float] = None, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> Optional[str]:
        """Place an order. Returns an order ID if available."""
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order by ID. Returns True if cancellation was successful."""
        raise NotImplementedError

    @abstractmethod
    def get_open_positions(self) -> List[Position]:
        """Retrieve a list of all current open positions."""
        raise NotImplementedError

    def flatten_all(self) -> None:
        """Flatten (close) all open positions by placing market orders offsetting each position."""
        positions = self.get_open_positions()
        for pos in positions:
            if pos.quantity == 0:
                continue
            # For each open position, send an opposite order to close it
            if pos.quantity > 0:
                # long position -> sell to close
                self.place_order(pos.instrument, pos.quantity, order_type="MARKET", side="SELL")
            elif pos.quantity < 0:
                # short position -> buy to close
                self.place_order(pos.instrument, abs(pos.quantity), order_type="MARKET", side="BUY")
        # After sending close orders, positions should be flattened.

    def is_connected(self) -> bool:
        """Return True if the broker is currently connected/authenticated."""
        return self._connected
