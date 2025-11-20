-- ===============================================
-- SCRIPT DE MIGRATION VERS PG_PARTMAN
-- ===============================================
-- Description: Migre le partitionnement manuel de webhook_events vers pg_partman
-- Usage: Exécuter manuellement sur une base de données existante
-- Prérequis: pg_partman doit être installé et configuré
-- ===============================================
-- ATTENTION: Ce script est pour les bases de données EXISTANTES uniquement
-- Pour les nouvelles installations, pg_partman sera configuré automatiquement
-- ===============================================

\echo '=========================================='
\echo '🔄 MIGRATION VERS PG_PARTMAN'
\echo '=========================================='

-- ===============================================
-- ÉTAPE 1: Vérifications préalables
-- ===============================================

\echo ''
\echo '📋 Étape 1: Vérifications préalables'

DO $$ 
DECLARE
    partman_exists boolean;
    table_exists boolean;
    partition_count integer;
    oldest_partition text;
    newest_partition text;
BEGIN
    -- Vérifier que pg_partman est installé
    SELECT EXISTS (
        SELECT FROM pg_extension 
        WHERE extname = 'pg_partman'
    ) INTO partman_exists;
    
    IF NOT partman_exists THEN
        RAISE EXCEPTION 'pg_partman n''est pas installé. Veuillez l''installer d''abord.';
    ELSE
        RAISE NOTICE '✅ pg_partman est installé';
    END IF;
    
    -- Vérifier que la table webhook_events existe
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'webhook_events'
    ) INTO table_exists;
    
    IF NOT table_exists THEN
        RAISE EXCEPTION 'La table webhook_events n''existe pas';
    ELSE
        RAISE NOTICE '✅ La table webhook_events existe';
    END IF;
    
    -- Compter les partitions existantes
    SELECT COUNT(*) INTO partition_count
    FROM pg_inherits
    JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
    JOIN pg_class child ON pg_inherits.inhrelid = child.oid
    WHERE parent.relname = 'webhook_events';
    
    RAISE NOTICE '📊 Partitions existantes: %', partition_count;
    
    -- Afficher les détails des partitions
    IF partition_count > 0 THEN
        SELECT MIN(child.relname), MAX(child.relname)
        INTO oldest_partition, newest_partition
        FROM pg_inherits
        JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
        JOIN pg_class child ON pg_inherits.inhrelid = child.oid
        WHERE parent.relname = 'webhook_events';
        
        RAISE NOTICE '   📅 Plus ancienne: %', oldest_partition;
        RAISE NOTICE '   📅 Plus récente: %', newest_partition;
    END IF;
END $$;

-- ===============================================
-- ÉTAPE 2: Sauvegarder l'état actuel
-- ===============================================

\echo ''
\echo '💾 Étape 2: Sauvegarde de l''état actuel'

-- Créer une table temporaire pour sauvegarder les noms des partitions
DROP TABLE IF EXISTS temp_partition_backup;

CREATE TEMP TABLE temp_partition_backup AS
SELECT 
    child.relname as partition_name,
    pg_get_expr(child.relpartbound, child.oid) as partition_bound
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname = 'webhook_events'
ORDER BY child.relname;

\echo '✅ État actuel sauvegardé'

-- Afficher les partitions sauvegardées
SELECT 
    partition_name AS "Partition",
    partition_bound AS "Bornes"
FROM temp_partition_backup;

-- ===============================================
-- ÉTAPE 3: Vérifier si pg_partman est déjà configuré
-- ===============================================

\echo ''
\echo '🔍 Étape 3: Vérification de la configuration pg_partman'

DO $$ 
DECLARE
    already_configured boolean;
BEGIN
    -- Vérifier si webhook_events est déjà configuré dans pg_partman
    SELECT EXISTS (
        SELECT 1 FROM partman.part_config 
        WHERE parent_table = 'public.webhook_events'
    ) INTO already_configured;
    
    IF already_configured THEN
        RAISE NOTICE '⚠️  webhook_events est déjà configuré dans pg_partman';
        RAISE NOTICE '   La migration peut avoir déjà été effectuée';
    ELSE
        RAISE NOTICE '✅ webhook_events n''est pas encore configuré dans pg_partman';
        RAISE NOTICE '   Prêt pour la migration';
    END IF;
END $$;

-- ===============================================
-- ÉTAPE 4: Configurer pg_partman (si pas déjà fait)
-- ===============================================

\echo ''
\echo '🔧 Étape 4: Configuration de pg_partman'

