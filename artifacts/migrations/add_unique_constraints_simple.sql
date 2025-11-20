-- ============================================================================
-- MIGRATION : Contraintes d'unicité simplifiées
-- ============================================================================
-- Date : 2025-10-23
-- Description : Ajoute des contraintes d'unicité simples et fonctionnelles
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. INDEX UNIQUE POUR TASK_RUNS (RÉACTIVATIONS)
-- ============================================================================

-- Éviter les doublons de task_runs pour la même réactivation
CREATE UNIQUE INDEX IF NOT EXISTS unique_task_reactivation_run
ON task_runs(task_id, reactivation_count)
WHERE is_reactivation = TRUE AND task_id IS NOT NULL;

-- ============================================================================
-- 2. CONTRAINTE D'UNICITÉ POUR HUMAN_VALIDATIONS
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
        UNIQUE (task_run_id, validation_id);
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- VÉRIFICATION
-- ============================================================================

-- Vérifier les index créés
SELECT 
    indexname,
    tablename,
    indexdef
FROM pg_indexes 
WHERE indexname LIKE '%unique%reactivation%' 
   OR indexname LIKE '%unique%validation%';

-- Vérifier les contraintes créées
SELECT 
    conname as constraint_name,
    contype as constraint_type,
    pg_get_constraintdef(oid) as definition
FROM pg_constraint 
WHERE conname LIKE '%unique%validation%';
