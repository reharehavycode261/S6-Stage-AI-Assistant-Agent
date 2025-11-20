#!/bin/bash
# ========================================================================
# SCRIPT DE MAINTENANCE DES PARTITIONS WEBHOOK_EVENTS
# À exécuter régulièrement (par exemple, via cron une fois par jour)
# ========================================================================

echo "🔧 Maintenance des partitions webhook_events avec pg_partman"
echo "=========================================================================="
echo ""

# Exécuter la maintenance pg_partman
echo "📋 Exécution de la maintenance pg_partman..."
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -c "
SELECT partman.run_maintenance('public.webhook_events', p_analyze := true);
"

echo ""
echo "📊 Partitions actuelles:"
docker exec ai_agent_postgres psql -U admin -d ai_agent_admin -c "
SELECT 
    schemaname || '.' || tablename as partition,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    (SELECT COUNT(*) 
     FROM webhook_events 
     WHERE tableoid = (schemaname||'.'||tablename)::regclass
    ) as row_count
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename LIKE 'webhook_events_p%'
ORDER BY tablename;
"

echo ""
echo "✅ Maintenance terminée"
echo "=========================================================================="
echo ""
echo "💡 Pour automatiser cette maintenance, ajoutez cette ligne à votre crontab:"
echo "   0 2 * * * /path/to/maintain_webhook_partitions.sh >> /var/log/webhook_partitions_maintenance.log 2>&1"

