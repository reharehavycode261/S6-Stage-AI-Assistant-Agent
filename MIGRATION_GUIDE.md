# Guide de Migration - Nouvelle Structure

Ce document explique la nouvelle structure du projet et comment l'utiliser après la réorganisation.

## 📁 Nouvelle Structure

```
S6-Stage-AI-Assistant-Agent/
├── backend/              # 🔧 Code backend (API, services, logique métier)
│   ├── admin/           # Interface d'administration
│   ├── ai/              # Modules IA et LLM
│   ├── config/          # Configuration
│   ├── graph/           # Graphes de workflow
│   ├── models/          # Modèles de données
│   ├── nodes/           # Nœuds de workflow
│   ├── services/        # Services métier
│   ├── tools/           # Outils backend
│   ├── utils/           # Utilitaires
│   ├── tests/           # Tests
│   ├── main.py          # Point d'entrée principal
│   ├── requirements.txt # Dépendances Python
│   └── Dockerfile       # Image Docker
│
├── frontend/            # 🎨 Code frontend
│   └── ai-agent-front/  # Application React
│
├── artifacts/           # 📜 Scripts, migrations, et fichiers annexes
│   ├── scripts/        # Scripts Python utilitaires
│   ├── shell/          # Scripts shell
│   ├── data/           # Données et fichiers SQL
│   ├── migrations/     # Migrations de base de données
│   ├── sql/            # Fichiers SQL
│   ├── docker/         # Fichiers Docker (postgres, etc.)
│   ├── backups/        # Sauvegardes
│   └── logs/           # Fichiers de logs
│
├── .env                 # Variables d'environnement (à créer)
├── .gitignore          # Fichiers à ignorer par Git
├── docker-compose.yml  # Configuration Docker principale
├── start.sh            # Script de démarrage (Docker)
├── start-dev.sh        # Script de démarrage (développement local)
└── README.md           # Documentation principale
```

## 🚀 Démarrage Rapide

### Option 1: Avec Docker (Recommandé)

```bash
# 1. Créer le fichier .env à partir du template
cp artifacts/env_template.txt .env

# 2. Éditer le fichier .env avec vos clés API
# ANTHROPIC_API_KEY=...
# GITHUB_TOKEN=...
# MONDAY_API_KEY=...

# 3. Démarrer tous les services
chmod +x start.sh
./start.sh
```

### Option 2: Développement Local (Sans Docker)

```bash
# 1. Créer le fichier .env
cp artifacts/env_template.txt .env

# 2. Éditer le fichier .env

# 3. Démarrer en mode développement
chmod +x start-dev.sh
./start-dev.sh
```

## 🔄 Changements Importants

### 1. Imports Python

Les imports restent **relatifs au dossier `backend/`**. Aucun changement n'est nécessaire dans le code Python tant que vous exécutez les scripts depuis le dossier `backend/`.

**Exemple d'import (inchangé):**
```python
from models.schemas import TaskRequest
from services.webhook_service import WebhookService
from config.settings import get_settings
```

### 2. Exécution des Scripts

#### Avant (racine du projet):
```bash
python main.py
python scripts/mon_script.py
```

#### Après (depuis backend/):
```bash
cd backend
python main.py

# Ou depuis la racine avec le bon chemin:
python backend/main.py
```

#### Scripts utilitaires (depuis la racine):
```bash
python artifacts/scripts/mon_script.py
```

### 3. Docker

Le nouveau `docker-compose.yml` à la racine pointe automatiquement vers `backend/` pour construire l'image.

**Commandes Docker (depuis la racine):**
```bash
# Démarrer
docker-compose up -d

# Voir les logs
docker-compose logs -f

# Arrêter
docker-compose down

# Reconstruire
docker-compose build
```

### 4. Frontend

Le frontend reste indépendant dans `frontend/ai-agent-front/`.

**Pour lancer le frontend:**
```bash
cd frontend/ai-agent-front
npm install
npm run dev
```

## 📝 Scripts Shell Utiles

Tous les scripts shell sont maintenant dans `artifacts/shell/`:

```bash
# Démarrer tous les services
./artifacts/shell/start_all.sh

# Arrêter tous les services
./artifacts/shell/stop_all.sh

# Redémarrer le backend
./artifacts/shell/restart_backend.sh

# Nettoyer Celery
./artifacts/shell/cleanup_celery.sh

# Appliquer les migrations
./artifacts/shell/apply_all_migrations.sh
```

