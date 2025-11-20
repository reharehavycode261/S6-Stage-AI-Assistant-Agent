#!/bin/bash

# ============================================
# Script de Vérification des Optimisations
# AI-Agent VyData
# ============================================

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "============================================"
echo "   VÉRIFICATION DES OPTIMISATIONS"
echo "   AI-Agent VyData"
echo "============================================"
echo -e "${NC}"

# ============================================
# 1. Vérifier PostgreSQL
# ============================================
echo -e "${YELLOW}📊 Vérification PostgreSQL...${NC}"

# Compter les index
INDEX_COUNT=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_%';" 2>/dev/null | tr -d ' ')

if [ "$INDEX_COUNT" -gt "40" ]; then
    echo -e "${GREEN}✅ $INDEX_COUNT index créés${NC}"
else
    echo -e "${RED}❌ Seulement $INDEX_COUNT index trouvés (attendu: 46+)${NC}"
fi

# Vérifier la taille des index
echo -e "${YELLOW}   Taille totale des index:${NC}"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT pg_size_pretty(SUM(pg_relation_size(indexname::regclass))) FROM pg_indexes WHERE schemaname = 'public';" 2>/dev/null

echo ""

# ============================================
# 2. Vérifier Redis
# ============================================
echo -e "${YELLOW}💾 Vérification Redis...${NC}"

if docker exec ai_agent_redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis est accessible${NC}"
    
    # Compter les clés en cache
    KEYS_COUNT=$(docker exec ai_agent_redis redis-cli DBSIZE 2>/dev/null | grep -o '[0-9]*')
    echo -e "${GREEN}   $KEYS_COUNT clés en cache${NC}"
    
    # Afficher quelques clés
    echo -e "${YELLOW}   Clés en cache:${NC}"
    docker exec ai_agent_redis redis-cli KEYS '*' 2>/dev/null | head -5
else
    echo -e "${RED}❌ Redis n'est pas accessible${NC}"
fi

echo ""

# ============================================
# 3. Tester les endpoints backend
# ============================================
echo -e "${YELLOW}🌐 Test des endpoints backend...${NC}"

# Fonction pour tester un endpoint
test_endpoint() {
    local url=$1
    local name=$2
    
    echo -e "${BLUE}   Testing $name...${NC}"
    
    # Mesurer le temps de réponse
    RESPONSE_TIME=$(curl -o /dev/null -s -w '%{time_total}\n' "$url" 2>/dev/null)
    HTTP_CODE=$(curl -o /dev/null -s -w '%{http_code}\n' "$url" 2>/dev/null)
    
    if [ "$HTTP_CODE" -eq "200" ]; then
        # Convertir en millisecondes
        TIME_MS=$(echo "$RESPONSE_TIME * 1000" | bc)
        echo -e "${GREEN}   ✅ $name: ${TIME_MS}ms (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "${RED}   ❌ $name: HTTP $HTTP_CODE${NC}"
    fi
}

# Tester plusieurs endpoints
test_endpoint "http://localhost:8000/health" "Health Check"
test_endpoint "http://localhost:8000/api/dashboard/metrics" "Dashboard Metrics (1ère requête)"

# Attendre un peu puis tester à nouveau pour voir l'effet du cache
sleep 1
test_endpoint "http://localhost:8000/api/dashboard/metrics" "Dashboard Metrics (cache)"

test_endpoint "http://localhost:8000/api/tasks?page=1&per_page=20" "Tasks List"

echo ""

# ============================================
# 4. Vérifier les logs backend
# ============================================
echo -e "${YELLOW}📝 Vérification des logs backend...${NC}"

# Chercher les messages d'initialisation
if docker logs ai_agent_app 2>&1 | grep -q "Pool PostgreSQL initialisé"; then
    echo -e "${GREEN}✅ Pool PostgreSQL initialisé${NC}"
else
    echo -e "${RED}❌ Pool PostgreSQL non initialisé${NC}"
fi

if docker logs ai_agent_app 2>&1 | grep -q "Redis initialisé"; then
    echo -e "${GREEN}✅ Redis initialisé${NC}"
else
    echo -e "${YELLOW}⚠️  Redis non initialisé (non bloquant)${NC}"
fi

echo ""

# ============================================
# 5. Vérifier la compression GZIP
# ============================================
echo -e "${YELLOW}📦 Vérification compression GZIP...${NC}"

