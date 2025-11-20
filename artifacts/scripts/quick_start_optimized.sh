#!/bin/bash

# ============================================
# Quick Start - AI-Agent Optimisé
# Démarre tout le système avec optimisations
# ============================================

set -e

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "============================================"
echo "   🚀 QUICK START - AI-AGENT OPTIMISÉ"
echo "============================================"
echo -e "${NC}"

# ============================================
# 1. Démarrer les services Docker
# ============================================
echo -e "${YELLOW}🐳 Démarrage des containers Docker...${NC}"
docker-compose -f docker-compose.rabbitmq.yml up -d

echo -e "${YELLOW}⏳ Attente du démarrage des services (15 secondes)...${NC}"
sleep 15

# ============================================
# 2. Appliquer les optimisations
# ============================================
echo -e "${YELLOW}⚡ Application des optimisations...${NC}"
./scripts/apply_optimizations.sh

# ============================================
# 3. Démarrer le frontend
# ============================================
echo -e "${YELLOW}🎨 Configuration du frontend...${NC}"

if [ -d "ai-agent-front" ]; then
    cd ai-agent-front
    
    # Installer les dépendances si nécessaire
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}📦 Installation des dépendances npm...${NC}"
        npm install
    fi
    
    # Démarrer en mode dev en arrière-plan
    echo -e "${GREEN}🚀 Démarrage du frontend...${NC}"
    echo -e "${YELLOW}💡 Le frontend sera accessible sur http://localhost:3000${NC}"
    echo -e "${YELLOW}💡 Utilisez Ctrl+C pour arrêter${NC}"
    echo ""
    
    npm run dev
else
    echo -e "${RED}❌ Dossier ai-agent-front introuvable${NC}"
fi

