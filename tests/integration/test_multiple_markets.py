#!/usr/bin/env python3
"""
Test fetching multiple temperature markets.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.clients.polymarket_simulator import PolymarketSimulator

def main():
    print("Testing multiple event markets...")
    print("=" * 60)

    # Create simulator
    sim = PolymarketSimulator()

    # Test with the October 31 market
    print("\n1. Testing October 31 market:")
    print("-" * 60)
    markets_oct31 = sim.get_temperature_markets(
        city="NYC",
        active_only=False,
        event_slug="highest-temperature-in-nyc-on-october-31"
    )
    print(f"Found {len(markets_oct31)} market(s)")
    for m in markets_oct31:
        print(f"  - {m.question}")
        print(f"    Target: {m.target_date}")
        print(f"    Outcomes: {len(m.outcomes)}")

    # Test with the November 1 market
    print("\n2. Testing November 1 market:")
    print("-" * 60)
    markets_nov1 = sim.get_temperature_markets(
        city="NYC",
        active_only=False,
        event_slug="highest-temperature-in-nyc-on-november-1"
    )
    print(f"Found {len(markets_nov1)} market(s)")
    for m in markets_nov1:
        print(f"  - {m.question}")
        print(f"    Target: {m.target_date}")
        print(f"    Outcomes: {len(m.outcomes)}")

    # Summary
    print("\n" + "=" * 60)
    print(f"Total markets found: {len(markets_oct31) + len(markets_nov1)}")
    print("\nTo trade both markets, add to your .env:")
    print("EVENT_SLUGS=highest-temperature-in-nyc-on-october-31,highest-temperature-in-nyc-on-november-1")

if __name__ == "__main__":
    main()
