# topstep_quant/risk/kill_switch.py
"""Kill switch mechanism for TopstepQuant trading bot.

This module defines the KillSwitch class and the RiskViolationError exception.
The KillSwitch is triggered by the RiskManager when a risk limit is breached, 
and it signals the trading system to halt further trading. 

The coordinator should monitor the kill switch state or catch the RiskViolationError 
to perform necessary actions such as flattening positions via the broker and preventing new orders.
"""
import logging

logger = logging.getLogger(__name__)

class RiskViolationError(Exception):
    """Exception raised when a risk limit is violated, triggering the kill switch."""
    pass

class KillSwitch:
    """
    KillSwitch manages the state of a trading halt triggered by risk violations.
    
    Attributes:
        triggered (bool): True if the kill switch has been activated (trading is halted).
        reason (str): A short description of why the kill switch was activated.
    
    The KillSwitch is used in conjunction with RiskManager. When RiskManager 
    detects a rule breach, it calls `KillSwitch.activate()`, which:
    - Logs a critical alert (can be configured to notify, e.g., via Slack or monitoring systems).
    - Raises a RiskViolationError to break out of the normal trading flow.
    
    The trading coordinator or top-level system should catch RiskViolationError 
    to gracefully stop trading and initiate any cleanup (like cancelling orders and 
    closing positions through the broker).
    """
    def __init__(self) -> None:
        """Initialize the KillSwitch in a non-triggered (inactive) state."""
        self.triggered: bool = False
        self.reason: str = ""
    
    def activate(self, reason: str = "") -> None:
        """
        Activate the kill switch to halt trading immediately.
        
        This sets the kill switch state to triggered, logs a critical alert with the reason,
        and raises a RiskViolationError to interrupt the trading loop.
        
        Args:
            reason: A short description of the risk violation that caused the trigger.
        """
        self.triggered = True
        self.reason = reason if reason else "Risk limit breached"
        # Log the critical alert. In production, configure this logger to send alerts (Slack, etc.).
        logger.critical(f"KILL SWITCH ACTIVATED! Reason: {self.reason}")
        # Developer Note: Raising an exception to stop trading immediately.
        # Ensure the main coordinator catches this exception to handle shutdown gracefully.
        raise RiskViolationError(self.reason)
    
    def reset(self) -> None:
        """
        Reset the kill switch to allow trading again.
        
        This will clear the triggered state and reason. It should only be used when it is safe to 
        resume trading (e.g., at the start of a new day after a Daily Loss Limit trigger).
        Note: Trailing drawdown violations in a funded account usually mean the account is closed, 
        so the kill switch should not be reset in that case without administrative action.
        """
        if self.triggered:
            logger.info("KillSwitch reset. Trading may be resumed if allowed by rules.")
        self.triggered = False
        self.reason = ""
