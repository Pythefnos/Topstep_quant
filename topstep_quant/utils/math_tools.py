"""
Mathematical tools and helper functions for calculations (moving averages, volatility, etc.).
"""
from math import sqrt
from typing import Sequence, Optional

def moving_average(values: Sequence[float]) -> float:
    """
    Compute the simple average of a sequence of numeric values.

    Returns:
        float: The mean of the input values. Returns 0.0 if the sequence is empty.
    """
    vals = list(values)
    if not vals:
        return 0.0
    return sum(vals) / len(vals)

def volatility(values: Sequence[float]) -> float:
    """
    Compute the standard deviation (volatility) of a sequence of numeric values.

    This uses population standard deviation (N denominator).
    Returns 0.0 if the sequence has fewer than 2 values.

    Returns:
        float: The standard deviation of the input values.
    """
    vals = list(values)
    n = len(vals)
    if n < 2:
        return 0.0
    mean = sum(vals) / n
    var = sum((x - mean) ** 2 for x in vals) / n
    return sqrt(var)

def z_score(values: Sequence[float]) -> float:
    """
    Compute the z-score of the last value in the sequence relative to the mean and standard deviation of the sequence.

    If the sequence is empty or has zero variance, returns 0.0.

    Returns:
        float: Z-score of the last element of the sequence.
    """
    vals = list(values)
    if not vals:
        return 0.0
    mean = sum(vals) / len(vals)
    # population standard deviation (N denominator)
    var = sum((x - mean) ** 2 for x in vals) / len(vals)
    std = sqrt(var)
    if std == 0.0:
        return 0.0
    return (vals[-1] - mean) / std

def percent_change(values: Sequence[float]) -> list[float]:
    """
    Compute percentage change returns for a sequence of prices or values.

    If the sequence has fewer than 2 values, returns an empty list.

    Returns:
        list[float]: List of percent changes between consecutive values (in percentage points).
    """
    vals = list(values)
    if len(vals) < 2:
        return []
    returns = []
    for i in range(1, len(vals)):
        prev = vals[i-1]
        curr = vals[i]
        if prev == 0:
            returns.append(0.0)  # avoid division by zero, define return as 0
        else:
            returns.append((curr - prev) / prev * 100.0)
    return returns

def position_size(account_size: float,
                  risk_per_trade: float,
                  entry_price: float,
                  stop_loss_price: float,
                  risk_in_fraction: bool = True) -> int:
    """
    Calculate position size (number of units to trade) based on account size, risk, and stop loss distance.

    If risk_in_fraction is True, risk_per_trade is treated as a fraction of account size.
    If risk_in_fraction is False, risk_per_trade is treated as an absolute amount.
    Returns 0 if inputs are invalid or if calculated size is less than 1 unit.

    Parameters:
        account_size (float): Total account capital.
        risk_per_trade (float): Risk per trade (fraction of account, or absolute amount if risk_in_fraction is False).
        entry_price (float): Entry price of the trade.
        stop_loss_price (float): Stop-loss price for the trade (price at which the trade will be exited if it goes against the position).
        risk_in_fraction (bool): Flag indicating interpretation of risk_per_trade.

    Returns:
        int: Recommended position size (number of units/contracts to trade).
    """
    if account_size <= 0 or entry_price <= 0 or stop_loss_price <= 0:
        return 0
    # Determine risk amount in currency
    risk_amount = risk_per_trade * account_size if risk_in_fraction else risk_per_trade
    if risk_amount <= 0:
        return 0
    # Calculate per-unit risk (absolute difference between entry and stop)
    per_unit_risk = abs(entry_price - stop_loss_price)
    if per_unit_risk <= 0:
        return 0
    # Compute the maximum number of units such that risk_amount is not exceeded
    max_units = risk_amount / per_unit_risk
    if max_units < 1:
        return 0
    return int(max_units)
