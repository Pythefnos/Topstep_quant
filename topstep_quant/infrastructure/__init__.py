"""Infrastructure module providing broker connectivity and configuration.

This package contains the abstract Broker interface and concrete implementations
for Tradovate, Rithmic, and a Dummy simulation broker, as well as configuration structures.
It allows the trading execution logic to be independent of the underlying brokerage API.
"""

from topstep_quant.infrastructure.broker import Broker, Position
from topstep_quant.infrastructure.config import TradingConfig
from topstep_quant.infrastructure.dummy_broker import DummyBroker
from topstep_quant.infrastructure.tradovate_api import TradovateAPI
from topstep_quant.infrastructure.rithmic_api import RithmicAPI

__all__ = ["Broker", "Position", "TradingConfig", "DummyBroker", "TradovateAPI", "RithmicAPI"]
