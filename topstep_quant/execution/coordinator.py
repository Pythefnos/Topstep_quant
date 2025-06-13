"""Execution Coordinator for trade signals and broker execution.

The ExecutionCoordinator class interfaces between strategy signals and the broker,
ensuring that all trades comply with Topstep risk constraints. It enforces a hard
daily loss limit (e.g. $1,000 for a 50K account):contentReference[oaicite:0]{index=0} and a trailing drawdown
limit ($2,000 on a 50K account):contentReference[oaicite:1]{index=1}. If the daily loss limit is reached or exceeded,
the coordinator triggers a 'kill switch' – flattening all positions and blocking new trades
for the rest of the day:contentReference[oaicite:2]{index=2}. Similarly, if the account equity falls below the trailing
drawdown threshold, all positions are liquidated immediately and trading is halted (rule broken):contentReference[oaicite:3]{index=3}.
The coordinator also respects session boundaries: all positions are automatically flattened
at the end of the trading session (e.g., 3:55 PM CT) to avoid holding positions into the close:contentReference[oaicite:4]{index=4}.

This design promotes safe, intelligent, and autonomous trading of CME micro futures with
high probability of profit and zero rule violations, by strictly adhering to risk limits.
"""

import logging
from datetime import datetime, time
from typing import Optional

from topstep_quant.infrastructure.broker import Broker, Position
from topstep_quant.infrastructure.config import TradingConfig, TRADING_TIMEZONE

