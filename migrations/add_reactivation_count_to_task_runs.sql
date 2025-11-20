-- Migration: Ajouter reactivation_count à task_runs
-- Date: 2025-10-23
-- Description: Ajoute la colonne reactivation_count pour tracking des réactivations

BEGIN;

-- Ajouter la colonne reactivation_count
ALTER TABLE task_runs 
ADD COLUMN IF NOT EXISTS reactivation_count INTEGER NOT NULL DEFAULT 0;

-- Créer un index pour les performances
CREATE INDEX IF NOT EXISTS idx_task_runs_reactivation_count 
ON task_runs(reactivation_count) 
WHERE reactivation_count > 0;

-- Mettre à jour les réactivations existantes en calculant depuis parent_run_id chain
WITH RECURSIVE reactivation_chain AS (
    -- Base: runs sans parent (première exécution)
    SELECT 
        tasks_runs_id,
        task_id,
        parent_run_id,
        is_reactivation,
        0 as reactivation_count
    FROM task_runs
    WHERE parent_run_id IS NULL
    
    UNION ALL
    
    -- Récursif: enfants avec compteur incrémenté
    SELECT 
        tr.tasks_runs_id,
        tr.task_id,
        tr.parent_run_id,
        tr.is_reactivation,
        CASE 
            WHEN tr.is_reactivation THEN rc.reactivation_count + 1
            ELSE rc.reactivation_count
        END as reactivation_count
    FROM task_runs tr
    INNER JOIN reactivation_chain rc ON tr.parent_run_id = rc.tasks_runs_id
)
UPDATE task_runs tr
SET reactivation_count = rc.reactivation_count
FROM reactivation_chain rc
WHERE tr.tasks_runs_id = rc.tasks_runs_id
AND rc.reactivation_count > 0;

COMMIT;

-- Vérification
SELECT 
    tasks_runs_id,
    task_id,
    run_number,
    is_reactivation,
    reactivation_count,
    parent_run_id
FROM task_runs
WHERE reactivation_count > 0
ORDER BY task_id, started_at DESC
LIMIT 10;

