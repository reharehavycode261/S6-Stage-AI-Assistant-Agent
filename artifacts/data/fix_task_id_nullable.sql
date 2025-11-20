-- ============================================================
-- MIGRATION CRITIQUE: Rendre task_id nullable dans task_runs
-- Date: 2025-10-02
-- Objectif: Corriger l'erreur "null value in column task_id violates not-null constraint"
-- ============================================================

-- 1. Vérifier l'état actuel de la contrainte
SELECT 
    column_name, 
    is_nullable, 
    column_default,
    data_type
FROM information_schema.columns 
WHERE table_name = 'task_runs' AND column_name = 'task_id';

-- 2. Supprimer la contrainte NOT NULL sur task_id (si elle existe)
DO $$ 
BEGIN
    -- Vérifier si la colonne est actuellement NOT NULL
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns 
        WHERE table_name = 'task_runs' 
        AND column_name = 'task_id'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE task_runs ALTER COLUMN task_id DROP NOT NULL;
        RAISE NOTICE '✅ Contrainte NOT NULL supprimée de task_runs.task_id';
    ELSE
        RAISE NOTICE '✅ task_runs.task_id est déjà nullable';
    END IF;
END $$;

-- 3. Vérifier et corriger la contrainte de clé étrangère
DO $$
DECLARE
    fk_constraint_name TEXT;
BEGIN
    -- Trouver le nom de la contrainte FK actuelle
    SELECT constraint_name INTO fk_constraint_name
    FROM information_schema.table_constraints 
    WHERE table_name = 'task_runs' 
    AND constraint_type = 'FOREIGN KEY'
    AND constraint_name LIKE '%task_id%';
    
    IF fk_constraint_name IS NOT NULL THEN
        -- Supprimer l'ancienne contrainte
        EXECUTE format('ALTER TABLE task_runs DROP CONSTRAINT IF EXISTS %I', fk_constraint_name);
        RAISE NOTICE '✅ Ancienne contrainte FK supprimée: %', fk_constraint_name;
    END IF;
    
    -- Recréer la contrainte avec ON DELETE SET NULL
    ALTER TABLE task_runs 
    DROP CONSTRAINT IF EXISTS task_runs_task_id_fkey;
    
    ALTER TABLE task_runs 
    ADD CONSTRAINT task_runs_task_id_fkey 
    FOREIGN KEY (task_id) REFERENCES tasks(tasks_id) ON DELETE SET NULL;
    
    RAISE NOTICE '✅ Nouvelle contrainte FK créée avec ON DELETE SET NULL';
END $$;

-- 4. Modifier l'index unique pour supporter les valeurs NULL
-- Recréer l'index unique en excluant les NULL
DROP INDEX IF EXISTS uq_task_runs_task_run_number;
CREATE UNIQUE INDEX IF NOT EXISTS uq_task_runs_task_run_number 
ON task_runs(task_id, run_number) 
WHERE task_id IS NOT NULL;

RAISE NOTICE '✅ Index unique recréé avec condition WHERE task_id IS NOT NULL';

-- 5. Vérifier que la migration a réussi
DO $$
DECLARE
    v_is_nullable TEXT;
BEGIN
    SELECT is_nullable INTO v_is_nullable
    FROM information_schema.columns 
    WHERE table_name = 'task_runs' AND column_name = 'task_id';
    
    IF v_is_nullable = 'YES' THEN
        RAISE NOTICE '✅ SUCCÈS: task_runs.task_id est maintenant nullable';
    ELSE
        RAISE EXCEPTION '❌ ERREUR: task_runs.task_id est toujours NOT NULL';
    END IF;
END $$;

-- 6. Test d'insertion avec task_id NULL (optionnel - commenter si pas nécessaire)
-- DO $$
-- BEGIN
--     INSERT INTO task_runs (
--         task_id, status, celery_task_id, ai_provider, current_node, progress_percentage
--     ) VALUES (
--         NULL, 'started', 'test_null_task_id_' || EXTRACT(EPOCH FROM NOW()), 'claude', 'test_node', 0
--     );
--     
--     DELETE FROM task_runs WHERE celery_task_id LIKE 'test_null_task_id_%';
--     
--     RAISE NOTICE '✅ Test d''insertion avec task_id NULL réussi';
-- END $$;

-- Afficher le résultat final
SELECT 
    '✅ Migration terminée' AS status,
    column_name, 
    is_nullable, 
    data_type
FROM information_schema.columns 
WHERE table_name = 'task_runs' AND column_name = 'task_id';

