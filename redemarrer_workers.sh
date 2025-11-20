#!/bin/bash
# Script de redémarrage des workers Celery pour activer les modifications

echo "🔄 Redémarrage des workers Celery..."
echo ""

cd "$(dirname "$0")"

# Option 1 : Redémarrage avec Docker (recommandé)
if command -v docker-compose &> /dev/null; then
    echo "🐳 Docker Compose détecté - Redémarrage..."
    
    # Arrêter les workers
    docker-compose stop celery-worker-webhooks celery-worker-workflows
    
    # Redémarrer les workers
    docker-compose up -d celery-worker-webhooks celery-worker-workflows
    
    echo ""
    echo "✅ Workers redémarrés !"
    echo ""
    echo "📊 Vérification des logs (Ctrl+C pour arrêter) :"
    echo ""
    sleep 2
    docker-compose logs -f --tail=20 celery-worker-workflows
    
else
    echo "⚠️  Docker Compose non trouvé"
    echo "Veuillez redémarrer manuellement les workers Celery"
    echo ""
    echo "Option manuelle :"
    echo "1. Arrêter : docker-compose stop celery-worker-webhooks celery-worker-workflows"
    echo "2. Démarrer : docker-compose up -d celery-worker-webhooks celery-worker-workflows"
fi

