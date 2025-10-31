# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Poly-Weather** is an automated trading bot for temperature prediction markets on Polymarket. It uses weather forecasts from Weather.com to take positions and provide market-making liquidity on Polygon blockchain.

**Architecture**: 100% async Python bot with WebSocket real-time updates, state machine orchestration, and dual trading strategies (position taking + market making).

---

## Commands

### Development Setup

```bash
# Virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set PYTHONPATH for imports
export PYTHONPATH=.
```

### Running the Bot

```bash
# Check configuration status
python main.py status

# Run in dry-run mode (simulation, no real money)
python main.py run --dry-run

# Run in live mode (REAL MONEY - requires confirmation)
python main.py run --live

# Run for limited time (useful for testing)
python main.py run --dry-run --duration 300  # 5 minutes
```

### Testing

```bash
# Run all tests using helper script (RECOMMENDED)
./run_tests.sh all

# Unit tests only (fast, ~2.5s, 57 tests)
./run_tests.sh unit
pytest tests/unit/ -v

# Integration tests (slower, 15s-2min, 6 tests, requires API keys)
./run_tests.sh integration
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_position_taker.py -v

# With coverage
./run_tests.sh coverage
```

### Integration Tests (Real API Calls)

Integration tests require setting PYTHONPATH and may run standalone:

```bash
export PYTHONPATH=/home/enzo/go/src/poly-weather
python tests/integration/test_websocket.py
python tests/integration/test_markets.py
```

---

## Architecture

### Async Event Loop Model

The bot uses a **100% async architecture** (migrated from hybrid sync/async):

- **Single asyncio event loop** runs all components
- **All I/O operations are async**: HTTP clients (aiohttp), WebSocket, Polymarket CLOB calls (wrapped with asyncio.to_thread)
- **Entry point**: `main.py` → `bot.run()` (sync wrapper) → `asyncio.run(run_main_loop())`

### Core Components Flow

```
main.py (CLI)
    ↓
TradingBot.run() [sync wrapper]
    ↓
asyncio.run(run_main_loop()) [async event loop]
    ↓
    ├─→ scan_markets() [async]
    │     └─→ PolymarketClient.get_temperature_markets() [async]
    │
    ├─→ get_forecast_for_market() [async]
    │     └─→ WeatherClient.get_forecast_with_confidence() [async]
    │
    ├─→ handle_positioning() [async]
    │     ├─→ PositionTakerStrategy.analyze_market() [async]
    │     └─→ strategy.execute_order() [async]
    │           └─→ PolymarketClient.place_order() [async]
    │
    └─→ handle_market_making() [async]
          └─→ MarketMakerStrategy methods [async]
```

### State Machine

The bot operates as a state machine (`BotState` enum in `src/bot.py`):

1. **SCANNING**: Discovering temperature markets (auto-discovery or manual slugs)
2. **POSITIONING**: Taking directional positions (J-3 to J-1 days before target)
3. **MARKET_MAKING**: Providing bid/ask liquidity to capture spread
4. **DAY_OF_MONITORING**: Real-time monitoring on target day (polls every second)
5. **WAITING_RESOLUTION**: Market ended, waiting for resolution

State transitions happen based on `days_until_target()`:
- J-3 to J-1: POSITIONING
- J-0 (target day): DAY_OF_MONITORING
- Past target: WAITING_RESOLUTION

### Client Architecture

**WeatherClient** (`src/clients/weather.py`):
- Fully async using `aiohttp`
- Methods: `get_forecast()`, `get_historical_today()`, `get_forecast_with_confidence()`
- Uses Weather.com API with LaGuardia coordinates for NYC

**PolymarketClient** (`src/clients/polymarket.py`):
- Fully async hybrid:
  - HTTP methods use `aiohttp`: `_search_events()`, `_search_markets()`, `get_temperature_markets()`
  - CLOB methods wrapped with `asyncio.to_thread()`: `place_order()`, `cancel_order()`, `get_positions()`
