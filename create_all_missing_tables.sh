#!/bin/bash
# ========================================================================
# CRÉATION AUTOMATIQUE DE TOUTES LES TABLES MANQUANTES
# ========================================================================

set -e

echo "════════════════════════════════════════════════════════════════════════"
echo "🔧 CRÉATION DE TOUTES LES TABLES MANQUANTES"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "📊 État actuel: 14/30 tables présentes"
echo "📋 À créer: 16 tables dont 6 critiques"
echo ""

# Vérifier Docker
if ! docker ps | grep -q "ai_agent_postgres"; then
    echo "❌ Le conteneur PostgreSQL n'est pas démarré"
    exit 1
fi

echo "✅ Conteneur PostgreSQL détecté"
echo ""

# Étape 1: Tables de coûts IA critiques
echo "════════════════════════════════════════════════════════════════════════"
echo "📦 Étape 1: Tables de coûts IA (CRITIQUES)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "▶ Application de schema_complet_ai_agent.sql (pour ai_cost_tracking)..."
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < data/schema_complet_ai_agent.sql 2>&1 | grep -i "CREATE TABLE\|ERROR" || echo "  ✅ Appliqué"

# Étape 2: Tables conversationnelles et prompts
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📦 Étape 2: Tables conversationnelles (CRITIQUES)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "▶ Application de migration_conversational_features.sql..."
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < data/migration_conversational_features.sql 2>&1 | grep -i "CREATE TABLE\|ERROR" || echo "  ✅ Appliqué"

# Étape 3: Tables de validation humaine
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📦 Étape 3: Tables de validation humaine (OPTIONNELLES)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "▶ Application de human_validation_migration.sql..."
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < data/human_validation_migration.sql 2>&1 | grep -i "CREATE TABLE\|ERROR" || echo "  ✅ Appliqué"

# Étape 4: Task update triggers
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📦 Étape 4: Task update triggers (CRITIQUE)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "▶ Application de migration_task_update_triggers.sql..."
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < data/migration_task_update_triggers.sql 2>&1 | grep -i "CREATE TABLE\|ERROR" || echo "  ✅ Appliqué"

# Étape 5: Backup AI logs (optionnel)
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📦 Étape 5: Backup AI logs (OPTIONNEL)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "▶ Application de ai_cost_tracking_migration.sql..."
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < data/ai_cost_tracking_migration.sql 2>&1 | grep -i "CREATE TABLE\|ERROR" || echo "  ✅ Appliqué"

# Étape 6: Tables Celery (optionnelles mais utiles)
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📦 Étape 6: Tables Celery (OPTIONNELLES)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "▶ Création des tables Celery depuis scriptfinal.sql..."
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin <<'EOSQL'
-- Créer les tables Celery si elles n'existent pas
CREATE TABLE IF NOT EXISTS celery_taskmeta (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(155) UNIQUE,
    status VARCHAR(50),
    result BYTEA,
    date_done TIMESTAMPTZ,
    traceback TEXT,
    name VARCHAR(155),
    args BYTEA,
    kwargs BYTEA,
    worker VARCHAR(155),
    retries INTEGER,
    queue VARCHAR(155)
);

CREATE TABLE IF NOT EXISTS celery_tasksetmeta (
    id SERIAL PRIMARY KEY,
    taskset_id VARCHAR(155) UNIQUE,
    result BYTEA,
    date_done TIMESTAMPTZ
);

\echo '  ✅ Tables Celery créées'
EOSQL

# Vérification finale
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📊 VÉRIFICATION FINALE"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Compter les tables
TOTAL_TABLES=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "
SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND tablename NOT LIKE '%_____2025%';
" | tr -d ' ')

echo "✅ Nombre total de tables: $TOTAL_TABLES"
echo ""

# Lister les tables créées
echo "📋 Tables présentes dans la base:"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -c "
SELECT tablename 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename NOT LIKE '%_____2025%'
ORDER BY tablename;
" | grep -v "^-\|^(\|rows)" | awk 'NF'

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "✅ CRÉATION TERMINÉE"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "🔍 Vérification finale détaillée:"
echo "   ./venv/bin/python verify_all_tables.py"
echo ""

