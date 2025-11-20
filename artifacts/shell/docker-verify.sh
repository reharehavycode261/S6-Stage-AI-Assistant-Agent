#!/bin/bash
# ============================================================================
# Script de Vérification Docker pour AI-Agent
# ============================================================================
# Description: Vérifie que tous les services fonctionnent correctement
#              après un rebuild
# Usage: ./docker-verify.sh
# ============================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0;33m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

echo "============================================"
echo "🔍 AI-Agent Docker Verification"
echo "============================================"
echo ""

# Compteur de tests
TESTS_PASSED=0
TESTS_FAILED=0

# ============================================================================
# TEST 1: Vérifier que les containers tournent
# ============================================================================

log_info "Test 1: Vérification des containers"

EXPECTED_CONTAINERS=("ai_agent_postgres" "ai_agent_rabbitmq")
for container in "${EXPECTED_CONTAINERS[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        log_success "$container est en cours d'exécution"
        ((TESTS_PASSED++))
    else
        log_error "$container n'est pas en cours d'exécution"
        ((TESTS_FAILED++))
    fi
done

# ============================================================================
# TEST 2: Vérifier PostgreSQL
# ============================================================================

echo ""
log_info "Test 2: Vérification PostgreSQL"

# Test de connexion
if docker exec ai_agent_postgres pg_isready -U admin -d ai_agent_admin > /dev/null 2>&1; then
    log_success "PostgreSQL accepte les connexions"
    ((TESTS_PASSED++))
else
    log_error "PostgreSQL ne répond pas"
    ((TESTS_FAILED++))
fi

# Test des tables principales
TABLES=("tasks" "task_runs" "run_steps" "webhook_events")
for table in "${TABLES[@]}"; do
    if docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT 1 FROM $table LIMIT 1" > /dev/null 2>&1; then
        log_success "Table $table existe et est accessible"
        ((TESTS_PASSED++))
    else
        log_warning "Table $table n'existe pas encore ou n'est pas accessible"
        ((TESTS_FAILED++))
    fi
done

# ============================================================================
# TEST 3: Vérifier pg_partman
# ============================================================================

echo ""
log_info "Test 3: Vérification pg_partman"

PARTMAN_VERSION=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT extversion FROM pg_extension WHERE extname = 'pg_partman';" 2>/dev/null | tr -d ' ')

if [ -n "$PARTMAN_VERSION" ]; then
    log_success "pg_partman installé (version: $PARTMAN_VERSION)"
    ((TESTS_PASSED++))
else
    log_error "pg_partman non installé"
    ((TESTS_FAILED++))
fi

# Vérifier la configuration de webhook_events
PARTMAN_CONFIG=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT COUNT(*) FROM partman.part_config WHERE parent_table = 'public.webhook_events';" 2>/dev/null | tr -d ' ')

if [ "$PARTMAN_CONFIG" = "1" ]; then
    log_success "webhook_events configuré avec pg_partman"
    ((TESTS_PASSED++))
else
    log_warning "webhook_events non configuré avec pg_partman (peut être normal si première initialisation)"
fi

# ============================================================================
# TEST 4: Vérifier les corrections de failles
# ============================================================================

echo ""
log_info "Test 4: Vérification des corrections de failles"

# Faille #1: Colonnes de verrouillage
FAILLE1_COLUMNS=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "
SELECT COUNT(*) FROM information_schema.columns 
WHERE table_name='tasks' 
  AND column_name IN ('is_locked', 'locked_at', 'locked_by', 'reactivated_at', 'reactivation_count', 'previous_status')
" 2>/dev/null | tr -d ' ')

if [ "$FAILLE1_COLUMNS" = "6" ]; then
    log_success "Faille #1 (Verrouillage): 6/6 colonnes présentes"
    ((TESTS_PASSED++))
else
    log_error "Faille #1 (Verrouillage): $FAILLE1_COLUMNS/6 colonnes présentes"
    ((TESTS_FAILED++))
fi

# Faille #2: Colonnes de suivi Celery
FAILLE2_COLUMNS=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "
SELECT COUNT(*) FROM information_schema.columns 
WHERE table_name='task_runs' 
  AND column_name IN ('active_task_ids', 'last_task_id', 'task_started_at', 'is_reactivation')
" 2>/dev/null | tr -d ' ')

if [ "$FAILLE2_COLUMNS" = "4" ]; then
    log_success "Faille #2 (Celery): 4/4 colonnes présentes"
    ((TESTS_PASSED++))
