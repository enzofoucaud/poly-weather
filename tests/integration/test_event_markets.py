#!/usr/bin/env python3
"""
Quick test to verify event-based market discovery.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.clients.polymarket import PolymarketClient

def main():
    print("Testing event-based market discovery...")
    print("=" * 60)

    # Use dummy private key for dry-run mode
    dummy_key = "0x" + "0" * 64

    client = PolymarketClient(
        private_key=dummy_key,
        chain_id=137,
        dry_run=True
    )

    # Test with specific event slug
    event_slug = "highest-temperature-in-nyc-on-october-30"
    print(f"\nFetching markets for event: {event_slug}")
    print("-" * 60)

    markets = client.get_temperature_markets(
        city="NYC",
        active_only=False,
        event_slug=event_slug
    )

    print(f"\nFound {len(markets)} market(s)")

    for market in markets:
        print(f"\nMarket: {market.question}")
        print(f"Market ID: {market.market_id}")
        print(f"Target Date: {market.target_date}")
        print(f"Resolved: {market.resolved}")
        print(f"Volume 24h: ${market.volume_24h:,.2f}")
        print(f"Liquidity: ${market.liquidity:,.2f}")
        print(f"\nOutcomes ({len(market.outcomes)}):")

        for outcome in market.outcomes:
            print(f"  {outcome.temperature_range.label}: ${outcome.price:.3f}")
            print(f"    Token ID: {outcome.token_id}")
            print(f"    Volume 24h: ${outcome.volume_24h:,.2f}")

if __name__ == "__main__":
    main()
