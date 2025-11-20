#!/bin/bash
# ========================================================================
# SCRIPT DE SUPPRESSION DE TOUTES LES TABLES SAUF COÛT IA
# ========================================================================
# ⚠️  ATTENTION: Ce script supprime TOUTES les tables sauf celles du coût IA
# Un backup automatique est créé avant la suppression
# ========================================================================

set -e

echo "════════════════════════════════════════════════════════════════════════"
echo "⚠️  SUPPRESSION DE TOUTES LES TABLES (SAUF COÛT IA)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Tables qui seront PRÉSERVÉES:"
echo "   • ai_usage_logs"
echo "   • ai_cost_tracking"
echo "   • ai_interactions"
echo "   • ai_code_generations"
echo "   • ai_prompt_templates"
echo "   • ai_prompt_usage"
echo ""
echo "📈 Vues qui seront PRÉSERVÉES:"
echo "   • ai_cost_daily_summary"
echo "   • ai_cost_by_workflow"
echo "   • mv_cost_analysis"
echo ""
echo "🗑️  TOUT LE RESTE sera SUPPRIMÉ:"
echo "   • tasks"
echo "   • task_runs"
echo "   • run_steps"
echo "   • test_results"
echo "   • pull_requests"
echo "   • performance_metrics"
echo "   • webhook_events"
echo "   • workflow_reactivations"
echo "   • application_logs"
echo "   • system_config"
echo "   • ... et toutes les autres tables"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Demander confirmation
read -p "⚠️  Êtes-vous ABSOLUMENT SÛR de vouloir supprimer toutes les tables (sauf coût IA) ? (oui/non) " -r
echo ""

if [[ ! $REPLY =~ ^[Oo][Uu][Ii]$ ]]; then
    echo "❌ Opération annulée par l'utilisateur"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📦 ÉTAPE 1: Création du backup de sécurité"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Créer le dossier de backup
BACKUP_DIR="backups/before_drop_tables"
mkdir -p "$BACKUP_DIR"

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_all_tables_$BACKUP_DATE.sql"

echo "📁 Création du backup complet dans: $BACKUP_FILE"

# Backup de la base complète
if docker ps | grep -q ai-agent-postgres; then
    echo "🐳 Utilisation de Docker pour le backup..."
    docker exec ai-agent-postgres pg_dump -U admin -d ai_agent > "$BACKUP_FILE"
else
    echo "💻 Utilisation de pg_dump local..."
    pg_dump -U admin -d ai_agent > "$BACKUP_FILE"
fi

if [ $? -eq 0 ]; then
    echo "✅ Backup créé avec succès: $BACKUP_FILE"
    echo "📊 Taille du backup: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "❌ Erreur lors de la création du backup"
    echo "⚠️  Opération annulée pour sécurité"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "📦 ÉTAPE 2: Backup spécifique des tables coût IA"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

AI_COST_BACKUP="$BACKUP_DIR/backup_ai_cost_only_$BACKUP_DATE.sql"

echo "📁 Sauvegarde des données de coût IA: $AI_COST_BACKUP"

# Backup uniquement des tables coût IA
if docker ps | grep -q ai-agent-postgres; then
    docker exec ai-agent-postgres pg_dump -U admin -d ai_agent \
        -t ai_usage_logs \
        -t ai_cost_tracking \
        -t ai_interactions \
        -t ai_code_generations \
        -t ai_prompt_templates \
        -t ai_prompt_usage \
        > "$AI_COST_BACKUP"
else
    pg_dump -U admin -d ai_agent \
        -t ai_usage_logs \
        -t ai_cost_tracking \
        -t ai_interactions \
        -t ai_code_generations \
        -t ai_prompt_templates \
        -t ai_prompt_usage \
        > "$AI_COST_BACKUP"
fi

if [ $? -eq 0 ]; then
    echo "✅ Backup coût IA créé: $AI_COST_BACKUP"
    echo "📊 Taille: $(du -h "$AI_COST_BACKUP" | cut -f1)"
else
    echo "⚠️  Erreur lors du backup des tables IA (non critique)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "🗑️  ÉTAPE 3: Exécution de la suppression"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Dernière confirmation
read -p "⚠️  DERNIÈRE CONFIRMATION: Lancer la suppression maintenant ? (oui/non) " -r
echo ""

if [[ ! $REPLY =~ ^[Oo][Uu][Ii]$ ]]; then
    echo "❌ Opération annulée"
    echo "📦 Les backups ont été conservés:"
    echo "   • $BACKUP_FILE"
    echo "   • $AI_COST_BACKUP"
    exit 1
fi

echo "🗑️  Suppression en cours..."
echo ""

# Exécuter le script SQL de suppression
if docker ps | grep -q ai-agent-postgres; then
    docker exec -i ai-agent-postgres psql -U admin -d ai_agent < data/drop_all_except_ai_cost.sql
else
    psql -U admin -d ai_agent < data/drop_all_except_ai_cost.sql
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════════════"
    echo "✅ SUPPRESSION TERMINÉE AVEC SUCCÈS"
    echo "════════════════════════════════════════════════════════════════════"
    echo ""
    echo "📦 Backups disponibles:"
    echo "   • Backup complet: $BACKUP_FILE"
    echo "   • Backup coût IA: $AI_COST_BACKUP"
    echo ""
    echo "📊 Tables préservées (coût IA uniquement):"
    echo "   • ai_usage_logs"
    echo "   • ai_cost_tracking"
    echo "   • ai_interactions"
    echo "   • ai_code_generations"
    echo "   • ai_prompt_templates"
    echo "   • ai_prompt_usage"
    echo ""
    echo "💡 Pour restaurer la structure complète:"
    echo "   docker exec -i ai-agent-postgres psql -U admin -d ai_agent < data/base2.sql"
    echo ""
    echo "💡 Pour restaurer le backup complet:"
    echo "   docker exec -i ai-agent-postgres psql -U admin -d ai_agent < $BACKUP_FILE"
    echo ""
    echo "════════════════════════════════════════════════════════════════════"
else
    echo ""
    echo "❌ Erreur lors de la suppression"
    echo "📦 Les backups sont disponibles pour restauration:"
    echo "   • $BACKUP_FILE"
    echo "   • $AI_COST_BACKUP"
    exit 1
fi

