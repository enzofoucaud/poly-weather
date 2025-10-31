#!/usr/bin/env python3
"""Quick test to see if we can fetch markets."""

import requests

# Test Gamma API
url = "https://gamma-api.polymarket.com/markets"
params = {
    "limit": 100,
    # Try without closed filter
}

print("Fetching markets from Gamma API...")
response = requests.get(url, params=params, timeout=10)
print(f"Status: {response.status_code}")

markets = response.json()
print(f"Found {len(markets)} markets")

# Look for temperature OR NYC markets
temp_markets = [m for m in markets if "temperature" in m.get("question", "").lower() or "nyc" in m.get("question", "").lower()]
print(f"\nTemperature/NYC markets: {len(temp_markets)}")

for market in temp_markets[:3]:
    print(f"\n  - {market.get('question')}")
    print(f"    Outcomes: {market.get('outcomes', [])}")
    print(f"    Prices: {market.get('outcomePrices', [])}")
    print(f"    Closed: {market.get('closed', False)}")
