#!/bin/bash
# Script d'installation de chrome-devtools-mcp
# Documentation: https://github.com/ChromeDevTools/chrome-devtools-mcp

echo "=================================="
echo "🚀 Installation chrome-devtools-mcp"
echo "=================================="

# Vérifier si Node.js est installé
if ! command -v node &> /dev/null; then
    echo "❌ Node.js n'est pas installé"
    echo "   Installez Node.js depuis: https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js détecté: $(node --version)"

# Vérifier si npm est installé
if ! command -v npm &> /dev/null; then
    echo "❌ npm n'est pas installé"
    exit 1
fi

echo "✅ npm détecté: $(npm --version)"

# Installer chrome-devtools-mcp globalement
echo ""
echo "📦 Installation de chrome-devtools-mcp@latest..."
npm install -g chrome-devtools-mcp@latest

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ chrome-devtools-mcp installé avec succès!"
    echo ""
    echo "🔍 Vérification de l'installation..."
    
    # Tester la commande
    npx chrome-devtools-mcp@latest --help > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ chrome-devtools-mcp est fonctionnel"
        echo ""
        echo "📋 Outils disponibles (24 au total):"
        echo "   • Navigation (6): navigate_page, new_page, close_page, list_pages, select_page, wait_for"
        echo "   • Interaction (4): click, fill, hover, press_key"
        echo "   • Inspection (5): get_dom_snapshot, get_accessibility_tree, list_page_properties,"
        echo "                     get_console_message, list_console_messages"
        echo "   • Capture (2): take_screenshot, take_snapshot"
        echo "   • Emulation (2): emulate, resize_page"
        echo "   • Performance (3): performance_analyze_insight, performance_start_trace, performance_stop_trace"
        echo "   • Network (2): list_network_requests, get_network_request"
        echo "   • Debugging (1): evaluate_script"
        echo ""
        echo "🎉 Installation terminée! Les tests browser seront maintenant en mode MCP natif."
    else
        echo "⚠️ Installation réussie mais chrome-devtools-mcp ne démarre pas"
        echo "   Le système utilisera le mode simulation en fallback"
    fi
else
    echo "❌ Erreur lors de l'installation"
    echo "   Le système utilisera le mode simulation en fallback"
    exit 1
fi

echo ""
echo "=================================="
echo "✅ Installation terminée"
echo "=================================="

