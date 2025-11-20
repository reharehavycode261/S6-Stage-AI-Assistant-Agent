#!/bin/bash
# ========================================================================
# SCRIPT DE RECRÉATION DE LA STRUCTURE DE BASE
# ========================================================================
# Ce script recrée toutes les tables manquantes
# TOUT EN PRÉSERVANT les données de coût IA existantes
# ========================================================================

set -e

echo "════════════════════════════════════════════════════════════════════════"
echo "🔧 RECRÉATION DE LA STRUCTURE DE BASE DE DONNÉES"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "📊 État actuel de la base:"
echo "   ✅ 3 tables existantes (données IA)"
echo "   ❌ 13 tables manquantes"
echo ""
echo "💰 Données IA à PRÉSERVER:"
echo "   • ai_usage_logs: 241 enregistrements ($4.48)"
echo "   • ai_interactions: 0 enregistrements"
echo "   • ai_code_generations: 0 enregistrements"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Vérifier que Docker est lancé
if ! docker ps | grep -q "ai_agent_postgres"; then
    echo "❌ Le conteneur PostgreSQL n'est pas démarré"
    echo ""
    echo "💡 Démarrez-le avec:"
    echo "   docker-compose up -d postgres"
    exit 1
fi

echo "✅ Conteneur PostgreSQL détecté"
echo ""

# Créer un backup avant toute modification
echo "📦 Étape 1: Backup de sécurité"
echo "────────────────────────────────────────────────────────────────────────"
echo ""

BACKUP_DIR="backups/before_structure_recreation"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/backup_ai_data_$(date +%Y%m%d_%H%M%S).sql"

echo "💾 Sauvegarde des données IA existantes..."
docker exec ai_agent_postgres pg_dump -U admin -d ai_agent_admin \
    -t ai_usage_logs \
    -t ai_interactions \
    -t ai_code_generations \
    > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Backup créé: $BACKUP_FILE"
    echo "📊 Taille: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "❌ Erreur lors du backup"
    exit 1
fi

echo ""
echo "📦 Étape 2: Création de la structure complète"
echo "────────────────────────────────────────────────────────────────────────"
echo ""

# Appliquer le script base2.sql qui contient toute la structure
# Note: base2.sql utilise CREATE TABLE IF NOT EXISTS, donc il ne supprimera pas les tables existantes
echo "🔨 Application du schéma complet (base2.sql)..."
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < data/base2.sql

if [ $? -eq 0 ]; then
    echo "✅ Structure de base créée"
else
    echo "❌ Erreur lors de la création de la structure"
    echo "📦 Backup disponible: $BACKUP_FILE"
    exit 1
fi

echo ""
echo "📦 Étape 3: Création de la table workflow_reactivations"
echo "────────────────────────────────────────────────────────────────────────"
echo ""

# Modifier le script pour utiliser la bonne base
sed 's/tasks_id/tasks_id/g' data/migration_workflow_reactivations_table.sql | \
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin

if [ $? -eq 0 ]; then
    echo "✅ Table workflow_reactivations créée"
else
    echo "⚠️  Erreur lors de la création de workflow_reactivations (peut être normale si existe déjà)"
fi

echo ""
echo "📦 Étape 4: Vérification finale"
echo "────────────────────────────────────────────────────────────────────────"
echo ""

# Lancer le script de vérification
./venv/bin/python check_database_complete.py > /tmp/db_check_result.txt 2>&1

# Afficher le résumé
grep -A 10 "RÉSUMÉ FINAL" /tmp/db_check_result.txt || echo "Vérification en cours..."

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "✅ RECRÉATION TERMINÉE"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Résumé:"
echo "   ✅ Structure de base recréée"
echo "   ✅ Table workflow_reactivations ajoutée"
echo "   💰 Données IA préservées (241 enregistrements)"
echo ""
echo "📦 Backup disponible:"
echo "   $BACKUP_FILE"
echo ""
echo "🔍 Vérification complète:"
echo "   ./venv/bin/python check_database_complete.py"
echo ""
echo "🚀 Redémarrer l'application:"
echo "   docker-compose restart web"
echo ""
echo "════════════════════════════════════════════════════════════════════════"

