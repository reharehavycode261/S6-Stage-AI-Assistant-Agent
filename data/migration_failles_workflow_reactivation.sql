-- ============================================================================
-- MIGRATION : Correction des 3 Failles de Réactivation Workflow
-- ============================================================================
-- Date : 2025-10-21
-- Description : Ajout des champs pour gérer :
--   - Faille #1 : Gestion incohérente des états (verrouillage)
--   - Faille #2 : Duplication des tâches Celery
--   - Faille #3 : Cascade de réactivations (cooldown)
-- ============================================================================

-- ============================================================================
-- FAILLE #1 : Gestion Incohérente des États du Workflow
-- ============================================================================

-- Ajout des champs de réactivation et verrouillage à la table tasks
ALTER TABLE tasks 
ADD COLUMN IF NOT EXISTS reactivated_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reactivation_count INTEGER DEFAULT 0 NOT NULL,
ADD COLUMN IF NOT EXISTS previous_status VARCHAR(50),
ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS locked_by VARCHAR(255);

-- Créer un index pour les requêtes de verrouillage
CREATE INDEX IF NOT EXISTS idx_tasks_is_locked ON tasks(is_locked) WHERE is_locked = TRUE;
CREATE INDEX IF NOT EXISTS idx_tasks_reactivation ON tasks(reactivation_count) WHERE reactivation_count > 0;

COMMENT ON COLUMN tasks.reactivated_at IS 'Date de la dernière réactivation de la tâche';
COMMENT ON COLUMN tasks.reactivation_count IS 'Nombre de fois que la tâche a été réactivée';
COMMENT ON COLUMN tasks.previous_status IS 'Statut précédent avant réactivation';
COMMENT ON COLUMN tasks.is_locked IS 'Indique si la tâche est verrouillée pour éviter les modifications concurrentes';
COMMENT ON COLUMN tasks.locked_at IS 'Date du verrouillage';
COMMENT ON COLUMN tasks.locked_by IS 'Identifiant du processus/tâche qui a verrouillé (ex: celery_task_id)';

-- ============================================================================
-- FAILLE #2 : Duplication des Tâches Celery
-- ============================================================================

-- Ajout des champs de suivi des tâches Celery actives
ALTER TABLE task_runs
ADD COLUMN IF NOT EXISTS active_task_ids JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS last_task_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS task_started_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS is_reactivation BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS last_merged_pr_url VARCHAR(500);

-- Index pour les recherches de tâches actives
CREATE INDEX IF NOT EXISTS idx_task_runs_active_tasks ON task_runs USING GIN (active_task_ids) WHERE jsonb_array_length(active_task_ids) > 0;
CREATE INDEX IF NOT EXISTS idx_task_runs_is_reactivation ON task_runs(is_reactivation) WHERE is_reactivation = TRUE;

COMMENT ON COLUMN task_runs.active_task_ids IS 'Liste des IDs de tâches Celery actives (array JSON)';
COMMENT ON COLUMN task_runs.last_task_id IS 'ID de la dernière tâche Celery lancée';
COMMENT ON COLUMN task_runs.task_started_at IS 'Date de démarrage de la dernière tâche Celery';
COMMENT ON COLUMN task_runs.is_reactivation IS 'Indique si ce run est une réactivation';
COMMENT ON COLUMN task_runs.last_merged_pr_url IS 'URL de la dernière PR fusionnée (pour résolution repository)';

-- ============================================================================
-- FAILLE #3 : Cascade de Réactivations (Cooldown)
-- ============================================================================

-- Ajout des champs de cooldown à la table tasks
ALTER TABLE tasks
ADD COLUMN IF NOT EXISTS last_reactivation_attempt TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS cooldown_until TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS failed_reactivation_attempts INTEGER DEFAULT 0 NOT NULL;

