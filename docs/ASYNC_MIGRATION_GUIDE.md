# Guide de Migration vers 100% Asynchrone

## 📋 Vue d'ensemble

Ce guide explique comment convertir le bot de son architecture **hybride** (sync + async) actuelle vers une architecture **100% asynchrone**.

---

## 🏗️ Architecture Actuelle vs Cible

### Actuelle (Hybride)
```
┌─────────────────────────────────────────────────┐
│     Bot Principal (SYNCHRONE)                    │
│  - Main loop avec time.sleep()                   │
│  - HTTP requests bloquants                       │
│  - Stratégies synchrones                         │
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │  WebSocket (ASYNC dans thread séparé)  │    │
│  │  - Event loop dédié                     │    │
│  │  - Communication via callbacks          │    │
│  └────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### Cible (100% Async)
```
┌─────────────────────────────────────────────────┐
│    Event Loop Unique (asyncio)                   │
│                                                  │
│  ┌────────────────┐  ┌──────────────────┐      │
│  │  Main Loop     │  │  WebSocket       │      │
│  │  (async)       │  │  (async)         │      │
│  │  - scan markets│  │  - price updates │      │
│  │  - strategies  │  │  - orderbook     │      │
│  └────────────────┘  └──────────────────┘      │
│                                                  │
│  ┌────────────────┐  ┌──────────────────┐      │
│  │  HTTP Clients  │  │  Strategies      │      │
│  │  (aiohttp)     │  │  (async)         │      │
│  └────────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────┘
```

---

## 📊 Avantages de la Migration

### ✅ Avantages
- **Event loop unifié** : Tout dans le même contexte d'exécution
- **Meilleure scalabilité** : Gère facilement des milliers de connexions
- **Code plus "propre"** : Pas de mélange sync/async
- **Concurrence optimale** : Toutes les tâches peuvent s'exécuter en parallèle
- **Moins de threads** : Pas besoin de `WebSocketThread` wrapper

### ⚠️ Inconvénients
- **Refactoring important** : 3-5 heures de travail
- **Complexité accrue** : Plus de `async/await` partout
- **Risque de bugs** : Erreurs potentielles pendant la migration
- **Dépendances supplémentaires** : `aiohttp`, `aiofiles`, etc.

---

## 🛠️ Plan de Migration (Estimé : 3-5h)

### Phase 1 : Préparation (15 min)
- [ ] Installer les dépendances async
- [ ] Créer une branche Git : `git checkout -b feature/full-async`
- [ ] Backup du code actuel

### Phase 2 : HTTP Clients Async (2h)
- [ ] Convertir `WeatherClient` vers aiohttp
- [ ] Convertir `PolymarketClient` vers aiohttp
- [ ] Supprimer `WebSocketThread` (plus nécessaire)
- [ ] Tests unitaires

### Phase 3 : Strategies Async (1h)
- [ ] Convertir `PositionTakerStrategy` en async
- [ ] Convertir `MarketMakerStrategy` en async
- [ ] Tests unitaires

### Phase 4 : Main Bot Async (1h)
- [ ] Convertir `TradingBot.run_main_loop()` en async
- [ ] Intégrer WebSocket directement (sans thread)
- [ ] Convertir tous les `time.sleep()` en `asyncio.sleep()`
- [ ] Point d'entrée `asyncio.run()`

### Phase 5 : Tests & Debug (1h)
- [ ] Tests d'intégration complets
- [ ] Vérifier les performances
- [ ] Corriger les bugs

---

## 📦 Nouvelles Dépendances

```txt
# requirements.txt - AJOUTER ces lignes

# Async HTTP client (remplace requests)
aiohttp==3.9.1

# Async file operations (optionnel)
aiofiles==23.2.1

# Websockets (déjà installé)
websockets==12.0
```

Installation :
```bash
pip install aiohttp aiofiles
```

---

## 📝 Modifications Détaillées

### 1. WeatherClient (src/clients/weather.py)

#### Avant (Sync)
```python
import requests

