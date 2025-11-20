#!/bin/bash
# Script de réinstallation complète de l'environnement virtuel

set -e

echo "════════════════════════════════════════════════════════════════════════"
echo "🔄 RÉINSTALLATION DE L'ENVIRONNEMENT VIRTUEL"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# 1. Sauvegarder l'ancien venv
echo "📦 Étape 1: Sauvegarde de l'ancien environnement..."
if [ -d "venv" ]; then
    BACKUP_NAME="venv.backup.$(date +%Y%m%d_%H%M%S)"
    mv venv "$BACKUP_NAME"
    echo "✅ Ancien venv sauvegardé dans: $BACKUP_NAME"
else
    echo "ℹ️  Aucun venv existant à sauvegarder"
fi
echo ""

# 2. Vérifier Python
echo "📋 Étape 2: Vérification de Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 non trouvé"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
ARCH=$(python3 -c "import platform; print(platform.machine())")
echo "✅ $PYTHON_VERSION"
echo "✅ Architecture: $ARCH"
echo ""

# 3. Créer le nouveau venv
echo "📦 Étape 3: Création du nouvel environnement virtuel..."
python3 -m venv venv
echo "✅ Nouvel environnement virtuel créé"
echo ""

# 4. Activer le venv
echo "📦 Étape 4: Activation de l'environnement..."
source venv/bin/activate
echo "✅ Environnement activé"
echo ""

# 5. Mettre à jour pip
echo "📦 Étape 5: Mise à jour de pip..."
python -m pip install --upgrade pip setuptools wheel
echo "✅ pip mis à jour"
echo ""

# 6. Installer les dépendances
echo "📦 Étape 6: Installation des dépendances..."
if [ -f "requirements.txt" ]; then
    echo "📋 Installation depuis requirements.txt..."
    pip install -r requirements.txt
    echo "✅ Dépendances installées"
else
    echo "⚠️  requirements.txt non trouvé, installation manuelle..."
    pip install pydantic fastapi uvicorn asyncpg celery redis langchain langchain-anthropic langgraph
    echo "✅ Packages essentiels installés"
fi
echo ""

# 7. Vérification
echo "📦 Étape 7: Vérification de l'installation..."
echo ""
python -c "import pydantic; print('✅ pydantic:', pydantic.__version__)"
python -c "import fastapi; print('✅ fastapi:', fastapi.__version__)"
python -c "import asyncpg; print('✅ asyncpg:', asyncpg.__version__)"
python -c "import celery; print('✅ celery:', celery.__version__)"
echo ""

# 8. Test des imports du projet
echo "📦 Étape 8: Test des imports du projet..."
python -c "from models.schemas import MondayColumnValue, MondayEvent, TaskRequest, WebhookPayload; print('✅ Imports du projet: OK')" || echo "❌ Erreur dans les imports"
echo ""

echo "════════════════════════════════════════════════════════════════════════"
echo "✅ RÉINSTALLATION TERMINÉE AVEC SUCCÈS"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "🚀 Pour utiliser l'environnement:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""