-- Index pour les requêtes de cooldown
CREATE INDEX IF NOT EXISTS idx_tasks_cooldown ON tasks(cooldown_until) WHERE cooldown_until IS NOT NULL AND cooldown_until > NOW();
CREATE INDEX IF NOT EXISTS idx_tasks_failed_attempts ON tasks(failed_reactivation_attempts) WHERE failed_reactivation_attempts > 0;

COMMENT ON COLUMN tasks.last_reactivation_attempt IS 'Date de la dernière tentative de réactivation';
COMMENT ON COLUMN tasks.cooldown_until IS 'Date de fin du cooldown (pendant cette période, pas de réactivation)';
COMMENT ON COLUMN tasks.failed_reactivation_attempts IS 'Nombre de tentatives de réactivation échouées consécutives';

-- ============================================================================
-- FONCTIONS UTILITAIRES
-- ============================================================================

-- Fonction pour nettoyer automatiquement les verrous expirés (> 30 minutes)
CREATE OR REPLACE FUNCTION clean_expired_locks() 
RETURNS INTEGER AS $$
DECLARE
    cleaned_count INTEGER;
BEGIN
    UPDATE tasks
    SET is_locked = FALSE,
        locked_at = NULL,
        locked_by = NULL
    WHERE is_locked = TRUE 
      AND locked_at < (NOW() - INTERVAL '30 minutes');
    
    GET DIAGNOSTICS cleaned_count = ROW_COUNT;
    
    RETURN cleaned_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION clean_expired_locks() IS 'Nettoie automatiquement les verrous de tâches expirés (plus de 30 minutes)';

-- Fonction pour réinitialiser le compteur d'échecs après succès
CREATE OR REPLACE FUNCTION reset_failed_attempts_on_success()
RETURNS TRIGGER AS $$
BEGIN
    -- Si le statut passe à 'completed', réinitialiser les échecs
    IF NEW.internal_status = 'completed' AND OLD.internal_status != 'completed' THEN
        NEW.failed_reactivation_attempts = 0;
        NEW.cooldown_until = NULL;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour réinitialiser automatiquement les échecs
DROP TRIGGER IF EXISTS trigger_reset_failed_attempts ON tasks;
CREATE TRIGGER trigger_reset_failed_attempts
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    WHEN (NEW.internal_status = 'completed')
    EXECUTE FUNCTION reset_failed_attempts_on_success();

COMMENT ON FUNCTION reset_failed_attempts_on_success() IS 'Réinitialise le compteur d\'échecs de réactivation quand une tâche se termine avec succès';

-- ============================================================================
-- VUES UTILITAIRES
-- ============================================================================

-- Vue pour identifier les tâches réactivables (ni en cooldown, ni verrouillées)
CREATE OR REPLACE VIEW v_tasks_reactivable AS
SELECT 
    t.tasks_id,
    t.title,
    t.internal_status,
    t.reactivation_count,
    t.is_locked,
    t.cooldown_until,
    t.failed_reactivation_attempts,
    CASE 
        WHEN t.is_locked THEN 'LOCKED'
        WHEN t.cooldown_until > NOW() THEN 'COOLDOWN'
        WHEN t.internal_status IN ('processing', 'pending') THEN 'ALREADY_ACTIVE'
        WHEN t.reactivation_count >= 5 THEN 'MAX_REACTIVATIONS'
        ELSE 'REACTIVABLE'
    END AS reactivation_status,
    CASE 
        WHEN t.cooldown_until > NOW() THEN 
            EXTRACT(EPOCH FROM (t.cooldown_until - NOW()))::INTEGER
        ELSE 0
    END AS cooldown_remaining_seconds
FROM tasks t
WHERE t.internal_status IN ('completed', 'failed');

COMMENT ON VIEW v_tasks_reactivable IS 'Vue des tâches potentiellement réactivables avec leur statut de réactivation';

