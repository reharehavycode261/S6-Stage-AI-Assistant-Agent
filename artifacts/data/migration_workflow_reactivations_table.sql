-- ============================================================================
-- MIGRATION : Ajout de la table workflow_reactivations
-- ============================================================================
-- Date : 2025-10-21
-- Description : Création de la table pour enregistrer les réactivations de workflow
--               avec suivi du statut et des erreurs
-- ============================================================================

-- ============================================================================
-- CRÉATION DE LA TABLE workflow_reactivations
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_reactivations (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL,
    reactivated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    trigger_type VARCHAR(50) NOT NULL CHECK (trigger_type IN ('update', 'manual', 'automatic')),
    update_data JSONB,
    task_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Clé étrangère vers la table tasks
    CONSTRAINT fk_workflow_reactivations_workflow 
        FOREIGN KEY (workflow_id) 
        REFERENCES tasks(tasks_id) 
        ON DELETE CASCADE
);

-- ============================================================================
-- INDEX POUR OPTIMISER LES REQUÊTES
-- ============================================================================

-- Index sur workflow_id pour les jointures
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_workflow_id 
    ON workflow_reactivations(workflow_id);

-- Index sur status pour filtrer rapidement les réactivations par statut
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_status 
    ON workflow_reactivations(status);

-- Index sur trigger_type pour analyser les types de déclencheurs
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_trigger_type 
    ON workflow_reactivations(trigger_type);

-- Index composite pour les requêtes courantes (workflow + statut)
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_workflow_status 
    ON workflow_reactivations(workflow_id, status);

-- Index sur reactivated_at pour les requêtes temporelles
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_reactivated_at 
    ON workflow_reactivations(reactivated_at DESC);

-- Index GIN sur update_data pour recherches JSON
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_update_data 
    ON workflow_reactivations USING GIN (update_data);

-- ============================================================================
-- COMMENTAIRES DE DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE workflow_reactivations IS 
    'Table d''enregistrement des réactivations de workflow pour suivi et audit';

COMMENT ON COLUMN workflow_reactivations.id IS 
    'Identifiant unique de la réactivation';

COMMENT ON COLUMN workflow_reactivations.workflow_id IS 
    'ID du workflow/tâche réactivé (référence à tasks.tasks_id)';

COMMENT ON COLUMN workflow_reactivations.reactivated_at IS 
    'Date et heure de la réactivation';

COMMENT ON COLUMN workflow_reactivations.trigger_type IS 
    'Type de déclencheur de la réactivation (update, manual, automatic)';

COMMENT ON COLUMN workflow_reactivations.update_data IS 
    'Données de l''update Monday.com ou contexte de la réactivation (JSON)';

COMMENT ON COLUMN workflow_reactivations.task_id IS 
    'ID de la tâche Celery lancée pour cette réactivation';

COMMENT ON COLUMN workflow_reactivations.status IS 
    'Statut de la réactivation (pending, processing, completed, failed)';

COMMENT ON COLUMN workflow_reactivations.error_message IS 
    'Message d''erreur en cas d''échec de la réactivation';

COMMENT ON COLUMN workflow_reactivations.completed_at IS 
    'Date de complétion (succès ou échec) de la réactivation';

-- ============================================================================
-- TRIGGER POUR METTRE À JOUR updated_at AUTOMATIQUEMENT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_workflow_reactivations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_workflow_reactivations_updated_at ON workflow_reactivations;

CREATE TRIGGER trigger_workflow_reactivations_updated_at
    BEFORE UPDATE ON workflow_reactivations
    FOR EACH ROW
    EXECUTE FUNCTION update_workflow_reactivations_updated_at();

COMMENT ON FUNCTION update_workflow_reactivations_updated_at() IS 
    'Met à jour automatiquement le champ updated_at lors de chaque modification';

-- ============================================================================
-- VUES UTILITAIRES
-- ============================================================================

