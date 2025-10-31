#!/usr/bin/env python3
"""
Test automatic market discovery.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.clients.market_discovery import MarketDiscovery

def main():
    print("Testing automatic market discovery...")
    print("=" * 70)

    # Create discovery client
    discovery = MarketDiscovery(city="NYC")

    # Discover markets for next 7 days
    print("\nDiscovering temperature markets for NYC (next 7 days):")
    print("-" * 70)

    events = discovery.discover_temperature_events(days_ahead=7, active_only=True)

    if not events:
        print("❌ No markets found!")
        print("\nThis could mean:")
        print("  1. No active temperature markets on Polymarket right now")
        print("  2. API connection issue")
        print("  3. Market naming has changed")
        return

    print(f"\n✅ Found {len(events)} temperature event(s):\n")

    for i, evt in enumerate(events, 1):
        print(f"{i}. {evt['title']}")
        print(f"   Slug: {evt['slug']}")
        print(f"   Target Date: {evt['target_date'].strftime('%Y-%m-%d')} (J-{evt['days_until']})")
        print(f"   Status: {'Active' if evt['active'] else 'Closed'}")
        print(f"   Volume 24h: ${evt['volume_24h']:,.2f}")
        print(f"   Markets: {evt['markets_count']} outcomes")
        print()

    # Get just the slugs
    print("=" * 70)
    slugs = [evt['slug'] for evt in events]
    print(f"\nEvent slugs to use in .env:")
    print(f"EVENT_SLUGS={','.join(slugs)}")

    print("\n💡 Or leave EVENT_SLUGS empty for automatic discovery!")

if __name__ == "__main__":
    main()
