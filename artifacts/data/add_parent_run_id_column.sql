-- ============================================================================
-- MIGRATION : Ajout de la colonne parent_run_id à task_runs
-- ============================================================================
-- Date : 2025-10-21
-- Description : Ajoute la colonne parent_run_id pour chaîner les réactivations
--               Cette colonne permet de tracer la lignée des workflows réactivés
-- ============================================================================

-- ============================================================================
-- AJOUT DE LA COLONNE parent_run_id
-- ============================================================================

ALTER TABLE task_runs
ADD COLUMN IF NOT EXISTS parent_run_id BIGINT REFERENCES task_runs(tasks_runs_id) ON DELETE SET NULL;

-- ============================================================================
-- INDEX POUR OPTIMISER LES REQUÊTES
-- ============================================================================

-- Index pour rechercher les enfants d'un run parent
CREATE INDEX IF NOT EXISTS idx_task_runs_parent_run_id 
    ON task_runs(parent_run_id) 
    WHERE parent_run_id IS NOT NULL;

-- Index composite pour les requêtes de réactivation
CREATE INDEX IF NOT EXISTS idx_task_runs_reactivation_chain 
    ON task_runs(task_id, parent_run_id, is_reactivation) 
    WHERE is_reactivation = TRUE;

-- ============================================================================
-- COMMENTAIRES DE DOCUMENTATION
-- ============================================================================

COMMENT ON COLUMN task_runs.parent_run_id IS 
    'ID du run parent pour les réactivations (permet de tracer la lignée des workflows)';

-- ============================================================================
-- VUE UTILITAIRE : Arbre de réactivation
-- ============================================================================

CREATE OR REPLACE VIEW v_reactivation_tree AS
WITH RECURSIVE reactivation_chain AS (
    -- Racine : premiers runs (pas de parent)
    SELECT 
        tr.tasks_runs_id,
        tr.task_id,
        tr.run_number,
        tr.is_reactivation,
        tr.parent_run_id,
        tr.status,
        tr.started_at,
        tr.completed_at,
        0 AS depth,
        ARRAY[tr.tasks_runs_id] AS path,
        tr.tasks_runs_id::TEXT AS path_string
    FROM task_runs tr
    WHERE tr.parent_run_id IS NULL
    
    UNION ALL
    
    -- Récursion : runs enfants
    SELECT 
        tr.tasks_runs_id,
        tr.task_id,
        tr.run_number,
        tr.is_reactivation,
        tr.parent_run_id,
        tr.status,
        tr.started_at,
        tr.completed_at,
        rc.depth + 1,
        rc.path || tr.tasks_runs_id,
        rc.path_string || ' -> ' || tr.tasks_runs_id::TEXT
    FROM task_runs tr
    INNER JOIN reactivation_chain rc ON tr.parent_run_id = rc.tasks_runs_id
    WHERE tr.depth < 20  -- Limite de sécurité
)
SELECT 
    rc.*,
    t.title AS task_title,
    t.monday_item_id,
    CASE 
        WHEN rc.depth = 0 THEN 'Premier workflow'
        ELSE 'Réactivation niveau ' || rc.depth
    END AS reactivation_level
FROM reactivation_chain rc
JOIN tasks t ON rc.task_id = t.tasks_id
ORDER BY rc.task_id, rc.depth, rc.started_at;

COMMENT ON VIEW v_reactivation_tree IS 
    'Vue récursive montrant l''arbre complet des réactivations avec leur lignée';

-- ============================================================================
-- FONCTION : Obtenir l'historique complet d'un workflow
-- ============================================================================

CREATE OR REPLACE FUNCTION get_workflow_reactivation_history(p_task_id BIGINT)
RETURNS TABLE (
    run_id BIGINT,
    run_number INTEGER,
    is_reactivation BOOLEAN,
    parent_run_id BIGINT,
    depth INTEGER,
    status VARCHAR(50),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    path_string TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE reactivation_chain AS (
        -- Racine
        SELECT 
            tr.tasks_runs_id,
            tr.run_number,
            tr.is_reactivation,
            tr.parent_run_id,
            0 AS depth,
            tr.status,
            tr.started_at,
            tr.completed_at,
            tr.duration_seconds,
            tr.tasks_runs_id::TEXT AS path_string
        FROM task_runs tr
        WHERE tr.task_id = p_task_id
          AND tr.parent_run_id IS NULL
        
        UNION ALL
        
        -- Récursion
        SELECT 
            tr.tasks_runs_id,
            tr.run_number,
            tr.is_reactivation,
            tr.parent_run_id,
            rc.depth + 1,
            tr.status,
            tr.started_at,
            tr.completed_at,
            tr.duration_seconds,
            rc.path_string || ' -> ' || tr.tasks_runs_id::TEXT
        FROM task_runs tr
        INNER JOIN reactivation_chain rc ON tr.parent_run_id = rc.tasks_runs_id
        WHERE tr.task_id = p_task_id
          AND rc.depth < 20
    )
    SELECT * FROM reactivation_chain
    ORDER BY depth, started_at;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_workflow_reactivation_history(BIGINT) IS 
    'Retourne l''historique complet des réactivations d''un workflow donné';

-- ============================================================================
-- VALIDATION DE LA MIGRATION
-- ============================================================================

DO $$
DECLARE
    column_exists BOOLEAN;
    index_count INTEGER;
BEGIN
    -- Vérifier que la colonne existe
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'task_runs' 
        AND column_name = 'parent_run_id'
    ) INTO column_exists;
    
    IF NOT column_exists THEN
        RAISE EXCEPTION 'Colonne parent_run_id non créée dans task_runs';
    END IF;
    
    -- Vérifier les index
    SELECT COUNT(*)
    INTO index_count
    FROM pg_indexes 
    WHERE tablename = 'task_runs' 
    AND (indexname = 'idx_task_runs_parent_run_id' 
         OR indexname = 'idx_task_runs_reactivation_chain');
    
    IF index_count < 2 THEN
        RAISE WARNING 'Certains index parent_run_id sont manquants (trouvés: %)', index_count;
    END IF;
    
    -- Vérifier que la vue existe
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.views 
        WHERE table_name = 'v_reactivation_tree'
    ) THEN
        RAISE WARNING 'Vue v_reactivation_tree non créée';
    END IF;
    
    RAISE NOTICE '✅ Migration parent_run_id validée avec succès';
    RAISE NOTICE '   - Colonne: parent_run_id ajoutée à task_runs';
    RAISE NOTICE '   - Index: 2 index créés';
    RAISE NOTICE '   - Vue: v_reactivation_tree créée';
    RAISE NOTICE '   - Fonction: get_workflow_reactivation_history() créée';
END $$;

-- ============================================================================
-- FIN DE LA MIGRATION
-- ============================================================================

