-- ============================================================
-- MIGRATION: Rendre task_id nullable dans task_runs
-- Date: 2025-09-17
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

-- 2. Supprimer la contrainte NOT NULL sur task_id
ALTER TABLE task_runs 
ALTER COLUMN task_id DROP NOT NULL;

-- 3. Modifier la contrainte de clé étrangère pour utiliser ON DELETE SET NULL
-- D'abord, identifier le nom de la contrainte existante
SELECT 
    constraint_name, 
    constraint_type,
    table_name,
    column_name
FROM information_schema.key_column_usage 
WHERE table_name = 'task_runs' AND column_name = 'task_id';

-- 4. Supprimer l'ancienne contrainte de clé étrangère
-- (Le nom exact peut varier, remplacer par le nom trouvé ci-dessus)
ALTER TABLE task_runs 
DROP CONSTRAINT IF EXISTS task_runs_task_id_fkey;

-- 5. Recréer la contrainte de clé étrangère avec ON DELETE SET NULL
ALTER TABLE task_runs 
ADD CONSTRAINT task_runs_task_id_fkey 
FOREIGN KEY (task_id) REFERENCES tasks(tasks_id) ON DELETE SET NULL;

-- 6. Vérifier que la migration a réussi
SELECT 
    column_name, 
    is_nullable, 
    column_default,
    data_type
FROM information_schema.columns 
WHERE table_name = 'task_runs' AND column_name = 'task_id';

-- 7. Vérifier les contraintes de clé étrangère
SELECT 
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
LEFT JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
    AND tc.table_name = 'task_runs' 
    AND kcu.column_name = 'task_id';

-- 8. Test d'insertion avec task_id NULL (optionnel)
-- INSERT INTO task_runs (task_id, status, celery_task_id, ai_provider) 
-- VALUES (NULL, 'started', 'test_null_task_id', 'claude');

-- 9. Nettoyer le test (optionnel)
-- DELETE FROM task_runs WHERE celery_task_id = 'test_null_task_id';

COMMIT;

-- ============================================================
-- FIN DE LA MIGRATION
-- ============================================================ 