class ExecutionCoordinator:
    """Coordinates strategy trade signals with broker execution and risk management.

    The coordinator uses a Broker abstraction to send orders and manage positions.
    It monitors the account's profit/loss and time to enforce Topstep's rules:
    - Daily loss limit: if net P&L in a session reaches the negative limit (e.g. -$1,000),
      all positions are flattened and trading is halted until the next session:contentReference[oaicite:5]{index=5}.
    - Trailing max drawdown: if account equity drops below the trailing threshold (initial balance minus $2,000,
      trailing upward with profits), all trading stops and the account is effectively closed:contentReference[oaicite:6]{index=6}.
    - Session cutoff: ensures no positions are held past the end of day; auto-flattens all positions at the cutoff time:contentReference[oaicite:7]{index=7}.

    The coordinator should be used by feeding it strategy signals (orders) and periodically calling `monitor()`
    to update risk status (especially if market prices move). Strong logging and exceptions are used to alert
    when risk limits are breached.
    """
    def __init__(self, broker: Broker, config: TradingConfig):
        """
        Initialize the ExecutionCoordinator with a broker and configuration.

        :param broker: The Broker instance (Tradovate, Rithmic, or Dummy) through which orders will be placed.
        :param config: Trading configuration parameters including risk limits and session times.
        """
        self.broker: Broker = broker
        self.config: TradingConfig = config
        # Risk parameters
        self.daily_loss_limit: float = config.daily_loss_limit  # e.g. 1000.0 (positive value)
        self.trailing_drawdown: float = config.trailing_drawdown  # e.g. 2000.0
        self.flatten_time: time = config.flatten_time  # end of trading session (with timezone info)
        self.session_start: time = config.session_start  # start of trading session
        # Internal state
        self.initial_balance: Optional[float] = None
        self.max_balance_seen: Optional[float] = None
        self.trailing_threshold: Optional[float] = None
        self.day_start_balance: Optional[float] = None
        self.daily_locked: bool = False  # whether trading is locked for the rest of day due to daily loss
        self.account_closed: bool = False  # whether account is closed (trailing drawdown breached)
        # Logging setup
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        # Note: Broker connection is not initiated here. Call start_new_session() to connect and initialize session.

    def start_new_session(self) -> None:
        """Start a new trading session (typically at 5:00 PM CT, the next trading day).

        This resets the daily loss tracking and allows trading if the account is not closed.
        It should be called at the beginning of each trading day (after the previous session ended),
        to re-enable trading if it was locked due to a daily loss limit breach.
        """
        if self.account_closed:
            raise RuntimeError("Cannot start new session: account closed due to trailing drawdown breach.")
        # Connect to broker if not already connected
        if hasattr(self.broker, "is_connected"):
            if not getattr(self.broker, "is_connected")():
                self.broker.connect()
        else:
            # If broker has no is_connected, attempt connect anyway
            try:
                self.broker.connect()
            except Exception as e:
                self.logger.error("Broker connection failed: %s", e)
                raise
        # Fetch current account balance as session start balance
        start_balance = self.broker.get_account_balance()
        if start_balance is None:
            start_balance = 0.0
        self.day_start_balance = start_balance
        if self.initial_balance is None:
            # First session initialization
            self.initial_balance = start_balance
            self.max_balance_seen = start_balance
            # Set initial trailing threshold
            self.trailing_threshold = start_balance - self.trailing_drawdown
            # Ensure trailing threshold never goes above initial balance
            if self.trailing_threshold is None or self.trailing_threshold > self.initial_balance:
                self.trailing_threshold = self.initial_balance
        # Reset daily lock for new day
        self.daily_locked = False
        self.logger.info("New trading session started. Day start balance: $%.2f", self.day_start_balance)

    def end_session(self) -> None:
        """End the current trading session by flattening all positions and updating trailing drawdown.

        This should be called at the session cutoff (e.g., 3:55 PM CT) to close positions and update the trailing drawdown threshold.
        After calling end_session, no further trading is allowed until start_new_session() is called for the next day.
        """
        # Flatten all positions at session end (if any)
        try:
            self.broker.flatten_all()
        except Exception as e:
            self.logger.error("Error flattening positions at session end: %s", e)
        # Calculate end-of-day balance and update trailing drawdown if a new peak was achieved
        end_balance = self.broker.get_account_balance()
        if end_balance is None:
            end_balance = 0.0
        # Update max balance and trailing threshold if we achieved a new high
        if self.max_balance_seen is None:
            self.max_balance_seen = end_balance
        if end_balance > self.max_balance_seen:
            self.max_balance_seen = end_balance
            # New trailing threshold = max_balance_seen - trailing_drawdown (capped at initial balance)
            new_threshold = self.max_balance_seen - self.trailing_drawdown
            if self.initial_balance is not None and new_threshold >= self.initial_balance:
                # Once trailing threshold reaches initial balance, it stays there:contentReference[oaicite:8]{index=8}
                new_threshold = self.initial_balance
            # Only raise the threshold (never lower it on losses)
            if self.trailing_threshold is not None:
                self.trailing_threshold = max(self.trailing_threshold, new_threshold)
            else:
                self.trailing_threshold = new_threshold
        # Lock trading until next session
        self.daily_locked = True
        self.logger.info("Trading session ended. End-of-day balance: $%.2f. Trailing threshold: $%.2f",
                         end_balance, self.trailing_threshold or 0.0)

    def is_trading_allowed(self) -> bool:
        """Check if trading is currently allowed (within session hours and not locked by risk limits)."""
        if self.account_closed:
            return False
        # Check session time window
        now = datetime.now(tz=TRADING_TIMEZONE)
        current_time = now.time()
        # Session might span overnight (e.g., 5:00 PM to next day 3:55 PM)
        if self.session_start < self.flatten_time:
            # Session does not wrap midnight
            in_session_hours = self.session_start <= current_time < self.flatten_time
        else:
            # Session wraps to next day
            in_session_hours = (current_time >= self.session_start) or (current_time < self.flatten_time)
        if not in_session_hours:
            return False
        # Check daily lock
        if self.daily_locked:
            # Past daily loss limit triggered – locked until next session:contentReference[oaicite:9]{index=9}
            return False
        return True

    def execute_order(self, instrument: str, side: str, quantity: int, order_type: str = "MARKET",
                      price: Optional[float] = None, stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None) -> Optional[str]:
        """Execute a trade signal by placing an order through the broker, after checking all risk constraints.

        :param instrument: The symbol of the instrument (e.g., "MES", "MNQ").
        :param side: "BUY" or "SELL" indicating the trade direction.
        :param quantity: Number of contracts to trade.
        :param order_type: Order type, e.g., "MARKET" or "LIMIT".
        :param price: The price for limit orders (or optional execution price for dummy market orders).
        :param stop_loss: Optional stop-loss price for risk management (if supported).
        :param take_profit: Optional take-profit price (if supported).
        :return: An order ID if the broker provides one, otherwise None.
        :raises RuntimeError: if trading is not allowed or account is closed.
        """
        # Ensure a trading session is active
        if self.day_start_balance is None:
            raise RuntimeError("Trading session not started. Call start_new_session() first.")
        # Check if trading is currently allowed
        if not self.is_trading_allowed():
            if self.account_closed:
                raise RuntimeError("Trading blocked: account closed due to trailing drawdown violation.")
            elif self.daily_locked:
                raise RuntimeError("Trading blocked: daily loss limit reached, wait until next session.")
            else:
                raise RuntimeError("Trading not allowed at this time (outside session hours).")
        # Place order via broker
        try:
            order_id = self.broker.place_order(instrument, quantity, order_type, side, price, stop_loss, take_profit)
        except Exception as e:
            self.logger.error("Order placement failed: %s", e)
            raise
        # After placing the order, immediately check risk (especially if a market order filled and P/L updated)
        self._check_risk()
        return order_id

    def _check_risk(self) -> None:
        """Internal: evaluate current P&L against risk limits and take action if needed."""
        if self.day_start_balance is None or self.trailing_threshold is None:
            # Session not started or thresholds not set, skip risk check
            return
        # Get current equity (balance + unrealized P&L)
        current_equity = self.broker.get_account_equity()
        if current_equity is None:
            current_equity = self.broker.get_account_balance() or 0.0
        # Calculate net P&L for the day
        net_pl = current_equity - self.day_start_balance
        # Check daily loss limit breach (including unrealized):contentReference[oaicite:10]{index=10}
        if net_pl <= -self.daily_loss_limit and not self.daily_locked:
            # Daily loss limit hit or exceeded
            self.logger.warning("Daily Loss Limit reached (Net P&L %.2f). Flattening all positions!:contentReference[oaicite:11]{index=11}", net_pl)
            try:
                self.broker.flatten_all()
            except Exception as e:
                self.logger.error("Error flattening positions on daily loss limit: %s", e)
            # Lock trading for rest of day
            self.daily_locked = True
        # Check trailing drawdown breach:contentReference[oaicite:12]{index=12}
        if self.trailing_threshold is not None:
            # Trailing threshold is an absolute account value that should not be fallen below
            if current_equity < self.trailing_threshold and not self.account_closed:
                self.logger.error("Trailing drawdown breached! Current equity $%.2f below threshold $%.2f:contentReference[oaicite:13]{index=13}.",
                                  current_equity, self.trailing_threshold)
                try:
                    self.broker.flatten_all()
                except Exception as e:
                    self.logger.error("Error flattening positions on trailing drawdown breach: %s", e)
                # Permanently close account for trading (cannot continue without reset)
                self.account_closed = True
                self.daily_locked = True

    def monitor(self) -> None:
        """Monitor the trading state; flatten positions and lock trading if risk or time limits are reached.

        This method should be called periodically (e.g., every few seconds or on price updates) to enforce:
         - End-of-session flatten: if current time is at or past the configured flatten_time.
         - Daily loss or trailing drawdown breaches: triggers kill switch if necessary.
        """
        # Check time for session boundary
        now = datetime.now(tz=TRADING_TIMEZONE)
        current_time = now.time()
        if (self.session_start < self.flatten_time and current_time >= self.flatten_time) or \
           (self.session_start > self.flatten_time and current_time >= self.flatten_time and current_time < self.session_start):
            # Time is at or beyond session end
            if not self.daily_locked:
                # Only call end_session once per day (if not already locked by risk)
                self.logger.info("Session end time reached (%s). Auto-flattening positions.:contentReference[oaicite:14]{index=14}", self.flatten_time)
                self.end_session()
        # Always check risk limits
        self._check_risk()
