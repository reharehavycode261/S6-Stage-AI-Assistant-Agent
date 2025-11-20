-- ===============================================
-- MIGRATION: AJOUT DE LA COLONNE last_merged_pr_url
-- Description: Ajoute le stockage de l'URL de la dernière PR fusionnée
-- Date: 7 octobre 2025
-- ===============================================

-- Ajouter la colonne last_merged_pr_url dans la table task_runs
-- Cette colonne stocke l'URL de la dernière PR fusionnée récupérée depuis GitHub
ALTER TABLE task_runs 
ADD COLUMN IF NOT EXISTS last_merged_pr_url VARCHAR(500);

-- Ajouter un commentaire pour documenter la colonne
COMMENT ON COLUMN task_runs.last_merged_pr_url IS 
'URL de la dernière Pull Request fusionnée récupérée depuis GitHub lors de la mise à jour Monday.com';

-- Créer un index pour faciliter les recherches par URL de PR fusionnée
CREATE INDEX IF NOT EXISTS idx_task_runs_last_merged_pr_url 
ON task_runs(last_merged_pr_url) 
WHERE last_merged_pr_url IS NOT NULL;

-- Vérification de la migration
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'task_runs' 
        AND column_name = 'last_merged_pr_url'
    ) THEN
        RAISE NOTICE '✅ Migration réussie: Colonne last_merged_pr_url ajoutée à task_runs';
    ELSE
        RAISE EXCEPTION '❌ Migration échouée: Colonne last_merged_pr_url non trouvée';
    END IF;
END $$;

