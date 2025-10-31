# Guide de Lecture des Logs 📊

Ce guide t'aide à comprendre ce que fait le bot en lisant ses logs.

## Structure Générale

Le bot fonctionne en **itérations** (boucles) :

```
Iteration #1 | State: SCANNING
  ↓
1. 🔍 DÉCOUVERTE DES MARCHÉS
  ↓
2. 📊 RÉSUMÉ DES MARCHÉS TROUVÉS
  ↓
3. 🔄 TRAITEMENT DE CHAQUE MARCHÉ
  ↓
4. ⏱️  ATTENTE (60 secondes par défaut)
  ↓
Iteration #2 | State: SCANNING
  ...
```

## Phase 1 : Découverte des Marchés 🔍

### Auto-découverte

```
[DRY-RUN] No event slugs specified, auto-discovering markets for NYC
[DRY-RUN] Discovering temperature markets for NYC (next 3 days)
[DRY-RUN] ✓ Found event via direct slug: highest-temperature-in-nyc-on-october-31
[DRY-RUN] ✓ Found event via direct slug: highest-temperature-in-nyc-on-november-1
[DRY-RUN] Found 2 temperature event(s)
```

**Signification** :
- Le bot cherche automatiquement les marchés disponibles
- Utilise la génération prédictive de slugs (rapide !)
- Trouve 2 événements : 31 oct et 1er nov

### Résumé des Marchés

```
======================================================================
📊 Found 3 active market(s)
======================================================================

Market #1:
  Question: Will the highest temperature in NYC be 50°F or below on October 31?
  Market ID: 0xc169de2c32a59996d7cdcf991f9e467273bee6118bbd8df087d28aebc86e3200
  Target Date: 2025-10-31 (J-0)
  Outcomes: 7 temperature ranges
  Volume 24h: $38,633.40
  Status: 🟢 Active
  Prices:
    • 50°F or below: $0.000
    • 51-52°F: $0.000
    • 53-54°F: $0.000
    ... and 4 more outcomes
```

**À noter** :
- **J-0** = Aujourd'hui (target day)
- **J-1** = Demain
- **J-2** = Après-demain
- **Volume 24h** = Activité du marché (plus c'est élevé, plus c'est liquide)
- **🟢 Active** = Marché ouvert | **🔴 Resolved** = Marché résolu
- **Prices** = Prix actuels des 3 premiers outcomes (0.000 à 1.000)

## Phase 2 : Traitement des Marchés 🔄

Pour chaque marché, le bot suit ces étapes :

### 1. Identification du Marché

```
──────────────────────────────────────────────────────────────────────
📈 Market 1/3: Will the highest temperature in New York City be 50°F...
   ID: 0xc169de2c32a59996d7cdcf991f9e467273bee6118bbd8df087d28aebc86e3200
   Target: 2025-10-31 (J-0)
──────────────────────────────────────────────────────────────────────
```

**Signification** :
- Traite le marché 1 sur 3
- Affiche l'ID complet pour référence
- Rappelle la date cible

### 2. Prévision Météo

```
☁️  Fetching weather forecast for 2025-10-31...
✅ Forecast: 60°F (confidence: 95%)
```

**Signification** :
- Récupère la prévision pour la date du marché
- **60°F** = Température maximale prévue
- **95%** = Confiance dans la prévision (plus proche du jour = plus haute confiance)

### 3. Détermination de l'État

Le bot choisit une **stratégie** selon le nombre de jours restants :

```
💼 State: POSITIONING
🎯 Analyzing for position taking...
```

**États possibles** :

| Emoji | État | Quand | Action |
|-------|------|-------|--------|
| 🔍 | SCANNING | J > 3 | Surveille seulement |
| 💼 | POSITIONING | 1 ≤ J ≤ 3 | Prend des positions directionnelles |
| 📊 | MARKET_MAKING | 1 ≤ J ≤ 3 | Fait du market making (si activé) |
| 🔴 | DAY_OF_MONITORING | J = 0 | Monitoring temps réel (toutes les secondes!) |
| ⏳ | WAITING_RESOLUTION | J < 0 | Attend la résolution |

### 4a. Position Taking (J-1 à J-3)

Quand le bot trouve un **edge** (différence entre prévision et prix du marché) :

```
   🔍 Analyzing market opportunities...
   ✅ Edge found! Placing order:
      • Outcome: 17325427...
      • Side: BUY
      • Price: $0.2750
      • Size: $90.00
   🎉 Position successfully taken!
      Order ID: 17325427...
```

**Calcul de l'edge** :
```
Prévision = 58°F → Outcome 58-59°F devrait être à 80% (confiance)
Prix marché = 0.275 (27.5%)
Edge = 0.80 - 0.275 = 0.525 (52.5% d'edge!)
```

**Sizing avec Kelly Criterion** :
```
Kelly = (edge * probability) / odds
Position = Kelly * 0.25 (fractional Kelly, conservateur)
Scaling par jours : J-1: 85%, J-2: 70%, J-3: 50%
```

Quand **aucun edge** détecté :

```
   🔍 Analyzing market opportunities...
   ℹ️  No edge detected - market prices align with forecast
      This is normal and healthy! Waiting for better opportunity.
```

**Signification** : Les prix du marché reflètent déjà la prévision météo. C'est NORMAL et SAIN ! Le bot n'est pas obligé de trader à chaque itération.

### 4b. Real-Time Monitoring (J-0)

Quand c'est le **jour du marché** :

```
🔴 State: DAY_OF_MONITORING
🔴 LIVE: Starting real-time monitoring (target day is TODAY)

   🔴 REAL-TIME MONITORING MODE
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   📅 Today is the target day!
   🔄 Will check temperature every 1 second
   🎯 Will adjust positions if temperature changes range
   ⏰ Monitoring until end of day (23:00)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Initial max temperature: 60.0°F
```