class WeatherClient:
    def get_forecast(self, days: int = 7) -> List[WeatherForecast]:
        """Get weather forecast (SYNC)."""
        response = requests.get(
            f"{self.base_url}/forecast/daily/7day",
            params=self.params
        )
        data = response.json()
        return self._parse_forecasts(data)
```

#### Après (Async)
```python
import aiohttp

class WeatherClient:
    async def get_forecast(self, days: int = 7) -> List[WeatherForecast]:
        """Get weather forecast (ASYNC)."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/forecast/daily/7day",
                params=self.params
            ) as response:
                data = await response.json()
                return self._parse_forecasts(data)
```

**Changements** :
- `requests` → `aiohttp`
- Méthode devient `async def`
- `response.json()` → `await response.json()`
- Context manager `async with` pour session et response

---

### 2. PolymarketClient (src/clients/polymarket.py)

#### Avant (Sync)
```python
import requests

class PolymarketClient:
    def get_temperature_markets(self, city: str) -> List[TemperatureMarket]:
        """Get temperature markets (SYNC)."""
        events = self._search_events(city)
        markets = []
        for event in events:
            response = requests.get(f"{self.gamma_url}/markets/{event['id']}")
            markets.extend(self._parse_markets(response.json()))
        return markets
```

#### Après (Async)
```python
import aiohttp

class PolymarketClient:
    async def get_temperature_markets(self, city: str) -> List[TemperatureMarket]:
        """Get temperature markets (ASYNC)."""
        events = await self._search_events(city)
        markets = []

        # Requêtes en parallèle avec asyncio.gather
        tasks = [
            self._fetch_market(event['id'])
            for event in events
        ]
        results = await asyncio.gather(*tasks)

        for result in results:
            markets.extend(self._parse_markets(result))
        return markets

    async def _fetch_market(self, event_id: str) -> dict:
        """Fetch single market (ASYNC)."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.gamma_url}/markets/{event_id}") as response:
                return await response.json()
