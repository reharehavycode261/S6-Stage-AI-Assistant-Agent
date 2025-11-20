#!/bin/bash

# Script de nettoyage des tâches Celery en attente
# Pour éviter l'exécution automatique de workflows au démarrage

echo "🧹 Script de nettoyage des tâches Celery en attente"
echo "=================================================="

# 1. Arrêter les workers Celery
echo "1️⃣ Arrêt des workers Celery..."
pkill -f "celery.*worker" || echo "Aucun worker Celery en cours"

# 2. Purger toutes les queues RabbitMQ
echo "2️⃣ Purge des queues RabbitMQ..."

# Purger les queues principales
rabbitmqctl purge_queue workflows || echo "Queue workflows non trouvée"
rabbitmqctl purge_queue webhooks || echo "Queue webhooks non trouvée"
rabbitmqctl purge_queue ai_generation || echo "Queue ai_generation non trouvée"
rabbitmqctl purge_queue tests || echo "Queue tests non trouvée"
rabbitmqctl purge_queue dlq || echo "Queue dlq non trouvée"

# Purger la queue par défaut
rabbitmqctl purge_queue celery || echo "Queue celery non trouvée"

# 3. Nettoyer les résultats Celery dans PostgreSQL
echo "3️⃣ Nettoyage des résultats Celery en base..."

# Vérifier si DATABASE_URL est définie
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️ DATABASE_URL non définie, utilisation des valeurs par défaut"
    DATABASE_URL="postgresql://admin:password@localhost:5432/ai_agent_admin"
fi

# Nettoyer les résultats Celery
psql "$DATABASE_URL" -c "
DELETE FROM celery_tasksetresult WHERE date_done < NOW() - INTERVAL '1 hour';
DELETE FROM celery_taskresult WHERE date_done < NOW() - INTERVAL '1 hour';
DELETE FROM celery_tasksetmeta WHERE date_done < NOW() - INTERVAL '1 hour';
DELETE FROM celery_taskmeta WHERE date_done < NOW() - INTERVAL '1 hour';
" 2>/dev/null || echo "⚠️ Tables Celery non trouvées ou erreur de connexion DB"

# 4. Redémarrer RabbitMQ (optionnel)
echo "4️⃣ Redémarrage RabbitMQ (optionnel)..."
read -p "Voulez-vous redémarrer RabbitMQ ? (y/N): " restart_rabbitmq
if [[ $restart_rabbitmq =~ ^[Yy]$ ]]; then
    if command -v systemctl &> /dev/null; then
        sudo systemctl restart rabbitmq-server
    elif command -v service &> /dev/null; then
        sudo service rabbitmq-server restart
    elif command -v brew &> /dev/null; then
        brew services restart rabbitmq
    else
        echo "⚠️ Impossible de redémarrer RabbitMQ automatiquement"
        echo "💡 Redémarrez manuellement : sudo systemctl restart rabbitmq-server"
    fi
fi

echo ""
echo "✅ Nettoyage terminé !"
echo ""
echo "📋 Prochaines étapes :"
echo "   1. Vérifiez votre fichier .env (configurez MONDAY_API_TOKEN si nécessaire)"
echo "   2. Redémarrez le worker Celery : celery -A services.celery_app worker --loglevel=info"
echo "   3. Vérifiez les logs pour confirmer l'absence d'erreurs"
echo "" 