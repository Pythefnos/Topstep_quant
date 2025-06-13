"""Dummy broker for simulation and testing.

This broker simulates trade execution without connecting to a real API. It maintains positions and account balance
locally, enforcing the same behavior (fills, P&L) to facilitate testing of strategies and risk management.
"""
import uuid
from dataclasses import dataclass
from typing import List, Dict, Optional
from topstep_quant.infrastructure.broker import Broker, Position

@dataclass
class DummyOrder:
    """Represents a pending (not yet filled) limit order in the DummyBroker."""
    order_id: str
    instrument: str
    quantity: int
    side: str  # "BUY" or "SELL"
    price: float  # target price for limit
    order_type: str = "LIMIT"

class DummyBroker(Broker):
    """In-memory simulation of a broker for testing."""
    def __init__(self, initial_balance: float = 50000.0):
        """
        Initialize the dummy broker with an initial account balance.
        :param initial_balance: Starting cash balance for the simulated account.
        """
        super().__init__()
        self._balance: float = initial_balance  # account cash balance (realized P&L added here)
        # Market prices for instruments (to determine fills and P&L)
        self.market_prices: Dict[str, float] = {}
        # Active positions per instrument
        self.positions: Dict[str, Position] = {}
        # Pending limit orders by ID
        self.pending_orders: Dict[str, DummyOrder] = {}
        self._connected = False

    def connect(self) -> None:
        """Connect the dummy broker (no-op)."""
        # No actual connection needed for dummy; just mark as connected.
        self._connected = True

    def get_account_balance(self) -> float:
        """Return current account balance (realized gains/losses)."""
        return self._balance

    def get_account_equity(self) -> float:
        """Return current account equity (balance plus unrealized P&L of open positions)."""
        equity = self._balance
        # Add unrealized P&L for all open positions
        for pos in self.positions.values():
            equity += pos.unrealized_pnl
        return equity

    def place_order(self, instrument: str, quantity: int, order_type: str, side: str,
                    price: Optional[float] = None, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> str:
        """Simulate placing an order. Market orders execute immediately; limit orders may be pending."""
        if not self._connected:
            raise ConnectionError("DummyBroker is not connected.")
        side = side.upper()
        order_type = order_type.upper()
        order_id = str(uuid.uuid4())
        # Determine fill for market orders or immediate limit orders
        if order_type == "MARKET":
            # Market order executes at current market price (or given price if provided)
            if price is not None:
                exec_price = price
            else:
                if instrument not in self.market_prices:
                    raise RuntimeError(f"No market price for {instrument}; cannot execute market order.")
                exec_price = self.market_prices[instrument]
            self._execute_fill(instrument, side, quantity, exec_price)
        elif order_type == "LIMIT":
            if price is None:
                raise ValueError("Limit order must have a price.")
            # Check if immediate fill conditions are met
            if instrument in self.market_prices:
                current_price = self.market_prices[instrument]
                if (side == "BUY" and current_price <= price) or (side == "SELL" and current_price >= price):
                    # Fill immediately at current market price (better or equal to limit)
                    self._execute_fill(instrument, side, quantity, current_price)
                else:
                    # Pending until price condition is met
                    order = DummyOrder(order_id, instrument, quantity, side, price, "LIMIT")
                    self.pending_orders[order_id] = order
            else:
                # No price data yet; place as pending until a price update occurs
                order = DummyOrder(order_id, instrument, quantity, side, price, "LIMIT")
                self.pending_orders[order_id] = order
        else:
            # Other order types (e.g., STOP) could be implemented similarly
            raise ValueError(f"Order type {order_type} not supported in DummyBroker.")
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending limit order."""
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]
            return True
        return False

    def get_open_positions(self) -> List[Position]:
        """Return a list of all current open positions."""
        return list(self.positions.values())

    def update_market_price(self, instrument: str, price: float) -> None:
        """
        Update the market price for an instrument. This will trigger fills for pending orders
        and update unrealized P&L for open positions.
        """
        self.market_prices[instrument] = price
        # Update unrealized P&L for existing position in this instrument
        if instrument in self.positions:
            pos = self.positions[instrument]
            pos.current_price = price
            if pos.quantity != 0:
                pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
            else:
                pos.unrealized_pnl = 0.0
        # Check pending limit orders for fills at this new price
        triggered_orders = []
        for oid, order in list(self.pending_orders.items()):
            if order.instrument != instrument:
                continue
            if (order.side == "BUY" and price <= order.price) or (order.side == "SELL" and price >= order.price):
                # Trigger fill at this price
                triggered_orders.append(order)
                del self.pending_orders[oid]
        # Execute all triggered orders at the current price
        for order in triggered_orders:
            self._execute_fill(order.instrument, order.side, order.quantity, price)

    def _execute_fill(self, instrument: str, side: str, quantity: int, price: float) -> None:
        """Internal: execute a trade fill, update positions and account balance."""
        # Normalize side to numeric direction
        direction = 1 if side.upper() == "BUY" else -1
        fill_qty = quantity * direction  # positive for buy (long), negative for sell (short)
        # Get current position (if any) for the instrument
        if instrument in self.positions:
            pos = self.positions[instrument]
        else:
            # If no position, create one
            pos = Position(instrument=instrument, quantity=0, entry_price=0.0, current_price=price, unrealized_pnl=0.0)
            self.positions[instrument] = pos
        prev_qty = pos.quantity
        new_qty = pos.quantity + fill_qty
        if pos.quantity == 0 or (pos.quantity > 0 and fill_qty > 0) or (pos.quantity < 0 and fill_qty < 0):
            # Same direction (or opening from zero) - adjust average entry price
            if pos.quantity == 0:
                # Opening a new position
                pos.entry_price = price
                pos.quantity = new_qty
            else:
                # Adding to existing position in same direction: recalc weighted avg entry price
                total_qty = abs(pos.quantity) + abs(quantity)
                if total_qty != 0:
                    # Weighted average price calculation
                    pos.entry_price = (pos.entry_price * abs(pos.quantity) + price * abs(quantity)) / total_qty
                pos.quantity = new_qty
        else:
            # Position exists in opposite direction, so this fill is closing/reducing or reversing
            if pos.quantity > 0 and fill_qty < 0:
                # Existing long, and this is a sell (closing long or reversing to short)
                if abs(fill_qty) < pos.quantity:
                    # Partial close of long position
                    closed_qty = abs(fill_qty)
                    # Realized P/L: (sell price - entry price) * closed_qty
                    pnl = (price - pos.entry_price) * closed_qty
                    self._balance += pnl
                    pos.quantity -= closed_qty
                    # Position remains long with same entry_price for remaining qty
                elif abs(fill_qty) == pos.quantity:
                    # Full close of long position
                    closed_qty = pos.quantity
                    pnl = (price - pos.entry_price) * closed_qty
                    self._balance += pnl
                    pos.quantity = 0
                else:
                    # More sold than current long: close all long and go short with excess
                    closed_qty = pos.quantity
                    pnl = (price - pos.entry_price) * closed_qty
                    self._balance += pnl
                    # Determine new short quantity
                    new_short_qty = abs(fill_qty) - closed_qty
                    pos.quantity = -new_short_qty
                    pos.entry_price = price  # new short entry price is fill price
            elif pos.quantity < 0 and fill_qty > 0:
                # Existing short, and this is a buy (closing short or reversing to long)
                if abs(fill_qty) < abs(pos.quantity):
                    # Partial close of short position
                    closed_qty = abs(fill_qty)
                    pnl = (pos.entry_price - price) * closed_qty
                    self._balance += pnl
                    pos.quantity += closed_qty  # quantity is negative, adding a positive closes part
                elif abs(fill_qty) == abs(pos.quantity):
                    # Full close of short position
                    closed_qty = abs(pos.quantity)
                    pnl = (pos.entry_price - price) * closed_qty
                    self._balance += pnl
                    pos.quantity = 0
                else:
                    # More bought than current short: close all short and open long with excess
                    closed_qty = abs(pos.quantity)
                    pnl = (pos.entry_price - price) * closed_qty
                    self._balance += pnl
                    new_long_qty = abs(fill_qty) - closed_qty
                    pos.quantity = new_long_qty
                    pos.entry_price = price  # new long entry at fill price
            # If position quantity became zero, remove the position entry
            if pos.quantity == 0:
                del self.positions[instrument]
                return
        # Update current price and unrealized P&L for the position (if still open)
        if instrument in self.positions:
            pos = self.positions[instrument]
            pos.current_price = price
            if pos.quantity != 0:
                pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
            else:
                pos.unrealized_pnl = 0.0
