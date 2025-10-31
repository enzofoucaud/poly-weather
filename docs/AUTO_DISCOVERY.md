# Découverte Automatique des Marchés 🤖

Le bot peut maintenant **découvrir automatiquement** les marchés de température sur Polymarket sans configuration manuelle !

## Mode Automatique (Recommandé)

### Configuration

Laisse simplement `EVENT_SLUGS` vide dans ton `.env` :

```bash
# Market Discovery Configuration
TARGET_CITY=NYC
EVENT_SLUG=
EVENT_SLUGS=

# Le bot trouvera automatiquement les marchés disponibles
```

### Comment ça marche

Le bot utilise deux approches en parallèle :

1. **Génération directe de slugs** (rapide)
   - Génère des slugs prédictibles basés sur les dates
   - Pattern : `highest-temperature-in-{city}-on-{month}-{day}`
   - Exemples :
     - `highest-temperature-in-nyc-on-october-31`
     - `highest-temperature-in-nyc-on-november-1`

2. **Scan de l'API Gamma** (backup)
   - Si la génération directe échoue
   - Scanne les 500 premiers événements
   - Filtre par mots-clés : "temperature", "NYC", etc.

### Résultat

Le bot trouve automatiquement tous les marchés pour les N prochains jours :

```
2025-10-31 16:28:59 | INFO | ✓ Found event via direct slug: highest-temperature-in-nyc-on-october-31
2025-10-31 16:28:59 | INFO | ✓ Found event via direct slug: highest-temperature-in-nyc-on-november-1
2025-10-31 16:29:01 | INFO | Found 2 temperature event(s)
2025-10-31 16:29:01 | INFO |   - Highest temperature in NYC on October 31? | Target: 2025-10-31 (J-0)
2025-10-31 16:29:01 | INFO |   - Highest temperature in NYC on November 1? | Target: 2025-11-01 (J-1)
```

## Mode Manuel (Si nécessaire)

### Un seul marché

```bash
EVENT_SLUG=highest-temperature-in-nyc-on-october-31
```

### Plusieurs marchés

```bash
EVENT_SLUGS=highest-temperature-in-nyc-on-october-31,highest-temperature-in-nyc-on-november-1
```

## Configuration de la fenêtre temporelle

Le bot cherche les marchés jusqu'à N jours en avance :

```bash
# Dans .env
ADVANCE_DAYS=3  # Cherche J-0, J-1, J-2, J-3
```

Cela correspond au paramètre utilisé pour :
- La découverte automatique des marchés
- Le scaling des positions (J-3 : 50%, J-2 : 70%, J-1 : 85%, J-0 : 100%)

## Tester la découverte automatique

```bash
source venv/bin/activate
python test_auto_discovery.py
```

Exemple de sortie :

```
Testing automatic market discovery...
======================================================================

Discovering temperature markets for NYC (next 7 days):
----------------------------------------------------------------------

✅ Found 2 temperature event(s):

1. Highest temperature in NYC on October 31?
   Slug: highest-temperature-in-nyc-on-october-31
   Target Date: 2025-10-31 (J-0)
   Status: Active
   Volume 24h: $38,633.40
   Markets: 7 outcomes

2. Highest temperature in NYC on November 1?
   Slug: highest-temperature-in-nyc-on-november-1
   Target Date: 2025-11-01 (J-1)
   Status: Active
   Volume 24h: $2,476.56
   Markets: 7 outcomes

💡 Or leave EVENT_SLUGS empty for automatic discovery!
```

## Dry-Run avec marchés réels

En mode dry-run, le simulateur peut maintenant utiliser les **vrais prix** des marchés Polymarket tout en simulant les trades :

```bash
# Dans .env
DRY_RUN_MODE=true
EVENT_SLUGS=  # Laisse vide pour auto-découverte
```

