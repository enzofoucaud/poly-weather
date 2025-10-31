# Tests Guide

## 📂 Structure

```
tests/
├── README.md                # This file
├── __init__.py
├── unit/                    # Unit tests (isolated, fast)
│   ├── test_weather_client.py
│   ├── test_position_taker.py
│   ├── test_market_maker.py
│   └── test_realtime_monitor.py
│
└── integration/            # Integration tests (API calls, slower)
    ├── test_websocket.py           # WebSocket connection test
    ├── test_bot_websocket.py       # Bot with WebSocket test
    ├── test_markets.py             # Markets API test
    ├── test_event_markets.py       # Event-based discovery test
    ├── test_auto_discovery.py      # Auto-discovery test
    └── test_multiple_markets.py    # Multiple markets test
```

---

## 🧪 Running Tests

### All Tests
```bash
# From project root
pytest tests/
```

### Unit Tests Only (Fast, No API Calls)
```bash
pytest tests/unit/
```

**Expected output**:
```
============ test session starts ============
collected 57 items

tests/unit/test_market_maker.py ........... [ 19%]
tests/unit/test_position_taker.py ......... [ 38%]
tests/unit/test_realtime_monitor.py ...... [ 50%]
tests/unit/test_weather_client.py ........ [100%]

============ 57 passed in 2.34s ============
```

### Integration Tests Only (Slower, Makes API Calls)
```bash
# Set PYTHONPATH first
export PYTHONPATH=/home/enzo/go/src/poly-weather

# Run individual tests
python tests/integration/test_websocket.py
python tests/integration/test_bot_websocket.py
python tests/integration/test_markets.py
```

**Note**: Integration tests require:
- Active internet connection
- Valid API keys in `.env`
- May take 15-60 seconds per test

---

## 🎯 Test Types

### Unit Tests (`tests/unit/`)

**Characteristics**:
- ✅ Fast (runs in seconds)
- ✅ No external dependencies
- ✅ Mocked API calls
- ✅ Test single components in isolation

**When to run**:
- Before every commit
- During development
- In CI/CD pipeline

**Example**:
```bash
# Test position taker strategy only
pytest tests/unit/test_position_taker.py -v
```

### Integration Tests (`tests/integration/`)

**Characteristics**:
- ⏱️ Slower (may take 15-60s each)
- 🌐 Requires internet connection
- 🔑 Requires valid API keys
- 🔗 Tests real API integrations

**When to run**:
- Before deploying to production
- After major changes to API clients
- Manually to verify connectivity

**Example**:
```bash
# Test WebSocket connectivity
export PYTHONPATH=/home/enzo/go/src/poly-weather
timeout 15 python tests/integration/test_websocket.py
```

---

## 📋 Test Descriptions

### Unit Tests

#### `test_weather_client.py`
Tests WeatherClient functionality with mocked API responses.

**Tests**:
- API initialization
- Forecast parsing
- Historical data fetching
- Error handling

#### `test_position_taker.py`
Tests PositionTakerStrategy logic.

**Tests**:
- Edge calculation
- Position sizing (Kelly criterion)
- Order creation
- Risk management

#### `test_market_maker.py`
Tests MarketMakerStrategy logic.

**Tests**:
- Quote calculation
- Inventory management
- Circuit breakers
- PnL tracking

#### `test_realtime_monitor.py`
Tests RealtimeMonitor for day-of-event tracking.

**Tests**:
- Temperature change detection
- Historical data fetching
- End-of-day monitoring
- Callback triggers

---

### Integration Tests

#### `test_websocket.py`
Tests WebSocket connection to Polymarket.

**What it does**:
1. Connects to `wss://ws-subscriptions-clob.polymarket.com`
2. Subscribes to 2 test tokens
3. Listens for price updates
4. Verifies PING/PONG heartbeat

**Duration**: Runs indefinitely (use `timeout` to limit)

**Usage**:
```bash
export PYTHONPATH=/home/enzo/go/src/poly-weather
timeout 15 python tests/integration/test_websocket.py
```

**Expected logs**:
```
🔌 Connecting to Polymarket WebSocket...
✅ WebSocket connected!
📊 Subscribing to 2 asset(s)...
✅ Subscribed successfully
👂 Listening for WebSocket messages...
🏓 PING sent
Received PONG
💰 Price Change: 349191972469...
```

---

#### `test_bot_websocket.py`
Tests bot with WebSocket integration.

**What it does**:
1. Creates bot in dry-run mode
2. Forces WebSocket to be enabled (bypasses dry-run check)
3. Discovers markets
4. Subscribes to all token IDs
5. Listens for real-time price updates (60s)

**Duration**: ~60 seconds

**Usage**:
```bash
export PYTHONPATH=/home/enzo/go/src/poly-weather
python tests/integration/test_bot_websocket.py
```

**Expected output**:
```
Testing Bot with WebSocket Integration
🔧 Overriding dry-run mode to test WebSocket...
🚀 Starting WebSocket for real-time price updates...
✅ WebSocket started
🔍 Discovering markets and subscribing to WebSocket...
📊 Found 4 active market(s)
📡 Subscribing to 28 tokens via WebSocket...
✅ WebSocket subscriptions active!
⏰ Listening for WebSocket updates for 60 seconds...
⚡ [WEBSOCKET] Price Update: 349191972469...
```

---

#### `test_markets.py`
Tests basic market fetching from Polymarket API.

