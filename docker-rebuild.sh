#!/bin/bash
# ============================================================================
# Script de Rebuild Docker pour AI-Agent
# ============================================================================
# Description: Rebuild complet de PostgreSQL + RabbitMQ avec pg_partman
#              et corrections des failles de réactivation workflow
# Usage: ./docker-rebuild.sh [--clean] [--no-cache]
# ============================================================================

set -e  # Arrêter en cas d'erreur

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction de log
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Fonction pour afficher l'aide
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Rebuild complet de l'infrastructure Docker AI-Agent

OPTIONS:
    --clean         Supprime tous les volumes (données perdues!)
    --no-cache      Rebuild les images sans utiliser le cache Docker
    --help          Affiche cette aide

EXEMPLES:
    $0                    # Rebuild normal (conserve les données)
    $0 --clean            # Rebuild + suppression des données
    $0 --no-cache         # Rebuild forcé des images
    $0 --clean --no-cache # Rebuild complet from scratch

EOF
}

# Parser les arguments
CLEAN_VOLUMES=false
NO_CACHE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN_VOLUMES=true
            shift
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Option inconnue: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "============================================"
echo "🚀 AI-Agent Docker Rebuild"
echo "============================================"
echo ""

# Vérifier que docker-compose est installé
if ! command -v docker-compose &> /dev/null; then
    log_error "docker-compose n'est pas installé"
    exit 1
fi

log_info "Vérification de l'environnement..."

# Vérifier que le fichier docker-compose existe
if [ ! -f "docker-compose.rabbitmq.yml" ]; then
    log_error "Fichier docker-compose.rabbitmq.yml introuvable"
    exit 1
fi

log_success "Fichier docker-compose.rabbitmq.yml trouvé"

# Vérifier que le Dockerfile PostgreSQL existe
if [ ! -f "docker/postgres/Dockerfile" ]; then
    log_error "Dockerfile PostgreSQL introuvable"
    exit 1
fi

log_success "Dockerfile PostgreSQL trouvé"

# Vérifier que les scripts d'init existent
if [ ! -f "docker/postgres/init-scripts/01-enable-pg-partman.sql" ]; then
    log_error "Script pg_partman introuvable"
    exit 1
fi

if [ ! -f "docker/postgres/init-scripts/04-failles-workflow-corrections.sql" ]; then
    log_warning "Script des corrections de failles introuvable"
    log_warning "Vérifiez que le fichier 04-failles-workflow-corrections.sql existe"
fi

log_success "Scripts d'initialisation vérifiés"

# ============================================================================
# ÉTAPE 1: Arrêt des containers
# ============================================================================

echo ""
log_info "Arrêt des containers en cours..."

docker-compose -f docker-compose.rabbitmq.yml down || true

log_success "Containers arrêtés"

# ============================================================================
# ÉTAPE 2: Suppression des volumes (si --clean)
# ============================================================================

if [ "$CLEAN_VOLUMES" = true ]; then
    echo ""
    log_warning "ATTENTION: Suppression des volumes demandée"
    log_warning "Toutes les données seront perdues!"
    
    read -p "Êtes-vous sûr ? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        log_info "Suppression des volumes..."
        
        docker volume rm ai_agent_postgres_data 2>/dev/null || true
        docker volume rm ai_agent_rabbitmq_data 2>/dev/null || true
        docker volume rm ai_agent_rabbitmq_logs 2>/dev/null || true
        docker volume rm ai_agent_prometheus_data 2>/dev/null || true
        
        log_success "Volumes supprimés"
    else
        log_info "Suppression des volumes annulée"
    fi
else
    log_info "Conservation des volumes existants"
fi

# ============================================================================
# ÉTAPE 3: Rebuild de l'image PostgreSQL
# ============================================================================

echo ""
log_info "Rebuild de l'image PostgreSQL avec pg_partman..."

docker-compose -f docker-compose.rabbitmq.yml build $NO_CACHE postgres

log_success "Image PostgreSQL rebuild avec succès"

# ============================================================================
# ÉTAPE 4: Rebuild des autres images (si nécessaire)
# ============================================================================

if [ -n "$NO_CACHE" ]; then
    echo ""
    log_info "Rebuild de toutes les images (--no-cache)..."
    
    docker-compose -f docker-compose.rabbitmq.yml build --no-cache
    
    log_success "Toutes les images rebuild"
fi

# ============================================================================
# ÉTAPE 5: Démarrage des services
# ============================================================================

echo ""
log_info "Démarrage des services..."

# Démarrer d'abord les services de base (postgres + rabbitmq)
log_info "Démarrage PostgreSQL et RabbitMQ..."
docker-compose -f docker-compose.rabbitmq.yml up -d postgres rabbitmq

