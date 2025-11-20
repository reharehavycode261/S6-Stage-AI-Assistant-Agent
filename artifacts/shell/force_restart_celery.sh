#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   🔥 REDÉMARRAGE FORCÉ AVEC VÉRIFICATION                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Arrêt TOTAL
echo "🔴 Arrêt TOTAL de tous les processus..."
pkill -9 -f "celery" 2>/dev/null
sleep 5

# Nettoyage COMPLET
echo "🧹 Nettoyage COMPLET du cache..."
cd "/Users/stagiaire_vycode/Stage Smartelia/AI-Agent "
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
find . -name "*.pyo" -delete 2>/dev/null
echo "✅ Cache nettoyé"

# Vérification fichier source
echo ""
echo "🔍 VÉRIFICATION DU CODE SOURCE..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CORRECTION_1=$(grep -c "update_text = result.get('update_text'" services/celery_app.py)
CORRECTION_2=$(grep -c "🔢 reactivation_count:" services/celery_app.py)

if [ "$CORRECTION_1" -ge "2" ] && [ "$CORRECTION_2" -ge "1" ]; then
    echo "✅ CORRECTIONS PRÉSENTES dans services/celery_app.py"
    echo "   • update_text extraction: $CORRECTION_1 occurrences"
    echo "   • Logs reactivation_count: $CORRECTION_2 occurrences"
else
    echo "❌ ERREUR: Corrections manquantes !"
    echo "   • update_text: $CORRECTION_1 (attendu: >=2)"
    echo "   • Logs: $CORRECTION_2 (attendu: >=1)"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Attente
sleep 3

# Redémarrage
echo "🚀 REDÉMARRAGE avec PYTHONDONTWRITEBYTECODE=1..."
source venv/bin/activate
export PYTHONDONTWRITEBYTECODE=1

# ✅ CORRECTION CRITIQUE: Ajouter le répertoire racine au PYTHONPATH
export PYTHONPATH="/Users/stagiaire_vycode/Stage Smartelia/AI-Agent :$PYTHONPATH"

celery -A services.celery_app worker \
    --loglevel=info \
    --pool=prefork \
    --concurrency=4 \
    --purge \
    > logs/celery_FORCE_RESTART_$(date +%Y%m%d_%H%M%S).log 2>&1 &

CELERY_PID=$!

echo "✅ Celery démarré (PID: $CELERY_PID)"
echo ""
echo "⏳ Attente 10 secondes pour initialisation..."
sleep 10

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ✅ REDÉMARRAGE TERMINÉ !                                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Logs: logs/celery_FORCE_RESTART_*.log"
echo ""
echo "🧪 TEST MAINTENANT:"
echo "  tail -f logs/celery_FORCE_RESTART_*.log | grep -E \"🔢 reactivation_count|📝 Contexte réactivation|Réactivation #\""
echo ""

