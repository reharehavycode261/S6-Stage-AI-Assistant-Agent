-- ===============================================
-- SCRIPT 02: Configuration de pg_partman pour webhook_events
-- ===============================================
-- Description: Configure le partitionnement automatique pour webhook_events
-- Migration: Convertit le partitionnement manuel vers pg_partman
-- Attention: Ce script vérifie d'abord si la table existe déjà
-- ===============================================

\echo '=========================================='
\echo '📊 Configuration du partitionnement automatique'
\echo '    Table: webhook_events'
\echo '=========================================='

-- ===============================================
-- ÉTAPE 1: Vérifier et préparer la table webhook_events
-- ===============================================

DO $$ 
DECLARE
    table_exists boolean;
    partition_count integer;
BEGIN
    -- Vérifier si la table existe déjà
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'webhook_events'
    ) INTO table_exists;

    IF table_exists THEN
        RAISE NOTICE '✅ Table webhook_events existe déjà';
        
        -- Compter les partitions existantes
        SELECT COUNT(*) INTO partition_count
        FROM pg_inherits
        JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
        JOIN pg_class child ON pg_inherits.inhrelid = child.oid
        WHERE parent.relname = 'webhook_events';
        
        RAISE NOTICE '   📊 Partitions existantes: %', partition_count;
    ELSE
        RAISE NOTICE '⚠️  Table webhook_events n''existe pas encore';
        RAISE NOTICE '   Elle sera créée par le script principal (init-db.sql)';
    END IF;
END $$;

-- ===============================================
-- ÉTAPE 2: Configurer pg_partman pour webhook_events
-- ===============================================

DO $$ 
DECLARE
    table_exists boolean;
BEGIN
    -- Vérifier si la table existe
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'webhook_events'
    ) INTO table_exists;

    IF table_exists THEN
        RAISE NOTICE '========================================';
        RAISE NOTICE '🔧 Configuration de pg_partman';
        RAISE NOTICE '========================================';
        
        -- Enregistrer la table dans pg_partman
        -- Configuration :
        --   - Interval : 1 mois (native)
        --   - Premaintain : 4 partitions futures (4 mois à l'avance)
        --   - Retention : conserver 6 mois de données
        --   - Retention_keep_table : false (supprimer les anciennes partitions)
        PERFORM partman.create_parent(
            p_parent_table := 'public.webhook_events',
            p_control := 'received_at',
            p_type := 'native',
            p_interval := '1 month',
            p_premake := 4,
            p_start_partition := to_char(NOW() - interval '1 month', 'YYYY-MM-01')::text
        );
        
        RAISE NOTICE '✅ Table webhook_events enregistrée dans pg_partman';
        RAISE NOTICE '   📅 Partitions futures: 4 mois';
        RAISE NOTICE '   🗓️  Intervalle: 1 mois';
        
        -- Configurer la rétention des données
        UPDATE partman.part_config 
        SET retention = '6 months',
            retention_keep_table = false,
            retention_keep_index = false,
            infinite_time_partitions = true
        WHERE parent_table = 'public.webhook_events';
        
        RAISE NOTICE '✅ Rétention configurée: 6 mois';
        RAISE NOTICE '   🗑️  Suppression automatique des anciennes partitions activée';
        
        -- Créer les partitions manquantes
        PERFORM partman.run_maintenance('public.webhook_events');
        
        RAISE NOTICE '✅ Maintenance initiale exécutée';
        
    ELSE
        RAISE NOTICE '⏭️  Table webhook_events pas encore créée, configuration reportée';
    END IF;
END $$;

-- ===============================================
-- ÉTAPE 3: Afficher la configuration actuelle
-- ===============================================

DO $$ 
DECLARE
    config_exists boolean;
BEGIN
    -- Vérifier si la configuration existe
    SELECT EXISTS (
        SELECT 1 FROM partman.part_config 
        WHERE parent_table = 'public.webhook_events'
    ) INTO config_exists;

    IF config_exists THEN
        RAISE NOTICE '========================================';
        RAISE NOTICE '📋 Configuration pg_partman pour webhook_events';
        RAISE NOTICE '========================================';
    END IF;
END $$;

-- Afficher la configuration si elle existe
SELECT 
    parent_table AS "Table parent",
    partition_type AS "Type",
    partition_interval AS "Intervalle",
    premake AS "Partitions futures",
    retention AS "Rétention",
    retention_keep_table AS "Conserver tables supprimées",
    infinite_time_partitions AS "Partitions infinies"
FROM partman.part_config
WHERE parent_table = 'public.webhook_events';

\echo '=========================================='
\echo '✅ Configuration pg_partman terminée'
\echo '=========================================='

