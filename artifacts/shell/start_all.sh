#!/bin/bash

echo "🚀 DÉMARRAGE DE L'AI-AGENT VYDATA"
echo "═══════════════════════════════════════════════════"

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Répertoire du projet
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Créer le dossier logs s'il n'existe pas
mkdir -p logs

# 1. Vérifier PostgreSQL
echo -e "${BLUE}📊 Vérification PostgreSQL...${NC}"
if brew services list | grep postgresql@15 | grep started > /dev/null; then
    echo -e "${GREEN}✅ PostgreSQL actif${NC}"
else
    echo -e "${YELLOW}⚡ Démarrage PostgreSQL...${NC}"
    brew services start postgresql@15
    sleep 3
fi

# 2. Vérifier RabbitMQ
echo -e "${BLUE}🐰 Vérification RabbitMQ...${NC}"
if brew services list | grep rabbitmq | grep started > /dev/null; then
    echo -e "${GREEN}✅ RabbitMQ actif${NC}"
else
    echo -e "${YELLOW}⚡ Démarrage RabbitMQ...${NC}"
    brew services start rabbitmq
    sleep 3
fi

# 3. Vérifier Redis
echo -e "${BLUE}💾 Vérification Redis...${NC}"
if brew services list | grep redis | grep started > /dev/null; then
    echo -e "${GREEN}✅ Redis actif${NC}"
else
    echo -e "${YELLOW}⚡ Démarrage Redis...${NC}"
    brew services start redis
    sleep 2
fi

# 4. Activer l'environnement Python
echo -e "${BLUE}🐍 Activation environnement Python...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✅ Environnement Python activé${NC}"
else
    echo -e "${RED}❌ Environnement virtuel Python non trouvé!${NC}"
    echo -e "${YELLOW}   Créez-le avec: python3.12 -m venv venv${NC}"
    exit 1
fi

# 5. Démarrer Celery Worker
echo -e "${BLUE}⚙️  Démarrage Celery Worker...${NC}"
pkill -9 -f "celery.*worker" 2>/dev/null
sleep 1
nohup celery -A main.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --pool=prefork \
    > logs/celery_worker.log 2>&1 &
CELERY_PID=$!
sleep 2
echo -e "${GREEN}✅ Celery Worker démarré (PID: $CELERY_PID)${NC}"

# 6. Démarrer Celery Beat (Tâches planifiées)
echo -e "${BLUE}⏰ Démarrage Celery Beat...${NC}"
pkill -9 -f "celery.*beat" 2>/dev/null
sleep 1
nohup celery -A main.celery_app beat \
    --loglevel=info \
    > logs/celery_beat.log 2>&1 &
BEAT_PID=$!
sleep 2
echo -e "${GREEN}✅ Celery Beat démarré (PID: $BEAT_PID)${NC}"

# 7. Démarrer le Backend FastAPI
echo -e "${BLUE}🚀 Démarrage Backend FastAPI...${NC}"
pkill -9 -f "uvicorn main:app" 2>/dev/null
sleep 1
nohup uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    > logs/backend.log 2>&1 &
BACKEND_PID=$!
sleep 3
echo -e "${GREEN}✅ Backend FastAPI démarré (PID: $BACKEND_PID)${NC}"

# 8. Démarrer le Frontend React
echo -e "${BLUE}⚛️  Démarrage Frontend React...${NC}"
cd ai-agent-front
pkill -9 -f "vite" 2>/dev/null
sleep 1
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
sleep 3
echo -e "${GREEN}✅ Frontend React démarré (PID: $FRONTEND_PID)${NC}"

# 9. Démarrer Ngrok (optionnel - pour webhooks externes)
if command -v ngrok &> /dev/null; then
    echo -e "${BLUE}🌐 Démarrage Ngrok...${NC}"
    pkill -9 ngrok 2>/dev/null
    sleep 1
    nohup ngrok http 8000 > logs/ngrok.log 2>&1 &
    NGROK_PID=$!
    sleep 3
    echo -e "${GREEN}✅ Ngrok démarré (PID: $NGROK_PID)${NC}"
    
    # Afficher l'URL Ngrok
    sleep 2
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o 'https://[^"]*' | head -1)
    if [ -n "$NGROK_URL" ]; then
        echo -e "${YELLOW}📡 URL Ngrok: $NGROK_URL${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Ngrok non installé (optionnel)${NC}"
fi

# Résumé
echo ""
echo "═══════════════════════════════════════════════════"
echo -e "${GREEN}✅ TOUS LES SERVICES DÉMARRÉS !${NC}"
echo "═══════════════════════════════════════════════════"
echo ""
echo "📊 Services actifs:"
echo "   • PostgreSQL    ✅"
echo "   • RabbitMQ      ✅"
echo "   • Redis         ✅"
echo "   • Celery Worker ✅ (PID: $CELERY_PID)"
echo "   • Celery Beat   ✅ (PID: $BEAT_PID)"
echo "   • Backend API   ✅ (PID: $BACKEND_PID)"
echo "   • Frontend      ✅ (PID: $FRONTEND_PID)"
if [ -n "$NGROK_PID" ]; then
    echo "   • Ngrok         ✅ (PID: $NGROK_PID)"
fi
echo ""
echo "🌐 URLs:"
echo "   • Frontend:     http://localhost:3000"
echo "   • Backend API:  http://localhost:8000"
echo "   • API Docs:     http://localhost:8000/docs"
echo "   • Browser QA:   http://localhost:3000/browser-qa"
echo "   • RabbitMQ:     http://localhost:15672 (guest/guest)"
if [ -n "$NGROK_URL" ]; then
    echo "   • Ngrok:        $NGROK_URL"
fi
echo ""
echo "📝 Logs:"
echo "   • Celery:   tail -f logs/celery_worker.log"
echo "   • Backend:  tail -f logs/backend.log"
echo "   • Frontend: tail -f logs/frontend.log"
echo ""
echo "🛑 Pour arrêter: ./stop_all.sh"
echo ""

