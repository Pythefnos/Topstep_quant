"""Main bot module for TopstepQuant trading system.

This module provides the main entry point and coordination logic for the trading bot.
It initializes all components (strategies, risk management, broker) and runs the main trading loop.
"""

import logging
import signal
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from topstep_quant.execution.coordinator import ExecutionCoordinator
from topstep_quant.infrastructure.broker import Broker
from topstep_quant.infrastructure.config import TradingConfig, TRADING_TIMEZONE
from topstep_quant.infrastructure.dummy_broker import DummyBroker
from topstep_quant.infrastructure.tradovate_api import TradovateAPI
from topstep_quant.infrastructure.rithmic_api import RithmicAPI
from topstep_quant.monitoring.logger import configure_logger, get_logger
from topstep_quant.monitoring.alerts import SlackAlerter
from topstep_quant.risk.risk_manager import RiskManager
from topstep_quant.risk.kill_switch import KillSwitch, RiskViolationError
from topstep_quant.strategies.microstructure_mm import MicrostructureMarketMakingStrategy
from topstep_quant.strategies.intraday_mean_revert import IntradayMeanReversionStrategy
from topstep_quant.strategies.trend_follow import TrendFollowingStrategy
from topstep_quant.strategies.tail_hedge import TailHedgeStrategy


class TradingBot:
    """Main trading bot coordinator that manages all strategies and risk controls."""
    
    def __init__(self, config: TradingConfig) -> None:
        """Initialize the trading bot with configuration."""
        self.config = config
        self.logger = get_logger("TradingBot")
        self.running = False
        
        # Initialize components
        self.broker = self._create_broker()
        self.kill_switch = KillSwitch()
        self.risk_manager = RiskManager(
            initial_balance=config.initial_balance,
            daily_loss_limit=config.daily_loss_limit,
            trailing_drawdown=config.trailing_drawdown,
            kill_switch=self.kill_switch
        )
        self.execution_coordinator = ExecutionCoordinator(self.broker, config)
        
        # Initialize strategies
        self.strategies = self._create_strategies()
        
        # Optional alerting
        self.alerter: Optional[SlackAlerter] = None
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _create_broker(self) -> Broker:
        """Create and return the appropriate broker instance based on configuration."""
        broker_type = self.config.broker_type.lower()
        
        if broker_type == "dummy":
            return DummyBroker(self.config.initial_balance)
        elif broker_type == "tradovate":
            if not all([self.config.tradovate_username, self.config.tradovate_password, self.config.tradovate_api_key]):
                raise ValueError("Tradovate credentials not provided in configuration")
            return TradovateAPI(
                username=self.config.tradovate_username,
                password=self.config.tradovate_password,
                api_key=self.config.tradovate_api_key,
                demo=self.config.tradovate_demo
            )
        elif broker_type == "rithmic":
            if not all([self.config.rithmic_username, self.config.rithmic_password]):
                raise ValueError("Rithmic credentials not provided in configuration")
            return RithmicAPI(
                username=self.config.rithmic_username,
                password=self.config.rithmic_password,
                server=self.config.rithmic_server or "demo"
            )
        else:
            raise ValueError(f"Unknown broker type: {broker_type}")
    
    def _create_strategies(self) -> List[Any]:
        """Create and return strategy instances."""
        strategies = []
        
        # Create strategy instances for micro futures
        instruments = ["MES", "MNQ", "MYM"]  # Micro E-mini futures
        
        for instrument in instruments:
            # Market making strategy
            mm_strategy = MicrostructureMarketMakingStrategy(
                instrument=instrument,
                max_daily_loss=self.config.daily_loss_limit / 4,  # Split risk across strategies
                flatten_time=self.config.flatten_time.time()
            )
            strategies.append(mm_strategy)
            
            # Mean reversion strategy
            mr_strategy = IntradayMeanReversionStrategy(
                instrument=instrument,
                max_daily_loss=self.config.daily_loss_limit / 4,
                flatten_time=self.config.flatten_time.time()
            )
            strategies.append(mr_strategy)
            
            # Trend following strategy
            tf_strategy = TrendFollowingStrategy(
                instrument=instrument,
                max_daily_loss=self.config.daily_loss_limit / 4,
                flatten_time=self.config.flatten_time.time()
            )
            strategies.append(tf_strategy)
            
            # Tail hedge strategy
            th_strategy = TailHedgeStrategy(
                instrument=instrument,
                max_daily_loss=self.config.daily_loss_limit / 4,
                flatten_time=self.config.flatten_time.time()
            )
            strategies.append(th_strategy)
        
        return strategies
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    def start(self) -> None:
        """Start the trading bot."""
        self.logger.info("Starting TopstepQuant trading bot...")
        
        try:
            # Start new trading session
            self.execution_coordinator.start_new_session()
            current_balance = self.broker.get_account_balance()
            self.risk_manager.start_new_day(current_balance)
            
            self.running = True
            self.logger.info("Trading bot started successfully")
            
            # Main trading loop
            self._run_trading_loop()
            
        except Exception as e:
            self.logger.error(f"Error starting trading bot: {e}")
            raise
    
    def _run_trading_loop(self) -> None:
        """Main trading loop."""
        while self.running:
            try:
                # Check if trading is allowed
                if not self.execution_coordinator.is_trading_allowed():
                    time.sleep(1)
                    continue
                
                # Monitor risk limits
                self.execution_coordinator.monitor()
                
                # Update risk manager with current account state
                current_balance = self.broker.get_account_balance()
                positions = self.broker.get_open_positions()
                unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
                
                self.risk_manager.check_limits(current_balance, unrealized_pnl)
                
                # Generate market data (simplified for demo)
                market_data = self._get_market_data()
                
                # Process strategies
                for strategy in self.strategies:
                    if strategy.active:
                        try:
                            strategy.on_tick(market_data)
                        except Exception as e:
                            self.logger.error(f"Error in strategy {strategy.__class__.__name__}: {e}")
                
                # Sleep briefly before next iteration
                time.sleep(0.1)
                
            except RiskViolationError as e:
                self.logger.critical(f"Risk violation detected: {e}")
                if self.alerter:
                    self.alerter.alert_kill_switch(str(e))
                break
            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in trading loop: {e}")
                time.sleep(1)
        
        self._shutdown()
    
    def _get_market_data(self) -> Dict[str, Any]:
        """Get current market data (simplified implementation)."""
        # In a real implementation, this would fetch live market data
        # For now, return dummy data
        return {
            'timestamp': datetime.now(TRADING_TIMEZONE),
            'bid': 4500.0,
            'ask': 4500.25,
            'last': 4500.125
        }
    
    def _shutdown(self) -> None:
        """Shutdown the trading bot gracefully."""
        self.logger.info("Shutting down trading bot...")
        
        try:
            # Flatten all positions
            self.broker.flatten_all()
            
            # End trading session
            current_balance = self.broker.get_account_balance()
            self.risk_manager.end_of_day(current_balance)
            self.execution_coordinator.end_session()
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        
        self.logger.info("Trading bot shutdown complete")


def main() -> None:
    """Main entry point for the trading bot."""
    # Configure logging
    logger = configure_logger("TopstepQuant", level="INFO")
    
    try:
        # Create default configuration
        config = TradingConfig()
        
        # Create and start the trading bot
        bot = TradingBot(config)
        bot.start()
        
    except Exception as e:
        logger.error(f"Failed to start trading bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()