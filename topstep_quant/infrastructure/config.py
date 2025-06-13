"""Configuration for Topstep Quant trading system.

Defines risk parameters and session timing. The default values correspond to a Topstep
50K Combine account: daily loss limit $1,000 and trailing drawdown $2,000.
Session times default to closing positions by 3:55 PM CT and resuming trading at 5:00 PM CT.
"""
from dataclasses import dataclass, field
from datetime import time
from zoneinfo import ZoneInfo
from typing import Optional, Dict

# Define the trading timezone (Central Time)
TRADING_TIMEZONE = ZoneInfo("America/Chicago")

@dataclass
class TradingConfig:
    """Holds configuration parameters for trading, including risk limits and broker settings."""
    daily_loss_limit: float = 1000.0  # Hard daily loss limit in USD (max loss per day)
    trailing_drawdown: float = 2000.0  # Trailing max drawdown in USD (from initial balance)
    initial_balance: float = 50000.0  # Initial account balance (for dummy or if needed for reference)
    flatten_time: time = field(default_factory=lambda: time(15, 55, tzinfo=TRADING_TIMEZONE))  # Daily auto-flatten time (CT)
    session_start: time = field(default_factory=lambda: time(17, 0, tzinfo=TRADING_TIMEZONE))  # Trading session start time (CT, usually 5:00 PM)
    broker_type: str = "dummy"  # Which broker backend to use: "tradovate", "rithmic", or "dummy"
    # Optional broker credentials and settings
    tradovate_username: Optional[str] = None
    tradovate_password: Optional[str] = None
    tradovate_api_key: Optional[str] = None  # API key or client ID for Tradovate
    tradovate_demo: bool = True  # Use Tradovate demo environment by default
    rithmic_username: Optional[str] = None
    rithmic_password: Optional[str] = None
    rithmic_server: Optional[str] = None  # e.g., "demo" or specific server name
    extra_settings: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize configuration after initialization."""
        # Validate times have timezone for consistency
        if self.flatten_time.tzinfo is None:
            self.flatten_time = self.flatten_time.replace(tzinfo=TRADING_TIMEZONE)
        if self.session_start.tzinfo is None:
            self.session_start = self.session_start.replace(tzinfo=TRADING_TIMEZONE)