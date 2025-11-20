#!/bin/bash
# ========================================================================
# SCRIPT DE CORRECTION - Création de la table webhook_events
# ========================================================================
# Ce script crée la table webhook_events manquante
# ========================================================================

set -e

echo "════════════════════════════════════════════════════════════════════════"
echo "🔧 CORRECTION: Création de la table webhook_events"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Vérifier si Docker est en cours d'exécution
if docker ps | grep -q "ai-agent-postgres"; then
    echo "✅ Conteneur PostgreSQL détecté"
    echo ""
    echo "📋 Exécution du script SQL..."
    echo ""
    
    docker exec -i ai-agent-postgres psql -U admin -d ai_agent < data/create_webhook_events_table.sql
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "════════════════════════════════════════════════════════════════════════"
        echo "✅ TABLE webhook_events CRÉÉE AVEC SUCCÈS"
        echo "════════════════════════════════════════════════════════════════════════"
        echo ""
        echo "📊 La table est maintenant prête à recevoir les webhooks Monday.com"
        echo ""
        echo "🔄 Vous pouvez redémarrer l'application:"
        echo "   docker-compose restart web"
        echo ""
    else
        echo ""
        echo "❌ Erreur lors de la création de la table"
        exit 1
    fi
else
    echo "⚠️  Conteneur PostgreSQL non trouvé"
    echo ""
    echo "💡 Options:"
    echo "   1. Démarrer Docker et lancer: docker-compose up -d postgres"
    echo "   2. Utiliser PostgreSQL local:"
    echo "      psql -U admin -d ai_agent < data/create_webhook_events_table.sql"
    echo ""
    exit 1
fi

