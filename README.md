# Poly-Weather Trading Bot

Automated trading bot for temperature prediction markets on Polymarket.

## Features

- **Weather Forecasting Integration**: Uses Weather.com API for accurate temperature predictions
- **Multiple Trading Strategies**:
  - Position Taking: Takes directional positions based on forecasts
  - Market Making: Provides liquidity and captures the spread
- **Real-time Monitoring**: Monitors temperature changes every second on target day
- **Risk Management**: Circuit breakers, position limits, daily loss limits
- **Dry-Run Mode**: Test strategies without risking real money
- **Comprehensive Logging**: Detailed logs for debugging and analysis

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd poly-weather

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API keys and configuration
```

## Configuration

Edit the `.env` file with your settings:

```bash
# Weather API (required)
WEATHER_API_KEY=your_weather_com_api_key

# Polymarket (required for live trading)
POLYMARKET_PRIVATE_KEY=your_private_key_here

# Trading parameters
MAX_POSITION_SIZE=100.0
MAX_DAILY_LOSS=50.0
ENABLE_POSITION_TAKING=true
ENABLE_MARKET_MAKING=false

# Dry run (recommended for testing)
DRY_RUN_MODE=true
DRY_RUN_INITIAL_BALANCE=1000.0
```

## Usage

### Check Bot Status

```bash
python main.py status
```

### Run in Dry-Run Mode (Simulation)

```bash
python main.py run --dry-run
```

### Run in Live Mode (Real Money)

⚠️ **WARNING**: This will trade with real money!

```bash
python main.py run --live
```

### Run Tests

```bash
python main.py test
# or directly:
pytest tests/ -v
```

## How It Works

### State Machine

The bot operates as a state machine with the following states:

1. **SCANNING**: Looking for temperature markets
2. **POSITIONING**: Taking positions J-3 to J-1
3. **MARKET_MAKING**: Providing liquidity with bid/ask pairs
4. **DAY_OF_MONITORING**: Real-time monitoring on target day
5. **WAITING_RESOLUTION**: Waiting for market resolution

### Trading Strategies

#### Position Taking

- Analyzes weather forecasts vs market prices
- Calculates "edge" (confidence - market_price)
- Uses Kelly Criterion for position sizing
- Scales positions based on:
  - Days ahead (J-0: 100%, J-3: 70%)
  - Forecast confidence
  - Current exposure limits

#### Market Making

- Calculates fair value from forecasts
- Places bid/ask pairs around fair value
- Adjusts quotes based on inventory:
  - Long inventory → Lower quotes (encourage selling)
  - Short inventory → Higher quotes (encourage buying)
- Circuit breakers for risk control

### Real-time Monitoring (Day-of)

- Polls Weather.com API every second
- Detects temperature max changes
- Automatically switches positions when temp changes ranges
- Uses market orders for speed

## Project Structure

```
poly-weather/
├── main.py                 # CLI entry point
├── src/
│   ├── bot.py             # Main bot orchestrator
│   ├── clients/           # API clients
│   │   ├── weather.py
│   │   ├── polymarket.py
│   │   └── polymarket_simulator.py
│   ├── config/            # Configuration
│   │   └── settings.py
│   ├── models/            # Data models
│   │   ├── market.py
│   │   └── trade.py
│   ├── strategies/        # Trading strategies
│   │   ├── base.py
│   │   ├── position_taker.py
│   │   └── market_maker.py
│   └── utils/             # Utilities
│       ├── helpers.py
│       ├── logger.py
│       └── realtime_monitor.py
├── tests/                 # Test suite (57 tests)
├── logs/                  # Log files
├── data/                  # Database and cache
└── requirements.txt
```

## Safety Features

- **Dry-Run Mode**: Test without real money
- **Circuit Breakers**: Stop trading on excessive losses
- **Position Limits**: Prevent over-exposure
- **Graceful Shutdown**: Cleanup on Ctrl+C
- **Comprehensive Logging**: Track all actions

## Examples

### Example 1: Test Bot in Dry-Run

```bash
# Run for 5 minutes in dry-run mode
python main.py run --dry-run --duration 300
```

### Example 2: Monitor Specific Market

The bot automatically detects and monitors all active temperature markets for NYC.

### Example 3: Check Performance

Logs are saved in `logs/bot_YYYY-MM-DD.log`. Check them for:
- Trade execution details
- Position updates
- P&L tracking
- Error messages

## Testing

Run the comprehensive test suite:

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_position_taker.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

Current test coverage: **57 tests, 100% passing**

## Risk Disclaimer

⚠️ **IMPORTANT**: This software is for educational purposes. Trading involves risk of loss. Only trade with money you can afford to lose. The authors are not responsible for any financial losses.

- Start with small amounts
- Always test in dry-run mode first
- Understand the risks of prediction markets
- Never share your private keys

## Troubleshooting

### "Module not found" errors

```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Set PYTHONPATH if needed
export PYTHONPATH=.
```

### "API key not set" errors

Check your `.env` file and make sure all required keys are set.

### Bot not finding markets

- Check that markets exist on Polymarket for NYC temperature
- Verify your API keys are working
- Check logs in `logs/` directory

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## License

[MIT License](LICENSE)

## Support

For issues and questions:
- Check the logs in `logs/` directory
- Run `python main.py status` to verify configuration
- Review test output: `pytest tests/ -v`

## Roadmap

- [x] Phase 1: Infrastructure
- [x] Phase 2: Weather client
- [x] Phase 3: Polymarket client
- [x] Phase 4: Position taking strategy
- [x] Phase 5: Market making strategy
- [x] Phase 6: Real-time monitoring
- [x] Phase 7: Bot orchestration
- [ ] Phase 8: Advanced risk management
- [ ] Phase 9: Database persistence
- [ ] Phase 10: Multi-day simulation
- [ ] Phase 11: Web dashboard
- [ ] Phase 12: ML-based predictions

---

Built with ❤️ using Python, Polymarket CLOB API, and Weather.com API
