-- ========================================================================
-- SCRIPT DE SUPPRESSION DES DONNÉES (PRÉSERVATION DES TABLES IA)
-- ========================================================================
-- Ce script supprime les données du workflow (tasks, runs, tests, etc.)
-- MAIS PRÉSERVE TOUTES les données IA pour l'analyse et le suivi:
--   • ai_interactions - Interactions avec les modèles IA
--   • ai_code_generations - Code généré par l'IA
--   • ai_usage_logs - Coûts et usage des APIs IA
--   • ai_cost_daily_summary - Vue des coûts quotidiens
--   • ai_cost_by_workflow - Vue des coûts par workflow
-- ========================================================================

DO $$ 
DECLARE
    ai_logs_count bigint;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '🗑️  SUPPRESSION DES DONNÉES DU WORKFLOW';
    RAISE NOTICE '📊 PRÉSERVATION DE TOUTES LES TABLES IA';
    RAISE NOTICE '========================================';
    
    -- 1. Supprimer les données des tables enfants d'abord (ordre hiérarchique)
    
    -- Tables enfants liées aux runs
    DELETE FROM run_steps;
    RAISE NOTICE '✅ run_steps supprimés';
    
    DELETE FROM test_results;
    RAISE NOTICE '✅ test_results supprimés';
    
    DELETE FROM pull_requests;
    RAISE NOTICE '✅ pull_requests supprimés';
    
    -- ⚠️  IMPORTANT: Ne PAS supprimer les tables AI
    -- - ai_interactions (PRÉSERVÉE)
    -- - ai_code_generations (PRÉSERVÉE)
    -- - ai_usage_logs (PRÉSERVÉE)
    
    -- Tables de runs et tasks
    DELETE FROM task_runs;
    RAISE NOTICE '✅ task_runs supprimés';
    
    -- ✅ Table de gestion de queue de workflows (dépend de tasks via FK)
    DELETE FROM workflow_queue;
    RAISE NOTICE '✅ workflow_queue supprimés';
    
    DELETE FROM tasks;
    RAISE NOTICE '✅ tasks supprimés';
    
    -- Tables de métriques (hors données AI)
    -- performance_metrics peut contenir total_ai_cost mais c'est un agrégat, pas le détail
    DELETE FROM performance_metrics;
    RAISE NOTICE '✅ performance_metrics supprimés';
    
    -- Tables système et événements
    DELETE FROM webhook_events;
    RAISE NOTICE '✅ webhook_events supprimés';
    
    DELETE FROM application_logs;
    RAISE NOTICE '✅ application_logs supprimés';
    
    DELETE FROM system_config;
    RAISE NOTICE '✅ system_config supprimés';
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ PRÉSERVATION DE TOUTES LES DONNÉES IA';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Les tables AI suivantes sont CONSERVÉES:';
    RAISE NOTICE '- ai_interactions (interactions IA)';
    RAISE NOTICE '- ai_code_generations (code généré par IA)';
    RAISE NOTICE '- ai_usage_logs (coûts et usage IA)';
    RAISE NOTICE '- ai_cost_daily_summary (vue des coûts)';
    RAISE NOTICE '- ai_cost_by_workflow (vue par workflow)';
    
    -- Compter les enregistrements AI préservés
    IF EXISTS (SELECT FROM information_schema.tables 
              WHERE table_schema = 'public' 
              AND table_name = 'ai_usage_logs') THEN
        SELECT COUNT(*) INTO ai_logs_count FROM ai_usage_logs;
        RAISE NOTICE '📊 ai_usage_logs: % enregistrements PRÉSERVÉS', ai_logs_count;
    ELSE
        RAISE NOTICE 'ℹ️  Table ai_usage_logs pas encore créée';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables 
              WHERE table_schema = 'public' 
              AND table_name = 'ai_interactions') THEN
        SELECT COUNT(*) INTO ai_logs_count FROM ai_interactions;
        RAISE NOTICE '📊 ai_interactions: % enregistrements PRÉSERVÉS', ai_logs_count;
    ELSE
        RAISE NOTICE 'ℹ️  Table ai_interactions pas encore créée';
    END IF;
    
    IF EXISTS (SELECT FROM information_schema.tables 
              WHERE table_schema = 'public' 
              AND table_name = 'ai_code_generations') THEN
        SELECT COUNT(*) INTO ai_logs_count FROM ai_code_generations;
        RAISE NOTICE '📊 ai_code_generations: % enregistrements PRÉSERVÉS', ai_logs_count;
    ELSE
        RAISE NOTICE 'ℹ️  Table ai_code_generations pas encore créée';
    END IF;
    
