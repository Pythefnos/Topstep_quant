# File: tests/integration/test_end_to_end.py

from tests.conftest import DummyStrategy, DummyBroker, TradeSignal
from topstepquant.risk_manager import RiskManager

def test_strategy_to_broker_flow():
    """
    End-to-end integration test simulating strategy -> signal -> risk manager -> broker.
    It verifies that a valid trade signal is executed and that trades are blocked after risk limits are reached.
    """
    # Initialize components with controlled parameters
    strategy = DummyStrategy()  # always produces a BUY signal for "ES"
    risk_manager = RiskManager(max_daily_loss=100, max_trade_size=5)
    broker = DummyBroker()

    # First cycle: strategy generates a signal and it passes risk checks
    signals = strategy.generate_signals()
    assert signals and len(signals) == 1, "Strategy should produce one trade signal"
    signal = signals[0]
    allowed = risk_manager.validate_signal(signal)
    assert allowed is True, "RiskManager should allow the first trade within limits"
    result = broker.execute_order(signal)
    assert result is not None, "Broker should return a confirmation for the executed order"
    # After execution, simulate that the trade resulted in a loss hitting the daily loss limit
    risk_manager.current_loss = 100  # assume the first trade lost 100, reaching the daily limit

    # Second cycle: strategy produces another signal but it should be blocked by the risk manager
    signals2 = strategy.generate_signals()
    assert signals2 and len(signals2) == 1, "Strategy produces another trade signal"
    signal2 = signals2[0]
    allowed2 = risk_manager.validate_signal(signal2)
    # Risk manager should now block the trade since daily loss limit is reached
    assert allowed2 is False, "RiskManager should block trades after reaching daily loss limit"
    # Ensure the broker did not execute a second order
    assert len(broker.executed_orders) == 1, "No new order should have executed once risk limit was reached"
    # The one executed order should match the first signal
    executed_signal = broker.executed_orders[0]
    assert executed_signal == signal, "The executed order should correspond to the first trade signal"
