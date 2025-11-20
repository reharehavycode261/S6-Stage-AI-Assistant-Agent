#!/bin/bash
# ================================================================
# Script pour appliquer la migration pgvector manuellement
# ================================================================

set -e  # Arrêter en cas d'erreur

echo "=================================================================================================="
echo "🚀 APPLICATION DE LA MIGRATION PGVECTOR"
echo "=================================================================================================="

# Couleurs pour le terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Chemin de la migration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MIGRATION_FILE="$SCRIPT_DIR/../migrations/add_pgvector_extension.sql"

# Credentials PostgreSQL (fournis par l'utilisateur)
DB_USER="admin"
DB_NAME="ai_agent_admin"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo ""
echo -e "${BLUE}📋 Configuration:${NC}"
echo "   • Base de données: $DB_NAME"
echo "   • Utilisateur: $DB_USER"
echo "   • Hôte: $DB_HOST"
echo "   • Port: $DB_PORT"
echo "   • Fichier SQL: $MIGRATION_FILE"
echo ""

# Vérifier que le fichier de migration existe
if [ ! -f "$MIGRATION_FILE" ]; then
    echo -e "${RED}❌ Erreur: Fichier de migration non trouvé: $MIGRATION_FILE${NC}"
    exit 1
fi

echo -e "${BLUE}🔍 Vérification de la connexion PostgreSQL...${NC}"

# Tester la connexion
if psql -U "$DB_USER" -d "$DB_NAME" -h "$DB_HOST" -p "$DB_PORT" -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Connexion PostgreSQL réussie${NC}"
else
    echo -e "${RED}❌ Impossible de se connecter à PostgreSQL${NC}"
    echo ""
    echo -e "${YELLOW}💡 Vérifiez:${NC}"
    echo "   1. PostgreSQL est démarré"
    echo "   2. Les credentials sont corrects"
    echo "   3. psql est installé dans le PATH"
    echo ""
    exit 1
fi

echo ""
echo -e "${BLUE}🔧 Application de la migration pgvector...${NC}"
echo ""

# Appliquer la migration
if psql -U "$DB_USER" -d "$DB_NAME" -h "$DB_HOST" -p "$DB_PORT" -f "$MIGRATION_FILE"; then
    echo ""
    echo -e "${GREEN}✅ Migration appliquée avec succès !${NC}"
else
    echo ""
    echo -e "${RED}❌ Erreur lors de l'application de la migration${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}🔍 Vérification de l'installation...${NC}"
echo ""

# Vérifier l'extension pgvector
echo "1️⃣  Vérification de l'extension pgvector:"
PGVECTOR_EXISTS=$(psql -U "$DB_USER" -d "$DB_NAME" -h "$DB_HOST" -p "$DB_PORT" -t -c "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector');" | xargs)

if [ "$PGVECTOR_EXISTS" = "t" ]; then
    echo -e "   ${GREEN}✅ Extension pgvector installée${NC}"
else
    echo -e "   ${RED}❌ Extension pgvector non installée${NC}"
    exit 1
fi

# Vérifier les tables
echo ""
echo "2️⃣  Vérification des tables:"

TABLES=("message_embeddings" "project_context_embeddings")
for table in "${TABLES[@]}"; do
    TABLE_EXISTS=$(psql -U "$DB_USER" -d "$DB_NAME" -h "$DB_HOST" -p "$DB_PORT" -t -c "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = '$table');" | xargs)
    
    if [ "$TABLE_EXISTS" = "t" ]; then
        echo -e "   ${GREEN}✅ Table '$table' créée${NC}"
    else
        echo -e "   ${RED}❌ Table '$table' manquante${NC}"
        exit 1
    fi
done

# Vérifier les index HNSW
echo ""
echo "3️⃣  Vérification des index HNSW:"

INDEX_COUNT=$(psql -U "$DB_USER" -d "$DB_NAME" -h "$DB_HOST" -p "$DB_PORT" -t -c "SELECT COUNT(*) FROM pg_indexes WHERE tablename IN ('message_embeddings', 'project_context_embeddings') AND indexname LIKE '%embedding%';" | xargs)

if [ "$INDEX_COUNT" -ge 2 ]; then
    echo -e "   ${GREEN}✅ $INDEX_COUNT index HNSW créés${NC}"
else
    echo -e "   ${YELLOW}⚠️  Seulement $INDEX_COUNT index trouvés (attendu: 2)${NC}"
fi

# Afficher les statistiques
echo ""
echo "4️⃣  Statistiques actuelles:"

MESSAGE_COUNT=$(psql -U "$DB_USER" -d "$DB_NAME" -h "$DB_HOST" -p "$DB_PORT" -t -c "SELECT COUNT(*) FROM message_embeddings;" | xargs)
CONTEXT_COUNT=$(psql -U "$DB_USER" -d "$DB_NAME" -h "$DB_HOST" -p "$DB_PORT" -t -c "SELECT COUNT(*) FROM project_context_embeddings;" | xargs)

echo "   • Messages stockés: $MESSAGE_COUNT"
echo "   • Contextes stockés: $CONTEXT_COUNT"

echo ""
echo "=================================================================================================="
echo -e "${GREEN}✅ INSTALLATION TERMINÉE AVEC SUCCÈS !${NC}"
echo "=================================================================================================="
echo ""
echo -e "${BLUE}📝 Prochaines étapes:${NC}"
echo "   1. Installer les dépendances Python:"
echo "      pip install -r requirements.txt"
echo ""
echo "   2. Tester le système avec Python:"
echo "      python scripts/init_vector_store.py"
echo ""
echo "   3. Vérifier les statistiques:"
echo "      python scripts/vector_store_stats.py"
echo ""
echo "   4. Redémarrer le service AI-Agent"
echo ""
echo -e "${GREEN}🎉 Le système RAG est maintenant opérationnel !${NC}"
echo ""

