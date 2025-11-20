-- ========================================================================
-- SCRIPT DE SUPPRESSION DE TOUTES LES TABLES SAUF LE COÛT IA
-- ========================================================================
-- ⚠️  ATTENTION: Ce script SUPPRIME (DROP) toutes les tables et vues
-- SAUF celles liées au tracking des coûts IA
--
-- 📊 TABLES PRÉSERVÉES (Coût IA uniquement):
--   • ai_usage_logs
--   • ai_cost_tracking
--   • ai_interactions (si contient des données de coût)
--   • ai_code_generations (si contient des données de coût)
--   • ai_prompt_templates
--   • ai_prompt_usage
--
-- 📈 VUES PRÉSERVÉES (Analyse des coûts):
--   • ai_cost_daily_summary
--   • ai_cost_by_workflow
--   • mv_cost_analysis
--
-- 🗑️  TOUT LE RESTE EST SUPPRIMÉ
-- ========================================================================

DO $$ 
DECLARE
    v_table_name text;
    v_view_name text;
    v_count integer := 0;
    v_preserved_tables text[] := ARRAY[
        'ai_usage_logs',
        'ai_cost_tracking',
        'ai_interactions',
        'ai_code_generations',
        'ai_prompt_templates',
        'ai_prompt_usage'
    ];
    v_preserved_views text[] := ARRAY[
        'ai_cost_daily_summary',
        'ai_cost_by_workflow',
        'mv_cost_analysis'
    ];
BEGIN
    RAISE NOTICE '========================================================================';
    RAISE NOTICE '⚠️  SUPPRESSION DE TOUTES LES TABLES (SAUF COÛT IA)';
    RAISE NOTICE '========================================================================';
    RAISE NOTICE '';
    
    -- ============================================================
    -- ÉTAPE 1: SUPPRIMER TOUTES LES VUES (SAUF VUES DE COÛT IA)
    -- ============================================================
    RAISE NOTICE '📋 Suppression des vues...';
    RAISE NOTICE '────────────────────────────────────────────────────────────────────────';
    
    FOR v_view_name IN 
        SELECT table_name 
        FROM information_schema.views 
        WHERE table_schema = 'public'
        AND table_name != ALL(v_preserved_views)
        ORDER BY table_name
    LOOP
        EXECUTE format('DROP VIEW IF EXISTS %I CASCADE', v_view_name);
        RAISE NOTICE '  ✅ Vue supprimée: %', v_view_name;
        v_count := v_count + 1;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '📊 Total vues supprimées: %', v_count;
    RAISE NOTICE '';
    
    -- ============================================================
    -- ÉTAPE 2: SUPPRIMER TOUTES LES VUES MATÉRIALISÉES (SAUF COÛT IA)
    -- ============================================================
    v_count := 0;
    RAISE NOTICE '📋 Suppression des vues matérialisées...';
    RAISE NOTICE '────────────────────────────────────────────────────────────────────────';
    
    FOR v_view_name IN 
        SELECT matviewname 
        FROM pg_matviews 
        WHERE schemaname = 'public'
        AND matviewname != ALL(v_preserved_views)
        ORDER BY matviewname
    LOOP
        EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I CASCADE', v_view_name);
        RAISE NOTICE '  ✅ Vue matérialisée supprimée: %', v_view_name;
        v_count := v_count + 1;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '📊 Total vues matérialisées supprimées: %', v_count;
    RAISE NOTICE '';
    
    -- ============================================================
    -- ÉTAPE 3: SUPPRIMER TOUTES LES TABLES (SAUF TABLES COÛT IA)
    -- ============================================================
    v_count := 0;
    RAISE NOTICE '📋 Suppression des tables...';
    RAISE NOTICE '────────────────────────────────────────────────────────────────────────';
    
    -- Désactiver temporairement les contraintes de clés étrangères
    SET CONSTRAINTS ALL DEFERRED;
    
    FOR v_table_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename != ALL(v_preserved_tables)
        ORDER BY tablename
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', v_table_name);
        RAISE NOTICE '  ✅ Table supprimée: %', v_table_name;
        v_count := v_count + 1;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '📊 Total tables supprimées: %', v_count;
    RAISE NOTICE '';
    
    -- ============================================================
    -- ÉTAPE 4: VÉRIFICATION DES TABLES PRÉSERVÉES
    -- ============================================================
    RAISE NOTICE '========================================================================';
    RAISE NOTICE '✅ TABLES PRÉSERVÉES (Coût IA)';
    RAISE NOTICE '========================================================================';
    
    FOR v_table_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename = ANY(v_preserved_tables)
        ORDER BY tablename
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %I', v_table_name) INTO v_count;
        RAISE NOTICE '  📊 % : % enregistrements', v_table_name, v_count;
    END LOOP;
    
    RAISE NOTICE '';
    
    -- ============================================================
    -- ÉTAPE 5: VÉRIFICATION DES VUES PRÉSERVÉES
    -- ============================================================
    RAISE NOTICE '========================================================================';
    RAISE NOTICE '✅ VUES PRÉSERVÉES (Analyse des coûts)';
    RAISE NOTICE '========================================================================';
    
    FOR v_view_name IN 
        SELECT table_name 
        FROM information_schema.views 
        WHERE table_schema = 'public'
        AND table_name = ANY(v_preserved_views)
        ORDER BY table_name
    LOOP
        RAISE NOTICE '  📈 Vue préservée: %', v_view_name;
    END LOOP;
    
    FOR v_view_name IN 
        SELECT matviewname 
        FROM pg_matviews 
        WHERE schemaname = 'public'
        AND matviewname = ANY(v_preserved_views)
        ORDER BY matviewname
    LOOP
        RAISE NOTICE '  📈 Vue matérialisée préservée: %', v_view_name;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================================================';
    RAISE NOTICE '✅ SUPPRESSION TERMINÉE AVEC SUCCÈS';
    RAISE NOTICE '========================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Toutes les tables ont été supprimées SAUF:';
    RAISE NOTICE '   • ai_usage_logs';
    RAISE NOTICE '   • ai_cost_tracking';
    RAISE NOTICE '   • ai_interactions';
    RAISE NOTICE '   • ai_code_generations';
    RAISE NOTICE '   • ai_prompt_templates';
    RAISE NOTICE '   • ai_prompt_usage';
    RAISE NOTICE '';
    RAISE NOTICE '📈 Vues d''analyse préservées:';
    RAISE NOTICE '   • ai_cost_daily_summary';
    RAISE NOTICE '   • ai_cost_by_workflow';
    RAISE NOTICE '   • mv_cost_analysis';
    RAISE NOTICE '';
    RAISE NOTICE '⚠️  IMPORTANT: Vous devez recréer la structure de base avec base2.sql';
    RAISE NOTICE '   si vous voulez réutiliser l''application.';
    RAISE NOTICE '========================================================================';
    