## 🗃️ Base de Données

Les fichiers SQL sont dans `artifacts/`:
- **Migrations**: `artifacts/migrations/`
- **Schémas**: `artifacts/data/`
- **Scripts SQL**: `artifacts/sql/`

## 📊 Logs

Tous les logs sont centralisés dans `artifacts/logs/`:
- `celery.log`
- `workflows.log`
- `performance.log`
- etc.

## 🔧 Variables d'Environnement

Le fichier `.env` doit être créé **à la racine du projet** (pas dans `backend/`).

**Template disponible:**
- `artifacts/env_template.txt` (version simple)
- `artifacts/env_template_with_slack.txt` (avec Slack)

## ⚠️ Points d'Attention

### 1. PYTHONPATH

Si vous exécutez des scripts Python depuis la racine, ajoutez le dossier `backend/` au `PYTHONPATH`:

```bash
export PYTHONPATH="${PYTHONPATH}:${PWD}/backend"
python artifacts/scripts/mon_script.py
```

### 2. Chemins Relatifs

Certains scripts dans `artifacts/scripts/` peuvent contenir des imports qui supposent qu'ils sont à la racine. Si vous rencontrez des erreurs d'import:

**Solution 1: Ajuster PYTHONPATH**
```bash
cd artifacts/scripts
export PYTHONPATH="${PYTHONPATH}:${PWD}/../../backend"
python mon_script.py
```

**Solution 2: Exécuter depuis backend/**
```bash
cd backend
python ../artifacts/scripts/mon_script.py
```

### 3. Tests

Les tests sont dans `backend/tests/` :

```bash
cd backend
pytest
# ou
pytest tests/
```

## 🛠️ Mise à Jour des Configurations

### Si vous avez des scripts personnalisés:

1. **Scripts qui lancent le backend**: Ajoutez `cd backend` avant
2. **Scripts qui utilisent des imports Python**: Ajoutez le backend au PYTHONPATH
3. **Scripts qui référencent des fichiers**: Mettez à jour les chemins

### Exemple de mise à jour:

**Avant:**
```bash
#!/bin/bash
python main.py
```

**Après:**
```bash
#!/bin/bash
cd backend
python main.py
```

## 📚 Ressources

- **Documentation backend**: `backend/README.md` (si existe)
- **Documentation frontend**: `frontend/ai-agent-front/README.md`
- **Structure du projet**: `README_STRUCTURE.md`

## ❓ Dépannage

### Erreur "Module not found"

```bash
# Vérifiez que vous êtes dans le bon dossier
pwd

# Si vous êtes à la racine et voulez lancer le backend:
cd backend
python main.py

# Ou ajoutez backend au PYTHONPATH:
export PYTHONPATH="${PYTHONPATH}:${PWD}/backend"
```

### Erreur Docker "No such file or directory"

```bash
# Reconstruisez les images Docker
docker-compose build --no-cache
docker-compose up -d
```

### Les logs n'apparaissent pas

```bash
# Vérifiez que le dossier artifacts/logs existe
ls -la artifacts/logs/

# Si nécessaire, créez-le
mkdir -p artifacts/logs
chmod 755 artifacts/logs
```

## ✅ Checklist Post-Migration

- [ ] Fichier `.gitignore` créé
- [ ] Fichier `.env` configuré à la racine
- [ ] Docker fonctionne: `docker-compose up -d`
- [ ] API accessible: http://localhost:8000
- [ ] RabbitMQ accessible: http://localhost:15672
- [ ] Frontend fonctionne (si applicable)
- [ ] Tests passent: `cd backend && pytest`
- [ ] Scripts shell mis à jour et fonctionnels

## 📞 Support

Si vous rencontrez des problèmes après la migration, vérifiez:
1. Les chemins dans vos scripts personnalisés
2. Le PYTHONPATH si vous avez des erreurs d'import
3. Les volumes Docker dans `docker-compose.yml`
4. Les permissions des fichiers (notamment les scripts .sh)

---

**Date de migration**: 2025-11-20
**Version**: 2.0 (Structure réorganisée)