# Attendre que PostgreSQL soit prêt
log_info "Attente de PostgreSQL (health check)..."
for i in {1..30}; do
    if docker exec ai_agent_postgres pg_isready -U admin -d ai_agent_admin > /dev/null 2>&1; then
        log_success "PostgreSQL est prêt"
        break
    fi
    
    if [ $i -eq 30 ]; then
        log_error "Timeout: PostgreSQL n'est pas prêt après 60s"
        exit 1
    fi
    
    echo -n "."
    sleep 2
done

# Attendre que RabbitMQ soit prêt
log_info "Attente de RabbitMQ (health check)..."
for i in {1..30}; do
    if docker exec ai_agent_rabbitmq rabbitmq-diagnostics ping > /dev/null 2>&1; then
        log_success "RabbitMQ est prêt"
        break
    fi
    
    if [ $i -eq 30 ]; then
        log_error "Timeout: RabbitMQ n'est pas prêt après 60s"
        exit 1
    fi
    
    echo -n "."
    sleep 2
done

# Démarrer les autres services
log_info "Démarrage des autres services..."
docker-compose -f docker-compose.rabbitmq.yml up -d

log_success "Tous les services démarrés"

# ============================================================================
# ÉTAPE 6: Vérification de la migration des failles
# ============================================================================

echo ""
log_info "Vérification de la migration des failles..."

# Vérifier que les colonnes ont été ajoutées
VERIFICATION_SQL="
SELECT 
    COUNT(*) FILTER (WHERE column_name IN (
        'reactivated_at', 'reactivation_count', 'previous_status',
        'is_locked', 'locked_at', 'locked_by',
        'last_reactivation_attempt', 'cooldown_until', 'failed_reactivation_attempts'
    )) as tasks_columns,
    COUNT(*) FILTER (WHERE column_name IN (
        'active_task_ids', 'last_task_id', 'task_started_at', 'is_reactivation'
    ) AND table_name = 'task_runs') as task_runs_columns
FROM information_schema.columns
WHERE table_name IN ('tasks', 'task_runs')
  AND table_schema = 'public';
"

# Attendre 5 secondes pour que la migration soit appliquée
sleep 5

# Exécuter la vérification
RESULT=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "$VERIFICATION_SQL" 2>/dev/null || echo "ERROR")

if [ "$RESULT" = "ERROR" ]; then
    log_warning "Impossible de vérifier la migration (la base n'est peut-être pas encore initialisée)"
else
    log_info "Résultat de la migration:"
    echo "$RESULT"
    
    # Parser le résultat (simple check)
    if echo "$RESULT" | grep -q "9.*4"; then
        log_success "Migration des corrections de failles appliquée ✅"
    else
        log_warning "Migration partiellement appliquée ou en cours"
    fi
fi

# ============================================================================
# ÉTAPE 7: Vérification de pg_partman
# ============================================================================

echo ""
log_info "Vérification de pg_partman..."

PARTMAN_CHECK=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT extversion FROM pg_extension WHERE extname = 'pg_partman';" 2>/dev/null || echo "ERROR")

if [ "$PARTMAN_CHECK" = "ERROR" ]; then
    log_warning "Impossible de vérifier pg_partman"
elif [ -z "$PARTMAN_CHECK" ]; then
    log_warning "pg_partman non installé"
else
    log_success "pg_partman version: $PARTMAN_CHECK"
fi

# ============================================================================
# ÉTAPE 8: Affichage du statut final
# ============================================================================

echo ""
echo "============================================"
echo "📊 Statut des Services"
echo "============================================"

docker-compose -f docker-compose.rabbitmq.yml ps

echo ""
echo "============================================"
echo "🔗 URLs des Services"
echo "============================================"
echo "🐘 PostgreSQL:          localhost:5432"
echo "🐰 RabbitMQ:            localhost:5672"
echo "📊 RabbitMQ Management: http://localhost:15672"
echo "   └─ User: ai_agent_user / secure_password_123"
echo "🌸 Flower (Celery):     http://localhost:5555"
echo "   └─ User: admin / flower123"
echo "🚀 API:                 http://localhost:8000"
echo "📈 Prometheus:          http://localhost:9090"
echo "============================================"

echo ""
log_success "Rebuild terminé avec succès! 🎉"

echo ""
echo "Commandes utiles:"
echo "  docker-compose -f docker-compose.rabbitmq.yml logs -f postgres     # Logs PostgreSQL"
echo "  docker-compose -f docker-compose.rabbitmq.yml logs -f rabbitmq     # Logs RabbitMQ"
echo "  docker-compose -f docker-compose.rabbitmq.yml ps                   # Statut des services"
echo "  docker-compose -f docker-compose.rabbitmq.yml down                 # Arrêter tout"
echo "  docker exec ai_agent_postgres psql -U admin -d ai_agent_admin     # Connexion PostgreSQL"
echo ""

exit 0

