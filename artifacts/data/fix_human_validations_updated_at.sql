-- ===============================================
-- MIGRATION: Ajout colonne updated_at manquante
-- Description: Ajoute la colonne updated_at à human_validations pour le trigger
-- ===============================================

-- Ajouter la colonne updated_at si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'human_validations' 
        AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE human_validations 
        ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
        
        -- Mettre à jour les valeurs existantes
        UPDATE human_validations 
        SET updated_at = created_at 
        WHERE updated_at IS NULL;
        
        RAISE NOTICE 'Colonne updated_at ajoutée à human_validations';
    ELSE
        RAISE NOTICE 'Colonne updated_at existe déjà dans human_validations';
    END IF;
END $$;

-- Créer un index sur updated_at pour les requêtes de tri
CREATE INDEX IF NOT EXISTS idx_human_validations_updated_at 
ON human_validations(updated_at DESC);

-- Recréer le trigger pour s'assurer qu'il fonctionne
DROP TRIGGER IF EXISTS sync_validation_status_trigger ON human_validation_responses;

CREATE OR REPLACE FUNCTION sync_validation_status() RETURNS TRIGGER AS $$
BEGIN
    -- Quand une réponse est créée, mettre à jour le statut de la validation
    UPDATE human_validations 
    SET status = NEW.response_status,
        updated_at = NOW()
    WHERE human_validations_id = NEW.human_validation_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sync_validation_status_trigger
AFTER INSERT ON human_validation_responses
FOR EACH ROW EXECUTE FUNCTION sync_validation_status();

-- Vérification
SELECT 'Migration completed successfully' AS status;