-- Vue pour les statistiques de réactivation par workflow
CREATE OR REPLACE VIEW v_workflow_reactivation_stats AS
SELECT 
    wr.workflow_id,
    t.title AS task_title,
    t.internal_status AS current_status,
    COUNT(*) AS total_reactivations,
    COUNT(*) FILTER (WHERE wr.status = 'completed') AS successful_reactivations,
    COUNT(*) FILTER (WHERE wr.status = 'failed') AS failed_reactivations,
    COUNT(*) FILTER (WHERE wr.status IN ('pending', 'processing')) AS ongoing_reactivations,
    MAX(wr.reactivated_at) AS last_reactivation_at,
    AVG(EXTRACT(EPOCH FROM (wr.completed_at - wr.reactivated_at))) FILTER (WHERE wr.completed_at IS NOT NULL) AS avg_duration_seconds
FROM workflow_reactivations wr
JOIN tasks t ON wr.workflow_id = t.tasks_id
GROUP BY wr.workflow_id, t.title, t.internal_status;

COMMENT ON VIEW v_workflow_reactivation_stats IS 
    'Statistiques de réactivation par workflow avec taux de succès et durées moyennes';

-- Vue pour les réactivations récentes (dernières 24h)
CREATE OR REPLACE VIEW v_recent_reactivations AS
SELECT 
    wr.id,
    wr.workflow_id,
    t.title AS task_title,
    wr.trigger_type,
    wr.status,
    wr.reactivated_at,
    wr.completed_at,
    EXTRACT(EPOCH FROM (COALESCE(wr.completed_at, NOW()) - wr.reactivated_at))::INTEGER AS duration_seconds,
    wr.error_message
FROM workflow_reactivations wr
JOIN tasks t ON wr.workflow_id = t.tasks_id
WHERE wr.reactivated_at >= NOW() - INTERVAL '24 hours'
ORDER BY wr.reactivated_at DESC;

COMMENT ON VIEW v_recent_reactivations IS 
    'Liste des réactivations des dernières 24 heures avec durées et statuts';

-- ============================================================================
-- VALIDATION DE LA MIGRATION
-- ============================================================================

DO $$
DECLARE
    table_exists BOOLEAN;
    missing_columns TEXT[];
BEGIN
    -- Vérifier que la table existe
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'workflow_reactivations'
    ) INTO table_exists;
    
    IF NOT table_exists THEN
        RAISE EXCEPTION 'Table workflow_reactivations non créée';
    END IF;
    
    -- Vérifier que toutes les colonnes essentielles existent
    SELECT array_agg(column_name)
    INTO missing_columns
    FROM (VALUES 
        ('id'),
        ('workflow_id'),
        ('reactivated_at'),
        ('trigger_type'),
        ('update_data'),
        ('task_id'),
        ('status'),
        ('error_message'),
        ('completed_at')
    ) AS expected(column_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'workflow_reactivations' 
        AND column_name = expected.column_name
    );
    
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE EXCEPTION 'Colonnes manquantes dans workflow_reactivations: %', 
            array_to_string(missing_columns, ', ');
    END IF;
    
    -- Vérifier que les index sont créés
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'workflow_reactivations' 
        AND indexname = 'idx_workflow_reactivations_workflow_id'
    ) THEN
        RAISE EXCEPTION 'Index idx_workflow_reactivations_workflow_id manquant';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'workflow_reactivations' 
        AND indexname = 'idx_workflow_reactivations_status'
    ) THEN
        RAISE EXCEPTION 'Index idx_workflow_reactivations_status manquant';
    END IF;
    
    RAISE NOTICE '✅ Migration validée : Table workflow_reactivations créée avec succès';
    RAISE NOTICE '   - Table: workflow_reactivations';
    RAISE NOTICE '   - Colonnes: 11 colonnes créées';
    RAISE NOTICE '   - Index: 6 index créés';
    RAISE NOTICE '   - Vues: 2 vues utilitaires créées';
    RAISE NOTICE '   - Triggers: 1 trigger de mise à jour automatique';
END $$;

-- ============================================================================
-- FIN DE LA MIGRATION
-- ============================================================================

