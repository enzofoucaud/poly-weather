# Intégration WebSocket - Prochaines Étapes

## Ce qui est fait ✅

1. **WebSocket Client** (`src/clients/polymarket_ws.py`)
   - Connexion à Polymarket WSS
   - Subscription aux asset IDs
   - Gestion des événements : price_change, book, trades
   - Auto-reconnexion
   - Heartbeat PING/PONG

2. **Thread Wrapper** (`src/utils/websocket_thread.py`)
   - Permet d'utiliser WebSocket async dans bot sync
   - Event loop séparé dans thread dédié
   - Subscribe thread-safe

3. **Configuration** (`src/config/settings.py`)
   - `USE_WEBSOCKET` : Enable/disable
   - `WS_PING_INTERVAL` : Heartbeat
   - `WS_AUTO_RECONNECT` : Auto-reconnect
   - `WS_MAX_RECONNECT_ATTEMPTS` : Max retries

4. **Test** (`test_websocket.py`)
   - Vérifié : connexion fonctionne
   - PING/PONG OK
   - Messages parsés correctement

## Ce qui reste à faire 📋

### 1. Intégrer WebSocket dans TradingBot

**Fichier** : `src/bot.py`

**Modifications** :

```python
from .utils.websocket_thread import WebSocketThread

class TradingBot:
    def __init__(self, ...):
        # ... existing code ...

        # WebSocket client (only if enabled and not dry-run)
        self.ws_thread: Optional[WebSocketThread] = None
        if self.settings.use_websocket and not self.dry_run:
            self.ws_thread = WebSocketThread(
                on_price_change=self._on_price_change,
                on_book_update=self._on_book_update,
                ping_interval=self.settings.ws_ping_interval
            )

    def _on_price_change(self, data: Dict):
        """
        Handle real-time price change from WebSocket.

        Called from WebSocket thread when price changes.
        """
        try:
            asset_id = data.get("asset_id")
            best_bid = data.get("best_bid")
            best_ask = data.get("best_ask")
            changes = data.get("changes", [])

            logger.info(f"💰 WS Price Update: {asset_id[:12]}...")
            logger.info(f"   Bid/Ask: ${best_bid} / ${best_ask}")

            # Find which market/outcome this belongs to
            market, outcome = self._find_market_and_outcome_by_token(asset_id)

            if not market or not outcome:
                return

            # Update cached price
            outcome.price = float(best_ask)  # Use ask for buying

            # Check if this creates an edge opportunity
            forecast = self.forecasts.get(market.market_id)

            if forecast:
                self._check_real_time_edge(market, outcome, forecast)

        except Exception as e:
            logger.error(f"Error handling price change: {e}")

    def _find_market_and_outcome_by_token(self, token_id: str):
        """Find market and outcome for a token ID."""
        for market_id, market in self.markets.items():
            for outcome in market.outcomes:
                if outcome.token_id == token_id:
                    return market, outcome
        return None, None

    def _check_real_time_edge(
        self,
        market: TemperatureMarket,
        outcome: PolymarketOutcome,
        forecast: WeatherForecast
    ):
        """
        Check if price change creates immediate trading opportunity.

        This is the KEY method - runs on every price update!
        """
        # Check if forecast predicts this outcome
        predicted_temp = forecast.max_temperature

        if not outcome.temperature_range.contains(predicted_temp):
            return  # Forecast doesn't predict this outcome

        # Calculate edge
        forecast_prob = forecast.confidence
        market_prob = outcome.price
        edge = forecast_prob - market_prob

        if edge > self.settings.min_edge:
            logger.info(f"⚡ REAL-TIME EDGE DETECTED!")
            logger.info(f"   Outcome: {outcome.temperature_range.label}")
            logger.info(f"   Edge: {edge:.2%}")
            logger.info(f"   Forecast: {predicted_temp}°F @ {forecast_prob:.0%}")
            logger.info(f"   Market: ${outcome.price:.4f}")

            # Place order immediately using position taker
            if self.position_taker:
                order = self.position_taker._create_order(
                    market=market,
                    outcome=outcome,
                    forecast=forecast,
                    edge=edge
                )

                if order:
                    self.position_taker.execute_order(order)
                    logger.info(f"   ✅ Order placed in <1s!")

    def run(self, duration: Optional[int] = None):
        """Start the bot."""
        # ... existing setup ...

        # Start WebSocket if enabled
        if self.ws_thread:
            logger.info("🚀 Starting WebSocket for real-time updates...")
            self.ws_thread.start()

        try:
            self.run_main_loop(duration)

        finally:
            # Stop WebSocket
            if self.ws_thread:
                self.ws_thread.stop()

    def scan_markets(self) -> List[TemperatureMarket]:
        """Scan for markets and subscribe to WebSocket."""
        markets = # ... existing market discovery ...

        # Subscribe to WebSocket for ALL token IDs
        if self.ws_thread and self.ws_thread.is_connected():
            all_token_ids = []
            for market in markets:
                for outcome in market.outcomes:
                    all_token_ids.append(outcome.token_id)

            if all_token_ids:
                logger.info(f"📡 Subscribing to {len(all_token_ids)} tokens via WebSocket...")
                self.ws_thread.subscribe(all_token_ids)

        return markets
```