```

**Changements** :
- `requests` → `aiohttp`
- Méthode devient `async def`
- Boucle `for` → `asyncio.gather()` pour paralléliser
- Ajout de méthode helper `_fetch_market()`

---

### 3. PositionTakerStrategy (src/strategies/position_taker.py)

#### Avant (Sync)
```python
class PositionTakerStrategy:
    def analyze_market(
        self,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> Optional[Order]:
        """Analyze market and return order (SYNC)."""
        # Calculs
        edge = self._calculate_edge(market, forecast)
        if edge > self.min_edge:
            return self._create_order(market, outcome, forecast, edge)
        return None

    def execute_order(self, order: Order) -> bool:
        """Execute order (SYNC)."""
        return self.client.place_order(order)
```

#### Après (Async)
```python
class PositionTakerStrategy:
    async def analyze_market(
        self,
        market: TemperatureMarket,
        forecast: WeatherForecast
    ) -> Optional[Order]:
        """Analyze market and return order (ASYNC)."""
        # Calculs (toujours synchrones, pas besoin de await)
        edge = self._calculate_edge(market, forecast)
        if edge > self.min_edge:
            return self._create_order(market, outcome, forecast, edge)
        return None

    async def execute_order(self, order: Order) -> bool:
        """Execute order (ASYNC)."""
        return await self.client.place_order(order)
```

**Changements** :
- Méthodes deviennent `async def`
- `self.client.place_order()` → `await self.client.place_order()`
- Les calculs purs (sans I/O) restent synchrones

---

### 4. TradingBot - Main Loop (src/bot.py)

#### Avant (Sync)
```python
import time
from threading import Thread

class TradingBot:
    def __init__(self, dry_run: bool = True):
        # WebSocket dans thread séparé
        self.ws_thread = WebSocketThread(
            on_price_change=self._on_price_change
        )

    def run_main_loop(self) -> None:
        """Run main trading loop (SYNC)."""
        while self.running:
            markets = self.scan_markets()  # Blocking

            for market in markets:
                forecast = self.get_forecast_for_market(market)  # Blocking
                self.handle_positioning(market, forecast)  # Blocking

            time.sleep(60)  # Blocking

    def run(self) -> None:
        """Run bot (SYNC)."""
        # Start WebSocket thread
        if self.ws_thread:
            self.ws_thread.start()

        self.run_main_loop()
```

#### Après (Async)
```python
import asyncio

class TradingBot:
    def __init__(self, dry_run: bool = True):
        # WebSocket client direct (pas de thread)
        from src.clients.polymarket_ws import PolymarketWebSocketClient

        self.ws_client = PolymarketWebSocketClient(
            on_price_change=self._on_price_change
        )

    async def run_main_loop(self) -> None:
        """Run main trading loop (ASYNC)."""
        while self.running:
            markets = await self.scan_markets()  # Non-blocking

            # Paralléliser le traitement des markets
            tasks = [
                self._process_market(market)
                for market in markets
            ]
            await asyncio.gather(*tasks)

            await asyncio.sleep(600)  # Non-blocking (10 min avec WebSocket)

    async def _process_market(self, market: TemperatureMarket) -> None:
        """Process single market (ASYNC)."""
        forecast = await self.get_forecast_for_market(market)  # Non-blocking
        if forecast:
            await self.handle_positioning(market, forecast)  # Non-blocking

    async def run(self) -> None:
        """Run bot (ASYNC)."""
        # Démarrer WebSocket et main loop en parallèle
        await asyncio.gather(
            self.ws_client.connect(),
            self.run_main_loop()
        )
```

**Changements** :
- `time.sleep()` → `asyncio.sleep()`
- `WebSocketThread` → `PolymarketWebSocketClient` direct
- Boucle `for` → `asyncio.gather()` pour paralléliser
- Ajout de méthode `_process_market()` pour structurer
- WebSocket et main loop dans le même event loop

---

### 5. WebSocket Integration (src/bot.py)

#### Avant (Hybride avec Thread)
```python
from src.utils.websocket_thread import WebSocketThread

class TradingBot:
    def __init__(self):
        # WebSocket dans thread séparé
        self.ws_thread = WebSocketThread(
            on_price_change=self._on_price_change
        )

    def _on_price_change(self, data: Dict) -> None:
        """Callback synchrone appelé depuis thread."""
        # Traitement synchrone
        pass

    def run(self):
        if self.ws_thread:
            self.ws_thread.start()  # Thread séparé
        self.run_main_loop()  # Boucle principale
```

#### Après (Async Direct)
```python
from src.clients.polymarket_ws import PolymarketWebSocketClient

class TradingBot:
    def __init__(self):
        # WebSocket direct dans event loop principal
        self.ws_client = PolymarketWebSocketClient(
            on_price_change=self._on_price_change
        )

    async def _on_price_change(self, data: Dict) -> None:
        """Callback async dans même event loop."""
        # Traitement async
        asset_id = data.get("asset_id")
        market, outcome = self._find_market_and_outcome_by_token(asset_id)

        if market and outcome:
            forecast = self.forecasts.get(market.market_id)
            if forecast:
                await self._check_real_time_edge(market, outcome, forecast)

    async def _check_real_time_edge(self, market, outcome, forecast) -> None:
        """Check edge and place order (ASYNC)."""
        edge = self._calculate_edge(outcome, forecast)
        if edge > self.settings.min_edge:
            order = self._create_order(market, outcome, forecast, edge)
            await self.position_taker.execute_order(order)  # ASYNC!

    async def run(self):
        # WebSocket et main loop dans même event loop
        await asyncio.gather(
            self.ws_client.connect(),
            self.run_main_loop()
        )
```

**Changements** :
- Suppression de `WebSocketThread`
- WebSocket intégré directement dans event loop
- Callback `_on_price_change()` devient async
- Order placement devient async : `await execute_order()`

---

### 6. Point d'Entrée (main.py)

#### Avant (Sync)
```python
def main():
    bot = TradingBot(dry_run=args.dry_run)
    bot.run()  # Synchrone

if __name__ == "__main__":
    main()
```

#### Après (Async)
```python
import asyncio

async def main():
    bot = TradingBot(dry_run=args.dry_run)
    await bot.run()  # Asynchrone

if __name__ == "__main__":
    asyncio.run(main())  # Point d'entrée async
```

**Changements** :
- `main()` devient `async def`
- `bot.run()` → `await bot.run()`
- `asyncio.run(main())` comme point d'entrée

---

## 🧪 Tests après Migration

### 1. Test WebSocket Direct
```python
# test_async_websocket.py
import asyncio
from src.clients.polymarket_ws import PolymarketWebSocketClient

async def test_websocket():
    """Test WebSocket without thread wrapper."""

    def on_price_change(data):
        print(f"Price update: {data}")

    client = PolymarketWebSocketClient(on_price_change=on_price_change)

    await client.connect()
    await client.subscribe(['349191972469807925876222822752744302929638865067642821958270388318826323155'])

    # Listen for 30 seconds
    await asyncio.sleep(30)

    await client.disconnect()

asyncio.run(test_websocket())
```

### 2. Test Bot Async
```python
# test_async_bot.py
import asyncio
from src.bot import TradingBot

async def test_bot():
    """Test bot with full async."""
    bot = TradingBot(dry_run=True)

    # Run for 60 seconds
    try:
        await asyncio.wait_for(bot.run(), timeout=60)
    except asyncio.TimeoutError:
        print("Test completed")
        await bot.shutdown()

asyncio.run(test_bot())
```

---

## 🐛 Problèmes Courants et Solutions

### Problème 1 : "coroutine was never awaited"
```python
# ❌ ERREUR
async def foo():
    return "bar"

result = foo()  # RuntimeWarning: coroutine 'foo' was never awaited
```

**Solution** :
```python
# ✅ CORRECT
result = await foo()
```

---

### Problème 2 : "await outside async function"
```python
# ❌ ERREUR
def sync_function():
    result = await async_function()  # SyntaxError
```

**Solution** :
```python
# ✅ CORRECT
async def async_function_wrapper():
    result = await async_function()
```

---

### Problème 3 : Mixing sync and async callbacks
```python
# ❌ ERREUR
class WebSocketClient:
    def __init__(self, callback):
        self.callback = callback  # callback peut être sync ou async

    async def _handle_message(self, data):
        self.callback(data)  # Problème si callback est async
```

**Solution** :
```python
# ✅ CORRECT
import inspect

class WebSocketClient:
    async def _handle_message(self, data):
        if inspect.iscoroutinefunction(self.callback):
            await self.callback(data)  # Async callback
        else:
            self.callback(data)  # Sync callback
```

---

### Problème 4 : Blocking operations dans async
```python
# ❌ ERREUR (bloque l'event loop)
async def process_data():
    time.sleep(10)  # Bloque tout l'event loop!
```

**Solution** :
```python
# ✅ CORRECT
async def process_data():
    await asyncio.sleep(10)  # Non-bloquant

# Ou pour code CPU-intensif
async def process_data():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, cpu_intensive_function)
```

---

## 📋 Checklist de Migration

### Avant de Commencer
- [ ] Lire ce guide en entier
- [ ] Créer une branche Git : `git checkout -b feature/full-async`
- [ ] Faire un backup du code : `git commit -am "Before async migration"`
- [ ] Installer dépendances : `pip install aiohttp aiofiles`

### Phase HTTP Clients
- [ ] Convertir `WeatherClient.get_forecast()` en async
- [ ] Convertir `WeatherClient.get_historical_max()` en async
- [ ] Convertir `PolymarketClient.get_temperature_markets()` en async
- [ ] Convertir `PolymarketClient._search_events()` en async
- [ ] Supprimer `WebSocketThread` (src/utils/websocket_thread.py)
- [ ] Tester avec `pytest tests/test_clients.py`

### Phase Strategies
- [ ] Convertir `PositionTakerStrategy.analyze_market()` en async
- [ ] Convertir `PositionTakerStrategy.execute_order()` en async
- [ ] Convertir `MarketMakerStrategy` méthodes en async
- [ ] Tester avec `pytest tests/test_strategies.py`

### Phase Main Bot
- [ ] Convertir `TradingBot.scan_markets()` en async
- [ ] Convertir `TradingBot.get_forecast_for_market()` en async
- [ ] Convertir `TradingBot.handle_positioning()` en async
- [ ] Convertir `TradingBot.run_main_loop()` en async
- [ ] Intégrer WebSocket direct (sans thread)
- [ ] Convertir `TradingBot._on_price_change()` en async
- [ ] Convertir `TradingBot._check_real_time_edge()` en async
- [ ] Modifier `main.py` : `asyncio.run(main())`
- [ ] Remplacer tous `time.sleep()` par `asyncio.sleep()`

### Tests & Validation
- [ ] Tester WebSocket direct : `python test_async_websocket.py`
- [ ] Tester bot complet : `python test_async_bot.py`
- [ ] Tester en dry-run : `python main.py run --duration 60`
- [ ] Vérifier logs : pas d'erreurs "coroutine was never awaited"
- [ ] Vérifier performances : latence <1s maintenue
- [ ] Tests d'intégration : `pytest tests/`

### Finalisation
- [ ] Documentation mise à jour (README.md)
- [ ] Commit : `git commit -am "Complete async migration"`
- [ ] Merge : `git checkout main && git merge feature/full-async`

---

## 🎯 Bénéfices Attendus Après Migration

### Performance
- ⚡ **Latence identique** : <1s (déjà atteint avec WebSocket)
- 📈 **Scalabilité** : Peut gérer 1000+ markets simultanément
- 🔄 **Concurrence** : Toutes les opérations I/O en parallèle

### Code
- 🧹 **Plus propre** : Pas de mélange sync/async
- 🐛 **Moins de bugs** : Pas de problèmes de threading
- 📦 **Plus simple** : Pas de `WebSocketThread` wrapper

### Maintenance
- 🛠️ **Plus facile** : Event loop unique
- 🧪 **Tests plus simples** : Tout dans asyncio
- 📚 **Meilleure documentation** : Pattern async standard

---

## 💡 Recommandations

### Option A : Garder Hybride (Recommandé)
**Pourquoi** :
- ✅ Fonctionne parfaitement
- ✅ Latence <1s déjà atteinte
- ✅ Code stable et testé
- ✅ Pas de risque de régression

**Quand migrer** :
- Si tu gères 100+ markets simultanément
- Si tu veux une architecture "pure"
- Si tu as besoin de scalabilité extrême

### Option B : Migrer vers Full Async
**Pourquoi** :
- ✅ Architecture plus élégante
- ✅ Meilleure scalabilité (futureproof)
- ✅ Event loop unifié

**Coût** :
- ⏱️ 3-5 heures de travail
- 🐛 Risque de bugs temporaires
- 📚 Courbe d'apprentissage asyncio

---

## 📞 Support

Si tu migres et rencontres des problèmes :

1. **"Coroutine never awaited"** → Ajoute `await` devant l'appel
2. **"Event loop closed"** → Utilise `asyncio.run()` au point d'entrée
3. **"Task was destroyed but pending"** → Ajoute `await asyncio.gather()` pour attendre toutes les tasks
4. **Performance dégradée** → Vérifie que tu n'as pas de `time.sleep()` restant

Ressources :
- [asyncio documentation](https://docs.python.org/3/library/asyncio.html)
- [aiohttp documentation](https://docs.aiohttp.org/)
- [Real Python asyncio guide](https://realpython.com/async-io-python/)

---

## 🎉 Conclusion

La migration vers 100% async est **possible** et **bien documentée** ici, mais elle n'est **pas nécessaire** pour atteindre tes objectifs de performance (<1s latence).

**Décision** :
- 🟢 **Garder hybride** : Si tu veux stabilité et rapidité
- 🔵 **Migrer async** : Si tu veux architecture pure et scalabilité maximale

**Mon conseil** : Garde l'architecture hybride actuelle jusqu'à ce que tu aies vraiment besoin de gérer des centaines de markets simultanément. À ce moment-là, cette doc te permettra de migrer en 3-5h ! 🚀
