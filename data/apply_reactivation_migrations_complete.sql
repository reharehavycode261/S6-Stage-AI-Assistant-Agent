-- ============================================================================
-- SCRIPT COMPLET : Application de toutes les migrations de réactivation
-- ============================================================================
-- Date : 2025-10-21
-- Description : Applique TOUTES les migrations nécessaires pour la réactivation
--               de workflow en un seul script
-- 
-- Ordre d'exécution :
--   1. Table workflow_reactivations
--   2. Colonnes de réactivation (tasks et task_runs)
--   3. Colonne parent_run_id
--   4. Validation complète
-- ============================================================================

\set ON_ERROR_STOP on

-- Afficher l'heure de début
\echo '================================================================================'
\echo '🚀 DÉBUT DES MIGRATIONS DE RÉACTIVATION'
\echo '================================================================================'
\echo 'Date :' `date`
\echo ''

-- ============================================================================
-- ÉTAPE 1 : Création de la table workflow_reactivations
-- ============================================================================

\echo '📋 ÉTAPE 1/3 : Création de la table workflow_reactivations...'
\echo ''

\i data/migration_workflow_reactivations_table.sql

\echo ''
\echo '✅ Table workflow_reactivations créée'
\echo ''

-- ============================================================================
-- ÉTAPE 2 : Ajout des colonnes de réactivation
-- ============================================================================

\echo '📋 ÉTAPE 2/3 : Ajout des colonnes de réactivation...'
\echo ''

\i data/migration_failles_workflow_reactivation.sql

\echo ''
\echo '✅ Colonnes de réactivation ajoutées'
\echo ''

-- ============================================================================
-- ÉTAPE 3 : Ajout de la colonne parent_run_id
-- ============================================================================

\echo '📋 ÉTAPE 3/3 : Ajout de la colonne parent_run_id...'
\echo ''

\i data/add_parent_run_id_column.sql

\echo ''
\echo '✅ Colonne parent_run_id ajoutée'
\echo ''

-- ============================================================================
-- VALIDATION FINALE COMPLÈTE
-- ============================================================================

\echo ''
\echo '================================================================================'
\echo '🔍 VALIDATION FINALE COMPLÈTE'
\echo '================================================================================'
\echo ''

DO $$
DECLARE
    missing_tables TEXT[];
    missing_columns TEXT[];
    missing_indexes TEXT[];
    missing_views TEXT[];
    error_count INTEGER := 0;
BEGIN
    RAISE NOTICE '🔍 Vérification des tables...';
    
    -- Vérifier les tables
    SELECT array_agg(table_name)
    INTO missing_tables
    FROM (VALUES ('workflow_reactivations')) AS expected(table_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = expected.table_name
    );
    
    IF array_length(missing_tables, 1) > 0 THEN
        RAISE WARNING '❌ Tables manquantes: %', array_to_string(missing_tables, ', ');
        error_count := error_count + 1;
    ELSE
        RAISE NOTICE '✅ Toutes les tables créées';
    END IF;
    
    -- Vérifier les colonnes de tasks
    RAISE NOTICE '🔍 Vérification des colonnes de tasks...';
    
    SELECT array_agg(column_name)
    INTO missing_columns
    FROM (VALUES 
        ('reactivation_count'),
        ('reactivated_at'),
        ('is_locked'),
        ('locked_at'),
        ('locked_by'),
        ('previous_status'),
        ('last_reactivation_attempt'),
        ('cooldown_until'),
        ('failed_reactivation_attempts')
    ) AS expected(column_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'tasks' 
        AND column_name = expected.column_name
    );
    
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE WARNING '❌ Colonnes manquantes dans tasks: %', array_to_string(missing_columns, ', ');
        error_count := error_count + 1;
    ELSE
        RAISE NOTICE '✅ Toutes les colonnes de tasks présentes';
    END IF;
    
    -- Vérifier les colonnes de task_runs
    RAISE NOTICE '🔍 Vérification des colonnes de task_runs...';
    
    SELECT array_agg(column_name)
    INTO missing_columns
    FROM (VALUES 
        ('is_reactivation'),
        ('parent_run_id'),
        ('active_task_ids'),
        ('last_task_id'),
        ('task_started_at'),
        ('last_merged_pr_url')
    ) AS expected(column_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'task_runs' 
        AND column_name = expected.column_name
    );
    
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE WARNING '❌ Colonnes manquantes dans task_runs: %', array_to_string(missing_columns, ', ');
        error_count := error_count + 1;
    ELSE
        RAISE NOTICE '✅ Toutes les colonnes de task_runs présentes';
    END IF;
    
    -- Vérifier les index critiques
    RAISE NOTICE '🔍 Vérification des index critiques...';
    
    SELECT array_agg(indexname)
    INTO missing_indexes
    FROM (VALUES 
        ('idx_workflow_reactivations_workflow_id'),
        ('idx_workflow_reactivations_status'),
        ('idx_task_runs_is_reactivation'),
        ('idx_task_runs_parent_run_id'),
        ('idx_tasks_reactivation')
    ) AS expected(indexname)
    WHERE NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE schemaname = 'public' 
        AND indexname = expected.indexname
    );
    
    IF array_length(missing_indexes, 1) > 0 THEN
        RAISE WARNING '⚠️ Index manquants: %', array_to_string(missing_indexes, ', ');
        -- Ne pas incrémenter error_count car les index ne sont pas critiques
    ELSE
        RAISE NOTICE '✅ Tous les index critiques présents';
    END IF;
    
    -- Vérifier les vues
    RAISE NOTICE '🔍 Vérification des vues...';
    
    SELECT array_agg(table_name)
    INTO missing_views
    FROM (VALUES 
        ('v_tasks_reactivable'),
        ('v_workflow_reactivation_stats'),
        ('v_reactivation_tree')
    ) AS expected(table_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.views 
        WHERE table_schema = 'public' 
        AND table_name = expected.table_name
    );
    
    IF array_length(missing_views, 1) > 0 THEN
        RAISE WARNING '⚠️ Vues manquantes: %', array_to_string(missing_views, ', ');
    ELSE
        RAISE NOTICE '✅ Toutes les vues créées';
    END IF;
    
    -- Résultat final
    RAISE NOTICE '';
    RAISE NOTICE '================================================================================';
    
    IF error_count = 0 THEN
        RAISE NOTICE '🎉 MIGRATION COMPLÈTE RÉUSSIE !';
        RAISE NOTICE '================================================================================';
        RAISE NOTICE '';
        RAISE NOTICE '📊 Résumé des modifications :';
        RAISE NOTICE '   ✅ Table workflow_reactivations créée';
        RAISE NOTICE '   ✅ 9 colonnes ajoutées à tasks';
        RAISE NOTICE '   ✅ 6 colonnes ajoutées à task_runs';
        RAISE NOTICE '   ✅ Colonne parent_run_id ajoutée';
        RAISE NOTICE '   ✅ Index de performance créés';
        RAISE NOTICE '   ✅ Vues de monitoring créées';
        RAISE NOTICE '   ✅ Fonctions et triggers créés';
        RAISE NOTICE '';
        RAISE NOTICE '🔄 Le système de réactivation est maintenant OPÉRATIONNEL';
        RAISE NOTICE '';
    ELSE
        RAISE EXCEPTION '❌ MIGRATION ÉCHOUÉE - % erreur(s) détectée(s)', error_count;
    END IF;
