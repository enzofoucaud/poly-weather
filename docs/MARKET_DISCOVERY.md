# Market Discovery Guide

This guide explains how to configure the bot to find and trade on specific Polymarket temperature markets.

## Two Methods for Market Discovery

### Method 1: Event Slug (Recommended)

The most reliable way to target a specific temperature market is to use its event slug. This directly accesses the market you want to trade on.

#### How to find the event slug:

1. Go to the Polymarket event URL, e.g.:
   ```
   https://polymarket.com/event/highest-temperature-in-nyc-on-october-30
   ```

2. The event slug is the last part of the URL:
   ```
   highest-temperature-in-nyc-on-october-30
   ```

3. Add this to your `.env` file:
   ```bash
   EVENT_SLUG=highest-temperature-in-nyc-on-october-30
   ```

4. The bot will now target this specific event with all its temperature outcomes.

#### Example .env configuration:

```bash
# Market Discovery
TARGET_CITY=NYC
EVENT_SLUG=highest-temperature-in-nyc-on-october-30

# The bot will now trade on this specific market
```

### Method 2: General Search

If you don't specify an `EVENT_SLUG`, the bot will search for all temperature markets matching the `TARGET_CITY`.

```bash
# Market Discovery
TARGET_CITY=NYC
EVENT_SLUG=

# The bot will search for any NYC temperature markets
```

**Note:** General search may not find all markets, especially newer ones, as the Gamma API only returns the top 100 markets by some ranking criteria.

## How It Works

### Event-Based Discovery (Method 1)

When you provide an `EVENT_SLUG`:

1. The bot calls the Gamma API events endpoint:
   ```
   https://gamma-api.polymarket.com/events?slug=highest-temperature-in-nyc-on-october-30
   ```

2. This returns all individual markets within the event (e.g., "54°F or below", "55-56°F", etc.)

3. The bot combines these into a single `TemperatureMarket` object with multiple outcomes

4. Each outcome has:
   - Temperature range (min/max)
   - Current price
   - Token ID (for placing orders)
   - Volume and liquidity data

### Market Data Structure

A temperature market event typically has 7 outcomes:
- **54°F or below** (min_temp=None, max_temp=54)
- **55-56°F** (min_temp=55, max_temp=56)
- **57-58°F** (min_temp=57, max_temp=58)
- **59-60°F** (min_temp=59, max_temp=60)
- **61-62°F** (min_temp=61, max_temp=62)
- **63-64°F** (min_temp=63, max_temp=64)
- **65°F or higher** (min_temp=65, max_temp=None)

## Testing Market Discovery

To verify your configuration works:

```bash
# Activate virtual environment
source venv/bin/activate

# Run the test script
python test_event_markets.py
```

This will show you:
- The market question
- Target date
- All temperature outcomes with current prices
- Token IDs for trading
- Volume and liquidity data

## Troubleshooting

### "0 active markets" error

**Solution:** Use Method 1 (Event Slug)

The general search (Method 2) may not find your market if it's not in the top 100 markets on Polymarket. Using the event slug directly accesses the specific market.

### "Failed to parse temperature range" warning

This usually happens with custom temperature ranges. The bot supports:
- Standard ranges: "55-56°F", "60-61°F"
- Lower bound: "54°F or below", "60 or lower"
- Upper bound: "65°F or higher", "70 or above"

### "Invalid date" in market

The bot tries two methods to get the target date:
1. Parse from the API's `endDate` field (most reliable)
2. Parse from the market question text

If both fail, it defaults to the current date. Check that your event has proper date information.

## Example: Finding Tomorrow's NYC Temperature Market

1. Go to Polymarket and find the temperature market for tomorrow
2. Copy the event URL: `https://polymarket.com/event/highest-temperature-in-nyc-on-november-1`
3. Extract the slug: `highest-temperature-in-nyc-on-november-1`
4. Update `.env`:
   ```bash
   EVENT_SLUG=highest-temperature-in-nyc-on-november-1
   ```
5. Run the bot:
   ```bash
   python main.py run
   ```

The bot will now:
- Fetch weather forecasts for November 1
- Analyze all temperature outcomes
- Calculate edge based on forecast vs market prices
- Execute trades according to your strategies

## Advanced: Multiple Markets

Currently, the bot is designed to focus on one market at a time. To trade multiple markets:

1. Run separate bot instances with different `.env` files
2. Or modify the bot to accept a list of event slugs

Future updates may include multi-market support in a single bot instance.
