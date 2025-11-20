#!/bin/bash
# ===============================================
# Script de maintenance pg_partman
# ===============================================
# Description: Exécute la maintenance automatique des partitions
# Usage: Peut être exécuté manuellement ou via cron
# ===============================================

set -e

# Variables d'environnement (avec valeurs par défaut)
POSTGRES_DB="${POSTGRES_DB:-ai_agent_admin}"
POSTGRES_USER="${POSTGRES_USER:-admin}"
PGPASSWORD="${POSTGRES_PASSWORD:-password}"

export PGPASSWORD

echo "=========================================="
echo "🔧 Maintenance pg_partman"
echo "=========================================="
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Database: $POSTGRES_DB"
echo "User: $POSTGRES_USER"
echo ""

# Exécuter la maintenance pg_partman
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    -- Maintenance globale de toutes les tables partitionnées
    SELECT partman.run_maintenance_proc();
    
    -- Afficher les résultats
    SELECT 
        parent_table AS "Table",
        last_partition AS "Dernière partition",
        premake AS "Partitions futures"
    FROM partman.part_config;
EOSQL

echo ""
echo "✅ Maintenance terminée avec succès"
echo "=========================================="

# Afficher les statistiques des partitions
echo ""
echo "📊 Statistiques des partitions webhook_events:"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
    SELECT 
        child.relname AS "Partition",
        pg_size_pretty(pg_total_relation_size(child.oid)) AS "Taille",
        (SELECT COUNT(*) FROM ONLY public.webhook_events 
         WHERE tablename = child.relname) AS "Nb événements (approx)"
    FROM pg_inherits
    JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
    JOIN pg_class child ON pg_inherits.inhrelid = child.oid
    WHERE parent.relname = 'webhook_events'
    ORDER BY child.relname DESC
    LIMIT 10;
EOSQL

echo ""
echo "=========================================="

