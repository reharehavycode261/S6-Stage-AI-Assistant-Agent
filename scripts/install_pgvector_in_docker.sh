#!/bin/bash
# ================================================================
# Script pour installer l'extension pgvector dans le conteneur Docker PostgreSQL
# ================================================================

set -e  # Arrêter en cas d'erreur

echo "=================================================================================================="
echo "🚀 INSTALLATION DE L'EXTENSION PGVECTOR DANS DOCKER"
echo "=================================================================================================="

# Couleurs pour le terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Nom du conteneur Docker
DOCKER_CONTAINER="ai_agent_postgres"

echo ""
echo -e "${BLUE}📋 Configuration:${NC}"
echo "   • Conteneur Docker: $DOCKER_CONTAINER"
echo ""

# Vérifier que le conteneur existe
if ! docker ps --format "{{.Names}}" | grep -q "^${DOCKER_CONTAINER}$"; then
    echo -e "${RED}❌ Conteneur '$DOCKER_CONTAINER' non trouvé${NC}"
    echo ""
    echo -e "${YELLOW}Conteneurs en cours d'exécution:${NC}"
    docker ps --format "   • {{.Names}} ({{.Image}})"
    exit 1
fi

echo -e "${GREEN}✅ Conteneur trouvé${NC}"
echo ""

# Vérifier la version de PostgreSQL
echo -e "${BLUE}🔍 Vérification de la version PostgreSQL...${NC}"
PG_VERSION=$(docker exec "$DOCKER_CONTAINER" psql -U admin -d ai_agent_admin -t -c "SHOW server_version;" | xargs | cut -d' ' -f1 | cut -d'.' -f1)
echo -e "   Version: PostgreSQL ${PG_VERSION}"
echo ""

# Installer les dépendances et pgvector
echo -e "${BLUE}📦 Installation de pgvector dans le conteneur...${NC}"
echo ""

echo "1️⃣  Mise à jour des paquets (Alpine)..."
docker exec -u root "$DOCKER_CONTAINER" sh -c "apk update" 2>&1 | tail -3

echo "2️⃣  Installation des dépendances de build (Alpine)..."
docker exec -u root "$DOCKER_CONTAINER" sh -c "apk add --no-cache build-base git clang15 llvm15 postgresql${PG_VERSION}-dev" 2>&1 | tail -5

echo "3️⃣  Clonage du dépôt pgvector..."
docker exec -u root "$DOCKER_CONTAINER" sh -c "cd /tmp && rm -rf pgvector && git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git" 2>&1 | grep -E "(Cloning|done)"

echo "4️⃣  Compilation de pgvector (sans bitcode)..."
docker exec -u root "$DOCKER_CONTAINER" sh -c "cd /tmp/pgvector && make clean && make OPTFLAGS='' NO_PGXS=0" 2>&1 | tail -10

echo "5️⃣  Installation de pgvector..."
docker exec -u root "$DOCKER_CONTAINER" sh -c "cd /tmp/pgvector && make install OPTFLAGS='' NO_PGXS=0" 2>&1 | tail -5

echo "6️⃣  Nettoyage..."
docker exec -u root "$DOCKER_CONTAINER" sh -c "cd /tmp && rm -rf pgvector"

echo ""
echo -e "${GREEN}✅ pgvector installé avec succès !${NC}"
echo ""

# Vérifier que l'extension est disponible
echo -e "${BLUE}🔍 Vérification de la disponibilité de l'extension...${NC}"
EXTENSION_AVAILABLE=$(docker exec "$DOCKER_CONTAINER" psql -U admin -d ai_agent_admin -t -c "SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'vector';" | xargs)

if [ "$EXTENSION_AVAILABLE" -eq 1 ]; then
    echo -e "${GREEN}✅ Extension pgvector disponible dans PostgreSQL${NC}"
else
    echo -e "${RED}❌ Extension pgvector non disponible${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}🔧 Activation de l'extension dans la base de données...${NC}"
docker exec "$DOCKER_CONTAINER" psql -U admin -d ai_agent_admin -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>&1

echo ""
echo -e "${BLUE}🔍 Vérification de l'installation de l'extension...${NC}"
EXTENSION_INSTALLED=$(docker exec "$DOCKER_CONTAINER" psql -U admin -d ai_agent_admin -t -c "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector');" | xargs)

if [ "$EXTENSION_INSTALLED" = "t" ]; then
    echo -e "${GREEN}✅ Extension pgvector activée dans la base de données${NC}"
else
    echo -e "${RED}❌ Extension pgvector non activée${NC}"
    exit 1
fi

echo ""
echo "=================================================================================================="
echo -e "${GREEN}✅ INSTALLATION TERMINÉE AVEC SUCCÈS !${NC}"
echo "=================================================================================================="
echo ""
echo -e "${BLUE}📝 Prochaine étape:${NC}"
echo "   Appliquez maintenant la migration des tables:"
echo "   bash scripts/apply_pgvector_migration_docker.sh"
echo ""

