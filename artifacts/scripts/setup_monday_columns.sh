#!/bin/bash

# ================================
# Script de configuration automatique des colonnes Monday.com
# ================================

echo "🚀 Configuration automatique des column IDs Monday.com..."
echo ""

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "config/settings.py" ]; then
    echo "❌ Erreur: Exécutez ce script depuis la racine du projet AI-Agent"
    exit 1
fi

# Vérifier que le fichier .env existe
if [ ! -f ".env" ]; then
    echo "❌ Erreur: Fichier .env introuvable"
    echo "💡 Copiez d'abord env_template.txt vers .env et configurez vos clés API"
    exit 1
fi

# Vérifier que l'environnement virtuel est activé
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️ Activation de l'environnement virtuel..."
    source venv/bin/activate
fi

# Exécuter le script Python de récupération des column IDs
echo "📡 Interrogation de l'API Monday.com..."
python3 scripts/get_monday_column_ids.py

# Vérifier le résultat
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Configuration terminée avec succès !"
    echo "♻️ Redémarrez Celery pour prendre en compte les nouveaux IDs:"
    echo "   pkill -f celery && celery -A services.celery_app worker --loglevel=info"
else
    echo ""
    echo "❌ Échec de la configuration automatique"
    echo "💡 Vérifiez vos clés API Monday.com dans .env"
    exit 1
fi 