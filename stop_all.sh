#!/bin/bash

echo "🛑 ARRÊT DE TOUS LES SERVICES AI-AGENT"
echo "═════════════════════════════════════════════════════"
echo "ℹ️  Note: Ngrok sera conservé actif pour les webhooks"
echo ""

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Fonction pour arrêter un processus
stop_process() {
    local process_name=$1
    local pattern=$2
    
    echo -e "${YELLOW}Arrêt de $process_name...${NC}"
    
    # Trouver les PIDs
    PIDS=$(pgrep -f "$pattern" 2>/dev/null)
    
    if [ -n "$PIDS" ]; then
        echo "   PIDs trouvés: $PIDS"
        pkill -9 -f "$pattern" 2>/dev/null
        sleep 1
        
        # Vérifier si encore actif
        if pgrep -f "$pattern" > /dev/null; then
            echo -e "${RED}   ⚠️  Certains processus résistent, force kill...${NC}"
            kill -9 $PIDS 2>/dev/null
        fi
        
        echo -e "${GREEN}   ✅ $process_name arrêté${NC}"
    else
        echo -e "${YELLOW}   ℹ️  $process_name n'était pas actif${NC}"
    fi
}

# Fonction pour libérer un port spécifique
free_port() {
    local port=$1
    local service_name=$2
    
    echo -e "${YELLOW}Libération du port $port ($service_name)...${NC}"
    
    # Trouver les PIDs qui utilisent le port
    PIDS=$(lsof -ti :$port 2>/dev/null)
    
    if [ -n "$PIDS" ]; then
        echo "   PIDs utilisant le port $port: $PIDS"
        kill -9 $PIDS 2>/dev/null
        sleep 0.5
        
        # Vérifier à nouveau
        PIDS_REMAINING=$(lsof -ti :$port 2>/dev/null)
        if [ -n "$PIDS_REMAINING" ]; then
            echo -e "${RED}   ⚠️  Force kill des processus restants...${NC}"
            kill -9 $PIDS_REMAINING 2>/dev/null
        fi
        
        echo -e "${GREEN}   ✅ Port $port libéré${NC}"
    else
        echo -e "${YELLOW}   ℹ️  Port $port déjà libre${NC}"
    fi
}

# Arrêter les processus Python/Node.js
stop_process "Celery Worker" "celery.*worker"
stop_process "Celery Beat" "celery.*beat"
stop_process "Backend FastAPI" "uvicorn main:app"
stop_process "Frontend React/Vite" "vite"
# stop_process "Ngrok" "ngrok"  # ⚠️ Ngrok conservé actif pour les webhooks Monday.com

echo ""
echo "🔧 Libération des ports..."
free_port "8000" "Backend FastAPI"
free_port "5173" "Frontend Vite"

# Arrêter les services Homebrew (optionnel - commenté par défaut)
echo ""
echo -e "${YELLOW}Services Homebrew (PostgreSQL, RabbitMQ, Redis):${NC}"
read -p "Voulez-vous les arrêter aussi? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Arrêt de PostgreSQL...${NC}"
    brew services stop postgresql@15
    
    echo -e "${YELLOW}Arrêt de RabbitMQ...${NC}"
    brew services stop rabbitmq
    
    echo -e "${YELLOW}Arrêt de Redis...${NC}"
    brew services stop redis
    
    echo -e "${GREEN}✅ Services Homebrew arrêtés${NC}"
else
    echo -e "${YELLOW}Services Homebrew conservés actifs${NC}"
fi

# Nettoyage des fichiers temporaires (optionnel)
echo ""
echo -e "${YELLOW}Nettoyage des fichiers temporaires:${NC}"
read -p "Nettoyer les logs? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f logs/*.log
    echo -e "${GREEN}✅ Logs nettoyés${NC}"
fi

# Résumé
echo ""
echo "═════════════════════════════════════════════════════"
echo -e "${GREEN}✅ TOUS LES PROCESSUS ARRÊTÉS !${NC}"
echo "═════════════════════════════════════════════════════"
echo ""
echo "📊 Vérification finale:"
ps aux | grep -E "(celery|uvicorn|vite)" | grep -v grep | wc -l | xargs -I {} echo "   Processus restants: {}"
echo "   (Ngrok conservé actif pour webhooks)"
echo ""
echo "🔌 État des ports:"
lsof -ti :8000 > /dev/null 2>&1 && echo "   ⚠️  Port 8000: OCCUPÉ" || echo "   ✅ Port 8000: LIBRE"
lsof -ti :5173 > /dev/null 2>&1 && echo "   ⚠️  Port 5173: OCCUPÉ" || echo "   ✅ Port 5173: LIBRE"
echo ""
echo "🚀 Pour redémarrer: ./start_all.sh"
echo ""
