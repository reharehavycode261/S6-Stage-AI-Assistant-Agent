-- ============================================================================
-- SCRIPT 05: Table de Logging des Réactivations de Workflow
-- ============================================================================
-- Description: Crée une table dédiée pour tracer toutes les réactivations
-- Exécution: Automatique au démarrage du container PostgreSQL
-- Ordre: 05-workflow-reactivations-table.sql
-- ============================================================================

\echo '=========================================='
\echo '📝 Création table workflow_reactivations'
\echo '=========================================='

-- ============================================================================
-- CRÉATION DE LA TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_reactivations (
    reactivation_id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(tasks_id) ON DELETE CASCADE,
    run_id BIGINT REFERENCES task_runs(tasks_runs_id) ON DELETE SET NULL,
    
    -- Informations de déclenchement
    trigger_type VARCHAR(50) NOT NULL,  -- 'update', 'manual', 'retry', etc.
    trigger_source VARCHAR(100),         -- 'monday.com', 'admin_panel', etc.
    triggered_by VARCHAR(255),           -- User ID ou process ID
    
    -- Données de l'update
    update_text TEXT,
    update_data JSONB,
    
    -- Analyse de la réactivation
    confidence_score DECIMAL(5,2),
    reasoning TEXT,
    
    -- Résultat de la réactivation
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    success BOOLEAN,
    error_message TEXT,
    
    -- Tâche Celery associée
    celery_task_id VARCHAR(255),
    celery_task_started_at TIMESTAMPTZ,
    
    -- Métriques
    duration_ms INTEGER,
    previous_tasks_revoked INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Contraintes
    CONSTRAINT workflow_reactivations_status_chk CHECK (
        status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')
    ),
    CONSTRAINT workflow_reactivations_trigger_type_chk CHECK (
        trigger_type IN ('update', 'manual', 'retry', 'scheduled', 'api', 'webhook')
    )
);

\echo '  ✅ Table workflow_reactivations créée'

-- ============================================================================
-- INDEX
-- ============================================================================

-- Index pour requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_task_id 
ON workflow_reactivations(task_id);

CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_run_id 
ON workflow_reactivations(run_id);

CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_status 
ON workflow_reactivations(status) 
WHERE status IN ('pending', 'processing');

CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_created_at 
ON workflow_reactivations(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_trigger_type 
ON workflow_reactivations(trigger_type);

CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_celery_task_id 
ON workflow_reactivations(celery_task_id) 
WHERE celery_task_id IS NOT NULL;

\echo '  ✅ Index créés'

-- ============================================================================
-- FONCTIONS UTILITAIRES
-- ============================================================================

-- Fonction pour obtenir les statistiques de réactivation d'une tâche
CREATE OR REPLACE FUNCTION get_task_reactivation_stats(p_task_id BIGINT)
RETURNS TABLE (
    total_reactivations BIGINT,
    successful_reactivations BIGINT,
    failed_reactivations BIGINT,
    avg_duration_ms NUMERIC,
    last_reactivation_at TIMESTAMPTZ,
    most_common_trigger VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_reactivations,
        COUNT(*) FILTER (WHERE success = TRUE) as successful_reactivations,
        COUNT(*) FILTER (WHERE success = FALSE) as failed_reactivations,
        AVG(duration_ms) as avg_duration_ms,
        MAX(created_at) as last_reactivation_at,
        (
            SELECT trigger_type 
            FROM workflow_reactivations 
            WHERE task_id = p_task_id 
            GROUP BY trigger_type 
            ORDER BY COUNT(*) DESC 
            LIMIT 1
        ) as most_common_trigger
    FROM workflow_reactivations
    WHERE task_id = p_task_id;
END;
$$ LANGUAGE plpgsql;

\echo '  ✅ Fonction get_task_reactivation_stats() créée'

-- Fonction pour nettoyer les anciennes réactivations
CREATE OR REPLACE FUNCTION cleanup_old_reactivations(retention_days INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM workflow_reactivations
    WHERE created_at < (NOW() - (retention_days || ' days')::INTERVAL)
      AND status IN ('completed', 'failed', 'cancelled');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

\echo '  ✅ Fonction cleanup_old_reactivations() créée'

-- ============================================================================
-- VUE POUR MONITORING
-- ============================================================================

CREATE OR REPLACE VIEW v_reactivation_history AS
SELECT 
    wr.reactivation_id,
    wr.task_id,
    t.title as task_title,
    t.monday_item_id,
    wr.trigger_type,
    wr.status,
    wr.success,
    wr.confidence_score,
    wr.created_at,
    wr.completed_at,
    wr.duration_ms,
    wr.error_message,
    wr.celery_task_id,
    t.reactivation_count as total_reactivations_count
FROM workflow_reactivations wr
JOIN tasks t ON wr.task_id = t.tasks_id
ORDER BY wr.created_at DESC;

\echo '  ✅ Vue v_reactivation_history créée'

-- Vue des réactivations récentes
CREATE OR REPLACE VIEW v_recent_reactivations AS
SELECT 
    wr.reactivation_id,
    wr.task_id,
    t.title,
    wr.trigger_type,
    wr.status,
    wr.created_at,
    wr.duration_ms,
    CASE 
        WHEN wr.status = 'pending' THEN 'En attente'
        WHEN wr.status = 'processing' THEN 'En cours'
        WHEN wr.status = 'completed' AND wr.success = TRUE THEN 'Réussi'
        WHEN wr.status = 'failed' OR wr.success = FALSE THEN 'Échoué'
        ELSE 'Inconnu'
    END as status_label
FROM workflow_reactivations wr
JOIN tasks t ON wr.task_id = t.tasks_id
WHERE wr.created_at > NOW() - INTERVAL '24 hours'
ORDER BY wr.created_at DESC;

\echo '  ✅ Vue v_recent_reactivations créée'

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Trigger pour calculer la durée
CREATE OR REPLACE FUNCTION update_reactivation_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_reactivation_duration ON workflow_reactivations;
CREATE TRIGGER trigger_update_reactivation_duration
    BEFORE UPDATE ON workflow_reactivations
    FOR EACH ROW
    WHEN (NEW.completed_at IS NOT NULL)
    EXECUTE FUNCTION update_reactivation_duration();

\echo '  ✅ Trigger duration créé'

-- ============================================================================
-- COMMENTAIRES
-- ============================================================================

COMMENT ON TABLE workflow_reactivations IS 'Historique complet des réactivations de workflows';
COMMENT ON COLUMN workflow_reactivations.confidence_score IS 'Score de confiance de l''analyse (0-100)';
COMMENT ON COLUMN workflow_reactivations.duration_ms IS 'Durée totale de la réactivation en millisecondes';
COMMENT ON COLUMN workflow_reactivations.previous_tasks_revoked IS 'Nombre de tâches Celery révoquées';

-- ============================================================================
-- VALIDATION
-- ============================================================================

\echo ''
\echo '🔍 Validation de la création'

DO $$
DECLARE
    table_exists boolean;
    index_count integer;
    function_count integer;
BEGIN
    -- Vérifier la table
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'workflow_reactivations'
    ) INTO table_exists;
    
    IF table_exists THEN
        RAISE NOTICE '  ✅ Table workflow_reactivations existe';
    ELSE
        RAISE EXCEPTION '  ❌ Table workflow_reactivations manquante';
    END IF;
    
    -- Vérifier les index
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'workflow_reactivations';
    
    RAISE NOTICE '  ✅ % index créés', index_count;
    
    -- Vérifier les fonctions
    SELECT COUNT(*) INTO function_count
    FROM pg_proc
    WHERE proname IN ('get_task_reactivation_stats', 'cleanup_old_reactivations');
    
    RAISE NOTICE '  ✅ % fonctions créées', function_count;
END $$;

\echo ''
\echo '=========================================='
\echo '✅ Table workflow_reactivations prête'
\echo '=========================================='
\echo ''

