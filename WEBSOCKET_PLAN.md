# Plan d'Implémentation WebSocket 🚀

## Problème Actuel

Le bot **poll toutes les 60 secondes** pour vérifier les changements de prix :
- ❌ Latence élevée (jusqu'à 60 secondes de retard)
- ❌ Requests API répétées (inefficace)
- ❌ Risque de rater des opportunités rapides
- ❌ Pas réactif aux changements de prix

## Solution : WebSockets Temps Réel

### Architecture WebSocket Polymarket

D'après la documentation officielle, Polymarket propose plusieurs channels WebSocket :

1. **`clob_market`** - Changements de marché (PAS d'auth requise ✅)
   - `price_change` : Changements de prix instantanés
   - `agg_orderbook` : Orderbook agrégé

2. **`clob_user`** - Ordres utilisateur (auth requise)
   - `order` : Mises à jour sur tes ordres
   - `fill` : Fills de tes ordres

3. **`activity`** - Activité publique
   - `trades` : Trades publics sur les marchés

### Ce Qu'on Va Implémenter

**Phase 1 : WebSocket Client de Base**
- Client Python WebSocket utilisant `websockets` library
- Connexion au serveur Polymarket WSS
- Subscription au channel `clob_market` pour nos token_ids
- Gestion de la reconnexion automatique

**Phase 2 : Intégration dans le Bot**
- Remplacer le polling par WebSocket pour les prix
- Garder le polling uniquement pour :
  - Découverte de nouveaux marchés (1x/minute)
  - Prévisions météo (1x/10 minutes)
- Réagir instantanément aux changements de prix

**Phase 3 : Stratégies Temps Réel**
- Détection d'edge en temps réel
- Placement d'ordre automatique si edge > seuil
- Ajustement de positions sur changements rapides

## Avantages

✅ **Latence < 1 seconde** (vs 60s actuellement)
✅ **Moins de requests API** (connexion persistante)
✅ **Opportunités rapides** (on est les premiers!)
✅ **Meilleure efficacité** (pas de polling inutile)

## Implémentation Technique

### 1. WebSocket Client (`src/clients/polymarket_ws.py`)

```python
import asyncio
import json
from typing import Callable, List, Dict, Optional
from websockets import connect
import websockets
from ..utils.logger import get_logger

logger = get_logger()

class PolymarketWebSocketClient:
    """
    WebSocket client for real-time Polymarket market data.

    Based on official Polymarket WebSocket API:
    https://docs.polymarket.com/developers/CLOB/websocket/wss-overview
    """

    def __init__(
        self,
        on_price_change: Callable[[Dict], None],
        on_orderbook_update: Optional[Callable[[Dict], None]] = None,
        on_trade: Optional[Callable[[Dict], None]] = None
    ):
        """
        Initialize WebSocket client.

        Args:
            on_price_change: Callback for price changes
            on_orderbook_update: Callback for orderbook updates
            on_trade: Callback for trade events
        """
        self.wss_url = "wss://ws-subscriptions-clob.polymarket.com/ws"
        self.on_price_change = on_price_change
        self.on_orderbook_update = on_orderbook_update
        self.on_trade = on_trade

        self.websocket = None
        self.subscribed_tokens = set()
        self.running = False

    async def connect(self):
        """Establish WebSocket connection."""
        logger.info("🔌 Connecting to Polymarket WebSocket...")

        try:
            self.websocket = await connect(self.wss_url)
            self.running = True
            logger.info("✅ WebSocket connected!")

            # Start listening for messages
            asyncio.create_task(self._listen())

        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            raise

    async def subscribe_to_market(self, token_ids: List[str]):
        """
        Subscribe to market updates for specific token IDs.

        Args:
            token_ids: List of token IDs to monitor
        """
        if not self.websocket:
            raise RuntimeError("WebSocket not connected")

        # Subscribe to price changes
        subscription = {
            "channel": "clob_market",
            "market_ids": token_ids,
            "types": ["price_change", "agg_orderbook"]
        }

        await self.websocket.send(json.dumps(subscription))

        for token_id in token_ids:
            self.subscribed_tokens.add(token_id)

        logger.info(f"📊 Subscribed to {len(token_ids)} token(s) via WebSocket")

    async def _listen(self):
        """Listen for incoming WebSocket messages."""
        try:
            async for message in self.websocket:
                await self._handle_message(message)

        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️  WebSocket connection closed, attempting reconnect...")
            await self._reconnect()

        except Exception as e:
            logger.error(f"❌ WebSocket error: {e}")

    async def _handle_message(self, message: str):
        """
        Handle incoming WebSocket message.

        Args:
            message: Raw message string
        """
        try:
            data = json.loads(message)

            msg_type = data.get("type")

            if msg_type == "price_change":
                # Price changed!
                await self._handle_price_change(data)

            elif msg_type == "agg_orderbook":
                # Orderbook updated
                if self.on_orderbook_update:
                    await self.on_orderbook_update(data)

            elif msg_type == "trade":
                # New trade
                if self.on_trade:
                    await self.on_trade(data)

        except Exception as e:
            logger.error(f"Failed to parse WebSocket message: {e}")

    async def _handle_price_change(self, data: Dict):
        """
        Handle price change event.

        Args:
            data: Price change data
        """
        token_id = data.get("token_id")
        price = data.get("price")

        logger.info(f"💰 Price Update: Token {token_id[:12]}... → ${price:.4f}")

        # Call user callback
        if self.on_price_change:
            await self.on_price_change(data)

    async def _reconnect(self, max_retries: int = 5):
        """
        Attempt to reconnect to WebSocket.

        Args:
            max_retries: Maximum reconnection attempts
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 Reconnection attempt {attempt + 1}/{max_retries}...")

                await asyncio.sleep(2 ** attempt)  # Exponential backoff

                await self.connect()

                # Re-subscribe to previous tokens
                if self.subscribed_tokens:
                    await self.subscribe_to_market(list(self.subscribed_tokens))

                logger.info("✅ Reconnected successfully!")
                return

            except Exception as e:
                logger.warning(f"Reconnection attempt {attempt + 1} failed: {e}")

        logger.error("❌ Failed to reconnect after max retries")

    async def disconnect(self):
        """Close WebSocket connection."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 WebSocket disconnected")
```

### 2. Intégration dans le Bot

**Modifications à `src/bot.py`** :

```python
class TradingBot:
    def __init__(self, ...):
        # ... existing code ...

        # WebSocket client
        self.ws_client = None
        if not self.dry_run:
            self.ws_client = PolymarketWebSocketClient(
                on_price_change=self._on_price_change
            )

    async def _on_price_change(self, data: Dict):
        """
        Handle real-time price change from WebSocket.

        Args:
            data: Price change data from WebSocket
        """
        token_id = data.get("token_id")
        new_price = data.get("price")

        logger.info(f"📊 Price update received: {token_id[:12]}... → ${new_price:.4f}")

        # Find which market this token belongs to
        market = self._find_market_by_token(token_id)

        if not market:
            return

        # Check if this creates a new edge opportunity
        forecast = self.get_forecast_for_market(market)

        if forecast:
            # Analyze if there's now an edge
            self._check_edge_opportunity(market, forecast, token_id, new_price)

    def _find_market_by_token(self, token_id: str) -> Optional[TemperatureMarket]:
        """Find market containing a specific token ID."""
        for market_id, market in self.markets.items():
            for outcome in market.outcomes:
                if outcome.token_id == token_id:
                    return market
        return None

    def _check_edge_opportunity(
        self,
        market: TemperatureMarket,
        forecast: WeatherForecast,
        token_id: str,
        new_price: float
    ):
        """
        Check if price change creates a trading opportunity.

        Args:
            market: Temperature market
            forecast: Weather forecast
            token_id: Token that changed price
            new_price: New price
        """
        # Get the outcome that changed
        outcome = None
        for o in market.outcomes:
            if o.token_id == token_id:
                outcome = o
                break

        if not outcome:
            return

        # Check if forecast predicts this outcome
        predicted_temp = forecast.max_temperature
        if not outcome.temperature_range.contains(predicted_temp):
            return  # Forecast doesn't predict this outcome

        # Calculate edge
        forecast_prob = forecast.confidence
        market_prob = new_price
        edge = forecast_prob - market_prob

        if edge > self.settings.min_edge:
            logger.info(f"🎯 EDGE DETECTED: {edge:.2%} on {outcome.temperature_range.label}")
            logger.info(f"   Forecast: {predicted_temp}°F ({forecast_prob:.0%})")
            logger.info(f"   Market: ${new_price:.4f}")

            # Place order immediately!
            self._place_edge_order(market, outcome, edge)
```

### 3. Nouvelle Boucle Principale

**Au lieu de** :
```python
while True:
    scan_markets()
    analyze_all_markets()
    sleep(60)  # ❌ Attente passive
```

**On fait** :
```python
# Setup WebSocket
await ws_client.connect()

# Subscribe to all token IDs from our markets
token_ids = get_all_token_ids_from_markets()
await ws_client.subscribe_to_market(token_ids)

# Boucle légère pour maintenance
while True:
    # Découverte de nouveaux marchés (1x/minute)
    new_markets = scan_markets()

    if new_markets:
        # Subscribe to new tokens
        new_tokens = get_token_ids(new_markets)
        await ws_client.subscribe_to_market(new_tokens)

    # Refresh weather forecasts (1x/10 min)
    if time() - last_forecast_update > 600:
        update_forecasts()

    # Le reste du temps, on écoute les WebSocket! ✅
    await asyncio.sleep(60)
```

## Configuration

Ajouter dans `.env` :

```bash
# WebSocket Configuration
USE_WEBSOCKET=true              # Enable WebSocket mode
WS_RECONNECT_ATTEMPTS=5         # Max reconnection attempts
WS_HEARTBEAT_INTERVAL=30        # Ping interval (seconds)
```

## Bénéfices Attendus

### Avant (Polling)
```
16:00:00 - Scan markets, prix = $0.27
16:01:00 - Scan markets, prix = $0.27
16:02:00 - Scan markets, prix = $0.23 ← Edge détecté!
16:02:05 - Place order @ $0.24 (prix a déjà changé)
```

**Latence** : 60-120 secondes

### Après (WebSocket)
```
16:00:00 - WebSocket connected, monitoring...
16:02:00.123 - Price change: $0.27 → $0.23 ← Edge détecté INSTANTANÉMENT!
16:02:00.456 - Place order @ $0.23 (on est les premiers!)
```

**Latence** : < 1 seconde

## Risques & Mitigations

### Risque 1 : WebSocket Disconnections
- **Mitigation** : Reconnexion automatique avec backoff exponentiel
- **Fallback** : Retour temporaire au polling si WebSocket indisponible

### Risque 2 : Overhead Asyncio
- **Mitigation** : Utiliser asyncio proprement avec event loop dédié
- **Test** : Benchmarker la latence end-to-end

### Risque 3 : Rate Limiting
- **Mitigation** : WebSocket a des limites plus élevées que REST API
- **Monitor** : Logger les erreurs de rate limit

## Timeline d'Implémentation

**Phase 1** (2-3 heures) : WebSocket Client de base
- Créer `polymarket_ws.py`
- Tester connexion et subscription
- Gérer reconnexions

**Phase 2** (2-3 heures) : Intégration Bot
- Refactoriser la boucle principale
- Ajouter callbacks pour price changes
- Tester avec dry-run

**Phase 3** (1-2 heures) : Optimisations
- Améliorer la détection d'edge
- Ajouter monitoring de latence
- Tests de stress

**Phase 4** (1 heure) : Documentation
- Mettre à jour README
- Ajouter guide WebSocket
- Exemples d'utilisation

## Prochaines Étapes

1. ✅ Tu approuves le plan ?
2. On commence par implémenter le WebSocket client ?
3. Ou tu préfères d'abord un prototype minimal pour tester ?

Cette amélioration va **transformer le bot** en le rendant vraiment réactif et compétitif ! 🚀
