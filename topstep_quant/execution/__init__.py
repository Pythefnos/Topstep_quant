"""Execution module for topstep_quant.

This package coordinates strategy signals with broker execution, enforcing
Topstep trading rules and risk management.
"""

from topstep_quant.execution.coordinator import ExecutionCoordinator

__all__ = ["ExecutionCoordinator"]