- Uses `py-clob-client` for Polygon blockchain interactions

**PolymarketSimulator** (`src/clients/polymarket_simulator.py`):
- Matches PolymarketClient async interface
- Used in dry-run mode (no real transactions)
- Simulates fills, tracks P&L, manages virtual balance

**WebSocket Integration** (`src/clients/polymarket_ws.py` + `src/utils/websocket_thread.py`):
- Real-time price updates (<1s latency, 60x faster than polling)
- Runs in separate thread (WebSocketThread wrapper) with its own event loop
- Communicates via callbacks to main bot (`_on_price_change`)

### Strategy Architecture

**BaseStrategy** (`src/strategies/base.py`):
- Abstract base with async methods: `analyze_market()`, `should_adjust_position()`, `execute_order()`, `update_positions()`

**PositionTakerStrategy** (`src/strategies/position_taker.py`):
- Takes directional positions based on forecast vs market price "edge"
- Uses Kelly Criterion for position sizing
- Scales positions by confidence and days ahead

**MarketMakerStrategy** (`src/strategies/market_maker.py`):
- Places bid/ask pairs around fair value (derived from forecast)
- Adjusts quotes based on inventory (long → lower quotes, short → higher)
- Circuit breakers for risk control

---

## Important Patterns

### Async Method Signatures

When adding new I/O operations, always use async:

```python
# HTTP calls
async def fetch_data(self):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Calling other async methods
async def process(self):
    data = await self.fetch_data()
    result = await self.analyze(data)
    return result

# Wrapping sync CLOB calls
async def place_order(self, order):
    result = await asyncio.to_thread(self.client.create_order, order_args)
    return result
```

### Configuration with Pydantic

All settings use Pydantic validation (`src/config/settings.py`):

```python
from src.config.settings import get_settings
settings = get_settings()
# Access: settings.max_position_size, settings.weather_api_key, etc.
```

Settings are loaded from `.env` file with validation and type checking.

### Logging Pattern

Use structured logging with `loguru`:

```python
from src.utils.logger import get_logger, log_trade, log_market_analysis

logger = get_logger()
logger.info(f"Processing market {market_id}")
logger.error(f"Failed to fetch: {e}", exc_info=True)

# Structured logs for trades
log_trade(
    action="BUY",
    market_id=market.market_id,
    outcome_id=outcome.token_id,
    price=0.45,
    size=100.0,
    details={"order_id": "abc123"}
)
```

### Market Discovery

Three modes (handled in `scan_markets()`):

1. **Manual single slug**: `EVENT_SLUG=highest-temperature-in-nyc-on-october-30`
2. **Manual multiple slugs**: `EVENT_SLUGS=slug1,slug2,slug3`
3. **Auto-discovery** (default): Uses `MarketDiscovery` to find markets for next N days

Auto-discovery pattern: "highest-temperature-in-{city}-on-{month}-{day}"

### Real-time Monitoring (Day-of)

When target day arrives, bot enters DAY_OF_MONITORING state:

- Polls Weather.com every second for current max temperature
- Detects when temperature crosses into new range
- Automatically switches positions using market orders
- Runs in separate thread (`RealtimeMonitor` with `PositionAdjuster`)

---

## Testing Patterns

### Unit Tests (tests/unit/)

- Mock all external API calls
- Fast execution (~2.5s for 57 tests)
- Use pytest fixtures for reusable components
- Example pattern:

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_weather_client():
    client = Mock()
    client.get_forecast.return_value = [...]
    return client

def test_strategy(mock_weather_client):
    strategy = PositionTakerStrategy(client=mock_client)
    result = await strategy.analyze_market(market, forecast)
    assert result is not None