Le bot va :
1. ✅ Découvrir automatiquement les marchés réels
2. ✅ Récupérer les prix réels des outcomes
3. ✅ Obtenir les prévisions météo réelles
4. ✅ Calculer l'edge avec les vraies données
5. ✅ Simuler les trades (pas d'argent réel)

C'est parfait pour tester la stratégie avec des conditions réelles !

## Fonctionnement continu

Le bot est conçu pour tourner **24/7** en mode automatique :

1. **Chaque minute** (configuré par `CHECK_INTERVAL_SECONDS`) :
   - Re-scanne les marchés disponibles
   - Trouve automatiquement les nouveaux marchés du jour
   - Met à jour les prévisions météo
   - Ajuste les positions si nécessaire

2. **Au changement de jour** :
   - Détecte automatiquement les nouveaux marchés (J+1 devient J)
   - Commence à trader sur le nouveau marché
   - Continue à monitorer les marchés précédents jusqu'à résolution

3. **Le jour J** :
   - Passe en mode monitoring temps réel (toutes les secondes)
   - Ajuste les positions selon la température observée
   - Ferme les positions au bon moment

## Avantages du mode automatique

✅ **Zéro configuration manuelle**
- Pas besoin de mettre à jour les event slugs chaque jour
- Le bot trouve les marchés tout seul

✅ **Opération 24/7**
- Lance le bot une fois, il tourne indéfiniment
- Trouve automatiquement les nouveaux marchés

✅ **Multi-marchés**
- Trade sur plusieurs jours simultanément (J, J+1, J+2...)
- Optimise l'exposition selon les jours restants

✅ **Robuste**
- Double approche (slug direct + API scan)
- Continue à fonctionner même si un marché n'existe pas

## Exemple de session complète

```bash
# 1. Configuration minimale
cp .env.example .env
# Édite juste WEATHER_API_KEY et DRY_RUN_MODE

# 2. Lance le bot
source venv/bin/activate
python main.py run

# 3. Le bot fait tout automatiquement :
#    - Découvre les marchés disponibles
#    - Récupère les prévisions
#    - Calcule les edges
#    - Place les ordres
#    - Monitore en temps réel le jour J
#    - Trouve automatiquement les nouveaux marchés le lendemain
```

## Troubleshooting

### "Found 0 temperature event(s)"

Possibilités :
1. Aucun marché de température actif sur Polymarket actuellement
2. Le pattern des slugs a changé (rare)
3. Problème de connexion API

Solution :
```bash
# Test la découverte manuellement
python test_auto_discovery.py

# Si ça ne trouve rien, spécifie manuellement :
EVENT_SLUG=highest-temperature-in-nyc-on-november-1
```

### "Slug not found"

Le marché n'existe peut-être pas encore. Polymarket crée généralement les marchés :
- 2-3 jours à l'avance pour J+1, J+2
- Parfois seulement 1 jour à l'avance

Le bot réessaiera automatiquement au prochain scan.

### Vérifier les marchés disponibles

Visite directement :
- https://polymarket.com/event/highest-temperature-in-nyc-on-october-31
- https://polymarket.com/event/highest-temperature-in-nyc-on-november-1

Si le marché existe mais n'est pas trouvé, ouvre une issue sur GitHub !

## Architecture technique

```
Bot.scan_markets()
  ↓
  ├─ EVENT_SLUGS défini ? → Utilise les slugs manuels
  ├─ EVENT_SLUG défini ?  → Utilise le slug unique
  └─ Sinon → MarketDiscovery.discover_temperature_events()
              ↓
              ├─ _try_direct_slugs() [Génération prédictive]
              │   ├─ Pour chaque jour de 0 à ADVANCE_DAYS :
              │   │   └─ Essaie : highest-temperature-in-{city}-on-{month}-{day}
              │   └─ Retourne les slugs trouvés
              │
              └─ API Scan [Backup si rien trouvé]
                  ├─ Fetch 500 events depuis Gamma API
                  ├─ Filtre par keywords (temperature, NYC)
                  └─ Filtre par date (dans les N prochains jours)
```

## Conclusion

Avec la découverte automatique, le bot est maintenant **100% autonome** ! 🚀

Tu le lances une fois, et il :
- Trouve les marchés automatiquement
- Trade intelligemment selon les prévisions
- S'adapte aux nouveaux marchés chaque jour
- Tourne indéfiniment sans intervention

C'est exactement ce qu'il faut pour un bot de trading automatisé !
