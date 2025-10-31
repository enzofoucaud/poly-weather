# Quick Start Guide

## Running the Bot with Real Markets

Now that the market discovery is working, here's how to run the bot:

### Step 1: Configure for a Specific Market

Edit your `.env` file (or create one from `.env.example`):

```bash
# Copy the example if you don't have a .env yet
cp .env.example .env
```

Then edit `.env` and set:

```bash
# Find a temperature market on Polymarket
# Example: https://polymarket.com/event/highest-temperature-in-nyc-on-november-1
EVENT_SLUG=highest-temperature-in-nyc-on-november-1

# Keep dry run mode enabled for testing
DRY_RUN_MODE=true

# Your Weather.com API key
WEATHER_API_KEY=your_api_key_here

# Enable position taking strategy
ENABLE_POSITION_TAKING=true
ENABLE_MARKET_MAKING=false
```

### Step 2: Test Market Discovery

First, verify the bot can find your market:

```bash
source venv/bin/activate
python test_event_markets.py
```

You should see output showing:
- The market question
- Target date
- All temperature outcomes with prices
- Token IDs for each outcome

### Step 3: Run in Dry-Run Mode

Test the full bot logic without real money:

```bash
source venv/bin/activate
python main.py run
```

The bot will:
1. **SCANNING**: Find temperature markets using your EVENT_SLUG
2. **Get forecasts**: Fetch weather data for the target date
3. **POSITIONING**: Analyze each outcome and calculate edge
4. **Execute trades**: Simulate orders (no real money in dry-run)

Press Ctrl+C to stop.

### Step 4: Monitor the Output

Watch for these key log messages:

```
✅ Good signs:
- "Found 1 temperature markets"
- "Analyzing market: Highest temperature in NYC..."
- "Forecast confidence: XX% for YY°F"
- "Edge detected: X.XX for outcome ZZ°F"
- "[DRY RUN] Order placed: BUY..."

❌ Issues to check:
- "Found 0 active markets" → Check your EVENT_SLUG
- "Failed to get forecast" → Check your WEATHER_API_KEY
- "No edge detected" → Market prices match forecast (normal)
```

### Step 5: Understanding the Strategy

The **Position Taking** strategy works as follows:

1. **Get Weather Forecast**: Fetch the predicted high temperature
2. **Calculate Confidence**: Higher confidence for nearer dates
3. **Find Edge**: Compare forecast probability vs market price
4. **Size Position**: Use Kelly Criterion (25% fraction) for sizing
5. **Place Order**: Buy the outcome with positive edge

Example:
```
Forecast: 62°F with 80% confidence
Market prices:
  - 59-60°F: $0.10 (10%)
  - 61-62°F: $0.25 (25%)  ← Our forecast says 80%!
  - 63-64°F: $0.40 (40%)

Edge = 0.80 - 0.25 = 0.55 (55% edge!)
→ Bot places BUY order for 61-62°F
```

### Step 6: Check Results

View logs:
```bash
# Main log
tail -f logs/bot.log

# Trade log
tail -f logs/trades.log

# Position log
tail -f logs/positions.log
```

### Step 7: Go Live (When Ready)

⚠️ **IMPORTANT**: Only do this when you're comfortable with the strategy!

1. **Get USDC on Polygon**: Transfer USDC to your wallet on Polygon network
2. **Export Private Key**: From your wallet (e.g., MetaMask)
3. **Update .env**:
   ```bash
   DRY_RUN_MODE=false
   POLYMARKET_PRIVATE_KEY=0xYourActualPrivateKeyHere
   ```
4. **Start with Small Position Sizes**:
   ```bash
   MAX_POSITION_SIZE=10.0  # Start with $10
   MAX_EXPOSURE_PER_MARKET=30.0  # Max $30 per market
   ```
5. **Run the bot**:
   ```bash
   python main.py run
   ```

The bot will now place REAL orders!

## Advanced Usage

### Running for a Specific Duration

Test for 5 minutes:
```bash
python main.py run --duration 300
```

### Checking Bot Status

```bash
python main.py status
```

Shows:
- Current balance
- Open positions
- Daily P&L
- Recent trades

### Simulating with Mock Data

If you don't have a Weather API key:
```bash
python main.py simulate --days 1
```

### Testing Configuration

Validate your settings:
```bash
python main.py test
```

## Troubleshooting

### "ModuleNotFoundError"
```bash
# Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt
```

### "Invalid private key"
In dry-run mode, use dummy key:
```bash
POLYMARKET_PRIVATE_KEY=0x0000000000000000000000000000000000000000000000000000000000000000
```

### "Forecast confidence too low"
This is normal if the target date is far away. The bot scales down positions for distant dates:
- J-0 (target day): 100% position size
- J-1: 85% position size
- J-2: 70% position size
- J-3: 50% position size

### "No edge detected"
The market prices align with the forecast. This is normal and healthy - it means the market is efficient!

## Safety Tips

1. **Always test in dry-run first**
2. **Start with small position sizes**
3. **Monitor daily loss limits**
4. **Never share your private key**
5. **Keep your .env file secure** (it's in .gitignore)
6. **Review the code** before going live
7. **Understand the risks** of prediction markets

## Next Steps

- Read [MARKET_DISCOVERY.md](MARKET_DISCOVERY.md) for details on finding markets
- Review [PLAN.md](PLAN.md) to see the full development plan
- Check the code in `src/` to understand how it works
- Consider implementing Phase 8+ features (risk management, database, dashboard)

Happy trading! 🚀
