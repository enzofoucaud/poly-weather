#!/usr/bin/env python3
"""
Test bot with WebSocket integration.

This test forces WebSocket to be enabled even in dry-run mode
to verify the integration works correctly.
"""

import os
import sys

# Force WebSocket to be enabled
os.environ['USE_WEBSOCKET'] = 'true'
os.environ['DRY_RUN_MODE'] = 'true'

sys.path.insert(0, os.path.dirname(__file__))

from src.bot import TradingBot
from src.utils.logger import get_logger

logger = get_logger()


def main():
    logger.info("="*70)
    logger.info("Testing Bot with WebSocket Integration")
    logger.info("="*70)
    logger.info("This test will:")
    logger.info("  1. Start bot in dry-run mode")
    logger.info("  2. Force WebSocket to be enabled (bypassing dry-run check)")
    logger.info("  3. Connect to Polymarket WebSocket")
    logger.info("  4. Subscribe to market tokens")
    logger.info("  5. Listen for real-time price updates for 60 seconds")
    logger.info("="*70 + "\n")

    # Create bot
    bot = TradingBot(dry_run=True)

    # OVERRIDE: Force enable WebSocket even in dry-run for testing
    if not bot.ws_thread:
        logger.info("🔧 Overriding dry-run mode to test WebSocket...")
        from src.utils.websocket_thread import WebSocketThread

        bot.ws_thread = WebSocketThread(
            on_price_change=bot._on_price_change,
            on_book_update=None,
            ping_interval=bot.settings.ws_ping_interval
        )
        logger.info("✅ WebSocket thread created for testing")

    # Run bot for 60 seconds
    try:
        # Start WebSocket
        if bot.ws_thread:
            bot.ws_thread.start()
            logger.info("✅ WebSocket started")

        # Run one iteration to discover markets and subscribe
        logger.info("\n🔍 Discovering markets and subscribing to WebSocket...")
        markets = bot.scan_markets()

        if markets:
            logger.info(f"✅ Found {len(markets)} market(s)")

            # Wait for WebSocket messages
            import time
            logger.info("\n⏰ Listening for WebSocket updates for 60 seconds...")
            logger.info("   (You should see real-time price updates below)\n")

            time.sleep(60)

        else:
            logger.warning("No markets found")

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")

    finally:
        # Stop WebSocket
        if bot.ws_thread:
            logger.info("\n🛑 Stopping WebSocket...")
            bot.ws_thread.stop()

        logger.info("✅ Test complete!")


if __name__ == "__main__":
    main()
