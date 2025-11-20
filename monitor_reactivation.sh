#!/bin/bash
# Script pour monitorer les logs de réactivation en temps réel

echo "======================================"
echo "🔍 MONITORING RÉACTIVATION WEBHOOK"
echo "======================================"
echo ""
echo "Ce script affiche les logs en temps réel pour diagnostiquer la réactivation."
echo "Postez maintenant votre 2ème update sur Monday.com..."
echo ""
echo "======================================"
echo ""

# Suivre les logs FastAPI et Celery en parallèle
tail -f logs/fastapi.log logs/celery_worker.log | grep -E "(WEBHOOK|RÉACTIVATION|REACTIVATION|Task ID|Run ID|is_reactivation|execute_workflow|create_new_workflow)" --color=always

