#!/bin/bash
# Script pour créer la table monday_users et synchroniser les données

set -e  # Arrêter en cas d'erreur

echo "🚀 Migration: Création de la table monday_users"
echo "=============================================="

# Couleurs pour les logs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Charger les variables d'environnement
if [ -f ".env" ]; then
    source .env
    echo -e "${GREEN}✅ Variables d'environnement chargées${NC}"
else
    echo -e "${RED}❌ Fichier .env non trouvé${NC}"
    exit 1
fi

# Vérifier DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ DATABASE_URL non défini${NC}"
    exit 1
fi

echo ""
echo "📝 Étape 1: Création de la table monday_users"
echo "----------------------------------------------"

psql "$DATABASE_URL" -f sql/create_monday_users_table.sql

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Table monday_users créée avec succès${NC}"
else
    echo -e "${RED}❌ Échec de la création de la table${NC}"
    exit 1
fi

echo ""
echo "🔄 Étape 2: Synchronisation des utilisateurs depuis Monday.com"
echo "--------------------------------------------------------------"

# Activer l'environnement virtuel si nécessaire
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✅ Environnement virtuel activé${NC}"
fi

# Exécuter le script de synchronisation
python3 scripts/sync_monday_users.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Synchronisation terminée${NC}"
else
    echo -e "${YELLOW}⚠️  Synchronisation partielle ou échec${NC}"
    echo -e "${YELLOW}   Ceci est normal si l'API Monday n'est pas accessible${NC}"
fi

echo ""
echo "📊 Étape 3: Vérification des données"
echo "------------------------------------"

# Compter les utilisateurs
USER_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM monday_users;")
echo -e "${GREEN}✅ Nombre d'utilisateurs dans monday_users: ${USER_COUNT}${NC}"

# Afficher quelques exemples
echo ""
echo "Exemples d'utilisateurs:"
psql "$DATABASE_URL" -c "SELECT monday_user_id, name, email, role, access_status, last_activity FROM monday_users LIMIT 5;"

echo ""
echo "========================================"
echo -e "${GREEN}✨ Migration terminée avec succès!${NC}"
echo "========================================"
echo ""
echo "Prochaines étapes:"
echo "  1. Redémarrer le backend: ./restart_backend.sh"
echo "  2. Vérifier l'API: curl http://localhost:3000/api/users"
echo "  3. Accéder à l'interface: http://localhost:3000/users"
echo ""