END $$;


-- ========================================================================
-- Vérification finale des suppressions
-- ========================================================================
DO $$ 
DECLARE
    table_name text;
    row_count bigint;
    total_cost numeric;
    total_calls bigint;
    provider_info text;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '📋 VÉRIFICATION DES TABLES SUPPRIMÉES';
    RAISE NOTICE '========================================';
    
    -- Vérifier chaque table une par une (SAUF les tables AI)
    FOR table_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename IN (
            'tasks', 'task_runs', 'run_steps',
            'test_results', 'pull_requests',
            'webhook_events', 'application_logs', 'performance_metrics',
            'system_config'
        )
        ORDER BY tablename
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %I', table_name) INTO row_count;
        
        IF row_count = 0 THEN
            RAISE NOTICE '✅ Table % : vide', table_name;
        ELSE
            RAISE WARNING '⚠️  Table % : % lignes restantes!', table_name, row_count;
        END IF;
    END LOOP;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '📊 VÉRIFICATION DES DONNÉES IA PRÉSERVÉES';
    RAISE NOTICE '========================================';
    
    -- 1. Vérifier ai_usage_logs
    IF EXISTS (SELECT FROM information_schema.tables 
              WHERE table_schema = 'public' 
              AND table_name = 'ai_usage_logs') THEN
        
        SELECT COUNT(*) INTO row_count FROM ai_usage_logs;
        RAISE NOTICE '✅ ai_usage_logs : % enregistrements PRÉSERVÉS', row_count;
        
        -- Calculer le coût total
        SELECT COALESCE(SUM(estimated_cost), 0), COUNT(*) 
        INTO total_cost, total_calls 
        FROM ai_usage_logs;
        
        IF total_calls > 0 THEN
            RAISE NOTICE '   📈 Coût total: $% (% appels)', ROUND(total_cost, 4), total_calls;
            
            -- Détails par provider
            FOR provider_info IN 
                SELECT '      - ' || provider || ': $' || 
                       ROUND(SUM(estimated_cost)::numeric, 4) || 
                       ' (' || COUNT(*) || ' appels)'
                FROM ai_usage_logs 
                GROUP BY provider
                ORDER BY SUM(estimated_cost) DESC
            LOOP
                RAISE NOTICE '%', provider_info;
            END LOOP;
        END IF;
    ELSE
        RAISE NOTICE 'ℹ️  ai_usage_logs pas encore créée';
    END IF;
    
    -- 2. Vérifier ai_interactions
    IF EXISTS (SELECT FROM information_schema.tables 
              WHERE table_schema = 'public' 
              AND table_name = 'ai_interactions') THEN
        SELECT COUNT(*) INTO row_count FROM ai_interactions;
        RAISE NOTICE '✅ ai_interactions : % enregistrements PRÉSERVÉS', row_count;
    ELSE
        RAISE NOTICE 'ℹ️  ai_interactions pas encore créée';
    END IF;
    
    -- 3. Vérifier ai_code_generations
    IF EXISTS (SELECT FROM information_schema.tables 
              WHERE table_schema = 'public' 
              AND table_name = 'ai_code_generations') THEN
        SELECT COUNT(*) INTO row_count FROM ai_code_generations;
        RAISE NOTICE '✅ ai_code_generations : % enregistrements PRÉSERVÉS', row_count;
    ELSE
        RAISE NOTICE 'ℹ️  ai_code_generations pas encore créée';
    END IF;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Suppression terminée avec succès!';
    RAISE NOTICE '📊 TOUTES les données IA préservées:';
    RAISE NOTICE '   - ai_interactions';
    RAISE NOTICE '   - ai_code_generations';
    RAISE NOTICE '   - ai_usage_logs';
    RAISE NOTICE '========================================';
END $$;