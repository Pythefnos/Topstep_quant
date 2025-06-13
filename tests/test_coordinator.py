# File: tests/unit/test_coordinator.py

import pytest
import time
import logging
from unittest.mock import MagicMock, call
from topstepquant.coordinator import Coordinator
from tests.conftest import TradeSignal

def test_coordinator_executes_valid_signal(monkeypatch):
    """Coordinator should call strategy, pass signal through risk, and execute via broker when allowed."""
    # Set up mocks for strategy, risk manager, and broker
    strategy = MagicMock()
    signal = TradeSignal("ES", "BUY", 1)
    strategy.generate_signals.return_value = [signal]
    risk_manager = MagicMock()
    risk_manager.validate_signal.return_value = True
    broker = MagicMock()
    broker.execute_order.return_value = "OK"

    coordinator = Coordinator(strategies=[strategy], risk_manager=risk_manager, broker=broker)
    # Monkeypatch time.sleep to break out after one loop iteration
    monkeypatch.setattr(time, "sleep", lambda t: (_ for _ in ()).throw(StopIteration()))
    # Run one iteration of the coordinator loop (StopIteration breaks after first iteration)
    with pytest.raises(StopIteration):
        coordinator.run()

    # Verify that each component was called correctly
    strategy.generate_signals.assert_called_once()
    risk_manager.validate_signal.assert_called_once_with(signal)
    broker.execute_order.assert_called_once_with(signal)

def test_coordinator_skips_no_signal(monkeypatch):
    """Coordinator should not call risk manager or broker if a strategy returns no signals."""
    strategy = MagicMock()
    strategy.generate_signals.return_value = []  # no signals generated
    risk_manager = MagicMock()
    broker = MagicMock()

    coordinator = Coordinator(strategies=[strategy], risk_manager=risk_manager, broker=broker)
    monkeypatch.setattr(time, "sleep", lambda t: (_ for _ in ()).throw(StopIteration()))
    with pytest.raises(StopIteration):
        coordinator.run()

    # Strategy runs, but no signals mean risk and broker should not be called
    strategy.generate_signals.assert_called_once()
    risk_manager.validate_signal.assert_not_called()
    broker.execute_order.assert_not_called()

def test_coordinator_blocks_disallowed_signal(monkeypatch):
    """Coordinator should not execute a trade if the risk manager disallows it."""
    strategy = MagicMock()
    signal = TradeSignal("ES", "BUY", 1)
    strategy.generate_signals.return_value = [signal]
    risk_manager = MagicMock()
    risk_manager.validate_signal.return_value = False  # risk check fails
    broker = MagicMock()

    coordinator = Coordinator(strategies=[strategy], risk_manager=risk_manager, broker=broker)
    monkeypatch.setattr(time, "sleep", lambda t: (_ for _ in ()).throw(StopIteration()))
    with pytest.raises(StopIteration):
        coordinator.run()

    strategy.generate_signals.assert_called_once()
    risk_manager.validate_signal.assert_called_once_with(signal)
    # Broker should never be called since risk did not approve the trade
    broker.execute_order.assert_not_called()

def test_coordinator_handles_broker_exception(monkeypatch, caplog):
    """Coordinator should handle broker exceptions without crashing and log an error."""
    strategy = MagicMock()
    signal = TradeSignal("ES", "BUY", 1)
    strategy.generate_signals.return_value = [signal]
    risk_manager = MagicMock()
    risk_manager.validate_signal.return_value = True
    broker = MagicMock()
    broker.execute_order.side_effect = Exception("Network error")

    coordinator = Coordinator(strategies=[strategy], risk_manager=risk_manager, broker=broker)
    monkeypatch.setattr(time, "sleep", lambda t: (_ for _ in ()).throw(StopIteration()))
    caplog.set_level(logging.ERROR)
    # Run the coordinator loop; it should catch the broker exception and continue
    with pytest.raises(StopIteration):
        coordinator.run()

    # Broker was called once and raised an exception (caught internally)
    strategy.generate_signals.assert_called_once()
    risk_manager.validate_signal.assert_called_once_with(signal)
    broker.execute_order.assert_called_once_with(signal)
    # Coordinator should log an error about the broker failure
    error_logs = [rec.getMessage() for rec in caplog.records if rec.levelname == "ERROR"]
    error_logged = any("Network error" in msg or "broker" in msg.lower() for msg in error_logs)
    assert error_logged, "Coordinator should log an error when broker execution fails"

def test_coordinator_multiple_strategies(monkeypatch):
    """Coordinator should handle multiple strategies, executing all allowed signals in order."""
    # Two strategies producing different signals
    strategy1 = MagicMock()
    strategy2 = MagicMock()
    sig1 = TradeSignal("ES", "BUY", 1)
    sig2 = TradeSignal("NQ", "SELL", 2)
    strategy1.generate_signals.return_value = [sig1]
    strategy2.generate_signals.return_value = [sig2]
    risk_manager = MagicMock()
    risk_manager.validate_signal.return_value = True  # allow all trades
    broker = MagicMock()

    coordinator = Coordinator(strategies=[strategy1, strategy2], risk_manager=risk_manager, broker=broker)
    monkeypatch.setattr(time, "sleep", lambda t: (_ for _ in ()).throw(StopIteration()))
    with pytest.raises(StopIteration):
        coordinator.run()

    # Each strategy should be called once
    strategy1.generate_signals.assert_called_once()
    strategy2.generate_signals.assert_called_once()
    # Risk manager should be called for each signal in sequence
    risk_manager.validate_signal.assert_has_calls([call(sig1), call(sig2)], any_order=False)
    # Broker should execute both orders in sequence
    broker.execute_order.assert_has_calls([call(sig1), call(sig2)], any_order=False)
