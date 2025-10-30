# Plan de développement - Bot Trading Polymarket (Températures NYC)

## Vue d'ensemble

Bot de trading automatisé pour les marchés de température sur Polymarket, focalisé sur New York City. Le bot utilise les données météorologiques de Weather.com pour prendre des positions intelligentes et faire du market making.

### Objectifs principaux
- Trader les marchés de température NYC sur Polymarket
- Se positionner en avance (jusqu'à J-3) pour profiter de meilleurs prix
- Utiliser le market making pour générer des profits sur le spread
- Monitorer en temps réel le jour J pour ajuster les positions rapidement

### Stack technique
- **Langage** : Python 3.10+
- **Blockchain** : Polygon (pour Polymarket)
- **APIs** : Polymarket CLOB API, Weather.com API
- **Wallet** : Web3.py pour la gestion des transactions

---

## Phase 1 : Infrastructure de base ⬜

### 1.1 Configuration du projet ⬜

- [ ] Créer la structure de dossiers du projet
  ```
  poly-weather/
  ├── src/
  │   ├── __init__.py
  │   ├── config/
  │   │   ├── __init__.py
  │   │   └── settings.py
  │   ├── clients/
  │   │   ├── __init__.py
  │   │   ├── polymarket.py
  │   │   └── weather.py
  │   ├── strategies/
  │   │   ├── __init__.py
  │   │   ├── base.py
  │   │   ├── position_taker.py
  │   │   └── market_maker.py
  │   ├── models/
  │   │   ├── __init__.py
  │   │   ├── market.py
  │   │   └── trade.py
  │   └── utils/
  │       ├── __init__.py
  │       ├── logger.py
  │       └── helpers.py
  ├── tests/
  ├── data/
  ├── logs/
  ├── main.py
  ├── requirements.txt
  ├── .env.example
  └── README.md
  ```

- [ ] Créer `requirements.txt` avec les dépendances
  - `web3` : Interaction avec la blockchain Polygon
  - `py-clob-client` : Client officiel Polymarket
  - `requests` : Appels API Weather.com
  - `python-dotenv` : Gestion des variables d'environnement
  - `pydantic` : Validation des données
  - `loguru` : Logging avancé
  - `pandas` : Analyse de données
  - `numpy` : Calculs mathématiques
  - `schedule` : Tâches planifiées

- [ ] Créer `.env.example` avec toutes les variables nécessaires
  ```
  # Polymarket
  POLYMARKET_PRIVATE_KEY=
  POLYMARKET_PROXY_ADDRESS=
  POLYGON_RPC_URL=https://polygon-rpc.com

  # Weather.com
  WEATHER_API_KEY=e1f10a1e78da46f5b10a1e78da96f525
  WEATHER_GEOCODE=40.761,-73.864

  # Trading Config
  MAX_POSITION_SIZE=100.0
  MIN_SPREAD=0.02
  MAX_SLIPPAGE=0.05

  # Risk Management
  MAX_DAILY_LOSS=50.0
  MAX_EXPOSURE_PER_MARKET=200.0

  # Bot Behavior
  CHECK_INTERVAL_SECONDS=60
  HISTORICAL_CHECK_INTERVAL_SECONDS=1
  ADVANCE_DAYS=3

  # Logging
  LOG_LEVEL=INFO
  ```

- [ ] Initialiser git et créer `.gitignore`
  - Ignorer `.env`, `__pycache__/`, `*.pyc`, `logs/`, `data/*.db`

### 1.2 Configuration et logging ⬜

- [ ] Créer `src/config/settings.py`
  - Charger toutes les variables d'environnement avec Pydantic
  - Valider les types et formats
  - Fournir des valeurs par défaut sécurisées
  - Gérer les différents environnements (dev/prod)

- [ ] Créer `src/utils/logger.py`
  - Configurer Loguru avec rotation de fichiers
  - Niveaux : DEBUG, INFO, WARNING, ERROR
  - Format : timestamp, level, module, message
  - Sauvegarde dans `logs/bot_{date}.log`
  - Console output coloré pour le développement

### 1.3 Modèles de données ⬜

- [ ] Créer `src/models/market.py`
  ```python
  @dataclass
  class TemperatureRange:
      min_temp: Optional[float]
      max_temp: Optional[float]
      label: str  # "61-62°F", "65°F or higher"

  @dataclass
  class PolymarketOutcome:
      token_id: str
      price: float  # Prix actuel (0-1)
      temperature_range: TemperatureRange
      liquidity: float

  @dataclass
  class TemperatureMarket:
      market_id: str
      question: str
      target_date: datetime
      outcomes: List[PolymarketOutcome]
      volume_24h: float
      created_at: datetime
  ```

- [ ] Créer `src/models/trade.py`
  ```python
  @dataclass
  class Order:
      market_id: str
      outcome_id: str
      side: str  # "BUY" or "SELL"
      size: float  # Montant en USDC
      price: float  # Prix limite (0-1)
      order_type: str  # "LIMIT" or "MARKET"

  @dataclass
  class Position:
      market_id: str
      outcome_id: str
      shares: float
      avg_entry_price: float
      current_price: float
      unrealized_pnl: float

  @dataclass
  class Trade:
      order_id: str
      timestamp: datetime
      market_id: str
      outcome_id: str
      side: str
      size: float
      price: float
      status: str  # "PENDING", "FILLED", "CANCELLED"
  ```

---

## Phase 2 : Client Weather.com ⬜

### 2.1 Client de base ⬜

- [ ] Créer `src/clients/weather.py`
  - Classe `WeatherClient` avec initialisation de l'API key et geocode
  - Gestion des erreurs HTTP (retry avec backoff exponentiel)
  - Timeout configurables
  - Rate limiting (éviter de surcharger l'API)

### 2.2 Endpoint des prévisions ⬜

- [ ] Implémenter `get_forecast(days: int = 7)`
  - Appel à `GET /v3/wx/forecast/daily/7day`
  - Parser la réponse JSON, extraire `calendarDayTemperatureMax` array
  - Structure attendue: `{"calendarDayTemperatureMax": [62, 62, 58, 59, ...]}`
  - Mapper chaque température à sa date (aujourd'hui + index)
  - Retourner un dict `{date: max_temp}` pour les N prochains jours
  - Gérer les cas d'erreur (API down, données manquantes)

- [ ] Créer les tests unitaires pour les prévisions
  - Mock des réponses API
  - Vérifier le parsing correct
  - Tester les edge cases (données manquantes, format inattendu)

### 2.3 Endpoint historique du jour ⬜

- [ ] Implémenter `get_historical_today()`
  - Appel à `GET /v1/location/KLGA:9:US/observations/historical.json`
  - Paramètre `startDate` = aujourd'hui (format YYYYMMDD, ex: 20251030)
  - Parser le JSON: `response["observations"]` est une liste
  - Chaque observation contient `temp` (température actuelle)
  - Calculer le max en itérant: `max([obs["temp"] for obs in observations])`
  - Retourner `{"current_max": float, "observation_count": int, "latest_temp": float}`
  - Note: `max_temp` et `min_temp` dans les observations sont souvent `null`, utiliser `temp`

- [ ] Optimiser pour des appels fréquents (toutes les secondes le jour J)
  - Cache intelligent (invalider toutes les 1-2 secondes)
  - Connection pooling
  - Logging minimal pour ne pas polluer

### 2.4 Utilitaires météo ⬜

- [ ] Créer `get_confidence_score(forecast_date: datetime) -> float`
  - Plus on est proche de la date, plus la confiance est élevée
  - J-3: confidence ~0.6, J-2: ~0.75, J-1: ~0.85, J-0: ~0.95
  - Utilisé pour ajuster la taille des positions

- [ ] Créer `detect_forecast_change(old_max: float, new_max: float) -> bool`
  - Détecter si la prévision a changé significativement
  - Seuil : changement > 1°F = True
  - Déclencher des ajustements de position

---

## Phase 3 : Client Polymarket ⬜

### 3.1 Setup wallet et authentification ⬜

- [ ] Créer `src/clients/polymarket.py`
  - Initialiser le client CLOB avec private key
  - Setup du proxy address (si nécessaire)
  - Connexion au RPC Polygon
  - Vérifier le solde USDC disponible

- [ ] Implémenter `setup_allowances()`
  - Approuver le contrat Polymarket à dépenser USDC
  - Vérifier que les allowances sont suffisantes
  - Logger les transactions d'approval
  - Gérer les erreurs de transaction (gas, slippage)

### 3.2 Récupération des marchés ⬜

- [ ] Implémenter `get_temperature_markets(city: str = "NYC") -> List[TemperatureMarket]`
  - Rechercher les marchés actifs contenant "temperature" et "NYC"
  - Parser la question pour extraire la date cible
  - Récupérer tous les outcomes possibles avec leurs prix
  - Filtrer les marchés déjà résolus ou expirés

- [ ] Implémenter `get_market_orderbook(market_id: str, outcome_id: str)`
  - Récupérer le carnet d'ordres (bids/asks)
  - Calculer le spread actuel
  - Estimer la liquidité disponible
  - Retourner les meilleurs prix d'achat et de vente

- [ ] Implémenter `get_market_details(market_id: str)`
  - Informations détaillées sur le marché
  - Règles de résolution
  - Volume 24h
  - Historique des prix (si disponible)

### 3.3 Passage d'ordres ⬜

- [ ] Implémenter `place_order(order: Order) -> str`
  - Créer un ordre limite ou market
  - Signer la transaction
  - Soumettre via CLOB API
  - Retourner l'order_id
  - Logger tous les détails

- [ ] Implémenter `cancel_order(order_id: str) -> bool`
  - Annuler un ordre non rempli
  - Gérer les cas où l'ordre est déjà rempli
  - Retourner le succès/échec

- [ ] Implémenter `get_order_status(order_id: str) -> Trade`
  - Vérifier si l'ordre est rempli/partiel/en attente
  - Mettre à jour l'objet Trade
  - Gérer les échecs de transaction

### 3.4 Gestion des positions ⬜

- [ ] Implémenter `get_positions() -> List[Position]`
  - Récupérer toutes les positions ouvertes
  - Calculer le PnL non réalisé
  - Identifier les positions à risque

- [ ] Implémenter `close_position(position: Position, price: Optional[float])`
  - Vendre une position entière
  - Option market order ou limit order
  - Calculer le PnL réalisé
  - Logger la clôture

---

## Phase 4 : Stratégie de Position Taking ⬜

### 4.1 Analyse et sélection ⬜

- [ ] Créer `src/strategies/position_taker.py`
  - Classe `PositionTakerStrategy`
  - Méthode `analyze_market(market: TemperatureMarket, forecast: dict)`

- [ ] Implémenter la logique de sélection d'outcome
  - Comparer la température prévue avec les ranges disponibles
  - Si prévision = 63.5°F, acheter "63-64°F"
  - Gérer les cas limites (63.0°F → acheter quel bucket ?)
  - Prendre en compte la confidence (J-3 vs J-1)

- [ ] Calculer le edge (avantage)
  ```python
  def calculate_edge(predicted_temp: float, outcome: PolymarketOutcome, confidence: float) -> float:
      # Si on prédit 63.5°F et outcome est "63-64°F"
      # Edge = probability_model - current_price
      # probability_model basé sur forecast + confidence
      # Exemple: si current_price = 0.30 et notre proba = 0.60, edge = 0.30
  ```

### 4.2 Sizing des positions ⬜

- [ ] Implémenter Kelly Criterion adapté
  ```python
  def calculate_position_size(edge: float, confidence: float, bankroll: float) -> float:
      # Kelly = (edge * confidence) / odds
      # Ajuster avec un fractional Kelly (25-50%) pour être conservateur
      # Appliquer les limites MAX_POSITION_SIZE et MAX_EXPOSURE_PER_MARKET
  ```

- [ ] Gérer les contraintes de risque
  - Ne jamais dépasser MAX_EXPOSURE_PER_MARKET par marché
  - Vérifier le solde USDC disponible
  - Réserver de la liquidité pour le market making

### 4.3 Exécution des trades ⬜

- [ ] Implémenter `execute_entry(market: TemperatureMarket, outcome: PolymarketOutcome, size: float)`
  - Vérifier le spread actuel
  - Décider entre limit order (meilleur prix) ou market order (rapidité)
  - Placer l'ordre via le client Polymarket
  - Monitorer le fill (attendre max 5 minutes)
  - Si pas rempli, ajuster le prix et retry

- [ ] Implémenter la logique de trading anticipé
  - J-3: Acheter si edge > 0.15 (15%)
  - J-2: Acheter si edge > 0.10 (10%)
  - J-1: Acheter si edge > 0.05 (5%)
  - Acheter aussi des outcomes "proches" pour diversifier

### 4.4 Ajustement dynamique ⬜

- [ ] Implémenter `check_forecast_updates()`
  - Appeler toutes les heures (configurable)
  - Comparer nouvelle prévision vs prévision précédente
  - Si changement significatif, réévaluer les positions

- [ ] Implémenter `rebalance_positions()`
  - Si la prévision change de 62°F à 64°F:
    - Vendre la position "61-62°F"
    - Acheter "63-64°F"
  - Calculer les frais de transaction
  - Exécuter seulement si le gain espéré > frais

---

## Phase 5 : Stratégie de Market Making ⬜

### 5.1 Concepts et configuration ⬜

- [ ] Créer `src/strategies/market_maker.py`
  - Classe `MarketMakerStrategy`
  - Configuration: spread minimum, inventory max, update frequency

- [ ] Définir la stratégie de base
  - Placer simultanément un bid (achat) et un ask (vente)
  - Gagner sur le spread (différence entre les deux)
  - Exemple: bid à 0.48, ask à 0.52 → gain de 0.04 (4%) si les deux remplissent

### 5.2 Calcul des prix ⬜

- [ ] Implémenter `calculate_fair_value(outcome: PolymarketOutcome, forecast: dict) -> float`
  - Utiliser la prévision météo pour estimer la "vraie" probabilité
  - Ajuster selon la confidence temporelle
  - Retourner un prix entre 0 et 1

- [ ] Implémenter `calculate_quotes(fair_value: float, spread: float) -> Tuple[float, float]`
  - Bid price = fair_value - (spread / 2)
  - Ask price = fair_value + (spread / 2)
  - S'assurer que bid < ask
  - Ajuster selon la liquidité du marché (spread plus large si faible liquidité)

### 5.3 Gestion de l'inventaire ⬜

- [ ] Implémenter le suivi de l'inventaire
  - Tracker combien de shares on possède par outcome
  - Si inventaire trop élevé (long), baisser ask price pour vendre
  - Si inventaire trop bas (short), augmenter bid price
  - Objectif: rester neutre (market neutral)

- [ ] Implémenter `adjust_quotes_for_inventory(bid, ask, inventory: float, max_inventory: float)`
  - Si inventory > 0.7 * max_inventory: skew vers la vente (baisser ask, monter bid)
  - Si inventory < 0.3 * max_inventory: skew vers l'achat (monter ask, baisser bid)

### 5.4 Placement et gestion des ordres ⬜

- [ ] Implémenter `place_market_making_orders(outcome: PolymarketOutcome, bid: float, ask: float, size: float)`
  - Placer ordre d'achat (bid) et ordre de vente (ask) simultanément
  - Utiliser des limit orders
  - Logger les deux order_ids

- [ ] Implémenter la boucle de market making
  ```python
  def run_market_making_loop():
      while True:
          # Annuler les anciens ordres
          cancel_all_open_orders()

          # Recalculer fair value avec nouvelle météo
          fair_value = calculate_fair_value(...)

          # Calculer nouveau spread
          bid, ask = calculate_quotes(fair_value, spread)

          # Ajuster pour inventaire
          bid, ask = adjust_quotes_for_inventory(...)

          # Placer nouveaux ordres
          place_market_making_orders(...)

          # Attendre N secondes
          sleep(UPDATE_INTERVAL)
  ```

### 5.5 Gestion du risque market making ⬜

- [ ] Implémenter des circuit breakers
  - Stop market making si perte > MAX_DAILY_LOSS
  - Stop si inventaire > MAX_INVENTORY (trop de risque directionnel)
  - Stop si spread < MIN_SPREAD (pas assez profitable)

- [ ] Implémenter l'hedging
  - Si on accumule trop d'inventaire sur un outcome:
    - Option 1: Prendre une position inverse sur un autre outcome
    - Option 2: Sortir du market making et juste vendre l'inventaire
  - Calculer si le hedging est profitable vs les frais

---

## Phase 6 : Monitoring temps réel (Jour J) ⬜

### 6.1 Système de scraping historique ⬜

- [ ] Créer `src/utils/realtime_monitor.py`
  - Classe `RealtimeMonitor`
  - Boucle qui appelle `weather_client.get_historical_today()` chaque seconde

- [ ] Implémenter la détection de changement de max
  ```python
  def monitor_temperature_changes():
      previous_max = None
      while is_target_day():
          current_data = get_historical_today()
          current_max = current_data["current_max"]

          if previous_max and current_max != previous_max:
              logger.warning(f"Temperature max changed: {previous_max}°F -> {current_max}°F")
              trigger_position_adjustment(current_max)

          previous_max = current_max
          sleep(1)
  ```

### 6.2 Ajustement rapide des positions ⬜

- [ ] Implémenter `trigger_position_adjustment(new_max: float)`
  - Identifier l'outcome correspondant au new_max
  - Si on n'a pas de position dessus, acheter immédiatement (market order)
  - Si on a une position sur un mauvais outcome, vendre immédiatement

- [ ] Optimiser pour la vitesse
  - Pré-calculer les outcomes possibles
  - Utiliser market orders pour garantir l'exécution rapide
  - Minimiser les appels API inutiles
  - Paralléliser vente + achat si possible

### 6.3 Gestion de fin de journée ⬜

- [ ] Implémenter `end_of_day_strategy()`
  - Quelques heures avant la fin de la journée météo:
    - Arrêter le market making
    - Clôturer les positions perdantes
    - Conserver seulement la position gagnante
  - À 23h59 (ou deadline du marché):
    - Vérifier que tout est fermé
    - Logger le résultat final

- [ ] Implémenter `wait_for_resolution(market_id: str)`
  - Attendre que Polymarket résolve le marché
  - Vérifier que notre outcome gagnant est bien payé
  - Logger le PnL final

---

## Phase 7 : Orchestration et boucle principale ⬜

### 7.1 Architecture du bot ⬜

- [ ] Créer `main.py` avec la structure suivante:
  ```python
  class TradingBot:
      def __init__(self):
          self.weather_client = WeatherClient()
          self.poly_client = PolymarketClient()
          self.position_strategy = PositionTakerStrategy()
          self.mm_strategy = MarketMakerStrategy()

      def run(self):
          # Boucle principale
  ```

- [ ] Implémenter la machine à états
  - État 1: SCANNING (recherche de marchés intéressants)
  - État 2: POSITIONING (prise de position J-3 à J-1)
  - État 3: MARKET_MAKING (si activé)
  - État 4: DAY_OF_MONITORING (jour J, monitoring temps réel)
  - État 5: WAITING_RESOLUTION (attente résolution du marché)

### 7.2 Boucle principale ⬜

- [ ] Implémenter `run_main_loop()`
  ```python
  def run_main_loop():
      while True:
          try:
              # 1. Récupérer tous les marchés température NYC
              markets = poly_client.get_temperature_markets("NYC")

              # 2. Récupérer les prévisions météo
              forecast = weather_client.get_forecast(days=7)

              # 3. Pour chaque marché
              for market in markets:
                  state = determine_market_state(market)

                  if state == "POSITIONING":
                      position_strategy.analyze_and_trade(market, forecast)

                  elif state == "MARKET_MAKING":
                      mm_strategy.run_market_making(market, forecast)

                  elif state == "DAY_OF_MONITORING":
                      monitor_realtime(market)

              # 4. Attendre avant prochain cycle
              sleep(CHECK_INTERVAL_SECONDS)

          except Exception as e:
              logger.error(f"Error in main loop: {e}")
              sleep(60)  # Attendre 1 minute avant retry
  ```

### 7.3 Gestion des threads ⬜

- [ ] Implémenter le multi-threading
  - Thread 1: Boucle principale (position taking + market making)
  - Thread 2: Monitoring temps réel (actif seulement le jour J)
  - Thread 3: Logging et monitoring de santé
  - Utiliser des queues pour la communication inter-threads

- [ ] Gérer l'arrêt gracieux
  - Capturer SIGINT (Ctrl+C)
  - Annuler tous les ordres ouverts
  - Sauvegarder l'état actuel
  - Fermer les connexions proprement

---

## Phase 8 : Gestion des risques avancée ⬜

### 8.1 Limites et contrôles ⬜

- [ ] Implémenter `RiskManager` class
  - Tracker toutes les positions et ordres en temps réel
  - Vérifier avant chaque trade:
    - Solde USDC suffisant
    - Pas de dépassement de MAX_EXPOSURE_PER_MARKET
    - Pas de dépassement de MAX_DAILY_LOSS
  - Refuser les trades qui violent les limites

- [ ] Implémenter des alertes
  - Alert si exposition > 80% de la limite
  - Alert si perte journalière > 50% de la limite
  - Alert si solde USDC < 10% du bankroll initial

### 8.2 Diversification ⬜

- [ ] Implémenter la stratégie de diversification
  - Ne pas mettre tout sur un seul outcome
  - Si prévision = 63°F, considérer:
    - 60% sur "63-64°F"
    - 20% sur "61-62°F"
    - 20% sur "65°F or higher"
  - Ajuster selon la confidence

- [ ] Gérer plusieurs marchés en parallèle
  - Trader plusieurs dates simultanément (aujourd'hui + demain + après-demain)
  - Répartir le capital équitablement
  - Prioriser les marchés avec meilleur edge

### 8.3 Calcul de performance ⬜

- [ ] Implémenter le tracking de PnL
  - PnL réalisé: profits/pertes sur positions fermées
  - PnL non réalisé: valeur actuelle des positions ouvertes
  - Sharpe ratio: rendement ajusté au risque
  - Win rate: % de trades gagnants

- [ ] Créer un rapport quotidien
  - Nombre de trades exécutés
  - Volume total tradé
  - PnL net
  - Meilleurs et pires trades
  - Sauvegarder dans `data/performance_{date}.json`

---

## Phase 9 : Persistance et base de données ⬜

### 9.1 Choix de la base de données ⬜

- [ ] Installer SQLite pour commencer (simple, pas de setup)
  - Créer `data/trading.db`
  - Tables: markets, trades, positions, weather_data

### 9.2 Modèle de données ⬜

- [ ] Créer le schéma SQL
  ```sql
  CREATE TABLE markets (
      market_id TEXT PRIMARY KEY,
      question TEXT,
      target_date DATE,
      created_at TIMESTAMP,
      resolved_at TIMESTAMP,
      winning_outcome_id TEXT
  );

  CREATE TABLE trades (
      trade_id TEXT PRIMARY KEY,
      market_id TEXT,
      outcome_id TEXT,
      side TEXT,
      size REAL,
      price REAL,
      timestamp TIMESTAMP,
      status TEXT,
      FOREIGN KEY (market_id) REFERENCES markets(market_id)
  );

  CREATE TABLE positions (
      position_id INTEGER PRIMARY KEY AUTOINCREMENT,
      market_id TEXT,
      outcome_id TEXT,
      shares REAL,
      avg_entry_price REAL,
      current_price REAL,
      updated_at TIMESTAMP,
      FOREIGN KEY (market_id) REFERENCES markets(market_id)
  );

  CREATE TABLE weather_data (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date DATE,
      forecast_date DATE,
      max_temp REAL,
      source TEXT,
      timestamp TIMESTAMP
  );
  ```

### 9.3 Couche d'accès aux données ⬜

- [ ] Créer `src/utils/database.py`
  - Classe `DatabaseManager`
  - Méthodes CRUD pour chaque table
  - Connection pooling
  - Gestion des transactions

- [ ] Implémenter les méthodes principales
  - `save_trade(trade: Trade)`
  - `get_positions() -> List[Position]`
  - `save_weather_data(date, temp, forecast_date)`
  - `get_trade_history(market_id: str) -> List[Trade]`

### 9.4 Sauvegarde et récupération d'état ⬜

- [ ] Implémenter `save_state()`
  - Sauvegarder toutes les positions ouvertes
  - Sauvegarder tous les ordres en attente
  - Sauvegarder la configuration actuelle
  - Permettre de redémarrer le bot sans perte de données

- [ ] Implémenter `restore_state()`
  - Charger les positions depuis la DB
  - Vérifier que les ordres sont toujours valides
  - Réconcilier avec l'état réel sur Polymarket

---

## Phase 10 : Mode Dry-Run (Paper Trading) ⬜

### 10.1 Configuration du mode dry-run ⬜

- [ ] Ajouter la variable d'environnement `DRY_RUN_MODE`
  - `DRY_RUN_MODE=true` : Mode simulation (par défaut pour développement)
  - `DRY_RUN_MODE=false` : Mode réel avec argent
  - Logger clairement dans quel mode on est au démarrage du bot

- [ ] Créer un portefeuille simulé
  - Variable `DRY_RUN_INITIAL_BALANCE` (ex: 1000 USDC)
  - Tracker le solde en mémoire et en DB
  - Simuler les frais de transaction (0.2% par trade)
  - Permettre de reset le portefeuille facilement

### 10.2 Client Polymarket simulé ⬜

- [ ] Créer `src/clients/polymarket_simulator.py`
  - Classe `PolymarketSimulator` qui implémente la même interface que `PolymarketClient`
  - Charger les vrais marchés et prix depuis l'API (lecture seule)
  - Simuler les ordres sans les exécuter réellement

- [ ] Implémenter `place_order()` simulé
  ```python
  def place_order(order: Order) -> str:
      # Vérifier le solde simulé
      if order.side == "BUY":
          cost = order.size * order.price
          if cost > self.simulated_balance:
              raise InsufficientFundsError()
          self.simulated_balance -= cost

      # Générer un fake order_id
      order_id = f"sim_{uuid.uuid4()}"

      # Simuler le fill instantané (ou avec délai)
      self.simulated_orders[order_id] = {
          "status": "FILLED",
          "filled_price": order.price,
          "timestamp": datetime.now()
      }

      return order_id
  ```

- [ ] Implémenter les positions simulées
  - Tracker les shares achetées/vendues
  - Calculer le PnL basé sur les prix réels du marché
  - Permettre de fermer les positions

### 10.3 Simulation du temps et des marchés ⬜

- [ ] Créer un système de simulation multi-jours
  ```python
  class MarketSimulator:
      def __init__(self, start_date: date, num_days: int):
          self.current_date = start_date
          self.num_days = num_days
          self.daily_results = []

      def simulate_days(self):
          for day in range(self.num_days):
              self.simulate_day(self.current_date)
              self.current_date += timedelta(days=1)
  ```

- [ ] Implémenter `simulate_day(target_date: date)`
  - Récupérer les prévisions météo historiques (si disponibles)
  - OU utiliser les prévisions actuelles pour une date future
  - Simuler J-3: bot analyse et prend position
  - Simuler J-2: bot ajuste si prévision change
  - Simuler J-1: idem
  - Simuler J-0: monitoring temps réel avec données historiques réelles
  - Résoudre le marché avec la température réelle observée
  - Calculer le PnL du jour

- [ ] Gérer la résolution des marchés simulés
  - Utiliser les données historiques réelles de Weather.com
  - OU utiliser un mock si on simule le futur
  - Payer les positions gagnantes
  - Logger le résultat (win/loss/break-even)

### 10.4 Logging et reporting du dry-run ⬜

- [ ] Logger toutes les actions simulées
  - Préfixer chaque log avec `[DRY-RUN]`
  - Logger tous les trades "virtuels" avec leurs prix
  - Logger les changements de solde
  - Logger les décisions prises (pourquoi tel outcome a été choisi)

- [ ] Créer un rapport de simulation
  ```python
  {
    "simulation_period": "2025-10-20 to 2025-10-30",
    "initial_balance": 1000.0,
    "final_balance": 1127.50,
    "total_pnl": 127.50,
    "pnl_percentage": 12.75,
    "num_trades": 15,
    "num_wins": 9,
    "num_losses": 6,
    "win_rate": 0.60,
    "avg_win": 25.30,
    "avg_loss": -12.40,
    "max_drawdown": -45.20,
    "sharpe_ratio": 1.34,
    "daily_results": [
      {
        "date": "2025-10-20",
        "pnl": 15.20,
        "trades": 1,
        "balance": 1015.20
      },
      ...
    ]
  }
  ```

- [ ] Sauvegarder le rapport en JSON
  - Fichier `data/dry_run_report_{timestamp}.json`
  - Permettre de comparer plusieurs runs
  - Visualisation optionnelle (graphique du balance over time)

### 10.5 Validation et tests de stratégie ⬜

- [ ] Tester différentes configurations en dry-run
  - Conservative: petites positions, seulement J-1
  - Aggressive: grandes positions dès J-3
  - Market making: spread 2% vs 5%
  - Comparer les résultats

- [ ] Simuler des scénarios de stress
  - Prévisions qui changent radicalement chaque jour
  - Marchés avec faible liquidité (simulation de slippage)
  - Jours consécutifs de pertes (max drawdown)
  - Vérifier que les circuit breakers fonctionnent

- [ ] Valider les contraintes de risque
  - Vérifier que `MAX_EXPOSURE_PER_MARKET` est respecté
  - Vérifier que `MAX_DAILY_LOSS` arrête le trading
  - Vérifier que le bot ne peut pas shorter (solde négatif)

### 10.6 Commandes CLI pour le dry-run ⬜

- [ ] Créer des commandes pratiques
  ```bash
  # Lancer une simulation de 7 jours
  python main.py --dry-run --days 7 --start-date 2025-10-20

  # Lancer en mode replay (utiliser données historiques réelles)
  python main.py --dry-run --replay --start-date 2025-10-15 --end-date 2025-10-25

  # Lancer en mode live-simulation (utiliser marchés actuels, prévisions actuelles)
  python main.py --dry-run --live

  # Comparer plusieurs stratégies
  python main.py --dry-run --compare-strategies conservative,aggressive,mm
  ```

- [ ] Afficher le résumé en temps réel
  - Dashboard console avec Rich ou Textual
  - Afficher le solde actuel, positions ouvertes, dernier trade
  - Update en temps réel pendant la simulation

---

## Phase 11 : Testing et validation ⬜

### 11.1 Tests unitaires ⬜

- [ ] Créer tests pour `WeatherClient`
  - Mock des réponses API
  - Test des erreurs réseau
  - Test du parsing de données

- [ ] Créer tests pour `PolymarketClient`
  - Mock du CLOB API
  - Test des signatures de transactions
  - Test de la gestion des erreurs

- [ ] Créer tests pour les stratégies
  - Test du calcul de edge
  - Test du position sizing
  - Test du market making quotes

### 10.2 Tests d'intégration ⬜

- [ ] Test end-to-end sur testnet
  - Utiliser Polygon Mumbai testnet
  - Fake USDC
  - Simuler un marché complet

- [ ] Test du flow complet
  - Récupération marché → analyse → trade → monitoring → résolution
  - Vérifier les logs à chaque étape
  - Vérifier la persistence en DB

### 10.3 Backtesting ⬜

- [ ] Créer un module de backtesting
  - Charger les données météo historiques
  - Simuler les prix Polymarket (si disponibles)
  - Exécuter les stratégies sur données passées
  - Calculer le PnL théorique

- [ ] Analyser les résultats
  - Identifier les meilleures périodes (J-3 vs J-2 vs J-1)
  - Optimiser les paramètres (spread, position size, etc.)
  - Valider que les stratégies sont profitables

---

## Phase 11 : Monitoring et observabilité ⬜

### 11.1 Dashboard de monitoring ⬜

- [ ] Créer un simple dashboard Flask/FastAPI
  - Endpoint `/health` : status du bot
  - Endpoint `/positions` : positions actuelles
  - Endpoint `/pnl` : performance
  - Endpoint `/logs` : derniers logs

- [ ] Interface web basique
  - Tableau des positions ouvertes
  - Graphique du PnL cumulé
  - Liste des trades récents
  - Bouton d'arrêt d'urgence

### 11.2 Alertes et notifications ⬜

- [ ] Implémenter des alertes par email/SMS
  - Alert si erreur critique
  - Alert si perte > seuil
  - Alert si nouveau marché intéressant détecté
  - Utiliser un service comme SendGrid ou Twilio

- [ ] Logging structuré
  - Format JSON pour les logs importants
  - Faciliter le parsing et l'analyse
  - Intégration possible avec ELK/Grafana plus tard

### 11.3 Healthchecks ⬜

- [ ] Implémenter des healthchecks réguliers
  - Vérifier la connexion RPC Polygon
  - Vérifier l'API Weather.com
  - Vérifier le CLOB Polymarket
  - Ping toutes les 5 minutes

- [ ] Auto-recovery
  - Si un service est down, retry avec backoff
  - Si échec persistant, alert + pause du bot
  - Log détaillé pour debugging

---

## Phase 12 : Optimisations et améliorations ⬜

### 12.1 Optimisation des performances ⬜

- [ ] Profiling du code
  - Identifier les bottlenecks
  - Optimiser les appels API (caching, batching)
  - Réduire la latence de trading

- [ ] Améliorer la vitesse d'exécution le jour J
  - Pre-fetch des données
  - Connection permanente au RPC
  - Ordres pré-signés si possible

### 12.2 Amélioration des stratégies ⬜

- [ ] Ajouter du machine learning
  - Analyser les patterns historiques de prévisions météo
  - Prédire la volatilité des prévisions
  - Ajuster le sizing en fonction

- [ ] Arbitrage inter-outcomes
  - Si la somme des probabilités != 1, arbitrage possible
  - Exemple: "61-62" à 0.3, "63-64" à 0.4, "65+" à 0.4 → total = 1.1
  - Vendre tous les outcomes (garantir un profit)

- [ ] Stratégie de hedging avancée
  - Utiliser des options (si disponibles)
  - Couvrir les positions avec des marchés corrélés

### 12.3 Support de nouvelles villes ⬜

- [ ] Rendre le bot multi-villes
  - Paramétrer le geocode et location ID
  - Trader NYC, SF, Chicago, etc. en parallèle
  - Partager le capital intelligemment

- [ ] Adapter aux différents formats de questions
  - Certains marchés utilisent Celsius
  - Certains marchés ont des ranges différents
  - Parser de manière flexible

---

## Phase 13 : Déploiement et production ⬜

### 13.1 Préparation au déploiement ⬜

- [ ] Créer un Dockerfile
  - Image Python 3.10+
  - Installer toutes les dépendances
  - Copier le code
  - Exposer les ports (pour dashboard)

- [ ] Docker Compose pour l'orchestration
  - Service bot
  - Service dashboard
  - Service base de données (si migration vers PostgreSQL)

### 13.2 Sécurité ⬜

- [ ] Sécuriser les secrets
  - Ne JAMAIS commit les .env
  - Utiliser un gestionnaire de secrets (AWS Secrets Manager, etc.)
  - Chiffrer la private key au repos

- [ ] Audit de sécurité
  - Vérifier qu'aucune API key n'est loggée
  - Vérifier que les transactions sont correctement signées
  - Rate limiting sur les endpoints publics

### 13.3 Déploiement cloud ⬜

- [ ] Choisir un provider (AWS, GCP, DigitalOcean)
  - VM persistante ou serverless (Lambda/Cloud Functions)
  - Pour market making, préférer une VM 24/7

- [ ] Configuration du serveur
  - Installer Docker
  - Setup des cronjobs pour restart automatique
  - Monitoring système (CPU, RAM, disk)

- [ ] CI/CD
  - GitHub Actions pour les tests automatiques
  - Déploiement automatique sur push vers `main`
  - Rollback automatique si erreur détectée

---

## Phase 14 : Documentation ⬜

### 14.1 Documentation utilisateur ⬜

- [ ] Créer `README.md` complet
  - Description du projet
  - Prérequis et installation
  - Configuration (variables d'env)
  - Comment lancer le bot
  - Exemples d'utilisation

- [ ] Guide de configuration
  - Comment obtenir une API key Weather.com
  - Comment setup un wallet Polymarket
  - Comment déposer de l'USDC sur Polygon
  - Exemples de configurations (conservative vs aggressive)

### 14.2 Documentation développeur ⬜

- [ ] Documenter l'architecture
  - Diagramme des composants
  - Flow de données
  - Explication des stratégies

- [ ] Documenter le code
  - Docstrings pour toutes les fonctions publiques
  - Commentaires pour la logique complexe
  - Type hints partout

### 14.3 Runbook opérationnel ⬜

- [ ] Créer un guide de troubleshooting
  - Que faire si le bot crash
  - Que faire si un trade échoue
  - Que faire si on perd de l'argent rapidement

- [ ] Procédures d'urgence
  - Comment arrêter le bot immédiatement
  - Comment annuler tous les ordres manuellement
  - Comment contacter le support Polymarket

---

## Checklist de lancement ⬜

Avant de lancer le bot en production avec de l'argent réel:

- [ ] Tous les tests passent (unitaires + intégration)
- [ ] Backtesting montre des résultats positifs
- [ ] Testé sur testnet pendant au moins 1 semaine
- [ ] Limites de risque configurées et testées
- [ ] Système d'alertes fonctionnel
- [ ] Dashboard de monitoring opérationnel
- [ ] Documentation complète
- [ ] Backup de la private key sécurisé
- [ ] Commencer avec un petit capital ($50-100)
- [ ] Monitorer 24/7 les premiers jours

---

## Métriques de succès

### Court terme (1 mois)
- [ ] Win rate > 55%
- [ ] Sharpe ratio > 1.0
- [ ] Max drawdown < 20%
- [ ] Uptime du bot > 99%

### Moyen terme (3 mois)
- [ ] ROI > 15%
- [ ] Expansion à 3+ villes
- [ ] Zéro incident de sécurité
- [ ] Market making profitable (spread capture > frais)

### Long terme (6 mois)
- [ ] ROI > 50%
- [ ] Bot entièrement automatisé
- [ ] Stratégies ML performantes
- [ ] Communauté d'utilisateurs (si open source)

---

## Notes et idées futures

### Idées d'amélioration
- Intégrer d'autres sources météo pour validation croisée
- Créer un mode "paper trading" pour tester sans risque
- API publique pour partager les signaux (avec abonnement)
- Support des marchés de précipitations, vent, etc.

### Risques identifiés
- Changements dans l'API Polymarket
- Bugs dans les smart contracts
- Manipulation des marchés par des baleines
- Erreurs dans les données Weather.com
- Congestion réseau Polygon (high gas fees)

### Ressources utiles
- [Polymarket Docs](https://docs.polymarket.com/)
- [CLOB API Docs](https://docs.polymarket.com/api)
- [Weather.com API](https://docs.weather.com/)
- [Web3.py Documentation](https://web3py.readthedocs.io/)

---

**Date de création**: 2025-10-30
**Dernière mise à jour**: 2025-10-30
**Version**: 1.0
