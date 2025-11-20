-- Migration: Ajouter la colonne browser_qa_results à task_runs
-- Date: 2025-11-14
-- Description: Ajoute une colonne JSONB pour stocker les résultats des tests Browser QA

-- Vérifier si la colonne existe déjà et la créer si nécessaire
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'task_runs' 
        AND column_name = 'browser_qa_results'
    ) THEN
        -- Ajouter la colonne browser_qa_results
        ALTER TABLE task_runs 
        ADD COLUMN browser_qa_results JSONB DEFAULT NULL;
        
        -- Ajouter un index GIN pour les requêtes JSONB
        CREATE INDEX IF NOT EXISTS idx_task_runs_browser_qa_results 
        ON task_runs USING GIN (browser_qa_results);
        
        -- Ajouter un commentaire pour la documentation
        COMMENT ON COLUMN task_runs.browser_qa_results IS 
        'Résultats des tests Browser QA automatisés (Chrome DevTools MCP)';
        
        RAISE NOTICE 'Colonne browser_qa_results créée avec succès';
    ELSE
        RAISE NOTICE 'Colonne browser_qa_results existe déjà';
    END IF;
END $$;

-- Vérifier la création
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'task_runs' 
AND column_name = 'browser_qa_results';

