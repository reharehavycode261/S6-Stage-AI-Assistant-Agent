#!/bin/bash
# Script d'application de la migration browser_qa_results
# Date: 2025-11-14

set -e  # Arrêter en cas d'erreur

echo "🔧 Application de la migration Browser QA..."

# Charger les variables d'environnement
if [ -f .env ]; then
    source .env
fi

# Valeurs par défaut si non définies
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-ai_agent}"
DB_USER="${DB_USER:-postgres}"

# Chemin du fichier de migration
MIGRATION_FILE="migrations/add_browser_qa_results_column.sql"

if [ ! -f "$MIGRATION_FILE" ]; then
    echo "❌ Fichier de migration non trouvé: $MIGRATION_FILE"
    exit 1
fi

echo "📁 Fichier de migration: $MIGRATION_FILE"
echo "🗄️  Base de données: $DB_NAME@$DB_HOST:$DB_PORT"
echo ""

# Appliquer la migration
echo "⚙️  Application de la migration..."
PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -f "$MIGRATION_FILE"

echo ""
echo "✅ Migration appliquée avec succès!"
echo ""
echo "📊 Vérification de la structure..."

# Vérifier que la colonne existe
PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'task_runs' AND column_name = 'browser_qa_results';"

echo ""
echo "🎉 Migration Browser QA terminée!"
echo ""
echo "Vous pouvez maintenant:"
echo "  - Relancer le backend: uvicorn admin.backend.main:app --reload"
echo "  - Accéder à l'interface: http://localhost:3000/browser-qa"

