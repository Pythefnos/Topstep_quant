# topstep_quant/__init__.py
"""
TopstepQuant trading bot package.
This package provides trading strategy classes for use in the Topstep funded trading environment.
"""
# Expose core interfaces at package level
from .strategies import StrategyBase
from .strategies import MicrostructureMarketMakingStrategy, IntradayMeanReversionStrategy, TrendFollowingStrategy, TailHedgeStrategy

__all__ = [
    "StrategyBase",
    "MicrostructureMarketMakingStrategy",
    "IntradayMeanReversionStrategy",
    "TrendFollowingStrategy",
    "TailHedgeStrategy"
]
