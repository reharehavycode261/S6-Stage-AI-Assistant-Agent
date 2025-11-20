#!/bin/bash
# Installation du système de QA automatisé avec Chrome DevTools MCP

echo "🚀 Installation du système Browser QA Automation"
echo "================================================"

# Vérifier si npm est installé
if ! command -v npm &> /dev/null; then
    echo "❌ npm n'est pas installé. Installez Node.js d'abord:"
    echo "   https://nodejs.org/"
    exit 1
fi

echo "✅ npm détecté: $(npm --version)"

# Installer Chrome DevTools MCP globalement
echo ""
echo "📦 Installation de Chrome DevTools MCP..."
npm install -g chrome-devtools-mcp@latest

if [ $? -eq 0 ]; then
    echo "✅ Chrome DevTools MCP installé avec succès"
else
    echo "❌ Échec de l'installation de Chrome DevTools MCP"
    exit 1
fi

# Vérifier l'installation
echo ""
echo "🔍 Vérification de l'installation..."
if command -v chrome-devtools-mcp &> /dev/null; then
    echo "✅ chrome-devtools-mcp est accessible dans le PATH"
else
    echo "⚠️  chrome-devtools-mcp n'est pas dans le PATH"
    echo "   Ajoutez le chemin npm global à votre PATH:"
    echo "   export PATH=\"\$PATH:$(npm root -g)\""
fi

# Installer les dépendances Python pour le serveur dev
echo ""
echo "📦 Installation des dépendances Python..."
pip install psutil aiohttp asyncio

echo ""
echo "✅ Installation terminée !"
echo ""
echo "📘 Pour utiliser le système Browser QA:"
echo "   1. Les tests browser s'exécutent automatiquement pour les changements frontend"
echo "   2. Configuration dans .env (BROWSER_QA_ENABLED=true par défaut)"
echo "   3. Screenshots et rapports dans le répertoire de travail"
echo ""
echo "🔧 Configuration disponible dans config/settings.py"

