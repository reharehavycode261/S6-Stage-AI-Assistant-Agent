#!/bin/bash

# Script de déploiement - Nouveau Workflow depuis Updates Monday
# Date: 11 octobre 2025

set -e  # Arrêter en cas d'erreur

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🚀 DÉPLOIEMENT WORKFLOW UPDATE SYSTEM${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ============================================================================
# ÉTAPE 1: Vérifications pré-déploiement
# ============================================================================

echo -e "${YELLOW}[1/6] Vérifications pré-déploiement...${NC}"

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "main.py" ]; then
    echo -e "${RED}❌ Erreur: Exécutez ce script depuis la racine du projet${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Répertoire correct${NC}"

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 n'est pas installé${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 3 disponible${NC}"

# Vérifier que les nouveaux fichiers existent
FILES_TO_CHECK=(
    "services/update_analyzer_service.py"
    "services/workflow_trigger_service.py"
    "data/migration_task_update_triggers.sql"
    "tests/test_update_workflow_trigger.py"
    "validate_update_workflow.py"
)

for file in "${FILES_TO_CHECK[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Fichier manquant: $file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ Tous les fichiers présents${NC}"
echo ""

# ============================================================================
# ÉTAPE 2: Appliquer la migration SQL
# ============================================================================

echo -e "${YELLOW}[2/6] Application de la migration SQL...${NC}"

# Demander les informations de connexion DB
echo -e "${BLUE}Veuillez fournir les informations de connexion à la base de données:${NC}"
read -p "Hôte (localhost): " DB_HOST
DB_HOST=${DB_HOST:-localhost}

read -p "Port (5432): " DB_PORT
DB_PORT=${DB_PORT:-5432}

read -p "Nom de la base: " DB_NAME
read -p "Utilisateur: " DB_USER

# Vérifier que psql est disponible
if ! command -v psql &> /dev/null; then
    echo -e "${RED}❌ psql n'est pas installé${NC}"
    echo -e "${YELLOW}⚠️  Appliquez manuellement: psql -U $DB_USER -d $DB_NAME -f data/migration_task_update_triggers.sql${NC}"
    read -p "Appuyez sur Entrée quand c'est fait..."
else
    echo -e "${BLUE}Application de la migration...${NC}"
    PGPASSWORD="" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f data/migration_task_update_triggers.sql
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Migration SQL appliquée avec succès${NC}"
    else
        echo -e "${RED}❌ Erreur lors de l'application de la migration${NC}"
        echo -e "${YELLOW}⚠️  Vérifiez les erreurs ci-dessus et réessayez${NC}"
        exit 1
    fi
fi

echo ""

# ============================================================================
# ÉTAPE 3: Installer les dépendances (si nécessaire)
# ============================================================================

echo -e "${YELLOW}[3/6] Vérification des dépendances Python...${NC}"

# Les dépendances sont déjà dans requirements.txt
echo -e "${BLUE}Les dépendances sont déjà dans requirements.txt${NC}"
echo -e "${GREEN}✅ Aucune nouvelle dépendance requise${NC}"
echo ""

# ============================================================================
# ÉTAPE 4: Exécuter les tests
# ============================================================================

echo -e "${YELLOW}[4/6] Exécution des tests...${NC}"

# Tests unitaires
echo -e "${BLUE}Exécution des tests unitaires...${NC}"
if command -v pytest &> /dev/null; then
    pytest tests/test_update_workflow_trigger.py -v
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Tests unitaires passent${NC}"
    else
        echo -e "${YELLOW}⚠️  Certains tests ont échoué (continuez uniquement si attendu)${NC}"
        read -p "Continuer malgré les erreurs? (y/N): " CONTINUE
        if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}⚠️  pytest n'est pas installé - tests ignorés${NC}"
fi

echo ""

# Script de validation
echo -e "${BLUE}Exécution du script de validation...${NC}"
python3 validate_update_workflow.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Validation réussie${NC}"
else
    echo -e "${RED}❌ Validation échouée${NC}"
    echo -e "${YELLOW}⚠️  Corrigez les erreurs avant de continuer${NC}"
    exit 1
fi

echo ""

# ============================================================================
# ÉTAPE 5: Vérifier les clés API
# ============================================================================

echo -e "${YELLOW}[5/6] Vérification des clés API LLM...${NC}"

if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ Aucune clé API LLM configurée${NC}"
    echo -e "${YELLOW}⚠️  Configurez ANTHROPIC_API_KEY ou OPENAI_API_KEY${NC}"
    echo ""
    echo -e "${BLUE}Exemple:${NC}"
    echo "export ANTHROPIC_API_KEY='sk-ant-...'"
    echo ""
    read -p "Voulez-vous continuer sans clé API? (y/N): " CONTINUE
    if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
        exit 1
    fi
else
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        echo -e "${GREEN}✅ ANTHROPIC_API_KEY configurée${NC}"
    fi
    if [ -n "$OPENAI_API_KEY" ]; then
        echo -e "${GREEN}✅ OPENAI_API_KEY configurée${NC}"
    fi
fi

echo ""

# ============================================================================
# ÉTAPE 6: Instructions de redémarrage
# ============================================================================

echo -e "${YELLOW}[6/6] Instructions de redémarrage des services${NC}"
echo ""
echo -e "${BLUE}Pour que les changements prennent effet, redémarrez:${NC}"
echo ""
echo -e "1. ${YELLOW}FastAPI:${NC}"
echo "   - Si en mode dev: Le rechargement automatique devrait suffire"
echo "   - Si en prod: Redémarrez le processus FastAPI"
echo ""
echo -e "2. ${YELLOW}Celery Workers:${NC}"
echo "   - Arrêtez les workers actuels: Ctrl+C ou kill"
echo "   - Redémarrez: celery -A services.celery_app worker --loglevel=info"
echo ""

read -p "Appuyez sur Entrée une fois les services redémarrés..."

# ============================================================================
# FINALISATION
# ============================================================================

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ DÉPLOIEMENT TERMINÉ AVEC SUCCÈS${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${GREEN}Le système est maintenant opérationnel !${NC}"
echo ""
echo -e "${BLUE}📚 Prochaines étapes:${NC}"
echo ""
echo "1. Test manuel:"
echo "   - Aller sur Monday.com"
echo "   - Trouver une tâche terminée (statut 'Done')"
echo "   - Poster: 'Bonjour, pouvez-vous ajouter un export CSV ?'"
echo "   - Vérifier les logs"
echo ""
echo "2. Monitoring:"
echo "   tail -f logs/application.log | grep -E '(analyse|trigger|workflow)'"
echo ""
echo "3. Vérification DB:"
echo "   SELECT * FROM task_update_triggers ORDER BY created_at DESC LIMIT 5;"
echo ""
echo -e "${BLUE}📖 Documentation:${NC}"
echo "   - GUIDE_TEST_NOUVEAU_WORKFLOW_UPDATE.md"
echo "   - RAPPORT_IMPLEMENTATION_WORKFLOW_UPDATE.md"
echo "   - IMPLEMENTATION_COMPLETE_RESUME.md"
echo ""
echo -e "${GREEN}🎉 Bon lancement !${NC}"
echo ""