END $$;

-- ============================================================================
-- STATISTIQUES FINALES
-- ============================================================================

\echo ''
\echo '================================================================================'
\echo '📊 STATISTIQUES DE LA BASE DE DONNÉES'
\echo '================================================================================'
\echo ''

-- Compter les colonnes ajoutées
SELECT 
    'tasks' AS table_name,
    COUNT(*) FILTER (WHERE column_name IN (
        'reactivation_count', 'reactivated_at', 'is_locked', 'locked_at', 
        'locked_by', 'previous_status', 'last_reactivation_attempt', 
        'cooldown_until', 'failed_reactivation_attempts'
    )) AS reactivation_columns
FROM information_schema.columns 
WHERE table_name = 'tasks'

UNION ALL

SELECT 
    'task_runs' AS table_name,
    COUNT(*) FILTER (WHERE column_name IN (
        'is_reactivation', 'parent_run_id', 'active_task_ids', 
        'last_task_id', 'task_started_at', 'last_merged_pr_url'
    )) AS reactivation_columns
FROM information_schema.columns 
WHERE table_name = 'task_runs';

\echo ''
\echo 'Index créés pour la réactivation :'
\echo ''

SELECT 
    indexname,
    tablename,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND (indexname LIKE '%reactivation%' 
       OR indexname LIKE '%parent_run%'
       OR indexname LIKE '%cooldown%'
       OR indexname LIKE '%locked%')
ORDER BY tablename, indexname;

\echo ''
\echo 'Vues de monitoring :'
\echo ''

SELECT 
    table_name AS view_name,
    COALESCE(view_definition, 'N/A') AS definition_preview
FROM information_schema.views
WHERE table_schema = 'public'
  AND table_name IN (
      'v_tasks_reactivable',
      'v_workflow_reactivation_stats',
      'v_recent_reactivations',
      'v_active_celery_tasks',
      'v_reactivation_stats',
      'v_reactivation_tree'
  )
ORDER BY table_name;

\echo ''
\echo '================================================================================'
\echo '🏁 FIN DES MIGRATIONS'
\echo '================================================================================'
\echo 'Date :' `date`
\echo ''
\echo '✨ Vous pouvez maintenant utiliser le système de réactivation automatique !'
\echo ''
\echo 'Commandes utiles :'
\echo '  - SELECT * FROM v_tasks_reactivable;'
\echo '  - SELECT * FROM v_workflow_reactivation_stats;'
\echo '  - SELECT * FROM v_reactivation_tree;'
\echo '  - SELECT * FROM get_workflow_reactivation_history(<task_id>);'
\echo ''
\echo '================================================================================'

