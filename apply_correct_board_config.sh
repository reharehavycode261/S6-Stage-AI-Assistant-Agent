#!/bin/bash
# ========================================================================
# CORRECTION AUTOMATIQUE DE LA CONFIGURATION MONDAY.COM
# ========================================================================

echo "========================================================================"
echo "🔧 CORRECTION DE LA CONFIGURATION MONDAY.COM"
echo "========================================================================"
echo ""

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Fichier .env non trouvé"
    exit 1
fi

echo "📋 Configuration INCORRECTE détectée:"
echo "   • MONDAY_BOARD_ID=5037922237 (inaccessible)"
echo "   • MONDAY_STATUS_COLUMN_ID=task_status (n'existe pas)"
echo ""

echo "✅ Configuration CORRECTE à appliquer:"
echo "   • MONDAY_BOARD_ID=2135637353 (New Board AI Agent real)"
echo "   • MONDAY_STATUS_COLUMN_ID=status"
echo "   • MONDAY_REPOSITORY_URL_COLUMN_ID=link_mkwg662v"
echo ""

# Créer une sauvegarde
cp "$ENV_FILE" "${ENV_FILE}.backup_$(date +%Y%m%d_%H%M%S)"
echo "💾 Sauvegarde créée: ${ENV_FILE}.backup_$(date +%Y%m%d_%H%M%S)"
echo ""

# Appliquer les corrections
sed -i.tmp 's/^MONDAY_BOARD_ID=.*/MONDAY_BOARD_ID=2135637353/' "$ENV_FILE"
sed -i.tmp 's/^MONDAY_STATUS_COLUMN_ID=.*/MONDAY_STATUS_COLUMN_ID=status/' "$ENV_FILE"
sed -i.tmp 's/^MONDAY_REPOSITORY_URL_COLUMN_ID=.*/MONDAY_REPOSITORY_URL_COLUMN_ID=link_mkwg662v/' "$ENV_FILE"

# Supprimer le fichier temporaire
rm -f "${ENV_FILE}.tmp"

echo "✅ Fichier .env mis à jour"
echo ""

echo "📋 Nouvelle configuration:"
grep -E "MONDAY_BOARD_ID|MONDAY_STATUS_COLUMN_ID|MONDAY_REPOSITORY_URL_COLUMN_ID" "$ENV_FILE"
echo ""

echo "========================================================================"
echo "✅ CORRECTION TERMINÉE"
echo "========================================================================"
echo ""
echo "🔄 Prochaines étapes:"
echo "   1. Arrêter Celery:   pkill -f celery"
echo "   2. Redémarrer FastAPI (Ctrl+C puis relancer)"
echo "   3. Redémarrer Celery: celery -A ai_agent_background worker --loglevel=info"
echo "   4. Tester un webhook Monday.com"
echo ""

