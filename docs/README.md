# 📚 Documentation

Bienvenue dans la documentation complète du **Poly-Weather Trading Bot** !

## 📖 Table des Matières

### 🚀 Guides de Démarrage
- **[QUICK_START.md](QUICK_START.md)** - Démarrage rapide en 5 minutes
  - Configuration .env
  - Premier lancement
  - Tests de base

### 🔍 Découverte de Marchés
- **[MARKET_DISCOVERY.md](MARKET_DISCOVERY.md)** - Comment trouver les marchés Polymarket
  - API Gamma Markets
  - Recherche par slug
  - Filtrage par ville

- **[AUTO_DISCOVERY.md](AUTO_DISCOVERY.md)** - Découverte automatique de marchés
  - Génération automatique de slugs
  - Marchés pour J+0 à J+N
  - 100% autonome

### 📡 WebSocket & Temps Réel
- **[WEBSOCKET_COMPLETE.md](WEBSOCKET_COMPLETE.md)** - ⭐ Guide complet WebSocket
  - Architecture hybride (sync + async)
  - Configuration
  - Performance (<1s latence)
  - Troubleshooting

- **[WEBSOCKET_PLAN.md](WEBSOCKET_PLAN.md)** - Plan initial d'intégration WebSocket
  - Analyse de l'API Polymarket
  - Stratégie d'implémentation

- **[WEBSOCKET_INTEGRATION.md](WEBSOCKET_INTEGRATION.md)** - Guide d'intégration détaillé
  - Étapes d'intégration
  - Code examples

### 🔄 Migration Asynchrone
- **[ASYNC_MIGRATION_GUIDE.md](ASYNC_MIGRATION_GUIDE.md)** - Guide pour migration 100% async
  - Architecture cible
  - Plan de migration (3-5h)
  - Code avant/après
  - Troubleshooting

### 📊 Logs & Monitoring
- **[LOGS_GUIDE.md](LOGS_GUIDE.md)** - Comprendre les logs du bot
  - Emojis et leur signification
  - États du bot
  - Détection d'edges
  - Exemples de logs

### 🧪 Tests
- **[TEST_STRUCTURE.md](TEST_STRUCTURE.md)** - Structure des tests
  - Organisation unit/integration
  - Comment lancer les tests
  - Statistiques (63 tests)

- **[../tests/README.md](../tests/README.md)** - Documentation complète des tests
  - Description de chaque test
  - Troubleshooting
  - Comment ajouter des tests

---

## 🗺️ Navigation Rapide

### Par Use Case

**Je veux démarrer rapidement** →
- [QUICK_START.md](QUICK_START.md)

**Je veux comprendre comment le bot trouve les marchés** →
- [MARKET_DISCOVERY.md](MARKET_DISCOVERY.md)
- [AUTO_DISCOVERY.md](AUTO_DISCOVERY.md)

**Je veux activer le WebSocket pour <1s de latence** →
- [WEBSOCKET_COMPLETE.md](WEBSOCKET_COMPLETE.md)

**Je veux migrer vers 100% async** →
- [ASYNC_MIGRATION_GUIDE.md](ASYNC_MIGRATION_GUIDE.md)

**Je ne comprends pas les logs** →
- [LOGS_GUIDE.md](LOGS_GUIDE.md)

**Je veux lancer les tests** →
- [TEST_STRUCTURE.md](TEST_STRUCTURE.md)
- [../tests/README.md](../tests/README.md)

---

## 📂 Organisation des Fichiers

```
docs/
├── README.md                     # Ce fichier
│
├── 🚀 Démarrage
│   ├── QUICK_START.md
│   ├── MARKET_DISCOVERY.md
│   └── AUTO_DISCOVERY.md
│
├── 📡 WebSocket & Performance
│   ├── WEBSOCKET_COMPLETE.md    # Guide principal ⭐
│   ├── WEBSOCKET_PLAN.md
│   └── WEBSOCKET_INTEGRATION.md
│
├── 🔄 Architecture
│   └── ASYNC_MIGRATION_GUIDE.md
│
└── 🧪 Monitoring & Tests
    ├── LOGS_GUIDE.md
    └── TEST_STRUCTURE.md
```

---

## 🎯 Parcours Recommandés

### Pour Débuter
1. [QUICK_START.md](QUICK_START.md) - Configuration de base
2. [LOGS_GUIDE.md](LOGS_GUIDE.md) - Comprendre les logs
3. [WEBSOCKET_COMPLETE.md](WEBSOCKET_COMPLETE.md) - Activer le temps réel

### Pour Développer
1. [AUTO_DISCOVERY.md](AUTO_DISCOVERY.md) - Ajouter de nouvelles villes
2. [TEST_STRUCTURE.md](TEST_STRUCTURE.md) - Lancer les tests
3. [../tests/README.md](../tests/README.md) - Ajouter des tests

### Pour Optimiser
1. [WEBSOCKET_COMPLETE.md](WEBSOCKET_COMPLETE.md) - Performance temps réel
2. [ASYNC_MIGRATION_GUIDE.md](ASYNC_MIGRATION_GUIDE.md) - Architecture async
3. [LOGS_GUIDE.md](LOGS_GUIDE.md) - Debugging avancé

---

## 📊 Statistiques Documentation

- **9 guides** de documentation
- **~90,000 mots** au total
- **Tout est documenté** : API, WebSocket, Tests, Logs, Migration
- **Code examples** dans chaque guide
- **Screenshots & diagrammes** quand nécessaire

---

## 🤝 Contribuer

Si tu ajoutes une nouvelle fonctionnalité :

1. **Crée un guide** dans `/docs` si c'est une feature majeure
2. **Mets à jour** les guides existants si nécessaire
3. **Ajoute des examples** de code
4. **Mets à jour** ce README.md avec le lien

### Template pour Nouveau Guide

```markdown
# Titre de la Feature

## Vue d'ensemble
[Description en 2-3 phrases]

## Prérequis
- Prérequis 1
- Prérequis 2

## Installation/Configuration
[Étapes avec code]

## Utilisation
[Examples concrets]

## Troubleshooting
[Problèmes courants + solutions]

## Références
- [Lien externe]
```

---

## 📞 Support

Si un guide n'est pas clair :
1. Vérifie les autres guides liés
2. Regarde les exemples de code dans `/src`
3. Lance les tests : `./run_tests.sh`
4. Ouvre une issue sur GitHub

---

## 🎉 Résumé

Tous les guides sont **complets**, **testés** et **à jour** !

**Start here** : [QUICK_START.md](QUICK_START.md) 🚀
