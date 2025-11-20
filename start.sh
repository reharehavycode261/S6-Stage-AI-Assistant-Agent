#!/bin/bash

# ========================================================
# Script de démarrage principal
# ========================================================
# Lance le backend via Docker Compose
# ========================================================

set -e

echo "🚀 Démarrage de l'Agent d'Automatisation IA"
echo "============================================"
echo ""

# Vérifier que Docker est installé et en cours d'exécution
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Veuillez installer Docker Desktop."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker n'est pas en cours d'exécution. Veuillez démarrer Docker Desktop."
    exit 1
fi

# Vérifier que le fichier .env existe
if [ ! -f ".env" ]; then
    echo "⚠️  Fichier .env non trouvé."
    echo "📝 Création d'un fichier .env à partir du template..."
    
    if [ -f "artifacts/env_template.txt" ]; then
        cp artifacts/env_template.txt .env
        echo "✅ Fichier .env créé. Veuillez le remplir avec vos clés API."
        echo ""
        echo "Éditez le fichier .env avant de continuer:"
        echo "  - ANTHROPIC_API_KEY"
        echo "  - GITHUB_TOKEN"
        echo "  - MONDAY_API_KEY"
        echo "  - etc."
        echo ""
        read -p "Appuyez sur Entrée une fois le fichier .env configuré..."
    else
        echo "❌ Template .env non trouvé."
        exit 1
    fi
fi

# Arrêter les conteneurs existants
echo "🛑 Arrêt des conteneurs existants..."
docker-compose down 2>/dev/null || true

# Démarrer les services
echo "🚀 Démarrage des services Docker..."
docker-compose up -d

# Attendre que les services soient prêts
echo "⏳ Attente du démarrage des services..."
sleep 10

# Vérifier l'état des services
echo ""
echo "📊 État des services:"
docker-compose ps

echo ""
echo "✅ Services démarrés avec succès!"
echo ""
echo "📌 URLs d'accès:"
echo "  - API Backend:     http://localhost:8000"
echo "  - Documentation:   http://localhost:8000/docs"
echo "  - RabbitMQ:        http://localhost:15672 (ai_agent_user/secure_password_123)"
echo "  - Flower (Celery): http://localhost:5555 (admin/flower123)"
echo ""
echo "📋 Commandes utiles:"
echo "  - Voir les logs:     docker-compose logs -f"
echo "  - Arrêter:           docker-compose down"
echo "  - Redémarrer:        docker-compose restart"
echo ""

