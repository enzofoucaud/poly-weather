#!/usr/bin/env python3
"""
Test WebSocket connection to Polymarket.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.clients.polymarket_ws import PolymarketWebSocketClient


async def on_price_change(data):
    """Handle price change events."""
    asset_id = data.get("asset_id", "")[:20]
    best_bid = data.get("best_bid", "N/A")
    best_ask = data.get("best_ask", "N/A")
    print(f"\n💰 PRICE CHANGE")
    print(f"   Asset: {asset_id}...")
    print(f"   Bid: ${best_bid} | Ask: ${best_ask}")


async def on_book_update(data):
    """Handle orderbook updates."""
    asset_id = data.get("asset_id", "")[:20]
    bids = len(data.get("bids", []))
    asks = len(data.get("asks", []))
    print(f"\n📖 BOOK UPDATE")
    print(f"   Asset: {asset_id}...")
    print(f"   {bids} bid levels | {asks} ask levels")


async def on_trade(data):
    """Handle trade events."""
    asset_id = data.get("asset_id", "")[:20]
    price = data.get("price", "N/A")
    size = data.get("size", "N/A")
    side = data.get("side", "?")
    print(f"\n🔄 TRADE")
    print(f"   Asset: {asset_id}...")
    print(f"   {side} {size} @ ${price}")


async def main():
    print("=" * 70)
    print("Polymarket WebSocket Test")
    print("=" * 70)
    print("\nThis will connect to Polymarket WebSocket and subscribe to a test market.")
    print("Press Ctrl+C to stop.\n")

    # Example token IDs from a real market
    # (These are from the NYC temperature market - Oct 31)
    test_token_ids = [
        "34919197246921245897352242364111078848037274258358966114693891075682045601613",  # 50°F or below
        "82852309585748730744698897838131415368049210211740012961535778086395027169690",  # 51-52°F
    ]

    # Create WebSocket client
    client = PolymarketWebSocketClient(
        on_price_change=on_price_change,
        on_book_update=on_book_update,
        on_last_trade_price=on_trade,
        auto_reconnect=True,
        ping_interval=10
    )

    try:
        # Connect
        print("📡 Connecting to WebSocket...")
        await client.connect()

        # Subscribe to test tokens
        print(f"\n📊 Subscribing to {len(test_token_ids)} token(s)...")
        await client.subscribe(test_token_ids)

        print("\n✅ Subscribed! Listening for updates...")
        print("   (This may take a few seconds for first message)\n")

        # Keep running
        while client.is_connected():
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n🔌 Disconnecting...")
        await client.disconnect()
        print("✅ Disconnected")


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
