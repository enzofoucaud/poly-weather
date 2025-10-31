"""
WebSocket client for real-time Polymarket market data.

Based on official Polymarket WebSocket API:
https://docs.polymarket.com/developers/CLOB/websocket/wss-overview
"""

import asyncio
import json
from typing import Callable, List, Dict, Optional, Set
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from ..utils.logger import get_logger

logger = get_logger()


class PolymarketWebSocketClient:
    """
    WebSocket client for real-time Polymarket market updates.

    Connects to Polymarket's market channel to receive:
    - Price changes (real-time)
    - Orderbook updates
    - Last trade prices
    - Tick size changes

    No authentication required for market channel.
    """

    def __init__(
        self,
        on_price_change: Optional[Callable] = None,
        on_book_update: Optional[Callable] = None,
        on_last_trade_price: Optional[Callable] = None,
        on_tick_size_change: Optional[Callable] = None,
        auto_reconnect: bool = True,
        ping_interval: int = 10
    ):
        """
        Initialize WebSocket client.

        Args:
            on_price_change: Callback for price change events
            on_book_update: Callback for orderbook updates
            on_last_trade_price: Callback for last trade price
            on_tick_size_change: Callback for tick size changes
            auto_reconnect: Whether to auto-reconnect on disconnect
            ping_interval: Seconds between PING messages
        """
        self.wss_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

        # Callbacks
        self.on_price_change = on_price_change
        self.on_book_update = on_book_update
        self.on_last_trade_price = on_last_trade_price
        self.on_tick_size_change = on_tick_size_change

        # Connection state
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.subscribed_assets: Set[str] = set()
        self.running = False
        self.connected = False

        # Reconnection
        self.auto_reconnect = auto_reconnect
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        # Ping/pong
        self.ping_interval = ping_interval
        self.ping_task: Optional[asyncio.Task] = None
        self.listen_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Establish WebSocket connection."""
        try:
            logger.info("🔌 Connecting to Polymarket WebSocket...")
            logger.info(f"   URL: {self.wss_url}")

            self.websocket = await websockets.connect(
                self.wss_url,
                ping_interval=None,  # We'll handle pings manually
                close_timeout=10
            )

            self.connected = True
            self.running = True
            self.reconnect_attempts = 0

            logger.info("✅ WebSocket connected!")

            # Start background tasks
            self.listen_task = asyncio.create_task(self._listen())
            self.ping_task = asyncio.create_task(self._ping_loop())

        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            self.connected = False
            raise

    async def subscribe(self, asset_ids: List[str]):
        """
        Subscribe to market updates for specific asset IDs (token IDs).

        Args:
            asset_ids: List of token IDs to monitor
        """
        if not self.websocket or not self.connected:
            raise RuntimeError("WebSocket not connected. Call connect() first.")

        # Build subscription message
        subscription = {
            "assets_ids": asset_ids,
            "type": "market"
        }

        logger.info(f"📊 Subscribing to {len(asset_ids)} asset(s)...")
        logger.debug(f"   Asset IDs: {[aid[:12]+'...' for aid in asset_ids[:5]]}")

        try:
            await self.websocket.send(json.dumps(subscription))

            # Track subscribed assets
            self.subscribed_assets.update(asset_ids)

            logger.info(f"✅ Subscribed to {len(asset_ids)} asset(s) successfully")

        except Exception as e:
            logger.error(f"❌ Subscription failed: {e}")
            raise

    async def _listen(self):
        """Listen for incoming WebSocket messages."""
        logger.info("👂 Listening for WebSocket messages...")

        try:
            async for message in self.websocket:
                await self._handle_message(message)

        except ConnectionClosed as e:
            logger.warning(f"⚠️  WebSocket connection closed: {e}")
            self.connected = False

            if self.auto_reconnect and self.running:
                await self._reconnect()
            else:
                self.running = False

        except WebSocketException as e:
            logger.error(f"❌ WebSocket error: {e}")
            self.connected = False

            if self.auto_reconnect and self.running:
                await self._reconnect()
            else:
                self.running = False

        except Exception as e:
            logger.error(f"❌ Unexpected error in listen loop: {e}")
            self.connected = False
            self.running = False

    async def _handle_message(self, message: str):
        """
        Handle incoming WebSocket message.

        Args:
            message: Raw JSON message string
        """
        try:
            # Ignore PONG responses
            if message == "PONG":
                logger.debug("Received PONG")
                return

            data = json.loads(message)

            # Handle list responses (initial book snapshot)
            if isinstance(data, list):
                logger.debug(f"Received list message with {len(data)} items")
                # Process each item in the list
                for item in data:
                    if isinstance(item, dict):
                        await self._process_event(item)
                return

            # Handle single dict event
            if isinstance(data, dict):
                await self._process_event(data)
                return

            logger.debug(f"Unexpected message type: {type(data)}")

        except json.JSONDecodeError as e:
            # Not JSON - might be PONG or other control message
            logger.debug(f"Non-JSON message: {message[:50]}")

        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    async def _process_event(self, data: Dict):
        """
        Process a single event from WebSocket.

        Args:
            data: Event data dictionary
        """
        try:
            # Get event type
            event_type = data.get("event_type")

            if event_type == "price_change":
                await self._handle_price_change(data)

            elif event_type == "book":
                await self._handle_book(data)

            elif event_type == "last_trade_price":
                await self._handle_last_trade_price(data)

            elif event_type == "tick_size_change":
                await self._handle_tick_size_change(data)

            else:
                logger.debug(f"Unknown event type: {event_type}")

        except Exception as e:
            logger.error(f"Error processing event: {e}")

    async def _handle_price_change(self, data: Dict):
        """
        Handle price change event.

        Message structure:
        {
            "event_type": "price_change",
            "asset_id": "...",
            "changes": [
                {
                    "price": "0.52",
                    "size": "100.5",
                    "side": "BUY",
                    "order_hash": "..."
                }
            ],
            "best_bid": "0.51",
            "best_ask": "0.53",
            "timestamp": 1234567890
        }
        """
        asset_id = data.get("asset_id", "unknown")
        changes = data.get("changes", [])
        best_bid = data.get("best_bid")
        best_ask = data.get("best_ask")

        logger.info(f"💰 Price Change: {asset_id[:12]}...")
        logger.info(f"   Best Bid: ${best_bid} | Best Ask: ${best_ask}")
        logger.info(f"   Changes: {len(changes)} update(s)")

        # Call user callback
        if self.on_price_change:
            try:
                if asyncio.iscoroutinefunction(self.on_price_change):
                    await self.on_price_change(data)
                else:
                    self.on_price_change(data)
            except Exception as e:
                logger.error(f"Error in price_change callback: {e}")

    async def _handle_book(self, data: Dict):
        """
        Handle orderbook update.

        Message structure:
        {
            "event_type": "book",
            "asset_id": "...",
            "market": "...",
            "bids": [{"price": "0.50", "size": "100"}, ...],
            "asks": [{"price": "0.52", "size": "50"}, ...],
            "timestamp": 1234567890
        }
        """
        asset_id = data.get("asset_id", "unknown")
        bids = data.get("bids", [])
        asks = data.get("asks", [])

        logger.debug(f"📖 Book Update: {asset_id[:12]}...")
        logger.debug(f"   Bids: {len(bids)} levels | Asks: {len(asks)} levels")

        # Call user callback
        if self.on_book_update:
            try:
                if asyncio.iscoroutinefunction(self.on_book_update):
                    await self.on_book_update(data)
                else:
                    self.on_book_update(data)
            except Exception as e:
                logger.error(f"Error in book_update callback: {e}")

    async def _handle_last_trade_price(self, data: Dict):
        """
        Handle last trade price event.

        Message structure:
        {
            "event_type": "last_trade_price",
            "asset_id": "...",
            "price": "0.51",
            "side": "BUY",
            "size": "25.5",
            "fee_rate_bps": "20",
            "timestamp": 1234567890
        }
        """
        asset_id = data.get("asset_id", "unknown")
        price = data.get("price")
        size = data.get("size")
        side = data.get("side")

        logger.info(f"🔄 Trade: {asset_id[:12]}... @ ${price} ({side} {size})")

        # Call user callback
        if self.on_last_trade_price:
            try:
                if asyncio.iscoroutinefunction(self.on_last_trade_price):
                    await self.on_last_trade_price(data)
                else:
                    self.on_last_trade_price(data)
            except Exception as e:
                logger.error(f"Error in last_trade_price callback: {e}")

    async def _handle_tick_size_change(self, data: Dict):
        """Handle tick size change event."""
        asset_id = data.get("asset_id", "unknown")
        old_tick = data.get("old_tick_size")
        new_tick = data.get("new_tick_size")

        logger.info(f"📏 Tick Size Change: {asset_id[:12]}...")
        logger.info(f"   {old_tick} → {new_tick}")

        # Call user callback
        if self.on_tick_size_change:
            try:
                if asyncio.iscoroutinefunction(self.on_tick_size_change):
                    await self.on_tick_size_change(data)
                else:
                    self.on_tick_size_change(data)
            except Exception as e:
                logger.error(f"Error in tick_size_change callback: {e}")

    async def _ping_loop(self):
        """Send PING messages to keep connection alive."""
        logger.debug(f"🏓 Starting ping loop (interval: {self.ping_interval}s)")

        try:
            while self.running and self.connected:
                await asyncio.sleep(self.ping_interval)

                if self.websocket and self.connected:
                    try:
                        await self.websocket.send("PING")
                        logger.debug("🏓 PING sent")
                    except Exception as e:
                        logger.warning(f"Failed to send PING: {e}")
                        break

        except asyncio.CancelledError:
            logger.debug("Ping loop cancelled")

    async def _reconnect(self):
        """Attempt to reconnect to WebSocket with exponential backoff."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"❌ Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            self.running = False
            return

        self.reconnect_attempts += 1
        backoff = min(2 ** self.reconnect_attempts, 60)  # Max 60 seconds

        logger.info(f"🔄 Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")
        logger.info(f"   Waiting {backoff}s before reconnect...")

        await asyncio.sleep(backoff)

        try:
            # Close old connection if exists
            if self.websocket:
                await self.websocket.close()

            # Reconnect
            await self.connect()

            # Re-subscribe to previous assets
            if self.subscribed_assets:
                logger.info(f"Re-subscribing to {len(self.subscribed_assets)} asset(s)...")
                await self.subscribe(list(self.subscribed_assets))

            logger.info("✅ Reconnected successfully!")

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")

            if self.auto_reconnect and self.running:
                # Try again
                await self._reconnect()
            else:
                self.running = False

    async def disconnect(self):
        """Close WebSocket connection gracefully."""
        logger.info("🔌 Disconnecting WebSocket...")

        self.running = False
        self.connected = False

        # Cancel background tasks
        if self.ping_task and not self.ping_task.done():
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass

        if self.listen_task and not self.listen_task.done():
            self.listen_task.cancel()
            try:
                await self.listen_task
            except asyncio.CancelledError:
                pass

        # Close connection
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        self.subscribed_assets.clear()

        logger.info("✅ WebSocket disconnected")

    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.connected and self.websocket is not None

    def get_subscribed_assets(self) -> List[str]:
        """Get list of currently subscribed asset IDs."""
        return list(self.subscribed_assets)