DO $$ 
DECLARE
    already_configured boolean;
BEGIN
    -- Vérifier si déjà configuré
    SELECT EXISTS (
        SELECT 1 FROM partman.part_config 
        WHERE parent_table = 'public.webhook_events'
    ) INTO already_configured;
    
    IF NOT already_configured THEN
        RAISE NOTICE 'Configuration de pg_partman pour webhook_events...';
        
        -- Enregistrer la table dans pg_partman
        PERFORM partman.create_parent(
            p_parent_table := 'public.webhook_events',
            p_control := 'received_at',
            p_type := 'native',
            p_interval := '1 month',
            p_premake := 4,
            p_start_partition := to_char(NOW() - interval '1 month', 'YYYY-MM-01')::text
        );
        
        RAISE NOTICE '✅ Table enregistrée dans pg_partman';
        
        -- Configurer la rétention
        UPDATE partman.part_config 
        SET retention = '6 months',
            retention_keep_table = false,
            retention_keep_index = false,
            infinite_time_partitions = true
        WHERE parent_table = 'public.webhook_events';
        
        RAISE NOTICE '✅ Rétention configurée (6 mois)';
    ELSE
        RAISE NOTICE '⏭️  Configuration déjà existante, passage à l''étape suivante';
    END IF;
END $$;

-- ===============================================
-- ÉTAPE 5: Créer les partitions manquantes
-- ===============================================

\echo ''
\echo '🔨 Étape 5: Création des partitions manquantes'

DO $$ 
DECLARE
    partitions_created integer;
BEGIN
    -- Exécuter la maintenance pour créer les partitions
    PERFORM partman.run_maintenance('public.webhook_events');
    
    RAISE NOTICE '✅ Maintenance exécutée';
    RAISE NOTICE '   Partitions créées automatiquement pour les 4 prochains mois';
END $$;

-- ===============================================
-- ÉTAPE 6: Vérification post-migration
-- ===============================================

\echo ''
\echo '✔️  Étape 6: Vérification post-migration'

-- Compter les partitions après migration
DO $$ 
DECLARE
    partition_count integer;
    config_check record;
BEGIN
    -- Compter les partitions
    SELECT COUNT(*) INTO partition_count
    FROM pg_inherits
    JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
    JOIN pg_class child ON pg_inherits.inhrelid = child.oid
    WHERE parent.relname = 'webhook_events';
    
    RAISE NOTICE '📊 Total des partitions après migration: %', partition_count;
    
    -- Vérifier la configuration
    SELECT 
        partition_interval,
        premake,
        retention
    INTO config_check
    FROM partman.part_config
    WHERE parent_table = 'public.webhook_events';
    
    RAISE NOTICE '⚙️  Intervalle: %', config_check.partition_interval;
    RAISE NOTICE '⚙️  Partitions futures: %', config_check.premake;
    RAISE NOTICE '⚙️  Rétention: %', config_check.retention;
END $$;

-- Afficher toutes les partitions
\echo ''
\echo '📋 Liste des partitions webhook_events:'
SELECT 
    child.relname AS "Partition",
    pg_get_expr(child.relpartbound, child.oid) AS "Bornes",
    pg_size_pretty(pg_total_relation_size(child.oid)) AS "Taille"
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname = 'webhook_events'
ORDER BY child.relname;

-- ===============================================
-- ÉTAPE 7: Afficher la configuration finale
-- ===============================================

\echo ''
\echo '=========================================='
\echo '📋 CONFIGURATION FINALE'
\echo '=========================================='

SELECT 
    parent_table AS "Table parent",
    partition_type AS "Type",
    partition_interval AS "Intervalle",
    premake AS "Partitions futures",
    retention AS "Rétention",
    retention_keep_table AS "Conserver tables",
    infinite_time_partitions AS "Partitions infinies"
FROM partman.part_config
WHERE parent_table = 'public.webhook_events';

\echo ''
\echo '=========================================='
\echo '✅ MIGRATION TERMINÉE AVEC SUCCÈS'
\echo '=========================================='
\echo ''
\echo '📌 Prochaines étapes:'
\echo '  1. Configurer le cron job pour la maintenance automatique'
\echo '  2. Vérifier les partitions créées'
\echo '  3. Tester l''insertion de données'
\echo '  4. Monitorer les performances'
\echo ''
\echo '💡 Commande de maintenance manuelle:'
\echo '  SELECT partman.run_maintenance(''public.webhook_events'');'
\echo ''
\echo '=========================================='