**What it does**:
1. Fetches temperature markets for NYC
2. Verifies market structure
3. Checks outcome prices

**Duration**: ~5 seconds

**Usage**:
```bash
export PYTHONPATH=/home/enzo/go/src/poly-weather
python tests/integration/test_markets.py
```

---

#### `test_event_markets.py`
Tests event-based market discovery.

**What it does**:
1. Searches for specific event by slug
2. Fetches all markets for that event
3. Verifies event structure

**Duration**: ~5 seconds

---

#### `test_auto_discovery.py`
Tests automatic market discovery.

**What it does**:
1. Uses `MarketDiscovery` class
2. Discovers markets for next N days
3. Verifies slug generation patterns

**Duration**: ~10 seconds

---

#### `test_multiple_markets.py`
Tests handling multiple markets simultaneously.

**What it does**:
1. Discovers markets for multiple days
2. Processes each market
3. Verifies concurrent handling

**Duration**: ~10 seconds

---

## 🛠️ Development Workflow

### Before Committing
```bash
# Run unit tests (fast)
pytest tests/unit/ -v
```

### Before Deploying
```bash
# Run all tests
pytest tests/unit/ -v

# Test WebSocket connectivity
export PYTHONPATH=/home/enzo/go/src/poly-weather
timeout 15 python tests/integration/test_websocket.py

# Test bot integration
python tests/integration/test_bot_websocket.py
```

### After Changing API Clients
```bash
# Test affected integration tests
export PYTHONPATH=/home/enzo/go/src/poly-weather
python tests/integration/test_markets.py
python tests/integration/test_websocket.py
```

---

## 🐛 Troubleshooting

### "No module named 'src'"

**Problem**: Integration tests can't find `src` module.

**Solution**: Set `PYTHONPATH`:
```bash
export PYTHONPATH=/home/enzo/go/src/poly-weather
python tests/integration/test_websocket.py
```

Or add to your `.bashrc`/`.zshrc`:
```bash
export PYTHONPATH="${PYTHONPATH}:/home/enzo/go/src/poly-weather"
```

---

### "ModuleNotFoundError: No module named 'loguru'"

**Problem**: Dependencies not installed.

**Solution**: Install requirements:
```bash
pip install -r requirements.txt
```

Or activate venv:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

### Integration Test Hangs

**Problem**: Test like `test_websocket.py` runs indefinitely.

**Solution**: Use `timeout`:
```bash
timeout 15 python tests/integration/test_websocket.py
```

---

### "Connection refused" in WebSocket Test

**Problem**: Can't connect to Polymarket WebSocket.

**Solutions**:
1. Check internet connection
2. Verify URL: `wss://ws-subscriptions-clob.polymarket.com/ws/market`
3. Check firewall/proxy settings
4. Try with VPN if blocked

---

## 📊 Coverage

To check test coverage:

```bash
# Install coverage
pip install pytest-cov

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html

# Open report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**Expected coverage**:
- Unit tests: ~80% code coverage
- Integration tests: Verify real-world functionality

---

## ✅ CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt

    - name: Run unit tests
      run: |
        pytest tests/unit/ -v

    - name: Run integration tests
      env:
        PYTHONPATH: ${{ github.workspace }}
        WEATHER_API_KEY: ${{ secrets.WEATHER_API_KEY }}
      run: |
        timeout 15 python tests/integration/test_websocket.py || true
```

---

## 📚 Adding New Tests

### Add Unit Test

1. Create file in `tests/unit/test_<component>.py`
2. Import component: `from src.<module> import <Component>`
3. Write test with mocks
4. Run: `pytest tests/unit/test_<component>.py`

**Template**:
```python
import pytest
from unittest.mock import Mock, patch
from src.your_module import YourClass

class TestYourClass:
    def test_your_function(self):
        """Test description."""
        # Arrange
        obj = YourClass()

        # Act
        result = obj.your_function()

        # Assert
        assert result == expected_value
```

### Add Integration Test

1. Create file in `tests/integration/test_<feature>.py`
2. Import components
3. Add setup instructions at top:
   ```python
   """
   Integration test for <feature>.

   Usage:
       export PYTHONPATH=/home/enzo/go/src/poly-weather
       python tests/integration/test_<feature>.py
   """
   ```
4. Write test with real API calls
5. Document expected duration

---

## 🎯 Best Practices

### Unit Tests
- ✅ Mock all external dependencies
- ✅ Test edge cases and error handling
- ✅ Keep tests fast (<100ms each)
- ✅ Use descriptive test names
- ✅ One assertion per test (when possible)

### Integration Tests
- ✅ Document API keys required
- ✅ Add timeout limits
- ✅ Handle network errors gracefully
- ✅ Document expected duration
- ✅ Include setup instructions in docstring

---

## 🤝 Contributing

When adding new features:

1. **Write unit tests first** (TDD approach)
2. **Run unit tests**: `pytest tests/unit/`
3. **Write integration test** (if feature uses external API)
4. **Run all tests**: `pytest tests/`
5. **Update this README** if adding new test categories

---

## 📞 Support

If tests fail:

1. Check this README for troubleshooting
2. Verify `.env` configuration
3. Check internet connectivity
4. Review test logs carefully
5. Search for error message in issues

**Common Issues**:
- PYTHONPATH not set → Set it
- Dependencies missing → `pip install -r requirements.txt`
- API keys invalid → Check `.env`
- Network timeout → Check firewall/VPN
