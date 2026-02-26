import requests
import base64
import time
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import asyncio
import httpx
import pandas as pd
import numpy as np
import os
import csv
from tqdm import tqdm
from loguru import logger
from dotenv import load_dotenv

from requests.exceptions import HTTPError

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.exceptions import InvalidSignature

import websockets

# Load environment variables from .env file
load_dotenv()

# Import database functions for logging
try:
    from .database import log_order, log_trade, get_order_by_id, get_trade_by_id
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    print("Warning: Database not available. Ledger logging disabled.")

# Define constants
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

class Environment(Enum):
    DEMO = "demo"
    PROD = "prod"

class KalshiBaseClient:
    """Base client class for interacting with the Kalshi API."""
    def __init__(
        self,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        environment: Environment = Environment.DEMO,
    ):
        """Initializes the client with the provided API key and private key.

        Args:
            key_id (str): Your Kalshi API key ID.
            private_key (rsa.RSAPrivateKey): Your RSA private key.
            environment (Environment): The API environment to use (DEMO or PROD).
        """
        self.key_id = key_id
        self.private_key = private_key
        self.environment = environment
        self.last_api_call = datetime.now()

        if self.environment == Environment.DEMO:
            self.HTTP_BASE_URL = "https://demo-api.kalshi.co"
            self.WS_BASE_URL = "wss://demo-api.kalshi.co"
        elif self.environment == Environment.PROD:
            self.HTTP_BASE_URL = "https://api.elections.kalshi.com"
            self.WS_BASE_URL = "wss://api.elections.kalshi.com"
        else:
            raise ValueError("Invalid environment")

    def request_headers(self, method: str, path: str) -> Dict[str, Any]:
        """Generates the required authentication headers for API requests."""
        current_time_milliseconds = int(time.time() * 1000)
        timestamp_str = str(current_time_milliseconds)

        # Remove query params from path
        path_parts = path.split('?')

        msg_string = timestamp_str + method + path_parts[0]
        signature = self.sign_pss_text(msg_string)

        headers = {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_str,
        }
        return headers

    def sign_pss_text(self, text: str) -> str:
        """Signs the text using RSA-PSS and returns the base64 encoded signature."""
        message = text.encode('utf-8')
        try:
            signature = self.private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )
            return base64.b64encode(signature).decode('utf-8')
        except InvalidSignature as e:
            raise ValueError("RSA sign PSS failed") from e

