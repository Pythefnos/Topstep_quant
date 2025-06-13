"""
Alerting module for sending notifications (e.g., Slack) and optionally updating metrics.
"""
import json
import logging
from typing import Optional

import requests

class SlackAlerter:
    """
    Alerter for sending Slack webhook notifications for critical events (trade executions, kill switches, rule violations).
    Optionally maintains Prometheus-style counters for alerts.
    """
    def __init__(self, webhook_url: str, service_name: Optional[str] = None, enable_metrics: bool = False) -> None:
        """
        Initialize a SlackAlerter.

        Parameters:
            webhook_url (str): The Slack Webhook URL to send alerts to.
            service_name (str, optional): Name of the service to include in alert messages (for identification).
            enable_metrics (bool): If True, maintain counters for different types of alerts (requires prometheus_client).
        """
        self.webhook_url = webhook_url
        self.service_name = service_name
        self._metrics_enabled = False

        # Set up optional Prometheus counters if enabled
        if enable_metrics:
            try:
                from prometheus_client import Counter
                self._alert_counters: dict = {}
                self._alert_counters['trade_execution'] = Counter(
                    'trade_execution_alerts_total',
                    'Total number of trade execution alerts sent')
                self._alert_counters['kill_switch'] = Counter(
                    'kill_switch_alerts_total',
                    'Total number of kill switch alerts sent')
                self._alert_counters['rule_violation'] = Counter(
                    'rule_violation_alerts_total',
                    'Total number of rule violation alerts sent')
                self._metrics_enabled = True
            except ImportError:
                logging.warning("prometheus_client not installed; metrics will be disabled.")
                self._metrics_enabled = False

    def send_alert(self, message: str) -> bool:
        """
        Send a generic alert message to Slack.

        Parameters:
            message (str): The message text to send to Slack.

        Returns:
            bool: True if the alert was sent successfully, False otherwise.
        """
        full_message = f"[{self.service_name}] {message}" if self.service_name else message
        payload = {"text": full_message}
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            if response.status_code != 200:
                logging.error("Slack webhook returned non-OK status: %d", response.status_code)
                return False
        except requests.RequestException as e:
            # Log the exception without exposing sensitive URL details
            logging.error("Exception during Slack webhook post: %s", e.__class__.__name__)
            return False
        return True

    def alert_trade_execution(self, trade_info: str) -> None:
        """
        Send an alert about a trade execution event.

        Parameters:
            trade_info (str): Information about the trade execution to include in the alert.
        """
        message = f"Trade execution: {trade_info}"
        if self._metrics_enabled:
            counter = self._alert_counters.get('trade_execution')
            if counter:
                counter.inc()
        self.send_alert(message)

    def alert_kill_switch(self, reason: str) -> None:
        """
        Send an alert that a kill switch event has occurred (e.g., trading halted due to risk rules).

        Parameters:
            reason (str): Description of why the kill switch was triggered.
        """
        message = f"KILL SWITCH TRIGGERED: {reason}"
        if self._metrics_enabled:
            counter = self._alert_counters.get('kill_switch')
            if counter:
                counter.inc()
        self.send_alert(message)

    def alert_rule_violation(self, description: str) -> None:
        """
        Send an alert about a trading rule violation.

        Parameters:
            description (str): Details of the rule violation.
        """
        message = f"RULE VIOLATION: {description}"
        if self._metrics_enabled:
            counter = self._alert_counters.get('rule_violation')
            if counter:
                counter.inc()
        self.send_alert(message)
