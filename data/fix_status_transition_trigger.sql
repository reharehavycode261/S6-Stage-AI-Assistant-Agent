-- ============================================================
-- MIGRATION: Corriger le trigger validate_status_transition
-- Date: 2025-10-02
-- Objectif: Ajouter l'ignoration des transitions identiques
-- ============================================================

-- Recréer la fonction avec la correction
CREATE OR REPLACE FUNCTION validate_status_transition() RETURNS TRIGGER AS $$
DECLARE
    valid_transitions JSONB := '{
        "pending": ["processing", "failed"],
        "processing": ["testing", "debugging", "completed", "failed"],
        "testing": ["quality_check", "debugging", "completed", "failed"],
        "debugging": ["testing", "completed", "failed"],
        "quality_check": ["completed", "failed"],
        "completed": [],
        "failed": ["pending", "processing"]
    }'::JSONB;
BEGIN
    -- ✅ CORRECTION CRITIQUE: Ignorer les transitions identiques (idempotentes)
    IF OLD.internal_status = NEW.internal_status THEN
        RETURN NEW;
    END IF;

    -- Valider les autres transitions
    IF OLD.internal_status IS NOT NULL AND 
       NOT (valid_transitions->OLD.internal_status ? NEW.internal_status) THEN
        RAISE EXCEPTION 'Invalid status transition from % to %', 
            OLD.internal_status, NEW.internal_status;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Vérifier que le trigger existe et est actif
SELECT 
    trigger_name,
    event_manipulation,
    event_object_table,
    action_timing,
    action_statement
FROM information_schema.triggers
WHERE trigger_name = 'tr_validate_task_status';

-- Message de confirmation
DO $$
BEGIN
    RAISE NOTICE '✅ Fonction validate_status_transition mise à jour avec support des transitions identiques';
END $$;

