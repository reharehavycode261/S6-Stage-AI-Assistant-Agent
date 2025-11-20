#!/bin/bash

# Script pour redémarrer le backend proprement

echo "🔄 Redémarrage du backend AI-Agent..."

# Trouver et arrêter les processus uvicorn existants
echo "🛑 Arrêt des processus existants..."
pkill -f "uvicorn main:app" || echo "Aucun processus uvicorn à arrêter"

# Attendre que les processus se terminent
sleep 2

# Vérifier que le venv est activé
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Activation du virtualenv..."
    source venv/bin/activate
fi

# Démarrer le serveur
echo "🚀 Démarrage du serveur backend..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &

# Attendre quelques secondes pour vérifier le démarrage
sleep 5

# Vérifier que le serveur est démarré
if pgrep -f "uvicorn main:app" > /dev/null; then
    echo "✅ Backend démarré avec succès sur http://localhost:8000"
    echo "📊 Documentation API: http://localhost:8000/docs"
else
    echo "❌ Erreur lors du démarrage du backend"
    exit 1
fi

