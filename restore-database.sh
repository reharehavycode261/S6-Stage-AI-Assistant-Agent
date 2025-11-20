#!/bin/bash

# ========================================================
# RESTAURATION DE LA BASE DE DONNÉES
# ========================================================

set -e  # Arrêter en cas d'erreur

# FIX: Utiliser le bon socket Docker Desktop
export DOCKER_HOST=unix:///Users/stagiaire_vycode/.docker/run/docker.sock

# Vérifier que Docker est accessible
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker n'est pas accessible. Essayez :"
    echo "   1. Ouvrez Docker Desktop"
    echo "   2. Attendez que l'icône devienne verte"
    echo "   3. OU lancez: sudo ln -sf /Users/stagiaire_vycode/.docker/run/docker.sock /var/run/docker.sock"
    exit 1
fi

echo "✅ Docker est accessible !"
echo ""
echo "🔥 RESTAURATION DE LA BASE DE DONNÉES DEPUIS BACKUP"
echo "=================================================="
echo ""

# Variables
BACKUP_FILE="/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent/artifacts/backups/backup_before_phase1_1_20251014_155125.sql"
COMPOSE_FILE="/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent/docker-compose.yml"

cd "/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent"

echo "📋 Étape 1/6 : Arrêt de tous les containers..."
docker-compose down
echo "✅ Containers arrêtés"
echo ""

echo "🗑️  Étape 2/6 : Suppression des volumes..."
docker volume rm ai_agent_postgres_data 2>/dev/null || echo "Volume postgres déjà supprimé"
docker volume rm ai_agent_redis_data 2>/dev/null || echo "Volume redis déjà supprimé"
docker volume rm ai_agent_rabbitmq_data 2>/dev/null || echo "Volume rabbitmq déjà supprimé"
docker volume rm ai_agent_rabbitmq_logs 2>/dev/null || echo "Volume rabbitmq_logs déjà supprimé"
echo "✅ Anciens volumes supprimés"
echo ""

echo "🆕 Étape 3/6 : Création des nouveaux volumes..."
docker volume create ai_agent_postgres_data
docker volume create ai_agent_redis_data
docker volume create ai_agent_rabbitmq_data
docker volume create ai_agent_rabbitmq_logs
echo "✅ Nouveaux volumes créés"
echo ""

echo "🚀 Étape 4/6 : Démarrage de PostgreSQL uniquement..."
docker-compose up -d postgres
echo "⏳ Attente que PostgreSQL soit prêt (30 secondes)..."
sleep 30
echo "✅ PostgreSQL démarré"
echo ""

echo "📥 Étape 5/6 : Restauration du backup SQL..."
echo "   Backup: $BACKUP_FILE"
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < "$BACKUP_FILE"
echo "✅ Backup restauré avec succès !"
echo ""

echo "🚀 Étape 6/6 : Démarrage de tous les services..."
docker-compose up -d
echo "✅ Tous les services démarrés"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ RESTAURATION TERMINÉE AVEC SUCCÈS !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Vérification de la base de données :"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -c "\dt" | head -20
echo ""
echo "🌐 Services disponibles :"
echo "   - PostgreSQL:  localhost:5432"
echo "   - Redis:       localhost:6379"
echo "   - RabbitMQ:    localhost:15672"
echo "   - App:         http://localhost:8000"
echo ""