# Tester si la compression est active
GZIP_HEADER=$(curl -H "Accept-Encoding: gzip" -I http://localhost:8000/api/dashboard/metrics 2>/dev/null | grep -i "content-encoding: gzip")

if [ -n "$GZIP_HEADER" ]; then
    echo -e "${GREEN}✅ Compression GZIP activée${NC}"
else
    echo -e "${YELLOW}⚠️  Compression GZIP non détectée (réponse peut-être trop petite)${NC}"
fi

echo ""

# ============================================
# 6. Statistiques de performance
# ============================================
echo -e "${YELLOW}📈 Statistiques de performance...${NC}"

# Queries par minute (estimation)
echo -e "${BLUE}   Connexions PostgreSQL actives:${NC}"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'ai_agent_admin';" 2>/dev/null

# Taille de la base
echo -e "${BLUE}   Taille de la base de données:${NC}"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT pg_size_pretty(pg_database_size('ai_agent_admin'));" 2>/dev/null

# Cache hit ratio PostgreSQL
echo -e "${BLUE}   Cache hit ratio PostgreSQL:${NC}"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT round(100.0 * sum(blks_hit) / nullif(sum(blks_hit + blks_read), 0), 2) || '%' AS cache_hit_ratio FROM pg_stat_database WHERE datname = 'ai_agent_admin';" 2>/dev/null

echo ""

# ============================================
# 7. Vérifier le frontend
# ============================================
echo -e "${YELLOW}🎨 Vérification frontend...${NC}"

if [ -f "ai-agent-front/.env" ]; then
    echo -e "${GREEN}✅ Fichier .env existe${NC}"
else
    echo -e "${RED}❌ Fichier .env manquant${NC}"
fi

if [ -f "ai-agent-front/vite.config.ts" ]; then
    if grep -q "manualChunks" ai-agent-front/vite.config.ts; then
        echo -e "${GREEN}✅ Code splitting configuré${NC}"
    else
        echo -e "${RED}❌ Code splitting non configuré${NC}"
    fi
fi

if [ -f "ai-agent-front/src/hooks/useApiOptimized.ts" ]; then
    echo -e "${GREEN}✅ Hooks optimisés créés${NC}"
else
    echo -e "${RED}❌ Hooks optimisés manquants${NC}"
fi

echo ""

# ============================================
# Résumé final
# ============================================
echo -e "${BLUE}"
echo "============================================"
echo "   RÉSUMÉ DE LA VÉRIFICATION"
echo "============================================"
echo -e "${NC}"

# Compter les succès
SUCCESS_COUNT=0
TOTAL_CHECKS=10

# Vérifications critiques
[ "$INDEX_COUNT" -gt "40" ] && ((SUCCESS_COUNT++))
docker exec ai_agent_redis redis-cli ping > /dev/null 2>&1 && ((SUCCESS_COUNT++))
curl -f http://localhost:8000/health > /dev/null 2>&1 && ((SUCCESS_COUNT++))
docker logs ai_agent_app 2>&1 | grep -q "Pool PostgreSQL initialisé" && ((SUCCESS_COUNT++))
[ -f "ai-agent-front/.env" ] && ((SUCCESS_COUNT++))
[ -f "ai-agent-front/src/hooks/useApiOptimized.ts" ] && ((SUCCESS_COUNT++))
grep -q "manualChunks" ai-agent-front/vite.config.ts 2>/dev/null && ((SUCCESS_COUNT++))

# Note finale
PERCENTAGE=$((SUCCESS_COUNT * 100 / 7))

if [ $PERCENTAGE -ge 85 ]; then
    echo -e "${GREEN}✅ Score: $SUCCESS_COUNT/7 ($PERCENTAGE%)${NC}"
    echo -e "${GREEN}🎉 Les optimisations sont correctement appliquées !${NC}"
elif [ $PERCENTAGE -ge 60 ]; then
    echo -e "${YELLOW}⚠️  Score: $SUCCESS_COUNT/7 ($PERCENTAGE%)${NC}"
    echo -e "${YELLOW}Certaines optimisations ne sont pas complètes.${NC}"
else
    echo -e "${RED}❌ Score: $SUCCESS_COUNT/7 ($PERCENTAGE%)${NC}"
    echo -e "${RED}Les optimisations nécessitent une attention.${NC}"
fi

echo ""
echo -e "${YELLOW}💡 Pour plus d'informations:${NC}"
echo -e "   - Logs backend: ${BLUE}docker logs ai_agent_app${NC}"
echo -e "   - Logs PostgreSQL: ${BLUE}docker logs ai_agent_postgres${NC}"
echo -e "   - Logs Redis: ${BLUE}docker logs ai_agent_redis${NC}"
echo -e "   - Documentation: ${BLUE}docs/GUIDE_APPLICATION_OPTIMISATIONS.md${NC}"
echo ""

