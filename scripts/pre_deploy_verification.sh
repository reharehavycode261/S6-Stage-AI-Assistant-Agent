#!/bin/bash
# ===============================================
# Script de vérification pré-déploiement pg_partman
# ===============================================
# Description: Vérifie que tous les fichiers et configurations sont en place
# Usage: ./scripts/pre_deploy_verification.sh
# ===============================================

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Compteurs
CHECKS_PASSED=0
CHECKS_FAILED=0
TOTAL_CHECKS=0

# Fonction pour afficher le résultat
check_result() {
    local description=$1
    local result=$2
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✅${NC} $description"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        echo -e "${RED}❌${NC} $description"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
    fi
}

echo -e "${BLUE}=========================================="
echo "🔍 VÉRIFICATION PRÉ-DÉPLOIEMENT PG_PARTMAN"
echo -e "==========================================${NC}\n"

# ===============================================
# 1. VÉRIFICATION DES FICHIERS DOCKER
# ===============================================
echo -e "${YELLOW}📁 1. Vérification des fichiers Docker${NC}"

# Dockerfile
if [ -f "docker/postgres/Dockerfile" ]; then
    check_result "docker/postgres/Dockerfile existe" 0
    
    # Vérifier le contenu du Dockerfile
    if grep -q "pg_partman" "docker/postgres/Dockerfile"; then
        check_result "Dockerfile contient pg_partman" 0
    else
        check_result "Dockerfile contient pg_partman" 1
    fi
    
    if grep -q "dcron" "docker/postgres/Dockerfile"; then
        check_result "Dockerfile contient dcron" 0
    else
        check_result "Dockerfile contient dcron" 1
    fi
else
    check_result "docker/postgres/Dockerfile existe" 1
fi

# Scripts d'initialisation
if [ -f "docker/postgres/init-scripts/01-enable-pg-partman.sql" ]; then
    check_result "01-enable-pg-partman.sql existe" 0
else
    check_result "01-enable-pg-partman.sql existe" 1
fi

if [ -f "docker/postgres/init-scripts/02-configure-webhook-events-partman.sql" ]; then
    check_result "02-configure-webhook-events-partman.sql existe" 0
else
    check_result "02-configure-webhook-events-partman.sql existe" 1
fi

# Scripts de maintenance
if [ -f "docker/postgres/maintenance-partman.sh" ]; then
    check_result "maintenance-partman.sh existe" 0
    
    # Vérifier qu'il est exécutable (il le sera dans le container)
    if head -1 "docker/postgres/maintenance-partman.sh" | grep -q "#!/bin/bash"; then
        check_result "maintenance-partman.sh a un shebang" 0
    else
        check_result "maintenance-partman.sh a un shebang" 1
    fi
else
    check_result "maintenance-partman.sh existe" 1
fi

if [ -f "docker/postgres/cron-partman-maintenance" ]; then
    check_result "cron-partman-maintenance existe" 0
else
    check_result "cron-partman-maintenance existe" 1
fi

echo ""

# ===============================================
# 2. VÉRIFICATION DES SCRIPTS DE MIGRATION
# ===============================================
echo -e "${YELLOW}📄 2. Vérification des scripts de migration${NC}"

if [ -f "scripts/migrate_to_pg_partman.sql" ]; then
    check_result "migrate_to_pg_partman.sql existe" 0
    
    # Vérifier le contenu
    if grep -q "partman.create_parent" "scripts/migrate_to_pg_partman.sql"; then
        check_result "Script contient partman.create_parent" 0
    else
        check_result "Script contient partman.create_parent" 1
    fi
else
    check_result "migrate_to_pg_partman.sql existe" 1
fi

echo ""

# ===============================================
# 3. VÉRIFICATION DU DOCKER-COMPOSE
# ===============================================
echo -e "${YELLOW}🐳 3. Vérification du docker-compose.yml${NC}"

if [ -f "docker-compose.rabbitmq.yml" ]; then
    check_result "docker-compose.rabbitmq.yml existe" 0
    
    # Vérifier la section build
    if grep -q "context: ./docker/postgres" "docker-compose.rabbitmq.yml"; then
        check_result "docker-compose contient build postgres" 0
    else
        check_result "docker-compose contient build postgres" 1
    fi
    
    # Vérifier les volumes
    if grep -q "01-enable-pg-partman.sql" "docker-compose.rabbitmq.yml"; then
        check_result "docker-compose monte 01-enable-pg-partman.sql" 0
    else
        check_result "docker-compose monte 01-enable-pg-partman.sql" 1
    fi
    
    if grep -q "02-configure-webhook-events-partman.sql" "docker-compose.rabbitmq.yml"; then
        check_result "docker-compose monte 02-configure-webhook-events-partman.sql" 0
    else
        check_result "docker-compose monte 02-configure-webhook-events-partman.sql" 1
    fi
else
    check_result "docker-compose.rabbitmq.yml existe" 1
fi

echo ""

