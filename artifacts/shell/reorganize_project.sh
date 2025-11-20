#!/bin/bash

# Script pour réorganiser la structure du projet
# Ce script doit être exécuté depuis la racine du projet

set -e

echo "🚀 Début de la réorganisation du projet..."

# Créer les nouveaux dossiers
echo "📁 Création des dossiers principaux..."
mkdir -p backend
mkdir -p frontend
mkdir -p artifacts

# 1. BACKEND - Déplacer tous les fichiers backend
echo "📦 Déplacement des fichiers backend..."
mv admin backend/ 2>/dev/null || true
mv ai backend/ 2>/dev/null || true
mv config backend/ 2>/dev/null || true
mv graph backend/ 2>/dev/null || true
mv models backend/ 2>/dev/null || true
mv nodes backend/ 2>/dev/null || true
mv services backend/ 2>/dev/null || true
mv tools backend/ 2>/dev/null || true
mv utils backend/ 2>/dev/null || true

# Déplacer les fichiers Python principaux du backend
mv main.py backend/ 2>/dev/null || true
mv main.py.backup_before_evaluation backend/ 2>/dev/null || true
mv requirements.txt backend/ 2>/dev/null || true
mv setup.py backend/ 2>/dev/null || true
mv pytest.ini backend/ 2>/dev/null || true
mv ruff.toml backend/ 2>/dev/null || true
mv Dockerfile backend/ 2>/dev/null || true
mv docker-compose.rabbitmq.yml backend/ 2>/dev/null || true

# 2. FRONTEND - Déplacer ai-agent-front
echo "🎨 Déplacement du frontend..."
mv ai-agent-front frontend/ 2>/dev/null || true

# Déplacer package.json et package-lock.json du root s'ils sont pour le frontend
if [ -f "package.json" ]; then
    # Vérifier si c'est pour le frontend ou autre chose
    # Pour l'instant on les laisse à la racine ou on les déplace selon le contenu
    echo "⚠️  package.json trouvé à la racine - vérification manuelle nécessaire"
fi

# 3. ARTIFACTS - Déplacer les scripts, migrations, données, etc.
echo "📜 Déplacement des artifacts..."
mkdir -p artifacts/scripts
mkdir -p artifacts/shell
mkdir -p artifacts/data
mkdir -p artifacts/migrations
mkdir -p artifacts/docker
mkdir -p artifacts/backups
mkdir -p artifacts/sql

# Scripts shell
mv all_shell/* artifacts/shell/ 2>/dev/null || true
rmdir all_shell 2>/dev/null || true
mv scripts/* artifacts/scripts/ 2>/dev/null || true
rmdir scripts 2>/dev/null || true

# Fichiers de données et SQL
mv data/* artifacts/data/ 2>/dev/null || true
rmdir data 2>/dev/null || true
mv migrations/* artifacts/migrations/ 2>/dev/null || true
rmdir migrations 2>/dev/null || true
mv sql/* artifacts/sql/ 2>/dev/null || true
rmdir sql 2>/dev/null || true

# Docker
mv docker/* artifacts/docker/ 2>/dev/null || true
rmdir docker 2>/dev/null || true

# Backups et logs
mv backups/* artifacts/backups/ 2>/dev/null || true
rmdir backups 2>/dev/null || true
mv logs artifacts/ 2>/dev/null || true

# Scripts Python utilitaires (pas de service backend direct)
mv *.sh artifacts/shell/ 2>/dev/null || true
mv cleanup_duplicate_tasks.py artifacts/scripts/ 2>/dev/null || true
mv cout_ia.py artifacts/scripts/ 2>/dev/null || true
mv create_initial_task.py artifacts/scripts/ 2>/dev/null || true
mv custom_evaluation_interactive.py artifacts/scripts/ 2>/dev/null || true
mv debug_monday_validation.py artifacts/scripts/ 2>/dev/null || true
mv demo_evaluation.py artifacts/scripts/ 2>/dev/null || true
mv diagnose_reactivation.py artifacts/scripts/ 2>/dev/null || true
mv diagnostic_reactivation.py artifacts/scripts/ 2>/dev/null || true
mv get_board_info.py artifacts/scripts/ 2>/dev/null || true
mv monitorer_webhooks_temps_reel.py artifacts/scripts/ 2>/dev/null || true
mv r9.py artifacts/scripts/ 2>/dev/null || true
mv restart_celery_clean.py artifacts/scripts/ 2>/dev/null || true
mv update_monday_board_config.py artifacts/scripts/ 2>/dev/null || true

# Fichiers template et documentation
mv env_template*.txt artifacts/ 2>/dev/null || true
mv pytest_output.txt artifacts/ 2>/dev/null || true
mv structure.txt artifacts/ 2>/dev/null || true

# Tests - on peut les mettre dans backend car ils testent le backend
mv tests backend/ 2>/dev/null || true

# Créer un fichier README pour expliquer la nouvelle structure
cat > README_STRUCTURE.md << 'EOF'
# Structure du Projet

Ce projet a été réorganisé pour séparer clairement les différentes parties :

## 📁 Structure

```
├── backend/          # Code backend (API, services, logique métier)
│   ├── admin/       # Interface d'administration
│   ├── ai/          # Modules IA et LLM
│   ├── config/      # Configuration
│   ├── graph/       # Graphes de workflow
│   ├── models/      # Modèles de données
│   ├── nodes/       # Nœuds de workflow
│   ├── services/    # Services métier
│   ├── tools/       # Outils backend
│   ├── utils/       # Utilitaires
│   ├── tests/       # Tests
│   └── main.py      # Point d'entrée principal
│
├── frontend/         # Code frontend
│   └── ai-agent-front/  # Application React
│
├── artifacts/        # Scripts, migrations, et fichiers annexes
│   ├── scripts/     # Scripts Python utilitaires
│   ├── shell/       # Scripts shell
│   ├── data/        # Données et fichiers SQL
│   ├── migrations/  # Migrations de base de données
│   ├── sql/         # Fichiers SQL
│   ├── docker/      # Fichiers Docker
│   ├── backups/     # Sauvegardes
│   └── logs/        # Fichiers de logs
│
├── .gitignore       # Fichiers à ignorer par Git
└── README.md        # Documentation principale
EOF

echo "✅ Réorganisation terminée !"
echo ""
echo "⚠️  ATTENTION : Vous devez maintenant :"
echo "   1. Vérifier que tous les fichiers sont bien déplacés"
echo "   2. Mettre à jour les imports Python dans le backend"
echo "   3. Mettre à jour les chemins dans les fichiers de configuration"
echo "   4. Tester que tout fonctionne correctement"
echo "   5. Commit les changements avec git"
echo ""
echo "📝 Un fichier README_STRUCTURE.md a été créé pour documenter la nouvelle structure"

