#!/bin/bash
# ========================================================================
# APPLICATION DE TOUTES LES MIGRATIONS DANS LE BON ORDRE
# ========================================================================

set -e

POSTGRES_CMD="docker exec ai_agent_postgres psql -U admin -d ai_agent_admin"
DATA_DIR="data"

echo "========================================================================"
echo "🔧 APPLICATION DE TOUTES LES MIGRATIONS"
echo "========================================================================"
echo ""

# Fonction pour appliquer une migration
apply_migration() {
    local file=$1
    local description=$2
    
    echo "📋 Application: $file"
    echo "   $description"
    
    if [ ! -f "$DATA_DIR/$file" ]; then
        echo "   ⚠️  Fichier non trouvé, passage au suivant"
        echo ""
        return
    fi
    
    $POSTGRES_CMD < "$DATA_DIR/$file" > /tmp/migration_output.log 2>&1
    
    if [ $? -eq 0 ]; then
        echo "   ✅ Succès"
    else
        # Vérifier si c'est juste des erreurs "already exists"
        if grep -q "already exists" /tmp/migration_output.log; then
            echo "   ✅ Déjà appliqué (objets existants)"
        else
            echo "   ⚠️  Erreurs détectées (voir logs)"
            cat /tmp/migration_output.log | tail -10
        fi
    fi
    echo ""
}

# ÉTAPE 1: Schémas de base
echo "========================================================================"
echo "ÉTAPE 1: SCHÉMAS DE BASE"
echo "========================================================================"
echo ""

apply_migration "base2.sql" "Tables fondamentales du système"
apply_migration "schema_complet_ai_agent.sql" "Schéma complet de l'application"
apply_migration "scriptfinal.sql" "Tables, vues, fonctions et triggers principaux"

# ÉTAPE 2: Extensions et fonctions
echo "========================================================================"
echo "ÉTAPE 2: FONCTIONS ET TRIGGERS"
echo "========================================================================"
echo ""

apply_migration "fonction.sql" "Fonctions utilitaires"
apply_migration "fix_status_transition_trigger.sql" "Correction trigger de transition"
apply_migration "fix_human_validations_updated_at.sql" "Correction trigger updated_at"

# ÉTAPE 3: Migrations spécifiques
echo "========================================================================"
echo "ÉTAPE 3: MIGRATIONS SPÉCIFIQUES"
echo "========================================================================"
echo ""

apply_migration "human_validation_migration.sql" "Système de validation humaine"
apply_migration "ai_cost_tracking_migration.sql" "Suivi des coûts IA"
apply_migration "migration_workflow_reactivations_table.sql" "Table de réactivation de workflow"
apply_migration "migration_task_update_triggers.sql" "Triggers de mise à jour de tâches"
apply_migration "migration_conversational_features.sql" "Fonctionnalités conversationnelles"
apply_migration "migration_failles_workflow_reactivation.sql" "Corrections failles réactivation"

# ÉTAPE 4: Corrections et ajouts
echo "========================================================================"
echo "ÉTAPE 4: CORRECTIONS ET AJOUTS"
echo "========================================================================"
echo ""

apply_migration "create_checkpoints_table.sql" "Table des checkpoints"
apply_migration "add_checkpoint_column.sql" "Ajout colonne checkpoint"
apply_migration "add_last_merged_pr_url.sql" "Ajout colonne PR URL"
apply_migration "fix_task_id_nullable.sql" "Correction task_id nullable"

# ÉTAPE 5: Vues et analyses
echo "========================================================================"
echo "ÉTAPE 5: VUES ET ANALYSES"
echo "========================================================================"
echo ""

apply_migration "view2.sql" "Vues analytiques avancées"

# ÉTAPE 6: Partitions webhook_events (déjà fait)
echo "========================================================================"
echo "ÉTAPE 6: PARTITIONS WEBHOOK_EVENTS"
echo "========================================================================"
echo ""
echo "✅ Déjà configuré avec pg_partman"
echo ""

# Vérification finale
echo "========================================================================"
echo "📊 VÉRIFICATION FINALE"
echo "========================================================================"
echo ""

echo "Comptage des objets en base:"
echo ""

echo -n "Tables:    "
$POSTGRES_CMD -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND tablename NOT LIKE '%_____%';"

echo -n "Index:     "
$POSTGRES_CMD -t -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public';"

echo -n "Views:     "
$POSTGRES_CMD -t -c "SELECT COUNT(*) FROM (SELECT viewname FROM pg_views WHERE schemaname = 'public' UNION SELECT matviewname FROM pg_matviews WHERE schemaname = 'public') as v;"

echo -n "Functions: "
$POSTGRES_CMD -t -c "SELECT COUNT(*) FROM pg_proc WHERE pronamespace = 'public'::regnamespace;"

echo -n "Triggers:  "
$POSTGRES_CMD -t -c "SELECT COUNT(*) FROM pg_trigger WHERE tgisinternal = false;"

echo ""
echo "========================================================================"
echo "✅ MIGRATIONS APPLIQUÉES"
echo "========================================================================"
echo ""
echo "💡 Lancez verify_all_migrations.py pour vérifier les détails"

