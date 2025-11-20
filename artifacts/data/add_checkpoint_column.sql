-- Migration: Ajout de la colonne checkpoint_data à run_steps
-- Date: 2025-09-24
-- Objectif: Corriger l'erreur 'save_run_step_checkpoint' method not found

-- Ajouter la colonne checkpoint_data si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='run_steps' 
        AND column_name='checkpoint_data'
    ) THEN
        ALTER TABLE run_steps ADD COLUMN checkpoint_data JSONB;
        RAISE NOTICE 'Colonne checkpoint_data ajoutée à run_steps';
    ELSE
        RAISE NOTICE 'Colonne checkpoint_data existe déjà dans run_steps';
    END IF;
END $$;

-- Ajouter la colonne checkpoint_saved_at si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='run_steps' 
        AND column_name='checkpoint_saved_at'
    ) THEN
        ALTER TABLE run_steps ADD COLUMN checkpoint_saved_at TIMESTAMPTZ;
        RAISE NOTICE 'Colonne checkpoint_saved_at ajoutée à run_steps';
    ELSE
        RAISE NOTICE 'Colonne checkpoint_saved_at existe déjà dans run_steps';
    END IF;
END $$;

-- Créer un index pour optimiser les requêtes sur les checkpoints
CREATE INDEX IF NOT EXISTS idx_run_steps_checkpoint 
ON run_steps(run_steps_id) 
WHERE checkpoint_data IS NOT NULL;

RAISE NOTICE 'Migration checkpoint terminée avec succès'; 