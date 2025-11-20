#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   🔥 REDÉMARRAGE PROPRE DE CELERY (SANS CACHE)              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 1. Arrêt FORCÉ de tous les processus Celery
echo "🔴 Arrêt de tous les workers Celery..."
pkill -9 -f "celery.*worker" 2>/dev/null
sleep 3

# 2. Suppression COMPLÈTE du cache Python
echo "🧹 Nettoyage cache Python..."
find "/Users/stagiaire_vycode/Stage Smartelia/AI-Agent " -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find "/Users/stagiaire_vycode/Stage Smartelia/AI-Agent " -name "*.pyc" -delete 2>/dev/null
echo "✅ Cache nettoyé"

# 3. Attente pour s'assurer que tout est arrêté
echo "⏳ Attente 3 secondes..."
sleep 3

# 4. Redémarrage avec PYTHONDONTWRITEBYTECODE=1
echo "🚀 Redémarrage Celery SANS CACHE..."
cd "/Users/stagiaire_vycode/Stage Smartelia/AI-Agent "
source venv/bin/activate

# Variable d'environnement pour DÉSACTIVER complètement le cache Python
export PYTHONDONTWRITEBYTECODE=1

# ✅ CORRECTION CRITIQUE: Ajouter le répertoire racine au PYTHONPATH
export PYTHONPATH="/Users/stagiaire_vycode/Stage Smartelia/AI-Agent :$PYTHONPATH"

# Démarrage des workers
celery -A services.celery_app worker \
    --loglevel=info \
    --pool=prefork \
    --concurrency=4 \
    --purge \
    > logs/celery_CLEAN_RESTART_$(date +%Y%m%d_%H%M%S).log 2>&1 &

CELERY_PID=$!

echo "✅ Workers Celery démarrés (PID: $CELERY_PID)"
echo "📋 Logs: logs/celery_CLEAN_RESTART_*.log"
echo ""
echo "⏳ Attendez 10 secondes avant de tester..."
echo ""
echo "🎯 TESTEZ MAINTENANT:"
echo "  1. tail -f logs/celery_CLEAN_RESTART_*.log | grep -E 'Réactivation|Nouvelle demande|Contexte'"
echo "  2. Postez un commentaire sur Monday.com"
echo "  3. Changez Done → Working on it"
echo ""
echo "✅ Vous DEVEZ voir:"
echo "  ✅ 'Réactivation #1' (PAS #0!)"
echo "  ✅ 'Nouvelle demande: <votre commentaire>'"
echo "  ✅ 'Contexte: <votre commentaire>'"
echo "  ✅ PAS d''Event loop is closed'"
echo ""

