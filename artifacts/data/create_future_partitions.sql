-- Script pour créer les partitions futures de webhook_events
-- À exécuter chaque trimestre pour maintenir les partitions à jour

-- Novembre 2025
CREATE TABLE IF NOT EXISTS webhook_events_2025_11 
PARTITION OF webhook_events 
FOR VALUES FROM ('2025-11-01 00:00:00+00') TO ('2025-12-01 00:00:00+00');

-- Décembre 2025
CREATE TABLE IF NOT EXISTS webhook_events_2025_12 
PARTITION OF webhook_events 
FOR VALUES FROM ('2025-12-01 00:00:00+00') TO ('2026-01-01 00:00:00+00');

-- Janvier 2026
CREATE TABLE IF NOT EXISTS webhook_events_2026_01 
PARTITION OF webhook_events 
FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-02-01 00:00:00+00');

-- Février 2026
CREATE TABLE IF NOT EXISTS webhook_events_2026_02 
PARTITION OF webhook_events 
FOR VALUES FROM ('2026-02-01 00:00:00+00') TO ('2026-03-01 00:00:00+00');

-- Mars 2026
CREATE TABLE IF NOT EXISTS webhook_events_2026_03 
PARTITION OF webhook_events 
FOR VALUES FROM ('2026-03-01 00:00:00+00') TO ('2026-04-01 00:00:00+00');

-- Afficher toutes les partitions créées
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename LIKE 'webhook_events_%'
ORDER BY tablename;