-- Vue pour surveiller les tâches Celery actives
CREATE OR REPLACE VIEW v_active_celery_tasks AS
SELECT 
    tr.tasks_runs_id,
    tr.task_id,
    tr.celery_task_id,
    tr.active_task_ids,
    jsonb_array_length(tr.active_task_ids) AS active_tasks_count,
    tr.last_task_id,
    tr.task_started_at,
    tr.status,
    tr.is_reactivation,
    t.title AS task_title,
    t.is_locked,
    t.locked_by
FROM task_runs tr
JOIN tasks t ON tr.task_id = t.tasks_id
WHERE jsonb_array_length(tr.active_task_ids) > 0
   OR tr.status IN ('started', 'running');

COMMENT ON VIEW v_active_celery_tasks IS 'Vue de surveillance des tâches Celery actives avec détection des doublons potentiels';

-- ============================================================================
-- STATISTIQUES ET MONITORING
-- ============================================================================

-- Vue pour les statistiques de réactivation
CREATE OR REPLACE VIEW v_reactivation_stats AS
SELECT 
    COUNT(*) AS total_tasks,
    COUNT(*) FILTER (WHERE reactivation_count > 0) AS reactivated_tasks,
    COUNT(*) FILTER (WHERE is_locked = TRUE) AS locked_tasks,
    COUNT(*) FILTER (WHERE cooldown_until > NOW()) AS tasks_in_cooldown,
    COUNT(*) FILTER (WHERE failed_reactivation_attempts > 0) AS tasks_with_failures,
    AVG(reactivation_count) FILTER (WHERE reactivation_count > 0) AS avg_reactivations,
    MAX(reactivation_count) AS max_reactivations,
    COUNT(*) FILTER (WHERE reactivation_count >= 5) AS max_reactivations_reached
FROM tasks;

COMMENT ON VIEW v_reactivation_stats IS 'Statistiques globales sur les réactivations et les mécanismes de protection';

-- ============================================================================
-- DONNÉES DE TEST (Optionnel - à retirer en production)
-- ============================================================================

-- Initialiser les nouvelles colonnes pour les tâches existantes
UPDATE tasks 
SET 
    reactivation_count = COALESCE(reactivation_count, 0),
    is_locked = COALESCE(is_locked, FALSE),
    failed_reactivation_attempts = COALESCE(failed_reactivation_attempts, 0)
WHERE reactivation_count IS NULL 
   OR is_locked IS NULL 
   OR failed_reactivation_attempts IS NULL;

UPDATE task_runs
SET 
    active_task_ids = COALESCE(active_task_ids, '[]'::jsonb),
    is_reactivation = COALESCE(is_reactivation, FALSE)
WHERE active_task_ids IS NULL 
   OR is_reactivation IS NULL;

-- ============================================================================
-- VALIDATION DE LA MIGRATION
-- ============================================================================

-- Vérifier que tous les champs ont été ajoutés
DO $$
DECLARE
    missing_columns TEXT[];
BEGIN
    -- Vérifier les colonnes de tasks
    SELECT array_agg(column_name)
    INTO missing_columns
    FROM (VALUES 
        ('reactivated_at'), 
        ('reactivation_count'), 
        ('previous_status'),
        ('is_locked'),
        ('locked_at'),
        ('locked_by'),
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
        RAISE EXCEPTION 'Colonnes manquantes dans tasks: %', array_to_string(missing_columns, ', ');
    END IF;
    
    -- Vérifier les colonnes de task_runs
    SELECT array_agg(column_name)
    INTO missing_columns
    FROM (VALUES 
        ('active_task_ids'),
        ('last_task_id'),
        ('task_started_at'),
        ('is_reactivation'),
        ('last_merged_pr_url')
    ) AS expected(column_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'task_runs' 
        AND column_name = expected.column_name
    );
    
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE EXCEPTION 'Colonnes manquantes dans task_runs: %', array_to_string(missing_columns, ', ');
    END IF;
    
    RAISE NOTICE '✅ Migration validée : Tous les champs ont été ajoutés avec succès';
END $$;

-- ============================================================================
-- FIN DE LA MIGRATION
-- ============================================================================

