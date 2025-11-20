#!/bin/bash
# Script de correction automatique de l'environnement virtuel

set -e  # Arrêter en cas d'erreur

echo "════════════════════════════════════════════════════════════════════════"
echo "🔧 CORRECTION AUTOMATIQUE DE L'ENVIRONNEMENT VIRTUEL"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages
info() {
    echo -e "${GREEN}✅${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

error() {
    echo -e "${RED}❌${NC} $1"
}

# 1. Vérifier l'architecture du système
echo "📋 Étape 1: Vérification de l'architecture système"
echo "────────────────────────────────────────────────────────────────────────"
ARCH=$(uname -m)
info "Architecture détectée: $ARCH"

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
info "Version Python: $PYTHON_VERSION"
echo ""

# 2. Vérifier si l'environnement virtuel existe
echo "📋 Étape 2: Vérification de l'environnement virtuel"
echo "────────────────────────────────────────────────────────────────────────"

if [ -d "venv" ]; then
    warn "Environnement virtuel existant détecté"
    
    # Vérifier l'architecture du venv
    if [ -f "venv/bin/python" ]; then
        VENV_ARCH=$(file venv/bin/python | grep -o 'arm64\|x86_64' | head -1)
        info "Architecture du venv: $VENV_ARCH"
        
        if [ "$VENV_ARCH" != "$ARCH" ]; then
            error "INCOMPATIBILITÉ DÉTECTÉE: venv ($VENV_ARCH) != système ($ARCH)"
            echo ""
            read -p "Voulez-vous recréer l'environnement virtuel ? (o/n) " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Oo]$ ]]; then
                warn "Sauvegarde de l'ancien venv..."
                mv venv venv.backup.$(date +%Y%m%d_%H%M%S)
                info "Ancien venv sauvegardé"
            else
                error "Correction annulée par l'utilisateur"
                exit 1
            fi
        else
            info "Architecture compatible"
        fi
    fi
else
    warn "Aucun environnement virtuel trouvé"
fi
echo ""

# 3. Créer ou vérifier l'environnement virtuel
echo "📋 Étape 3: Création/vérification de l'environnement virtuel"
echo "────────────────────────────────────────────────────────────────────────"

if [ ! -d "venv" ]; then
    info "Création d'un nouvel environnement virtuel..."
    python3 -m venv venv
    info "Environnement virtuel créé"
else
    info "Environnement virtuel existant (compatible)"
fi
echo ""

# 4. Activer l'environnement virtuel
echo "📋 Étape 4: Activation de l'environnement virtuel"
echo "────────────────────────────────────────────────────────────────────────"
source venv/bin/activate
info "Environnement virtuel activé"
echo ""

# 5. Mettre à jour pip
echo "📋 Étape 5: Mise à jour de pip"
echo "────────────────────────────────────────────────────────────────────────"
python -m pip install --upgrade pip --quiet
info "pip mis à jour"
echo ""

# 6. Vérifier si requirements.txt existe
echo "📋 Étape 6: Installation des dépendances"
echo "────────────────────────────────────────────────────────────────────────"

if [ -f "requirements.txt" ]; then
    info "Fichier requirements.txt trouvé"
    
    # Compter le nombre de packages
    TOTAL_PACKAGES=$(grep -v '^#' requirements.txt | grep -v '^$' | wc -l | tr -d ' ')
    info "Installation de $TOTAL_PACKAGES packages..."
    
    # Installer les packages
    pip install -r requirements.txt --quiet
    
    if [ $? -eq 0 ]; then
        info "Toutes les dépendances installées avec succès"
    else
        error "Erreur lors de l'installation de certaines dépendances"
        warn "Essai d'installation package par package..."
        
        # Installer package par package en cas d'erreur
        while IFS= read -r package; do
            # Ignorer les lignes vides et les commentaires
            if [[ ! -z "$package" ]] && [[ ! "$package" =~ ^# ]]; then
                echo "  → Installation de $package..."
                pip install "$package" --quiet || warn "Échec: $package (ignoré)"
            fi
        done < requirements.txt
    fi
else
    error "Fichier requirements.txt non trouvé"
    warn "Installation manuelle des packages essentiels..."
    
    # Packages essentiels pour l'application
    ESSENTIAL_PACKAGES=(
        "pydantic>=2.0"
        "fastapi"
        "uvicorn"
        "asyncpg"
        "celery"
        "redis"
        "langchain"
        "langchain-anthropic"
        "langgraph"
    )
    
    for package in "${ESSENTIAL_PACKAGES[@]}"; do
        echo "  → Installation de $package..."
        pip install "$package" --quiet || warn "Échec: $package"
    done
fi
echo ""

# 7. Vérifier l'installation de pydantic
echo "📋 Étape 7: Vérification des packages critiques"
echo "────────────────────────────────────────────────────────────────────────"

CRITICAL_PACKAGES=("pydantic" "fastapi" "asyncpg" "celery")

for package in "${CRITICAL_PACKAGES[@]}"; do
    if python -c "import $package" 2>/dev/null; then
        VERSION=$(python -c "import $package; print($package.__version__)" 2>/dev/null || echo "N/A")
        info "$package: $VERSION"
    else
        error "$package: NON INSTALLÉ"
    fi
done
echo ""

# 8. Tester l'import de models.schemas
echo "📋 Étape 8: Test des imports du projet"
echo "────────────────────────────────────────────────────────────────────────"

if python -c "from models.schemas import WorkflowReactivation, MondayEvent" 2>/dev/null; then
    info "Import models.schemas: OK"
else
    error "Import models.schemas: ÉCHEC"
    warn "Vérification de la structure du projet..."
    
    if [ -f "models/schemas.py" ]; then
        info "Fichier models/schemas.py existe"
    else
        error "Fichier models/schemas.py manquant"
    fi
fi
echo ""

# 9. Résumé final
echo "════════════════════════════════════════════════════════════════════════"
echo "📊 RÉSUMÉ DE LA CORRECTION"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "Architecture système: $ARCH"
echo "Version Python: $PYTHON_VERSION"
echo "Environnement virtuel: venv/"
echo ""

# Test final
echo "🧪 Test final de l'application..."
if python -c "from models.schemas import MondayColumnValue, MondayEvent, TaskRequest, WebhookPayload; print('✅ Tous les imports fonctionnent')" 2>/dev/null; then
    echo ""
    info "✅ CORRECTION RÉUSSIE !"
    echo ""
    echo "🚀 Vous pouvez maintenant lancer l'application avec:"
    echo "   source venv/bin/activate"
    echo "   python main.py"
    echo ""
    exit 0
else
    echo ""
    error "❌ Certains imports échouent encore"
    echo ""
    echo "🔍 Diagnostic supplémentaire nécessaire. Exécutez:"
    echo "   source venv/bin/activate"
    echo "   python -c 'import pydantic; print(pydantic.__version__)'"
    echo ""
    exit 1
fi

