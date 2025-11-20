#!/bin/bash

# Script pour réparer la connexion Docker
echo "🔧 Réparation de la connexion Docker..."

# Créer un lien symbolique vers le bon socket
if [ ! -e /var/run/docker.sock ]; then
    sudo ln -sf /Users/stagiaire_vycode/.docker/run/docker.sock /var/run/docker.sock
    echo "✅ Lien symbolique créé"
fi

# Vérifier la connexion
docker ps > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Docker est maintenant accessible !"
    echo ""
    echo "📊 Containers en cours d'exécution :"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
else
    echo "❌ Toujours pas accessible. Essayez:"
    echo "   export DOCKER_HOST=unix:///Users/stagiaire_vycode/.docker/run/docker.sock"
fi