### 2. Ajouter Caching des Forecasts

**Pourquoi** : Le callback WebSocket a besoin d'accès rapide aux prévisions

```python
class TradingBot:
    def __init__(self, ...):
        # ... existing ...

        # Cache forecasts by market_id
        self.forecasts: Dict[str, WeatherForecast] = {}
        self.markets: Dict[str, TemperatureMarket] = {}

    def run_main_loop(self, duration: Optional[int] = None):
        # ... scan markets ...

        for market in markets:
            # Get and cache forecast
            forecast = self.get_forecast_for_market(market)

            if forecast:
                self.forecasts[market.market_id] = forecast
                self.markets[market.market_id] = market

        # Now WebSocket callbacks can access forecasts!
```

### 3. Modifier Intervalle de Polling

Quand WebSocket est actif, on poll moins souvent :

```python
def run_main_loop(self, ...):
    while self.running:
        # Scan markets
        markets = self.scan_markets()

        # Update forecasts
        # ... existing logic ...

        # Sleep interval depends on WebSocket
        if self.ws_thread and self.ws_thread.is_connected():
            # WebSocket handles price updates
            # Just refresh forecasts every 10 minutes
            sleep_time = 600
        else:
            # Fallback to polling
            sleep_time = self.settings.check_interval_seconds

        logger.info(f"⏱️  Next scan in {sleep_time}s...")
        time.sleep(sleep_time)
```

### 4. Logging Amélioré

Différencier les updates WebSocket vs polling :

```python
# WebSocket update
logger.info(f"⚡ [WEBSOCKET] Price update: {asset_id}")

# Polling update
logger.info(f"🔄 [POLLING] Scanning markets...")
```

### 5. Tests d'Intégration

Créer `test_bot_websocket.py` :

```python
#!/usr/bin/env python3
"""Test bot with WebSocket integration."""

import os
os.environ['USE_WEBSOCKET'] = 'true'
os.environ['DRY_RUN_MODE'] = 'true'

from src.bot import TradingBot

def main():
    bot = TradingBot()

    # Should start WebSocket thread
    bot.run(duration=60)  # Run for 1 minute

if __name__ == "__main__":
    main()
```

## Avantages de cette Architecture

✅ **Pas de refactoring majeur** : Le bot reste sync
✅ **WebSocket en parallèle** : Thread séparé avec son event loop
✅ **Fallback automatique** : Si WebSocket fail, polling continue
✅ **Réactivité maximale** : <1s vs 60s
✅ **Compatible dry-run** : Simulateur ne lance pas WebSocket

## Timeline

- **30 min** : Modifications dans `bot.py`
- **15 min** : Tests et debugging
- **15 min** : Documentation

**Total** : ~1 heure

## Commandes de Test

```bash
# Test WebSocket seul
python test_websocket.py

# Test bot avec WebSocket
USE_WEBSOCKET=true python main.py run --duration 60

# Test bot sans WebSocket (fallback)
USE_WEBSOCKET=false python main.py run --duration 60
```

## Prochaine Session

1. Implémenter les modifications dans `bot.py`
2. Tester avec marchés actifs
3. Benchmarker la latence
4. Documenter dans README

C'est la dernière étape pour avoir un bot **ultra-réactif** ! 🚀