**Ce qui se passe** :
- Le bot **poll Weather.com toutes les secondes** pour détecter les changements
- Si la température maximale change de range (ex: 59°F → 61°F)
- Il **ajuste automatiquement la position** vers le nouveau range
- Continue jusqu'à 23h00 puis attend la résolution

## Analyse de Logs Exemple

### Exemple 1 : Trade Réussi ✅

```
📈 Market 2/3: Will the highest temperature in NYC be 53°F...
   Target: 2025-11-01 (J-1)
☁️  Fetching weather forecast for 2025-11-01...
✅ Forecast: 58°F (confidence: 85%)
💼 State: POSITIONING
🎯 Analyzing for position taking...
   ✅ Edge found! Placing order:
      • Outcome: 58-59°F
      • Side: BUY
      • Price: $0.2750
      • Size: $90.00
   🎉 Position successfully taken!
```

**Interprétation** :
1. ✅ Marché du 1er novembre (demain)
2. ✅ Prévision : 58°F avec bonne confiance
3. ✅ Le marché 58-59°F est à seulement 27.5¢
4. ✅ Énorme edge ! Le bot achète pour $90
5. ✅ Si la prévision est correcte : profit de ~$237 !

### Exemple 2 : Pas d'Edge ℹ️

```
📈 Market 3/3: Will the highest temperature in NYC be 53°F...
   Target: 2025-11-02 (J-2)
☁️  Fetching weather forecast for 2025-11-02...
✅ Forecast: 56°F (confidence: 70%)
💼 State: POSITIONING
🎯 Analyzing for position taking...
   ℹ️  No edge detected - market prices align with forecast
      This is normal and healthy! Waiting for better opportunity.
```

**Interprétation** :
1. ✅ Marché du 2 novembre (J-2)
2. ✅ Prévision récupérée avec confiance moyenne (70%)
3. ℹ️  Les prix du marché sont déjà corrects
4. ℹ️  Le bot ne trade pas (c'est intelligent !)
5. ✅ Il attendra une meilleure opportunité

### Exemple 3 : Monitoring Temps Réel 🔴

```
📈 Market 1/3: Will the highest temperature in NYC be 50°F...
   Target: 2025-10-31 (J-0)
☁️  Fetching weather forecast for 2025-10-31...
✅ Forecast: 60°F (confidence: 95%)
🔴 State: DAY_OF_MONITORING
🔴 LIVE: Starting real-time monitoring (target day is TODAY)

   🔴 REAL-TIME MONITORING MODE
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   📅 Today is the target day!
   🔄 Will check temperature every 1 second
   🎯 Will adjust positions if temperature changes range
   ⏰ Monitoring until end of day (23:00)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Initial max temperature: 60.0°F
```

**Interprétation** :
1. 🔴 C'est AUJOURD'HUI (J-0) !
2. 🔴 Mode monitoring activé
3. 🔄 Poll toutes les secondes
4. 📊 Temp actuelle : 60°F
5. 🎯 Si ça change → ajustement automatique

## Logs de Diagnostic

### Erreurs Normales

```
⚠️  No forecast available, skipping this market
```
→ L'API météo n'a pas de données pour ce jour (trop loin dans le futur)

```
ℹ️  No edge detected - market prices align with forecast
```
→ Pas d'opportunité de trading (NORMAL !)

### Erreurs Problématiques

```
❌ Failed to fetch market for slug 'highest-temperature...'
```
→ Problème API Polymarket ou slug incorrect

```
❌ Failed to execute order
```
→ Problème lors du placement de l'ordre (vérifier balance, permissions)

```
❌ Error in positioning: ...
```
→ Bug dans la stratégie (à investiguer)

## Tips de Lecture

### Pour comprendre rapidement

1. **Cherche les emojis** 🎯
   - 📊 = combien de marchés
   - 💼 = en train de trader
   - 🔴 = monitoring temps réel
   - ✅ = succès
   - ❌ = erreur

2. **Regarde le J-X**
   - J-0 = Aujourd'hui → Mode monitoring
   - J-1, J-2, J-3 = Bientôt → Position taking
   - J > 3 = Trop loin → Juste surveille

3. **Vérifie les edges**
   - Edge > 50% = Excellente opportunité !
   - Edge 20-50% = Bonne opportunité
   - Edge < 5% = Pas d'edge (min threshold)

4. **Surveille le volume**
   - Volume > $10k = Marché actif, bon
   - Volume < $1k = Marché peu liquide, attention
   - Volume = $0 = Nouveau marché, pas encore de trades

## Fichiers de Logs

Le bot écrit dans plusieurs fichiers :

```
logs/
  ├── bot.log              # Log principal (tout)
  ├── trades.log           # Uniquement les trades
  ├── positions.log        # Positions ouvertes/fermées
  └── forecast_changes.log # Changements de prévisions
```

**Pour suivre en temps réel** :
```bash
tail -f logs/bot.log
tail -f logs/trades.log
```

**Pour filtrer par type** :
```bash
grep "Market #" logs/bot.log          # Résumés des marchés
grep "Edge found" logs/bot.log        # Opportunités trouvées
grep "Position taken" logs/bot.log    # Trades exécutés
grep "ERROR" logs/bot.log             # Erreurs seulement
```

## Conclusion

Maintenant tu peux facilement comprendre ce que fait le bot !

Les logs sont conçus pour être **clairs et structurés** :
- 📊 Emojis pour identification rapide
- ─── Séparateurs visuels
- ✅ Succès vs ❌ Erreurs
- Détails complets sur chaque action

Si quelque chose n'est pas clair, ouvre une issue sur GitHub !
