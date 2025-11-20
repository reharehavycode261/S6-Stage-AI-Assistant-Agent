#!/bin/bash

# Script pour ouvrir l'interface admin dans le navigateur

echo "🚀 OUVERTURE DE L'INTERFACE ADMIN"
echo ""

# Vérifier que le backend est accessible
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend accessible"
else
    echo "❌ Backend non accessible. Démarrez-le d'abord:"
    echo "   cd '/Users/stagiaire_vycode/Stage Smartelia/AI-Agent '"
    echo "   source venv/bin/activate"
    echo "   uvicorn main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

# Vérifier que le frontend est accessible
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend accessible"
else
    echo "❌ Frontend non accessible. Démarrez-le d'abord:"
    echo "   cd '/Users/stagiaire_vycode/Stage Smartelia/AI-Agent /ai-agent-front'"
    echo "   npm start"
    exit 1
fi

echo ""
echo "🌐 Ouverture dans le navigateur..."
echo ""

# Ouvrir le navigateur sur macOS
open http://localhost:3000

echo "✅ Navigateur ouvert sur http://localhost:3000"
echo ""
echo "📖 Ce que vous devriez voir:"
echo "   • Dashboard avec métriques CE MOIS"
echo "   • Graphique langages: Java 100%"
echo "   • État du système (Celery, DB, etc.)"
echo "   • Menu latéral avec toutes les sections"
echo ""
echo "🔍 Pour tester l'API directement:"
echo "   → Ouvrir http://localhost:8000/docs dans le navigateur"
echo ""
echo "📚 Guide complet: GUIDE_TEST_NAVIGATEUR.md"
echo ""

