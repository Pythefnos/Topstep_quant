"""Tradovate API Broker implementation.

This class integrates with the Tradovate REST API to execute trades. It handles authentication via OAuth,
placing orders, and retrieving account information. Note: Using Tradovate's API may require a data subscription for live market data.
"""
import requests
import uuid
from typing import Optional, List
from topstep_quant.infrastructure.broker import Broker, Position

class TradovateAPI(Broker):
    """Broker implementation for Tradovate's HTTP/WebSocket API."""
    def __init__(self, username: str, password: str, api_key: str, demo: bool = True):
        """
        Initialize TradovateAPI with user credentials.

        :param username: Tradovate login username.
        :param password: Tradovate login password.
        :param api_key: Tradovate API key (or application ID) for authentication.
        :param demo: Whether to connect to demo (paper trading) environment.
        """
        super().__init__()
        self.username = username
        self.password = password
        self.api_key = api_key  # Tradovate refers to this as an API access token key or client ID
        self.base_url = "https://demo.tradovateapi.com/v1" if demo else "https://live.tradovateapi.com/v1"
        self.access_token: Optional[str] = None
        self._balance: float = 0.0
        self.account_id: Optional[int] = None
        self._connected = False

    def connect(self) -> None:
        """Authenticate with Tradovate API and retrieve an access token and account info."""
        # Prepare payload for access token request (OAuth)
        payload = {
            "name": self.username,
            "password": self.password,
            "appId": self.api_key,
            "appVersion": "1.0"
        }
        url = f"{self.base_url}/auth/accesstokenrequest"
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            raise ConnectionError(f"Tradovate API authentication failed: {response.status_code} {response.text}")
        data = response.json()
        self.access_token = data.get("accessToken")
        if not self.access_token:
            raise ConnectionError("Tradovate API authentication returned no access token.")
        self._connected = True
        # Retrieve account list to get account balance and ID
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        acct_resp = requests.get(f"{self.base_url}/account/list", headers=headers)
        if acct_resp.status_code == 200:
            accounts = acct_resp.json()
            if accounts:
                # Assuming first account in list is the relevant trading account
                acct_info = accounts[0]
                self.account_id = acct_info.get("accountId") or acct_info.get("id")
                # Tradovate's API returns various balances; use available fields
                bal = acct_info.get("balance") or acct_info.get("equity") or acct_info.get("marginBalance")
                if bal is not None:
                    self._balance = float(bal)
        # If account list fetch fails or no accounts, proceed with 0 balance (to be updated by trades)

    def get_account_balance(self) -> float:
        """Return the last known account balance (realized P&L only)."""
        return self._balance

    def get_account_equity(self) -> float:
        """Return account equity (balance plus unrealized P&L)."""
        # In a live setting, we would retrieve current positions and market data to calculate equity.
        # Here, if we have no live data, assume equity = balance for simplicity.
        return self._balance

    def place_order(self, instrument: str, quantity: int, order_type: str, side: str,
                    price: Optional[float] = None, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None) -> Optional[str]:
        """Place an order via Tradovate API. Market orders are executed immediately; limit orders are placed."""
        if not self._connected or not self.access_token:
            raise ConnectionError("Not connected to Tradovate API.")
        order_side = 1 if side.upper() == "BUY" else -1  # Tradovate uses 1 for buy, -1 for sell
        # Construct order payload
        order = {
            "accountId": self.account_id,
            "action": "Buy" if order_side == 1 else "Sell",
            "symbol": instrument,
            "orderQty": quantity,
            "orderType": order_type.capitalize()  # e.g., "Market" or "Limit"
        }
        if order_type.upper() == "LIMIT":
            if price is None:
                raise ValueError("Limit order requires a price.")
            order["price"] = price
        # Note: stop_loss and take_profit could be sent as bracket orders via separate API calls (not implemented here).
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        resp = requests.post(f"{self.base_url}/order/placeorder", headers=headers, json=order)
        if resp.status_code != 200:
            raise RuntimeError(f"Order placement failed: {resp.status_code} {resp.text}")
        result = resp.json()
        order_id = str(result.get("orderId") or uuid.uuid4())
        # Tradovate will handle execution and P/L updates; we might fetch updated balance via another call
        # For now, we'll not update self._balance here. 
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order by ID."""
        if not self._connected or not self.access_token:
            raise ConnectionError("Not connected to Tradovate API.")
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        resp = requests.post(f"{self.base_url}/order/cancelorder", headers=headers, json={"orderId": order_id})
        return resp.status_code == 200

    def get_open_positions(self) -> List[Position]:
        """Retrieve current open positions from Tradovate."""
        if not self._connected or not self.access_token:
            return []
        headers = {'Authorization': f'Bearer {self.access_token}'}
        resp = requests.get(f"{self.base_url}/position/list", headers=headers)
        positions: List[Position] = []
        if resp.status_code == 200:
            pos_list = resp.json()
            for p in pos_list:
                inst = p.get("instrument") or p.get("symbol")
                qty = int(p.get("netPos", 0))
                avg_price = float(p.get("avgPrice", 0.0))
                # current price not directly given; in a full implementation, we'd fetch market price
                cur_price = avg_price
                unreal_pnl = 0.0
                if qty != 0:
                    unreal_pnl = (cur_price - avg_price) * qty
                positions.append(Position(inst, qty, avg_price, cur_price, unreal_pnl))
        return positions
