#!/bin/bash

echo "🔄 ===== REDÉMARRAGE CELERY AVEC CORRECTIONS ====="
echo ""

# 1. Arrêter Celery
echo "1️⃣ Arrêt de tous les processus Celery..."
pkill -9 -f celery 2>/dev/null
sleep 2

# 2. Vérifier que Celery est bien arrêté
CELERY_RUNNING=$(ps aux | grep celery | grep -v grep | wc -l)
if [ "$CELERY_RUNNING" -gt 0 ]; then
    echo "⚠️  ATTENTION: Des processus Celery sont toujours actifs !"
    ps aux | grep celery | grep -v grep
    echo ""
    echo "Forçage de l'arrêt..."
    pkill -9 -f celery
    sleep 2
else
    echo "✅ Tous les processus Celery arrêtés"
fi

# 3. Nettoyer le cache Python (optionnel mais recommandé)
echo ""
echo "2️⃣ Nettoyage du cache Python..."
cd "/Users/stagiaire_vycode/Stage Smartelia/AI-Agent "
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo "✅ Cache Python nettoyé"

# 4. Vérifier les fichiers modifiés
echo ""
echo "3️⃣ Vérification des corrections..."
echo ""
echo "📝 Fichiers modifiés :"
echo "   - graph/workflow_graph.py"
echo "   - nodes/implement_node.py"
echo "   - nodes/openai_debug_node.py"
echo "   - nodes/monday_validation_node.py"
echo "   - nodes/update_node.py"
echo ""

# Vérifier que rejected_with_retry est bien dans workflow_graph.py
if grep -q "rejected_with_retry" graph/workflow_graph.py; then
    echo "✅ workflow_graph.py contient bien les corrections"
else
    echo "❌ ERREUR: workflow_graph.py ne contient pas 'rejected_with_retry'"
    echo "   Les modifications n'ont peut-être pas été sauvegardées !"
    exit 1
fi

# Vérifier que le flag est bien dans monday_validation_node.py
if grep -q "reimplementation_message_posted" nodes/monday_validation_node.py; then
    echo "✅ monday_validation_node.py contient bien les corrections"
else
    echo "❌ ERREUR: monday_validation_node.py ne contient pas 'reimplementation_message_posted'"
    exit 1
fi

# 5. Redémarrer Celery
echo ""
echo "4️⃣ Redémarrage de Celery..."
echo ""
echo "🚀 Lancement de Celery en arrière-plan..."
echo "   (Les logs seront dans logs/celery.log)"
echo ""

# Créer le répertoire logs si nécessaire
mkdir -p logs

# Lancer Celery en arrière-plan
nohup celery -A services.celery_app worker --loglevel=info > logs/celery.log 2>&1 &
CELERY_PID=$!

sleep 3

# Vérifier que Celery a bien démarré
if ps -p $CELERY_PID > /dev/null; then
    echo "✅ Celery redémarré avec succès ! (PID: $CELERY_PID)"
    echo ""
    echo "📋 PROCHAINES ÉTAPES :"
    echo ""
    echo "1. Testez avec une réponse : 'Non, ajoute des commentaires dans le code'"
    echo ""
    echo "2. Vérifiez les logs en temps réel :"
    echo "   tail -f logs/celery.log | grep -E '(Flag reimplementation|Skip commentaire|relance via implement|INSTRUCTIONS DE MODIFICATION)'"
    echo ""
    echo "3. Dans Monday.com, vous devriez voir UN SEUL message personnalisé"
    echo ""
    echo "4. Le workflow devrait ré-implémenter le code avec vos instructions"
    echo ""
    echo "📖 Guide complet : cat GUIDE_REDEMARRAGE_CORRECTIONS.md"
else
    echo "❌ ERREUR: Celery n'a pas démarré correctement"
    echo ""
    echo "Vérifiez les logs : cat logs/celery.log"
    exit 1
fi

