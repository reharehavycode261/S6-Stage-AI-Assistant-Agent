#!/bin/bash

echo "🔄 Redémarrage des workers Celery..."
echo "======================================"

# Tuer tous les processus Celery
echo "🛑 Arrêt des workers existants..."
pkill -f 'celery worker' || echo "Aucun worker actif"

# Attendre que les processus se terminent
sleep 2

# Vérifier qu'ils sont bien arrêtés
if pgrep -f 'celery worker' > /dev/null; then
    echo "⚠️  Certains workers sont encore actifs, force kill..."
    pkill -9 -f 'celery worker'
    sleep 1
fi

echo "✅ Workers arrêtés"
echo ""
echo "🚀 Redémarrage des workers..."
echo "Pour redémarrer, utilisez docker-compose ou votre commande habituelle."
echo ""
echo "Exemples:"
echo "  • Docker: docker-compose restart celery_worker"
echo "  • Local: celery -A celery_app worker --loglevel=info"
echo ""
echo "✅ Script terminé"

