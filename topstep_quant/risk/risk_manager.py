# topstep_quant/risk/risk_manager.py
"""Risk management logic for TopstepQuant trading bot.

This module defines the RiskManager class, which monitors account P&L 
and enforces Topstep risk rules such as the daily loss limit and 
trailing drawdown (Maximum Loss Limit). It interacts with the coordinator 
and broker layers by receiving account updates (balance and P&L) from 
the broker and triggering the kill switch (through KillSwitch) to halt 
trading via the coordinator when a risk limit is breached.

The RiskManager is designed to be composable and testable:
- It does not directly call broker functions to liquidate positions; 
  instead, it signals the coordinator (via exceptions or flags) to take action.
- Logging is used to provide hooks for Slack alerts or Prometheus metrics 
  (e.g., when the kill switch triggers).
- All logic is encapsulated in this class, with clear interfaces for updating 
  P&L and resetting daily limits.
"""
import logging
from typing import Optional
from .kill_switch import KillSwitch, RiskViolationError

logger = logging.getLogger(__name__)

class RiskManager:
    """
    RiskManager enforces daily loss limits and trailing drawdown limits for a trading account.
    
    Attributes:
        initial_balance (float): The starting account balance (e.g., $50,000).
        daily_loss_limit (float): Max loss allowed in a single day (e.g., $1,000).
        trailing_drawdown (float): Trailing drawdown amount (e.g., $2,000).
        kill_switch (KillSwitch): The kill switch triggered when limits are breached.
        
    The RiskManager tracks both realized and unrealized P&L to determine the current 
    account equity (balance plus unrealized gains/losses). It uses this to check:
    - Daily Loss Limit: If current equity drops more than `daily_loss_limit` below the 
      day's starting balance, trading is halted for the day.
    - Trailing Drawdown (Maximum Loss Limit): If current equity falls below the minimum 
      account balance allowed (which starts at `initial_balance - trailing_drawdown` and 
      trails upward with profits), trading is halted and the account may be closed.
    
    This class should be integrated with the trading coordinator:
    - Call `start_new_day()` at the beginning of each trading day to reset daily loss tracking.
    - Call `check_limits()` after each trade or price update with current account values.
      If a limit is exceeded, `check_limits` will trigger the kill switch (and raise an error 
      to halt execution) so the coordinator can stop placing orders and instruct the broker to 
      flatten positions.
    """
    def __init__(self, 
                 initial_balance: float = 50_000.0,
                 daily_loss_limit: float = 1_000.0,
                 trailing_drawdown: float = 2_000.0,
                 kill_switch: Optional[KillSwitch] = None) -> None:
        """
        Initialize the RiskManager with account parameters.
        
        Args:
            initial_balance: Starting account balance for the account (default $50,000).
            daily_loss_limit: Maximum allowed loss in one day (default $1,000).
            trailing_drawdown: Trailing max drawdown value (default $2,000).
            kill_switch: An optional KillSwitch instance to use. If None, a new KillSwitch is created.
        """
        self._initial_balance: float = initial_balance
        self._daily_loss_limit: float = daily_loss_limit
        self._trailing_drawdown: float = trailing_drawdown
        
        # Highest account balance achieved (updated at end of day on new highs).
        self._high_balance: float = initial_balance
        # Minimum account equity allowed (trailing threshold). 
        # Starts at initial_balance - trailing_drawdown.
        self._trailing_threshold: float = initial_balance - trailing_drawdown
        # Starting balance of the current day (to measure daily P&L).
        self._start_of_day_balance: float = initial_balance
        
        # If a KillSwitch is not provided, create one.
        self.kill_switch: KillSwitch = kill_switch if kill_switch is not None else KillSwitch()
        
        # Log the initialization for audit purposes.
        logger.info(f"Initialized RiskManager: initial_balance=${initial_balance:.2f}, "
                    f"daily_loss_limit=${daily_loss_limit:.2f}, trailing_drawdown=${trailing_drawdown:.2f}. "
                    f"Initial trailing threshold=${self._trailing_threshold:.2f}.")
    
    def start_new_day(self, current_balance: float) -> None:
        """
        Reset daily loss tracking at the start of a new trading day.
        
        This should be called by the coordinator when a new trading session begins (e.g., 5 PM CT).
        It sets the start-of-day balance for calculating intraday P&L and allows trading if the 
        previous day ended with only a Daily Loss Limit trigger.
        
        Args:
            current_balance: The account balance at the start of the new day (usually the last closing balance).
        """
        # If the kill switch was triggered only due to daily loss (and not trailing drawdown), 
        # it can be reset to allow trading in the new day. In practice, trailing drawdown breaches 
        # in a funded account usually mean the account is closed.
        if self.kill_switch.triggered:
            if self.kill_switch.reason and "Daily Loss Limit" in self.kill_switch.reason:
                logger.info("Resetting kill switch for new day (previously triggered by daily loss limit).")
                self.kill_switch.reset()
            else:
                # If kill switch was triggered by trailing drawdown or another critical reason, do not auto-reset.
                logger.warning("Kill switch remains active (likely trailing drawdown hit) - cannot auto-reset for new day.")
        
        self._start_of_day_balance = current_balance
        logger.info(f"New trading day started. Start-of-day balance set to ${current_balance:.2f}. "
                    "Daily loss tracking has been reset.")
    
    def end_of_day(self, closing_balance: float) -> None:
        """
        Update the trailing drawdown threshold at the end of the trading day.
        
        This should be called by the coordinator after the trading session ends (e.g., 3:10 PM CT).
        If the account balance at end-of-day is a new high, the trailing drawdown threshold 
        (Maximum Loss Limit) will be raised accordingly. The threshold never decreases from losses; 
        it either stays the same or moves up when a new profit high is reached.
        
        Args:
            closing_balance: The account balance at the end of the trading day (realized P&L closed for the day).
        """
        if closing_balance > self._high_balance:
            # New all-time high achieved for account balance.
            self._high_balance = closing_balance
            # Calculate new trailing threshold: high_balance minus trailing_drawdown, capped at initial balance.
            if self._high_balance - self._initial_balance >= self._trailing_drawdown:
                # Once profit >= trailing_drawdown, threshold is fixed at the initial balance.
                self._trailing_threshold = self._initial_balance
            else:
                # Otherwise, trailing threshold rises with the new high.
                self._trailing_threshold = self._high_balance - self._trailing_drawdown
            logger.info(f"End of day: new high balance ${self._high_balance:.2f} reached. "
                        f"Trailing threshold raised to ${self._trailing_threshold:.2f}.")
        else:
            logger.debug(f"End of day: closing balance ${closing_balance:.2f} did not exceed prior high "
                         f"${self._high_balance:.2f}. Trailing threshold remains ${self._trailing_threshold:.2f}.")
    
    def check_limits(self, current_balance: float, current_unrealized_pnl: float) -> None:
        """
        Check current P&L against risk limits and trigger the kill switch if any limit is breached.
        
        This method should be called frequently (e.g., after each trade execution or significant price update) 
        with up-to-date account balance and unrealized P&L.
        
        Args:
            current_balance: The current account balance (realized gains/losses accounted for).
            current_unrealized_pnl: The current unrealized P&L from open positions.
        
        Raises:
            RiskViolationError: If the daily loss limit or trailing drawdown limit is breached.
        """
        # Compute current equity including unrealized P&L.
        current_equity: float = current_balance + current_unrealized_pnl
        
        # Calculate loss relative to start of day.
        daily_drawdown: float = self._start_of_day_balance - current_equity  # positive if there's a loss
        # Check Daily Loss Limit breach.
        if daily_drawdown >= self._daily_loss_limit:
            reason_details = (f"Daily Loss Limit breached: Drawdown ${daily_drawdown:.2f} "
                              f"exceeds daily limit ${self._daily_loss_limit:.2f}. "
                              f"Start-of-day balance ${self._start_of_day_balance:.2f}, "
                              f"current equity ${current_equity:.2f}.")
            logger.error(reason_details)
            # Trigger the kill switch to halt trading for the rest of the day.
            self.kill_switch.activate(reason="Daily Loss Limit breached")
            # The RiskViolationError exception will be raised by activate(), halting execution.
            return
        
        # Check Trailing Drawdown (Maximum Loss Limit) breach.
        if current_equity <= self._trailing_threshold:
            reason_details = (f"Trailing Drawdown Limit breached: Equity ${current_equity:.2f} "
                              f"is at/below allowed minimum ${self._trailing_threshold:.2f}. "
                              f"High balance ${self._high_balance:.2f}, initial ${self._initial_balance:.2f}, "
                              f"trailing drawdown ${self._trailing_drawdown:.2f}.")
            logger.error(reason_details)
            # Trigger the kill switch. In a funded account, this likely means account closure.
            self.kill_switch.activate(reason="Trailing Drawdown Limit breached")
            return
        
        # If we reach here, no limits were violated.
        logger.debug(f"Risk check OK. Equity=${current_equity:.2f}, daily_drawdown=${daily_drawdown:.2f}, "
                     f"trailing_threshold=${self._trailing_threshold:.2f}.")
    
    @property
    def trailing_threshold(self) -> float:
        """
        Get the current trailing drawdown threshold (minimum allowed equity).
        """
        return self._trailing_threshold
