"""
WebSocket thread wrapper for running async WebSocket in a sync context.
"""

import asyncio
import threading
from typing import Callable, List, Optional
from ..clients.polymarket_ws import PolymarketWebSocketClient
from ..utils.logger import get_logger

logger = get_logger()


class WebSocketThread:
    """
    Wrapper to run WebSocket client in a separate thread with its own event loop.

    This allows us to integrate async WebSocket into a synchronous bot architecture.
    """

    def __init__(
        self,
        on_price_change: Optional[Callable] = None,
        on_book_update: Optional[Callable] = None,
        ping_interval: int = 10
    ):
        """
        Initialize WebSocket thread.

        Args:
            on_price_change: Sync callback for price changes
            on_book_update: Sync callback for book updates
            ping_interval: PING interval in seconds
        """
        self.on_price_change = on_price_change
        self.on_book_update = on_book_update
        self.ping_interval = ping_interval

        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.client: Optional[PolymarketWebSocketClient] = None
        self.running = False

    def start(self):
        """Start WebSocket thread."""
        if self.running:
            logger.warning("WebSocket thread already running")
            return

        logger.info("🚀 Starting WebSocket thread...")

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        # Wait a bit for connection
        import time
        time.sleep(2)

        logger.info("✅ WebSocket thread started")

    def _run_loop(self):
        """Run async event loop in thread."""
        try:
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # Create WebSocket client
            self.client = PolymarketWebSocketClient(
                on_price_change=self.on_price_change,
                on_book_update=self.on_book_update,
                ping_interval=self.ping_interval
            )

            # Run until stopped
            self.loop.run_until_complete(self._async_run())

        except Exception as e:
            logger.error(f"❌ WebSocket thread error: {e}")
            self.running = False

        finally:
            if self.loop:
                self.loop.close()

    async def _async_run(self):
        """Async main loop for WebSocket."""
        try:
            # Connect
            await self.client.connect()

            # Keep running
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"WebSocket async error: {e}")

        finally:
            if self.client:
                await self.client.disconnect()

    def subscribe(self, asset_ids: List[str]):
        """
        Subscribe to asset IDs (thread-safe).

        Args:
            asset_ids: List of token IDs to monitor
        """
        if not self.loop or not self.client:
            logger.warning("WebSocket not ready, cannot subscribe")
            return

        # Schedule coroutine in WebSocket thread's event loop
        future = asyncio.run_coroutine_threadsafe(
            self.client.subscribe(asset_ids),
            self.loop
        )

        # Wait for subscription to complete (with timeout)
        try:
            future.result(timeout=5)
            logger.info(f"✅ Subscribed to {len(asset_ids)} assets via WebSocket")
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")

    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.client is not None and self.client.is_connected()

    def stop(self):
        """Stop WebSocket thread."""
        logger.info("🛑 Stopping WebSocket thread...")

        self.running = False

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

        logger.info("✅ WebSocket thread stopped")
