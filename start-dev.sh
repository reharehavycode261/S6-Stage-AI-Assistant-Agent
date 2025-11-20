#!/bin/bash

# ========================================================
# Script de démarrage pour le développement local
# ========================================================
# Lance le backend en mode développement (sans Docker)
# ========================================================

set -e

echo "🚀 Démarrage en mode développement"
echo "===================================="
echo ""

# Se déplacer dans le dossier backend
cd backend

# Vérifier que l'environnement virtuel existe
if [ ! -d "../venv" ]; then
    echo "❌ Environnement virtuel non trouvé."
    echo "📝 Création de l'environnement virtuel..."
    cd ..
    python3 -m venv venv
    source venv/bin/activate
    cd backend
    pip install --upgrade pip
    pip install -r requirements.txt
    cd ..
else
    source ../venv/bin/activate
fi

# Vérifier que le fichier .env existe
if [ ! -f "../.env" ] && [ ! -f ".env" ]; then
    echo "⚠️  Fichier .env non trouvé."
    echo ""
    echo "ℹ️  Le backend peut démarrer sans .env (avec des valeurs par défaut),"
    echo "   mais certaines fonctionnalités nécessiteront une configuration."
    echo ""
    echo "Pour créer un fichier .env :"
    echo "  cp ../artifacts/env_template.txt ../.env"
    echo "  # ou"
    echo "  cp ../artifacts/env_template.txt .env"
    echo ""
    read -p "Continuer sans .env ? (o/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Oo]$ ]]; then
        exit 1
    fi
else
    echo "✅ Fichier .env détecté"
fi

echo "📦 Installation/Mise à jour des dépendances..."
pip install -r requirements.txt --quiet

echo ""
echo "🚀 Démarrage de l'API FastAPI..."
echo ""

# Démarrer l'API avec uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Note: Pour lancer Celery en parallèle, ouvrez un autre terminal et exécutez:
# cd backend && source ../venv/bin/activate && celery -A services.celery_app worker --loglevel=info

