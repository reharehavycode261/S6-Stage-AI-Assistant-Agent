-- ============================================================================
-- MIGRATION : Ajout contraintes d'unicité pour éviter les doublons
-- ============================================================================
-- Date : 2025-10-23
-- Description : Ajoute des contraintes d'unicité pour éviter les doublons
--               "Réactivation enregistrée" et "another operation is in progress"
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CONTRAINTE D'UNICITÉ POUR WORKFLOW_REACTIVATIONS
-- ============================================================================

-- Éviter les doublons de réactivation pour la même tâche au même moment
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'unique_workflow_reactivation_per_task'
    ) THEN
        -- Créer un index unique simple pour éviter les doublons exacts
        CREATE UNIQUE INDEX unique_workflow_reactivation_per_task
        ON workflow_reactivations (workflow_id, trigger_type, reactivated_at);
    END IF;
END $$;

-- Index pour optimiser les requêtes avec cette contrainte
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_unique_check
ON workflow_reactivations(workflow_id, trigger_type, DATE_TRUNC('minute', reactivated_at));

-- ============================================================================
-- 2. CONTRAINTE D'UNICITÉ POUR TASK_RUNS (RÉACTIVATIONS)
-- ============================================================================

-- Éviter les doublons de task_runs pour la même réactivation
-- (Un seul run par task_id + reactivation_count)
CREATE UNIQUE INDEX IF NOT EXISTS unique_task_reactivation_run
ON task_runs(task_id, reactivation_count)
WHERE is_reactivation = TRUE AND task_id IS NOT NULL;

-- ============================================================================
-- 3. CONTRAINTE D'UNICITÉ POUR HUMAN_VALIDATIONS
-- ============================================================================

-- Éviter les doublons de validation pour le même run
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'unique_validation_per_run'
    ) THEN
        ALTER TABLE human_validations
        ADD CONSTRAINT unique_validation_per_run
        UNIQUE (task_run_id, validation_type);
    END IF;
END $$;

-- ============================================================================
-- COMMENTAIRES DE DOCUMENTATION
-- ============================================================================

COMMENT ON CONSTRAINT unique_workflow_reactivation_per_task_and_time ON workflow_reactivations IS 
    'Évite les doublons de réactivation pour la même tâche dans la même minute';

COMMENT ON INDEX unique_task_reactivation_run IS 
    'Évite les doublons de task_runs pour la même réactivation (task_id + reactivation_count)';

COMMENT ON CONSTRAINT unique_validation_per_run ON human_validations IS 
    'Évite les doublons de validation pour le même run et type';

COMMIT;

-- ============================================================================
-- VÉRIFICATION
-- ============================================================================

-- Vérifier les contraintes créées
SELECT 
    conname as constraint_name,
    contype as constraint_type,
    pg_get_constraintdef(oid) as definition
FROM pg_constraint 
WHERE conname LIKE '%unique%reactivation%' 
   OR conname LIKE '%unique%validation%';

-- Vérifier les index créés
SELECT 
    indexname,
    tablename,
    indexdef
FROM pg_indexes 
WHERE indexname LIKE '%unique%reactivation%' 
   OR indexname LIKE '%unique%validation%';
