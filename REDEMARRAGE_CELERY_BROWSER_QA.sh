#!/bin/bash

# Script de redémarrage Celery pour appliquer les modifications Browser QA
# Date: 14 novembre 2025

echo "🔄 Redémarrage de Celery pour appliquer les modifications Browser QA..."
echo ""

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Arrêter Celery
echo "${YELLOW}📛 Étape 1/4: Arrêt de Celery...${NC}"
pkill -f "celery -A main.celery_app worker"
sleep 3

# Vérifier que Celery est arrêté
if pgrep -f "celery -A main.celery_app worker" > /dev/null; then
    echo "${RED}⚠️  Celery encore actif, force kill...${NC}"
    pkill -9 -f "celery -A main.celery_app worker"
    sleep 2
fi

echo "${GREEN}✅ Celery arrêté${NC}"
echo ""

# 2. Se placer dans le bon répertoire
echo "${YELLOW}📂 Étape 2/4: Positionnement dans le répertoire...${NC}"
cd "/Users/stagiaire_vycode/Stage Smartelia/AI-Agent "
echo "${GREEN}✅ Répertoire: $(pwd)${NC}"
echo ""

# 3. Activer l'environnement virtuel
echo "${YELLOW}🐍 Étape 3/4: Activation environnement virtuel...${NC}"
source venv/bin/activate
echo "${GREEN}✅ Environnement virtuel activé${NC}"
echo ""

# 4. Redémarrer Celery
echo "${YELLOW}🚀 Étape 4/4: Redémarrage de Celery...${NC}"
nohup celery -A main.celery_app worker --loglevel=info --concurrency=4 > logs/celery_worker.log 2>&1 &
CELERY_PID=$!
sleep 5

# Vérifier que Celery est bien démarré
if pgrep -f "celery -A main.celery_app worker" > /dev/null; then
    echo "${GREEN}✅ Celery redémarré avec succès (PID: $CELERY_PID)${NC}"
    echo ""
    echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "${GREEN}✅ MODIFICATIONS BROWSER QA APPLIQUÉES${NC}"
    echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "📊 Détection maintenant supportée pour 50+ frameworks:"
    echo "   • JavaScript: React, Next.js, Vue, Angular, Svelte, Astro, Remix, Gatsby..."
    echo "   • Java: Spring Boot (Maven/Gradle)"
    echo "   • Python: Django, Flask, FastAPI, Streamlit, Gradio"
    echo "   • Ruby: Rails, Sinatra"
    echo "   • PHP: Laravel, Symfony"
    echo "   • Rust: Actix-web, Rocket, Axum"
    echo "   • Go, .NET, Kotlin, Hugo, Jekyll, Deno, Bun..."
    echo ""
    echo "📝 Pour surveiller les logs:"
    echo "   tail -f logs/celery_worker.log"
    echo ""
    echo "🧪 Pour tester:"
    echo "   1. Créer un commentaire sur Monday.com: @vydata test browser qa"
    echo "   2. Observer les logs: tail -f logs/celery_worker.log | grep 'Détection'"
    echo "   3. Vérifier: '✅ Spring Boot (Maven) détecté' au lieu de '⚠️ Aucun serveur de dev détecté'"
    echo ""
else
    echo "${RED}❌ Échec du redémarrage de Celery${NC}"
    echo "${RED}Vérifiez les logs: cat logs/celery_worker.log${NC}"
    exit 1
fi