```

### Integration Tests (tests/integration/)

- Make real API calls
- Require `PYTHONPATH` environment variable
- Run standalone or via pytest
- May take 15-60 seconds
- Test WebSocket connections, market discovery, etc.

---

## Common Modifications

### Adding a New Strategy

1. Extend `BaseStrategy` in `src/strategies/`
2. Implement async methods: `analyze_market()`, `should_adjust_position()`
3. Add strategy initialization in `TradingBot._init_strategies()`
4. Write unit tests in `tests/unit/`

### Adding a New Client

1. Create async client in `src/clients/`
2. Use `aiohttp` for HTTP calls
3. Wrap synchronous blockchain calls with `asyncio.to_thread()`
4. Match async interface pattern from existing clients
5. Create simulator version for dry-run mode

### Modifying Trading Logic

Key files:
- Position sizing: `src/strategies/position_taker.py` → `_calculate_position_size()`
- Market making spreads: `src/strategies/market_maker.py` → `_calculate_spread()`
- Risk limits: `src/config/settings.py` (MAX_POSITION_SIZE, MAX_DAILY_LOSS)
- State transitions: `src/bot.py` → `determine_market_state()`

---

## Environment Variables

Critical `.env` settings (see `.env.example`):

```bash
# REQUIRED
WEATHER_API_KEY=xxx                    # Weather.com API key
POLYMARKET_PRIVATE_KEY=0x...           # For live trading

# MARKET DISCOVERY (pick one approach)
EVENT_SLUG=highest-temperature-...     # Single market
EVENT_SLUGS=slug1,slug2,slug3         # Multiple markets
# (or leave empty for auto-discovery)

# TRADING CONFIGURATION
MAX_POSITION_SIZE=100.0                # Max per position (USDC)
MAX_DAILY_LOSS=50.0                    # Circuit breaker
ENABLE_POSITION_TAKING=true
ENABLE_MARKET_MAKING=false

# DRY RUN (IMPORTANT for testing)
DRY_RUN_MODE=true                      # Simulation mode
DRY_RUN_INITIAL_BALANCE=1000.0

# WEBSOCKET
ENABLE_WEBSOCKET=true                  # Real-time updates
```

---

## Git Workflow

Current branch structure:
- `main`: Production-ready code (100% async)
- `feature/*`: Feature branches

The async migration is **complete**. All components use async/await with single event loop.

---

## Documentation

Full documentation in `docs/`:
- `docs/QUICK_START.md`: Get started in 5 minutes
- `docs/WEBSOCKET_COMPLETE.md`: WebSocket setup and architecture
- `docs/ASYNC_MIGRATION_GUIDE.md`: Details on async migration (already completed)
- `docs/LOGS_GUIDE.md`: Understanding bot logs
- `docs/AUTO_DISCOVERY.md`: Market auto-discovery system
- `tests/README.md`: Comprehensive testing guide

See `docs/README.md` for complete documentation index.

---

## Known Patterns to Preserve

1. **Always use async for I/O**: HTTP, database, file operations
2. **Wrap sync CLOB calls**: `await asyncio.to_thread(self.client.method, args)`
3. **Use `asyncio.sleep()` not `time.sleep()`** in async context
4. **State machine transitions**: Only in `determine_market_state()`
5. **Structured logging**: Use `log_trade()`, `log_market_analysis()` for important events
6. **Configuration via Pydantic**: Never hardcode config values
7. **Dry-run first**: Always test new features with DRY_RUN_MODE=true
8. **WebSocket in thread**: Current architecture keeps WebSocket in separate thread with wrapper

---

## Critical Files

- `src/bot.py`: Main orchestrator, state machine, async event loop
- `src/clients/polymarket.py`: Polymarket integration (async HTTP + wrapped CLOB)
- `src/clients/weather.py`: Weather.com integration (async aiohttp)
- `src/strategies/position_taker.py`: Primary trading strategy
- `src/config/settings.py`: All configuration with Pydantic validation
- `main.py`: CLI entry point with Click
- `run_tests.sh`: Test runner helper script
