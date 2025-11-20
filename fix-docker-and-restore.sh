#!/bin/bash

# ========================================================
# FIX DOCKER + RESTAURATION
# ========================================================

echo "🔧 Création du lien symbolique Docker..."
echo ""
echo "⚠️  Ce script va vous demander votre mot de passe administrateur"
echo ""

# Créer le lien symbolique (nécessite sudo)
sudo ln -sf /Users/stagiaire_vycode/.docker/run/docker.sock /var/run/docker.sock

echo "✅ Lien symbolique créé !"
echo ""

# Vérifier que Docker fonctionne
if docker ps > /dev/null 2>&1; then
    echo "✅ Docker est maintenant accessible !"
    echo ""
    
    # Lancer la restauration
    echo "🚀 Lancement de la restauration..."
    cd "/Users/stagiaire_vycode/Stage Smartelia/S6-Stage-AI-Assistant-Agent"
    ./restore-database.sh
else
    echo "❌ Docker toujours inaccessible. Vérifiez que Docker Desktop est ouvert."
    exit 1
fi