END $$;


-- ========================================================================
-- VÉRIFICATION FINALE - Liste des tables restantes
-- ========================================================================
DO $$ 
DECLARE
    v_table_name text;
    v_row_count bigint;
    v_total_cost numeric;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================================================';
    RAISE NOTICE '📋 INVENTAIRE FINAL DES TABLES';
    RAISE NOTICE '========================================================================';
    
    FOR v_table_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %I', v_table_name) INTO v_row_count;
        RAISE NOTICE '  📊 % : % enregistrements', v_table_name, v_row_count;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================================================';
    RAISE NOTICE '💰 RÉSUMÉ DES COÛTS IA PRÉSERVÉS';
    RAISE NOTICE '========================================================================';
    
    -- Calculer le coût total si ai_usage_logs existe
    IF EXISTS (SELECT FROM information_schema.tables 
               WHERE table_schema = 'public' 
               AND table_name = 'ai_usage_logs') THEN
        
        SELECT COALESCE(SUM(estimated_cost), 0) INTO v_total_cost FROM ai_usage_logs;
        RAISE NOTICE '  💵 Coût total enregistré: $%', ROUND(v_total_cost, 4);
        
        -- Détails par provider
        FOR v_table_name IN 
            SELECT '     • ' || provider || ': $' || 
                   ROUND(SUM(estimated_cost)::numeric, 4) || 
                   ' (' || COUNT(*) || ' appels)'
            FROM ai_usage_logs 
            GROUP BY provider
            ORDER BY SUM(estimated_cost) DESC
        LOOP
            RAISE NOTICE '%', v_table_name;
        END LOOP;
    END IF;
    
    -- Vérifier ai_cost_tracking si elle existe
    IF EXISTS (SELECT FROM information_schema.tables 
               WHERE table_schema = 'public' 
               AND table_name = 'ai_cost_tracking') THEN
        
        SELECT COALESCE(SUM(cost_usd), 0) INTO v_total_cost FROM ai_cost_tracking;
        RAISE NOTICE '';
        RAISE NOTICE '  💵 Coût total (ai_cost_tracking): $%', ROUND(v_total_cost, 4);
        
        -- Détails par provider
        FOR v_table_name IN 
            SELECT '     • ' || provider || ': $' || 
                   ROUND(SUM(cost_usd)::numeric, 4) || 
                   ' (' || COUNT(*) || ' appels)'
            FROM ai_cost_tracking 
            GROUP BY provider
            ORDER BY SUM(cost_usd) DESC
        LOOP
            RAISE NOTICE '%', v_table_name;
        END LOOP;
    END IF;
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================================================';
    RAISE NOTICE '✅ VÉRIFICATION TERMINÉE';
    RAISE NOTICE '========================================================================';
    
END $$;

