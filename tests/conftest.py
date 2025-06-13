# File: tests/conftest.py

from collections import namedtuple

# Define a simple trade signal data structure for testing
TradeSignal = namedtuple('TradeSignal', ['symbol', 'action', 'quantity'])

class DummyStrategy:
    """A dummy strategy that always returns a preset trade signal for testing."""
    def __init__(self):
        self.name = "DummyStrategy"

    def generate_signals(self, *args, **kwargs):
        """Always return a single BUY signal (e.g., for symbol 'ES')."""
        signal = TradeSignal(symbol="ES", action="BUY", quantity=1)
        return [signal]

    def __repr__(self):
        return "<DummyStrategy>"

class DummyBroker:
    """A dummy broker that records orders instead of executing real trades."""
    def __init__(self):
        self.executed_orders = []  # Keep track of executed trade signals

    def execute_order(self, signal):
        """Record the signal/order and simulate a successful execution."""
        self.executed_orders.append(signal)
        # Return a dummy confirmation (e.g., an order ID or acknowledgment)
        return "ORDER123"

    def __repr__(self):
        return "<DummyBroker>"
