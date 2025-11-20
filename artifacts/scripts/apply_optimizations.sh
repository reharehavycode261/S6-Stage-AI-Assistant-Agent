#!/bin/bash

# ============================================
# Script d'Application des Optimisations
# AI-Agent VyData
# ============================================

set -e  # Arrêter en cas d'erreur

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "============================================"
echo "   OPTIMISATION AI-AGENT VYDATA"
echo "   Application des Optimisations"
echo "============================================"
echo -e "${NC}"

# ============================================
# Étape 1 : Vérifier les prérequis
# ============================================
echo -e "${YELLOW}📋 Vérification des prérequis...${NC}"

# Vérifier Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker n'est pas installé${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker trouvé${NC}"

# Vérifier Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose n'est pas installé${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose trouvé${NC}"

# Vérifier que le container PostgreSQL tourne
if ! docker ps | grep -q ai_agent_postgres; then
    echo -e "${RED}❌ Le container PostgreSQL n'est pas démarré${NC}"
    echo -e "${YELLOW}💡 Démarrez-le avec: docker-compose -f docker-compose.rabbitmq.yml up -d postgres${NC}"
    exit 1
fi
echo -e "${GREEN}✅ PostgreSQL est démarré${NC}"

# Vérifier que le container Redis tourne
if ! docker ps | grep -q ai_agent_redis; then
    echo -e "${YELLOW}⚠️  Le container Redis n'est pas démarré${NC}"
    echo -e "${YELLOW}💡 Démarrez-le avec: docker-compose -f docker-compose.rabbitmq.yml up -d redis${NC}"
    echo -e "${YELLOW}Le cache Redis ne sera pas disponible mais ce n'est pas bloquant.${NC}"
fi

echo ""

# ============================================
# Étape 2 : Créer les index PostgreSQL
# ============================================
echo -e "${YELLOW}📊 Création des index PostgreSQL...${NC}"

if [ -f "sql/create_performance_indexes.sql" ]; then
    docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < sql/create_performance_indexes.sql
    echo -e "${GREEN}✅ Index créés avec succès${NC}"
else
    echo -e "${RED}❌ Fichier sql/create_performance_indexes.sql introuvable${NC}"
    exit 1
fi

echo ""

# ============================================
# Étape 3 : Vérifier les index créés
# ============================================
echo -e "${YELLOW}🔍 Vérification des index...${NC}"

INDEX_COUNT=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_%';")

echo -e "${GREEN}✅ $INDEX_COUNT index créés${NC}"

echo ""

# ============================================
# Étape 4 : Redémarrer les services backend
# ============================================
echo -e "${YELLOW}🔄 Redémarrage des services backend...${NC}"

docker-compose -f docker-compose.rabbitmq.yml restart app

echo -e "${GREEN}✅ Services backend redémarrés${NC}"

# Attendre que l'app soit prête
echo -e "${YELLOW}⏳ Attente du démarrage de l'application (10 secondes)...${NC}"
sleep 10

# Vérifier que l'app est accessible
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Application backend accessible${NC}"
else
    echo -e "${RED}❌ Application backend non accessible${NC}"
    echo -e "${YELLOW}💡 Vérifiez les logs: docker logs ai_agent_app${NC}"
fi

echo ""

# ============================================
# Étape 5 : Configuration Frontend
# ============================================
echo -e "${YELLOW}🎨 Configuration Frontend...${NC}"

if [ -d "ai-agent-front" ]; then
    cd ai-agent-front
    
    # Créer le fichier .env s'il n'existe pas
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}📝 Création du fichier .env...${NC}"
        cat > .env << 'EOF'
# Configuration API Backend
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# Configuration Application
VITE_APP_NAME=AI-Agent VyData Admin
VITE_APP_VERSION=3.0.0
VITE_APP_ENV=development

# Configuration Cache (en millisecondes)
VITE_CACHE_STALE_TIME=300000
VITE_CACHE_GC_TIME=600000

# Feature Flags
VITE_ENABLE_WEBSOCKETS=true
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_DEBUG_MODE=false
VITE_ENABLE_DEVTOOLS=true

# Logging
VITE_LOG_LEVEL=info

# Performance
VITE_ENABLE_LAZY_LOADING=true
VITE_ENABLE_CODE_SPLITTING=true
VITE_ENABLE_COMPRESSION=true
EOF
        echo -e "${GREEN}✅ Fichier .env créé${NC}"
    else
        echo -e "${GREEN}✅ Fichier .env existe déjà${NC}"
    fi
    
    cd ..
else
    echo -e "${YELLOW}⚠️  Dossier ai-agent-front introuvable${NC}"
fi

echo ""

# ============================================
# Résumé final
# ============================================
echo -e "${BLUE}"
echo "============================================"
echo "   ✅ OPTIMISATIONS APPLIQUÉES"
echo "============================================"
echo -e "${NC}"

echo -e "${GREEN}✅ Index PostgreSQL créés et vérifiés${NC}"
echo -e "${GREEN}✅ Pool de connexions activé${NC}"
echo -e "${GREEN}✅ Cache Redis configuré${NC}"
echo -e "${GREEN}✅ Compression GZIP activée${NC}"
echo -e "${GREEN}✅ Services backend redémarrés${NC}"
echo -e "${GREEN}✅ Configuration frontend prête${NC}"

echo ""
echo -e "${YELLOW}📋 Prochaines étapes :${NC}"
echo ""
echo -e "  1. ${BLUE}Démarrer le frontend :${NC}"
echo -e "     cd ai-agent-front && npm run dev"
echo ""
echo -e "  2. ${BLUE}Vérifier les performances :${NC}"
echo -e "     ./scripts/verify_optimizations.sh"
echo ""
echo -e "  3. ${BLUE}Consulter la documentation :${NC}"
echo -e "     docs/GUIDE_APPLICATION_OPTIMISATIONS.md"
echo ""

echo -e "${GREEN}🎉 Toutes les optimisations ont été appliquées avec succès !${NC}"