class KalshiHttpClient(KalshiBaseClient):
    """Client for handling HTTP connections to the Kalshi API."""
    def __init__(
        self,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        environment: Environment = Environment.DEMO,
    ):
        super().__init__(key_id, private_key, environment)
        self.host = self.HTTP_BASE_URL
        self.exchange_url = "/trade-api/v2/exchange"
        self.markets_url = "/trade-api/v2/markets"
        self.portfolio_url = "/trade-api/v2/portfolio"

    def rate_limit(self) -> None:
        """Built-in rate limiter to prevent exceeding API rate limits."""
        THRESHOLD_IN_MILLISECONDS = 100
        now = datetime.now()
        threshold_in_microseconds = 1000 * THRESHOLD_IN_MILLISECONDS
        threshold_in_seconds = THRESHOLD_IN_MILLISECONDS / 1000
        if now - self.last_api_call < timedelta(microseconds=threshold_in_microseconds):
            time.sleep(threshold_in_seconds)
        self.last_api_call = datetime.now()

    def raise_if_bad_response(self, response: requests.Response) -> None:
        """Raises an HTTPError if the response status code indicates an error."""
        if response.status_code not in range(200, 299):
            response.raise_for_status()

    def post(self, path: str, body: dict) -> Any:
        """Performs an authenticated POST request to the Kalshi API."""
        self.rate_limit()
        response = requests.post(
            self.host + path,
            json=body,
            headers=self.request_headers("POST", path)
        )
        self.raise_if_bad_response(response)
        return response.json()

    def get(self, path: str, params: Dict[str, Any] = {}) -> Any:
        """Performs an authenticated GET request to the Kalshi API."""
        self.rate_limit()
        response = requests.get(
            self.host + path,
            headers=self.request_headers("GET", path),
            params=params
        )
        self.raise_if_bad_response(response)
        return response.json()

    def delete(self, path: str, params: Dict[str, Any] = {}) -> Any:
        """Performs an authenticated DELETE request to the Kalshi API."""
        self.rate_limit()
        response = requests.delete(
            self.host + path,
            headers=self.request_headers("DELETE", path),
            params=params
        )
        self.raise_if_bad_response(response)
        return response.json()

    def get_balance(self) -> Dict[str, Any]:
        """Retrieves the account balance."""
        return self.get(self.portfolio_url + '/balance')

    def get_fills(
        self,
        ticker: Optional[str] = None,
        order_id: Optional[str] = None,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves all fills (executed trades) for the member."""
        params = {
            'ticker': ticker,
            'order_id': order_id,
            'min_ts': min_ts,
            'max_ts': max_ts,
            'limit': limit,
            'cursor': cursor,
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        return self.get(self.portfolio_url + '/fills', params=params)

    def get_settlements(
        self,
        limit: Optional[int] = None,
        ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves all settlements (completed trades with final P&L) for the member."""
        params = {
            'limit': limit,
            'ticker': ticker,
            'event_ticker': event_ticker,
            'min_ts': min_ts,
            'max_ts': max_ts,
            'cursor': cursor,
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        return self.get(self.portfolio_url + '/settlements', params=params)

    def get_exchange_status(self) -> Dict[str, Any]:
        """Retrieves the exchange status."""
        return self.get(self.exchange_url + "/status")

    def get_trades(
        self,
        ticker: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        max_ts: Optional[int] = None,
        min_ts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieves trades based on provided filters."""
        params = {
            'ticker': ticker,
            'limit': limit,
            'cursor': cursor,
            'max_ts': max_ts,
            'min_ts': min_ts,
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        return self.get(self.markets_url + '/trades', params=params)

    def get_markets(
        self,
        ticker: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves markets based on provided filters."""
        params = {
            'ticker': ticker,
            'limit': limit,
            'cursor': cursor,
            'status': status,
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        return self.get(self.markets_url, params=params)

    def get_market_orderbook(self, ticker: str) -> Dict[str, Any]:
        """Retrieves the orderbook for a specific market."""
        return self.get(f"{self.markets_url}/{ticker}/orderbook")

    def place_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int,
        order_type: str = "market",  # "market" or "limit"
        price_cents: Optional[int] = None,  # Required for limit orders
        yes_price: Optional[int] = None,
        no_price: Optional[int] = None,
        yes_price_dollars: Optional[str] = None,
        no_price_dollars: Optional[str] = None,
        time_in_force: Optional[str] = None,
        post_only: bool = False,
        buy_max_cost: Optional[int] = None,
        client_order_id: Optional[str] = None,
        self_trade_prevention_type: Optional[str] = None,
        market_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Place an order on the Kalshi exchange.
        
        Args:
            ticker: Market ticker
            side: "yes" or "no"
            action: "buy" or "sell"
            count: Number of contracts
            order_type: "market" or "limit"
            price_cents: Price in cents (required for limit orders, 1-99)
            yes_price: YES price in cents (legacy parameter)
            no_price: NO price in cents (legacy parameter)
            yes_price_dollars: YES price in dollars (legacy parameter)
            no_price_dollars: NO price in dollars (legacy parameter)
            time_in_force: Order time in force
            post_only: Whether to use post-only
            buy_max_cost: Maximum cost for buy orders
            client_order_id: Optional client order ID
            self_trade_prevention_type: Self-trade prevention type
            market_info: Optional market information for logging
        
        Returns:
            Order response
        """
        import uuid
        
        # Validate order type
        if order_type not in ["market", "limit"]:
            raise ValueError("order_type must be 'market' or 'limit'")
        
        # For limit orders, validate price
        if order_type == "limit":
            if price_cents is None and yes_price is None and no_price is None:
                raise ValueError("Price must be specified for limit orders (use price_cents, yes_price, or no_price)")
            
            # Use price_cents if provided, otherwise use legacy parameters
            if price_cents is not None:
                if price_cents < 1 or price_cents > 99:
                    raise ValueError("Price must be between 1 and 99 cents")
                
                # Set price based on side
                if side == "yes":
                    yes_price = price_cents
                else:
                    no_price = price_cents
            
            # For limit orders, keep the time_in_force if specified
            # If not specified, use GTC (Good Till Canceled) by keeping None
            pass
        
        # For market orders, use immediate execution
        elif order_type == "market":
            # Don't specify time_in_force for market orders - buy_max_cost handles it
            time_in_force = None
            post_only = False
            # Don't include price fields for market orders
            yes_price = None
            no_price = None
            yes_price_dollars = None
            no_price_dollars = None
        
        order_data = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": order_type,  # Add type field for Kalshi API
            "client_order_id": client_order_id or f"order_{uuid.uuid4().hex[:16]}",
        }
        
        # Only add post_only for limit orders, not market orders
        if order_type == "limit":
            order_data["post_only"] = post_only
        
        # Add time_in_force only if specified
        if time_in_force is not None:
            order_data["time_in_force"] = time_in_force
        
        # Add optional parameters
        if self_trade_prevention_type is not None:
            order_data["self_trade_prevention_type"] = self_trade_prevention_type
        
        # Add price information
        if yes_price is not None:
            order_data["yes_price"] = yes_price
        if no_price is not None:
            order_data["no_price"] = no_price
        if yes_price_dollars is not None:
            order_data["yes_price_dollars"] = yes_price_dollars
        if no_price_dollars is not None:
            order_data["no_price_dollars"] = no_price_dollars
        
        # Add buy_max_cost for both limit and market buy orders
        if buy_max_cost is not None:
            order_data["buy_max_cost"] = buy_max_cost
        
        # Debug: Print order data for troubleshooting
        print(f"[DEBUG] Order data being sent: {order_data}")
            
        # Place the order
        result = self.post(self.portfolio_url + '/orders', order_data)
        
        # Log order to ledger
        if result and 'order' in result:
            self.log_order_to_ledger(result, market_info)
            
        return result


    def get_orders(self, status: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """Retrieves orders for the account."""
        params = {}
        if status is not None:
            params['status'] = status
        if limit is not None:
            params['limit'] = limit
        return self.get(self.portfolio_url + '/orders', params=params)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancels an order."""
        return self.delete(f"{self.portfolio_url}/orders/{order_id}")

    def get_positions(self) -> Dict[str, Any]:
        """Retrieves current positions."""
        return self.get(self.portfolio_url + '/positions')

    def calculate_limit_price(
        self,
        ticker: str,
        side: str,
        strategy: str = "mid_price",
        offset_cents: int = 0
    ) -> int:
        """
        Calculate optimal limit price based on current market data.
        
        Args:
            ticker: Market ticker
            side: "yes" or "no"
            strategy: Pricing strategy ("mid_price", "aggressive", "conservative")
            offset_cents: Price offset in cents (positive = higher price, negative = lower)
        
        Returns:
            Calculated price in cents
        """
        try:
            # Get current market data
            market_data = self.get_market_orderbook(ticker)
            
            if side == "yes":
                bid = market_data.get("yes_bid", 0)
                ask = market_data.get("yes_ask", 0)
            else:
                bid = market_data.get("no_bid", 0)
                ask = market_data.get("no_ask", 0)
            
            if bid == 0 or ask == 0:
                print(f"Warning: No valid bid/ask for {side} side")
                return 50  # Default to 50 cents
            
            mid_price = (bid + ask) / 2
            
            if strategy == "mid_price":
                price = mid_price
            elif strategy == "aggressive":
                # Price closer to the market (better fill probability)
                if side == "yes":
                    price = ask - 1  # Just below ask
                else:
                    price = ask - 1  # Just below ask
            elif strategy == "conservative":
                # Price further from market (better price, lower fill probability)
                if side == "yes":
                    price = bid + 1  # Just above bid
                else:
                    price = bid + 1  # Just above bid
            else:
                price = mid_price
            
            # Apply offset
            price += offset_cents
            
            # Ensure price is within valid range (1-99 cents)
            price = max(1, min(99, int(price)))
            
            print(f"Calculated {side} limit price: {price}¢ (strategy: {strategy}, offset: {offset_cents})")
            return price
            
        except Exception as e:
            print(f"Error calculating limit price: {e}")
            return 50  # Default fallback


    def get_active_orders(self) -> List[Dict[str, Any]]:
        """
        Get all active orders.
        
        Returns:
            List of active orders
        """
        try:
            orders = self.get_orders(status="open")
            return orders.get('orders', [])
        except Exception as e:
            print(f"Failed to get active orders: {e}")
            return []

    def cancel_all_orders(self, ticker: Optional[str] = None) -> int:
        """
        Cancel all active orders, optionally filtered by ticker.
        
        Args:
            ticker: Optional ticker filter
        
        Returns:
            Number of orders cancelled
        """
        try:
            active_orders = self.get_active_orders()
            cancelled_count = 0
            
            for order in active_orders:
                order_ticker = order.get('ticker')
                order_id = order.get('order_id')
                
                if ticker and order_ticker != ticker:
                    continue
                
                try:
                    self.cancel_order(order_id)
                    cancelled_count += 1
                    print(f"Cancelled order {order_id} for {order_ticker}")
                except Exception as e:
                    print(f"Failed to cancel order {order_id}: {e}")
            
            print(f"Cancelled {cancelled_count} orders")
            return cancelled_count
            
        except Exception as e:
            print(f"Failed to cancel all orders: {e}")
            return 0

    def get_order_fills(self, ticker: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get order fills (executed trades).
        
        Args:
            ticker: Optional ticker filter
            limit: Maximum number of fills to return
        
        Returns:
            List of fills
        """
        try:
            fills = self.get_fills(ticker=ticker, limit=limit)
            return fills.get('fills', [])
        except Exception as e:
            print(f"Failed to get fills: {e}")
            return []

    def calculate_order_cost(self, quantity: int, price_cents: int) -> int:
        """
        Calculate the total cost of an order.
        
        Args:
            quantity: Number of contracts
            price_cents: Price per contract in cents
        
        Returns:
            Total cost in cents
        """
        return quantity * price_cents

    def get_market_summary(self, ticker: str) -> Dict[str, Any]:
        """
        Get a summary of market data including calculated metrics.
        
        Args:
            ticker: Market ticker
        
        Returns:
            Market summary data
        """
        try:
            market_data = self.get_market_orderbook(ticker)
            
            yes_bid = market_data.get('yes_bid', 0)
            yes_ask = market_data.get('yes_ask', 0)
            no_bid = market_data.get('no_bid', 0)
            no_ask = market_data.get('no_ask', 0)
            
            # Calculate metrics
            yes_mid = (yes_bid + yes_ask) / 2 if yes_bid and yes_ask else 0
            no_mid = (no_bid + no_ask) / 2 if no_bid and no_ask else 0
            yes_spread = yes_ask - yes_bid if yes_bid and yes_ask else 0
            no_spread = no_ask - no_bid if no_bid and no_ask else 0
            
            return {
                'ticker': ticker,
                'yes_bid': yes_bid,
                'yes_ask': yes_ask,
                'yes_mid': yes_mid,
                'yes_spread': yes_spread,
                'no_bid': no_bid,
                'no_ask': no_ask,
                'no_mid': no_mid,
                'no_spread': no_spread,
                'volume': market_data.get('volume', 0),
                'status': market_data.get('status', 'unknown')
            }
            
        except Exception as e:
            print(f"Failed to get market summary for {ticker}: {e}")
            return {}

    def log_order_to_ledger(self, order_data: Dict[str, Any], market_info: Dict[str, Any] = None) -> bool:
        """Log order to database ledger"""
        if not DATABASE_AVAILABLE:
            return False
        
        # Check if we're in a Flask application context
        try:
            from flask import has_app_context
            if not has_app_context():
                return False  # Skip logging if no Flask context
        except ImportError:
            pass  # Flask not available, continue anyway
            
        try:
            # Extract order information
            order_id = order_data.get('order', {}).get('order_id', '')
            client_order_id = order_data.get('order', {}).get('client_order_id', '')
            
            # Get market information if provided
            if market_info:
                event_name = market_info.get('event_name', '')
                market_name = market_info.get('market_name', '')
                category = market_info.get('category', '')
                ticker = order_data.get('ticker', '')
            else:
                event_name = ''
                market_name = ''
                category = ''
                ticker = order_data.get('ticker', '')
            
            # Prepare order data for logging
            ledger_data = {
                'order_id': order_id,
                'client_order_id': client_order_id,
                'event_name': event_name,
                'market_name': market_name,
                'category': category,
                'ticker': ticker,
                'side': order_data.get('side', ''),
                'action': order_data.get('action', ''),
                'count': order_data.get('count', 0),
                'price': order_data.get('yes_price') or order_data.get('no_price'),
                'price_dollars': order_data.get('yes_price_dollars') or order_data.get('no_price_dollars'),
                'status': 'pending',
                'time_in_force': order_data.get('time_in_force', 'fill_or_kill'),
                'post_only': order_data.get('post_only', False),
                'total_cost': order_data.get('buy_max_cost')
            }
            
            return log_order(ledger_data) is not None
            
        except Exception as e:
            print(f"Error logging order to ledger: {e}")
            return False

    def log_trade_to_ledger(self, trade_data: Dict[str, Any], market_info: Dict[str, Any] = None) -> bool:
        """Log trade to database ledger"""
        if not DATABASE_AVAILABLE:
            return False
        
        # Check if we're in a Flask application context
        try:
            from flask import has_app_context
            if not has_app_context():
                return False  # Skip logging if no Flask context
        except ImportError:
            pass  # Flask not available, continue anyway
            
        try:
            # Extract trade information
            trade_id = trade_data.get('trade_id', '')
            order_id = trade_data.get('order_id', '')
            
            # Get market information if provided
            if market_info:
                event_name = market_info.get('event_name', '')
                market_name = market_info.get('market_name', '')
                category = market_info.get('category', '')
                ticker = trade_data.get('ticker', '')
            else:
                event_name = ''
                market_name = ''
                category = ''
                ticker = trade_data.get('ticker', '')
            
            # Prepare trade data for logging
            ledger_data = {
                'trade_id': trade_id,
                'order_id': order_id,
                'event_name': event_name,
                'market_name': market_name,
                'category': category,
                'ticker': ticker,
                'side': trade_data.get('side', ''),
                'action': trade_data.get('action', ''),
                'quantity': trade_data.get('count', 0),
                'price': trade_data.get('price', 0),
                'price_dollars': trade_data.get('price_dollars', ''),
                'total_cost': trade_data.get('total_cost', 0),
                'fees': trade_data.get('fees', 0)
            }
            
            return log_trade(ledger_data) is not None
            
        except Exception as e:
            print(f"Error logging trade to ledger: {e}")
            return False

class KalshiWebSocketClient(KalshiBaseClient):
    """Client for handling WebSocket connections to the Kalshi API."""
    def __init__(
        self,
        key_id: str,
        private_key: rsa.RSAPrivateKey,
        environment: Environment = Environment.DEMO,
    ):
        super().__init__(key_id, private_key, environment)
        self.ws = None
        self.url_suffix = "/trade-api/ws/v2"
        self.message_id = 1  # Add counter for message IDs

    async def connect(self):
        """Establishes a WebSocket connection using authentication."""
        host = self.WS_BASE_URL + self.url_suffix
        auth_headers = self.request_headers("GET", self.url_suffix)
        async with websockets.connect(host, additional_headers=auth_headers) as websocket:
            self.ws = websocket
            await self.on_open()
            await self.handler()

    async def on_open(self):
        """Callback when WebSocket connection is opened."""
        print("WebSocket connection opened.")
        await self.subscribe_to_tickers()

    async def subscribe_to_tickers(self):
        """Subscribe to ticker updates for all markets."""
        subscription_message = {
            "id": self.message_id,
            "cmd": "subscribe",
            "params": {
                "channels": ["ticker"]
            }
        }
        await self.ws.send(json.dumps(subscription_message))
        self.message_id += 1

    async def handler(self):
        """Handle incoming messages."""
        try:
            async for message in self.ws:
                await self.on_message(message)
        except websockets.ConnectionClosed as e:
            await self.on_close(e.code, e.reason)
        except Exception as e:
            await self.on_error(e)

    async def on_message(self, message):
        """Callback for handling incoming messages."""
        print("Received message:", message)

    async def on_error(self, error):
        """Callback for handling errors."""
        print("WebSocket error:", error)

    async def on_close(self, close_status_code, close_msg):
        """Callback when WebSocket connection is closed."""
        print("WebSocket connection closed with code:", close_status_code, "and message:", close_msg)


# Configuration class
class KalshiConfig:
    """Configuration class for Kalshi API client."""
    
    def __init__(self):
        self.base_url = "https://api.elections.kalshi.com"
        self.api_key = os.getenv('KALSHI_API_KEY')
        self.private_key = os.getenv('KALSHI_PRIVATE_KEY')
        
        if not self.api_key or not self.private_key:
            raise ValueError("KALSHI_API_KEY and KALSHI_PRIVATE_KEY must be set in .env file")
    
    @property
    def is_configured(self) -> bool:
        """Check if the configuration is complete."""
        return bool(self.api_key and self.private_key)


# AsyncKalshiClient class from kalshi_client_new.py
class AsyncKalshiClient:
    """Async Kalshi API client for advanced trading operations."""
    
    def __init__(self, config: KalshiConfig, minimum_time_remaining_hours: float = 1.0, max_markets_per_event: int = 10, max_close_ts: Optional[int] = None):
        self.config = config
        self.minimum_time_remaining_hours = minimum_time_remaining_hours
        self.max_markets_per_event = max_markets_per_event
        self.max_close_ts = max_close_ts
        self.client = None
        
        # Create sync client for basic operations
        from cryptography.hazmat.primitives import serialization
        private_key = serialization.load_pem_private_key(
            config.private_key.encode(),
            password=None
        )
        self.sync_client = KalshiHttpClient(
            key_id=config.api_key,
            private_key=private_key,
            environment=Environment.PROD
        )
        
    async def login(self):
        """Login to Kalshi API."""
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=30.0
        )
        logger.info(f"Connected to Kalshi API at {self.config.base_url}")
        
    async def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get top events sorted by 24-hour volume with advanced filtering."""
        try:
            # First, fetch ALL events from the platform using pagination
            all_events = await self._fetch_all_events()
            
            # Calculate total volume_24h for each event from its markets 
            enriched_events = []
            now = datetime.now(timezone.utc)
            minimum_time_remaining = self.minimum_time_remaining_hours * 3600
            filter_enabled = self.max_close_ts is not None
            markets_seen = 0
            markets_kept = 0
            events_dropped_by_expiration = 0
            
            for event in all_events:
                # Get markets and select top N by volume
                all_markets = event.get("markets", [])
                markets_seen += len(all_markets)

                # Optionally filter markets by close time if max_close_ts is provided
                if self.max_close_ts is not None and all_markets:
                    filtered_markets = []
                    for market in all_markets:
                        close_time_str = market.get("close_time", "")
                        if not close_time_str:
                            continue
                        try:
                            # Parse ISO8601 close_time
                            if close_time_str.endswith('Z'):
                                close_dt = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                            else:
                                close_dt = datetime.fromisoformat(close_time_str)
                            if close_dt.tzinfo is None:
                                close_dt = close_dt.replace(tzinfo=timezone.utc)
                            close_ts = int(close_dt.timestamp())
                            if close_ts <= self.max_close_ts:
                                filtered_markets.append(market)
                        except Exception:
                            continue
                    all_markets = filtered_markets
                
                # If no markets remain after filtering, skip this event
                if not all_markets:
                    if filter_enabled:
                        events_dropped_by_expiration += 1
                    continue

                if filter_enabled:
                    markets_kept += len(all_markets)

                # Sort markets by volume (descending) and take top N
                sorted_markets = sorted(all_markets, key=lambda m: m.get("volume", 0), reverse=True)
                top_markets = sorted_markets[:self.max_markets_per_event]
                
                if len(all_markets) > self.max_markets_per_event:
                    logger.info(f"Event {event.get('event_ticker', '')} has {len(all_markets)} markets, selecting top {len(top_markets)} by volume")
                
                # Calculate volume metrics for this event using top markets
                total_liquidity = 0
                total_volume = 0
                total_volume_24h = 0
                total_open_interest = 0
                
                for market in top_markets:
                    total_liquidity += market.get("liquidity", 0)
                    total_volume += market.get("volume", 0)
                    total_volume_24h += market.get("volume_24h", 0)
                    total_open_interest += market.get("open_interest", 0)
                
                # Calculate time remaining if strike_date exists
                time_remaining_hours = None
                strike_date_str = event.get("strike_date", "")
                
                if strike_date_str:
                    try:
                        # Parse strike date
                        if strike_date_str.endswith('Z'):
                            strike_date = datetime.fromisoformat(strike_date_str.replace('Z', '+00:00'))
                        else:
                            strike_date = datetime.fromisoformat(strike_date_str)
                        
                        # Ensure timezone awareness
                        if strike_date.tzinfo is None:
                            strike_date = strike_date.replace(tzinfo=timezone.utc)
                        
                        # Calculate time remaining
                        time_remaining = (strike_date - now).total_seconds()
                        time_remaining_hours = time_remaining / 3600
                        
                        # Optional: Skip events that are very close to striking
                        if time_remaining > 0 and time_remaining < minimum_time_remaining:
                            logger.info(f"Event {event.get('event_ticker', '')} strikes in {time_remaining/60:.1f} minutes, skipping")
                            continue
                        
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not parse strike_date '{strike_date_str}' for event {event.get('event_ticker', '')}: {e}")
                
                # If no top markets selected, skip event
                if not top_markets:
                    continue

                enriched_events.append({
                    "event_ticker": event.get("event_ticker", ""),
                    "title": event.get("title", ""),
                    "subtitle": event.get("sub_title", ""),
                    "volume": total_volume,
                    "volume_24h": total_volume_24h,
                    "liquidity": total_liquidity,
                    "open_interest": total_open_interest,
                    "category": event.get("category", ""),
                    "mutually_exclusive": event.get("mutually_exclusive", False),
                    "strike_date": strike_date_str,
                    "strike_period": event.get("strike_period", ""),
                    "time_remaining_hours": time_remaining_hours,
                    "markets": top_markets,
                    "total_markets": len(all_markets),
                })
            
            # Sort by volume_24h (descending) for true popularity ranking
            enriched_events.sort(key=lambda x: x.get("volume_24h", 0), reverse=True)
            
            # Return only the top N events as requested
            top_events = enriched_events[:limit]
            
            # Summary log for expiration filter effects
            if filter_enabled and markets_seen > 0:
                dropped = markets_seen - markets_kept
                logger.info(
                    f"Expiration filter summary: kept {markets_kept}/{markets_seen} markets; "
                    f"dropped {dropped}. Events dropped due to no remaining markets: {events_dropped_by_expiration}"
                )
            
            logger.info(f"Retrieved {len(all_events)} total events, filtered to {len(enriched_events)} active events, returning top {len(top_events)} by 24h volume")
            return top_events
            
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []
    
    async def _fetch_all_events(self) -> List[Dict[str, Any]]:
        """Fetch all events from the platform using pagination."""
        all_events = []
        cursor = None
        page = 1
        
        while True:
            try:
                headers = await self._get_headers("GET", "/trade-api/v2/events")
                params = {
                    "limit": 100,
                    "status": "open",
                    "with_nested_markets": "true"
                }
                
                if cursor:
                    params["cursor"] = cursor
                
                logger.info(f"Fetching events page {page}...")
                response = await self.client.get(
                    "/trade-api/v2/events",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                if data is None:
                    logger.error(f"Received None response from API")
                    break
                
                if not isinstance(data, dict):
                    logger.error(f"Received non-dict response from API: {type(data)}")
                    break
                    
                events = data.get("events", [])
                
                if not events:
                    break
                
                all_events.extend(events)
                logger.info(f"Page {page}: {len(events)} events (total: {len(all_events)})")
                
                # Check if there's a next page
                cursor = data.get("cursor")
                if not cursor:
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Error fetching events page {page}: {e}")
                break
        
        logger.info(f"Fetched {len(all_events)} total events from {page} pages")
        return all_events
    
    async def get_markets_for_event(self, event_ticker: str) -> List[Dict[str, Any]]:
        """Get markets for a specific event (returns pre-filtered top markets from get_events)."""
        logger.warning(f"get_markets_for_event called for {event_ticker} - markets should be pre-loaded from get_events()")
        
        # Fallback: fetch markets directly if needed
        try:
            headers = await self._get_headers("GET", "/trade-api/v2/markets")
            params = {"event_ticker": event_ticker, "status": "open"}
            if self.max_close_ts is not None:
                params["max_close_ts"] = self.max_close_ts
            response = await self.client.get(
                "/trade-api/v2/markets",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            all_markets = data.get("markets", [])

            # Client-side filtering as a fallback
            if self.max_close_ts is not None and all_markets:
                filtered_markets = []
                for market in all_markets:
                    close_time_str = market.get("close_time", "")
                    if not close_time_str:
                        continue
                    try:
                        if close_time_str.endswith('Z'):
                            close_dt = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                        else:
                            close_dt = datetime.fromisoformat(close_time_str)
                        if close_dt.tzinfo is None:
                            close_dt = close_dt.replace(tzinfo=timezone.utc)
                        close_ts = int(close_dt.timestamp())
                        if close_ts <= self.max_close_ts:
                            filtered_markets.append(market)
                    except Exception:
                        continue
                all_markets = filtered_markets
            
            # Sort by volume and take top markets
            sorted_markets = sorted(all_markets, key=lambda m: m.get("volume", 0), reverse=True)
            top_markets = sorted_markets[:self.max_markets_per_event]
            
            # Return markets without odds for research
            simple_markets = []
            for market in top_markets:
                simple_markets.append({
                    "ticker": market.get("ticker", ""),
                    "title": market.get("title", ""),
                    "subtitle": market.get("subtitle", ""),
                    "volume": market.get("volume", 0),
                    "open_time": market.get("open_time", ""),
                    "close_time": market.get("close_time", ""),
                })
            
            logger.info(f"Retrieved {len(simple_markets)} markets for event {event_ticker} (top {len(top_markets)} by volume)")
            return simple_markets
            
        except Exception as e:
            logger.error(f"Error getting markets for event {event_ticker}: {e}")
            return []
    
    async def get_market_with_odds(self, ticker: str) -> Dict[str, Any]:
        """Get a specific market with current odds for trading."""
        try:
            headers = await self._get_headers("GET", f"/trade-api/v2/markets/{ticker}")
            response = await self.client.get(
                f"/trade-api/v2/markets/{ticker}",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            market = data.get("market", {})
            
            return {
                "ticker": market.get("ticker", ""),
                "title": market.get("title", ""),
                "yes_bid": market.get("yes_bid", 0),
                "no_bid": market.get("no_bid", 0),
                "yes_ask": market.get("yes_ask", 0),
                "no_ask": market.get("no_ask", 0),
                "volume": market.get("volume", 0),
                "status": market.get("status", ""),
                "close_time": market.get("close_time", ""),
            }
            
        except Exception as e:
            logger.error(f"Error getting market {ticker}: {e}")
            return {}
    
    async def get_user_positions(self) -> List[Dict[str, Any]]:
        """Get all user positions."""
        try:
            headers = await self._get_headers("GET", "/trade-api/v2/portfolio/positions")
            response = await self.client.get(
                "/trade-api/v2/portfolio/positions",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            positions = data.get("market_positions", [])
            event_positions = data.get("event_positions", [])
            
            logger.info(f"Retrieved {len(positions)} market positions and {len(event_positions)} event positions")
            return positions
            
        except Exception as e:
            logger.error(f"Error getting user positions: {e}")
            return []
    
    async def has_position_in_market(self, ticker: str) -> bool:
        """Check if user already has a position in the specified market."""
        try:
            positions = await self.get_user_positions()
            
            for position in positions:
                if position.get("ticker") == ticker:
                    position_size = position.get("position", 0)
                    if position_size != 0:
                        position_type = "YES" if position_size > 0 else "NO"
                        logger.info(f"Found existing position in {ticker}: {abs(position_size)} {position_type} contracts")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking position for {ticker}: {e}")
            return False

    async def place_order(self, ticker: str, side: str, amount: float) -> Dict[str, Any]:
        """Place a simple limit order using sync client."""
        try:
            # Use sync client for order placement with proper order format
            import uuid
            client_order_id = str(uuid.uuid4())
            
            # Convert dollar amount to price (assuming 50% probability for simplicity)
            # In a real implementation, you'd want to get the current market price
            price_cents = 50  # 50 cents = 50% probability
            
            # Use the proper order format from the working client
            result = self.sync_client.place_order(
                ticker=ticker,
                side=side,
                action="buy",
                count=1,  # Start with 1 contract
                yes_price=price_cents if side == "yes" else None,
                no_price=price_cents if side == "no" else None,
                client_order_id=client_order_id,
                time_in_force="immediate_or_cancel"
            )
            
            logger.info(f"Order placed: {ticker} {side} ${amount} (price: {price_cents} cents)")
            return {"success": True, "order_id": result.get("order", {}).get("order_id", ""), "client_order_id": client_order_id, "result": result}
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        """Generate headers with RSA signature using sync client."""
        return self.sync_client.request_headers(method, path)
    
    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()


# Utility functions from kalshi.py
def sign_request(private_key, message):
    """Sign a request using the private key."""
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')

def get_headers(api_key, private_key, method, path, params=None):
    """Generate headers for API request with signature."""
    timestamp = str(int(time.time() * 1000))
    query_string = ""
    if params:
        query_string = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    full_path = path + query_string
    msg_string = timestamp + method + full_path
    signature = sign_request(private_key, msg_string)
    
    return {
        "accept": "application/json",
        "KALSHI-ACCESS-KEY": api_key,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp
    }

def get_all_data(category, url, headers, sleep_time_in_milliseconds=105):
    """Fetch all data from a paginated endpoint."""
    data = []
    cursor = None
    
    with tqdm(desc=f"Fetching {category}", unit="pages") as pbar:
        while cursor != "":
            url_with_cursor = f"{url}&cursor={cursor}" if cursor else url
            try:
                response = requests.get(url_with_cursor, headers=headers, timeout=10)
                if response.status_code != 200:
                    print(f"Request failed with status {response.status_code}: {response.text}")
                    break
                    
                response_data = response.json()
                cursor = response_data.get("cursor")
                
                if category == "markets":
                    data.extend(response_data.get("markets", []))
                elif category == "trades":
                    data.extend(response_data.get("trades", []))
                elif category == "history":
                    data.extend(response_data.get("history", []))
                elif category == "events":
                    data.extend(response_data.get("events", []))
                
                pbar.update(1)
                time.sleep(sleep_time_in_milliseconds / 1000)
                
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                break
    
    return data

def get_settled_markets(api_key, private_key, categories=["economics", "financials"], limit=10):
    """Get settled markets by category."""
    path = "/markets"
    params = {
        "limit": 1000,
        "status": "settled",
        "sort_by": "settlement_time",
        "order": "desc"
    }
    headers = get_headers(api_key, private_key, "GET", path, params)
    
    markets_by_category = {}
    for category in categories:
        markets_by_category[category] = []
        print(f"\nFetching {category} markets...")
        
        data = get_all_data("markets", f"{BASE_URL}{path}", headers)
        for market in data:
            if market.get("category", "").lower() == category:
                markets_by_category[category].append(market)
                if len(markets_by_category[category]) >= limit:
                    break
    
    return markets_by_category

def get_market_history(api_key, private_key, market, output_file):
    """Get historical data for a specific market."""
    ticker = market["ticker"]
    title = market["title"]
    settlement_time = datetime.fromisoformat(market['settlement_time'].replace('Z', '+00:00'))
    start_time = datetime.fromisoformat(market['start_time'].replace('Z', '+00:00'))
    
    print(f"\nFetching history for {ticker}: {title}")
    print(f"Period: {start_time.strftime('%Y-%m-%d')} to {settlement_time.strftime('%Y-%m-%d')}")
    
    path = f"/markets/{ticker}/history"
    params = {
        "limit": 1000,
        "start_time": start_time.strftime("%Y-%m-%d"),
        "end_time": settlement_time.strftime("%Y-%m-%d")
    }
    headers = get_headers(api_key, private_key, "GET", path, params)
    
    data = get_all_data("history", f"{BASE_URL}{path}", headers)
    
    if data:
        # Write to CSV
        with open(output_file, 'a', newline='', encoding="utf-8") as file:
            file_empty = file.tell() == 0
            writer = csv.DictWriter(file, fieldnames=data[0].keys(), extrasaction='ignore')
            if file_empty:
                writer.writeheader()
            writer.writerows(data)
        print(f"Saved {len(data)} daily records")
    else:
        print("No history data found")

def main():
    """Main function for running the kalshi data collection script."""
    # Get credentials from environment variables
    api_key = os.getenv("KALSHI_API_KEY")
    private_key_pem = os.getenv("KALSHI_PRIVATE_KEY")
    
    if not api_key or not private_key_pem:
        raise ValueError("KALSHI_API_KEY and KALSHI_PRIVATE_KEY must be set in .env file")
    
    # Load the private key
    private_key = load_pem_private_key(private_key_pem.encode(), password=None)
    
    snapshotdate = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Get 10 settled markets per category
    markets_by_category = get_settled_markets(api_key, private_key, categories=["economics", "financials"], limit=10)
    
    # Create output files
    markets_file = f'Kalshi_Settled_Markets_{snapshotdate}.csv'
    history_file = f'Kalshi_Market_History_{snapshotdate}.csv'
    
    # Save markets data
    with open(markets_file, 'w', newline='', encoding="utf-8") as file:
        fieldnames = ['category', 'ticker', 'title', 'settlement_time', 'settlement_value']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        
        for category, markets in markets_by_category.items():
            for market in markets:
                writer.writerow({
                    'category': category,
                    'ticker': market['ticker'],
                    'title': market['title'],
                    'settlement_time': market['settlement_time'],
                    'settlement_value': market.get('settlement_value', '')
                })
    
    # Get history for each market
    for category, markets in markets_by_category.items():
        print(f"\nProcessing {category.upper()} markets:")
        for market in tqdm(markets, desc=f"Fetching {category} history", unit="markets"):
            get_market_history(api_key, private_key, market, history_file)
    
    print(f"\nData saved to:")
    print(f"Markets data: {markets_file}")
    print(f"History data: {history_file}")

# Utility functions for limit orders
def calculate_probability_from_price(price_cents: int) -> float:
    """
    Convert price in cents to probability percentage.
    
    Args:
        price_cents: Price in cents (1-99)
    
    Returns:
        Probability as percentage (0-100)
    """
    return max(0, min(100, price_cents))


def calculate_price_from_probability(probability: float) -> int:
    """
    Convert probability percentage to price in cents.
    
    Args:
        probability: Probability as percentage (0-100)
    
    Returns:
        Price in cents (1-99)
    """
    return max(1, min(99, int(probability)))


def format_order_summary(order_result: Dict[str, Any]) -> str:
    """
    Format order result as a readable summary.
    
    Args:
        order_result: Order result to format
    
    Returns:
        Formatted summary string
    """
    if order_result and 'order' in order_result:
        order = order_result['order']
        order_id = order.get('order_id', 'N/A')
        client_order_id = order.get('client_order_id', 'N/A')
        status = order.get('status', 'N/A')
        
        return (f"✅ Order placed successfully\n"
                f"   Order ID: {order_id}\n"
                f"   Client ID: {client_order_id}\n"
                f"   Status: {status}")
    else:
        return f"❌ Order failed: {order_result.get('error', 'Unknown error')}"


if __name__ == "__main__":
    main()