else
    log_error "Faille #2 (Celery): $FAILLE2_COLUMNS/4 colonnes présentes"
    ((TESTS_FAILED++))
fi

# Faille #3: Colonnes de cooldown
FAILLE3_COLUMNS=$(docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "
SELECT COUNT(*) FROM information_schema.columns 
WHERE table_name='tasks' 
  AND column_name IN ('last_reactivation_attempt', 'cooldown_until', 'failed_reactivation_attempts')
" 2>/dev/null | tr -d ' ')

if [ "$FAILLE3_COLUMNS" = "3" ]; then
    log_success "Faille #3 (Cooldown): 3/3 colonnes présentes"
    ((TESTS_PASSED++))
else
    log_error "Faille #3 (Cooldown): $FAILLE3_COLUMNS/3 colonnes présentes"
    ((TESTS_FAILED++))
fi

# ============================================================================
# TEST 5: Vérifier les vues
# ============================================================================

echo ""
log_info "Test 5: Vérification des vues"

VIEWS=("v_tasks_reactivable" "v_active_celery_tasks" "v_reactivation_stats")
for view in "${VIEWS[@]}"; do
    if docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT 1 FROM $view LIMIT 1" > /dev/null 2>&1; then
        log_success "Vue $view existe et fonctionne"
        ((TESTS_PASSED++))
    else
        log_warning "Vue $view n'existe pas ou ne fonctionne pas"
        ((TESTS_FAILED++))
    fi
done

# ============================================================================
# TEST 6: Vérifier les fonctions
# ============================================================================

echo ""
log_info "Test 6: Vérification des fonctions"

FUNCTIONS=("clean_expired_locks" "reset_failed_attempts_on_success")
for func in "${FUNCTIONS[@]}"; do
    if docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT 1 FROM pg_proc WHERE proname = '$func'" > /dev/null 2>&1; then
        log_success "Fonction $func existe"
        ((TESTS_PASSED++))
    else
        log_error "Fonction $func n'existe pas"
        ((TESTS_FAILED++))
    fi
done

# ============================================================================
# TEST 7: Vérifier RabbitMQ
# ============================================================================

echo ""
log_info "Test 7: Vérification RabbitMQ"

if docker exec ai_agent_rabbitmq rabbitmq-diagnostics ping > /dev/null 2>&1; then
    log_success "RabbitMQ répond au ping"
    ((TESTS_PASSED++))
else
    log_error "RabbitMQ ne répond pas"
    ((TESTS_FAILED++))
fi

# Vérifier les queues
QUEUES_COUNT=$(docker exec ai_agent_rabbitmq rabbitmqctl list_queues -q 2>/dev/null | wc -l | tr -d ' ')
if [ "$QUEUES_COUNT" -gt 0 ]; then
    log_success "RabbitMQ: $QUEUES_COUNT queue(s) configurée(s)"
    ((TESTS_PASSED++))
else
    log_warning "RabbitMQ: Aucune queue configurée (normal si premier démarrage)"
fi

# ============================================================================
# TEST 8: Vérifier les index
# ============================================================================

echo ""
log_info "Test 8: Vérification des index"

INDEXES=("idx_tasks_is_locked" "idx_tasks_cooldown" "idx_task_runs_active_tasks")
for index in "${INDEXES[@]}"; do
    if docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -t -c "SELECT 1 FROM pg_indexes WHERE indexname = '$index'" | grep -q "1"; then
        log_success "Index $index existe"
        ((TESTS_PASSED++))
    else
        log_warning "Index $index n'existe pas"
        ((TESTS_FAILED++))
    fi
done

# ============================================================================
# RÉSUMÉ
# ============================================================================

echo ""
echo "============================================"
echo "📊 RÉSUMÉ DES TESTS"
echo "============================================"
echo -e "${GREEN}✅ Tests réussis: $TESTS_PASSED${NC}"
echo -e "${RED}❌ Tests échoués: $TESTS_FAILED${NC}"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
if [ $TOTAL_TESTS -gt 0 ]; then
    SUCCESS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))
    echo -e "📈 Taux de réussite: ${SUCCESS_RATE}%"
fi

echo "============================================"

if [ $TESTS_FAILED -eq 0 ]; then
    echo ""
    log_success "Toutes les vérifications sont passées! 🎉"
    echo ""
    exit 0
else
    echo ""
    log_warning "Certaines vérifications ont échoué"
    log_info "Consultez les logs pour plus de détails:"
    echo "  docker-compose -f docker-compose.rabbitmq.yml logs postgres"
    echo ""
    exit 1
fi