# ===============================================
# 4. VÉRIFICATION DU SCHÉMA INITIAL
# ===============================================
echo -e "${YELLOW}🗄️  4. Vérification du schéma initial${NC}"

if [ -f "config/init-db.sql" ]; then
    check_result "config/init-db.sql existe" 0
    
    # Vérifier que c'est un fichier SQL (pas un dossier)
    if [ -f "config/init-db.sql" ] && [ ! -d "config/init-db.sql" ]; then
        check_result "config/init-db.sql est un fichier (pas un dossier)" 0
    else
        check_result "config/init-db.sql est un fichier (pas un dossier)" 1
    fi
    
    # Vérifier qu'il contient la table webhook_events
    if grep -q "CREATE TABLE webhook_events" "config/init-db.sql"; then
        check_result "init-db.sql contient webhook_events" 0
    else
        check_result "init-db.sql contient webhook_events" 1
    fi
else
    check_result "config/init-db.sql existe" 1
fi

echo ""

# ===============================================
# 5. VÉRIFICATION DE LA DOCUMENTATION
# ===============================================
echo -e "${YELLOW}📚 5. Vérification de la documentation${NC}"

if [ -f "docs/PG_PARTMAN_IMPLEMENTATION.md" ]; then
    check_result "PG_PARTMAN_IMPLEMENTATION.md existe" 0
else
    check_result "PG_PARTMAN_IMPLEMENTATION.md existe" 1
fi

if [ -f "docs/VERIFICATION_PG_PARTMAN.md" ]; then
    check_result "VERIFICATION_PG_PARTMAN.md existe" 0
else
    check_result "VERIFICATION_PG_PARTMAN.md existe" 1
fi

if [ -f "QUICK_START_PG_PARTMAN.md" ]; then
    check_result "QUICK_START_PG_PARTMAN.md existe" 0
else
    check_result "QUICK_START_PG_PARTMAN.md existe" 1
fi

if [ -f "IMPLEMENTATION_PG_PARTMAN_RESUME.md" ]; then
    check_result "IMPLEMENTATION_PG_PARTMAN_RESUME.md existe" 0
else
    check_result "IMPLEMENTATION_PG_PARTMAN_RESUME.md existe" 1
fi

echo ""

# ===============================================
# 6. TEST DE BUILD DOCKER (optionnel)
# ===============================================
echo -e "${YELLOW}🔨 6. Test de build Docker (optionnel)${NC}"

read -p "Voulez-vous tester le build Docker maintenant ? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Construction de l'image PostgreSQL...${NC}"
    if docker-compose -f docker-compose.rabbitmq.yml build postgres > /tmp/pg_partman_build.log 2>&1; then
        check_result "Build Docker réussi" 0
        echo -e "${GREEN}   📋 Logs: /tmp/pg_partman_build.log${NC}"
    else
        check_result "Build Docker réussi" 1
        echo -e "${RED}   ❌ Erreur de build. Voir: /tmp/pg_partman_build.log${NC}"
        echo -e "${YELLOW}   Dernières lignes du log:${NC}"
        tail -20 /tmp/pg_partman_build.log
    fi
else
    echo -e "${YELLOW}⏭️  Build Docker ignoré${NC}"
fi

echo ""

# ===============================================
# 7. RÉSUMÉ
# ===============================================
echo -e "${BLUE}=========================================="
echo "📊 RÉSUMÉ DE LA VÉRIFICATION"
echo -e "==========================================${NC}"
echo -e "Total de vérifications: ${TOTAL_CHECKS}"
echo -e "${GREEN}✅ Réussies: ${CHECKS_PASSED}${NC}"
echo -e "${RED}❌ Échouées: ${CHECKS_FAILED}${NC}"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "🎉 TOUTES LES VÉRIFICATIONS SONT PASSÉES !"
    echo -e "==========================================${NC}"
    echo ""
    echo -e "${GREEN}✅ Le projet est prêt pour le déploiement${NC}"
    echo ""
    echo -e "${BLUE}Prochaines étapes:${NC}"
    echo "1. Sauvegarder la base de données actuelle (si migration)"
    echo "2. Suivre le guide: QUICK_START_PG_PARTMAN.md"
    echo "3. Déployer avec: docker-compose -f docker-compose.rabbitmq.yml up -d"
    echo ""
    exit 0
else
    echo -e "${RED}=========================================="
    echo "⚠️  DES VÉRIFICATIONS ONT ÉCHOUÉ"
    echo -e "==========================================${NC}"
    echo ""
    echo -e "${RED}❌ Le projet n'est PAS prêt pour le déploiement${NC}"
    echo ""
    echo -e "${YELLOW}Actions recommandées:${NC}"
    echo "1. Corriger les erreurs ci-dessus"
    echo "2. Relancer ce script de vérification"
    echo "3. Consulter IMPLEMENTATION_PG_PARTMAN_RESUME.md"
    echo ""
    exit 1
fi

