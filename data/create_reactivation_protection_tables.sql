-- ============================================================================
-- Tables de Protection pour la Réactivation des Workflows
-- ============================================================================
-- Date: 21 octobre 2025
-- Objectif: Créer les tables manquantes pour le système de protection
--           contre les réactivations multiples (Failles #1, #2, #3)
-- ============================================================================

-- ============================================================================
-- Table 1: workflow_locks
-- Protection contre les exécutions concurrentes (Faille #1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_locks (
    lock_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(tasks_id) ON DELETE CASCADE,
    lock_key VARCHAR(255) NOT NULL,
    is_locked BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    locked_at TIMESTAMP DEFAULT NOW(),
    released_at TIMESTAMP,
    lock_owner VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_locks_task_id ON workflow_locks(task_id);
CREATE INDEX IF NOT EXISTS idx_workflow_locks_is_active ON workflow_locks(is_active);
CREATE INDEX IF NOT EXISTS idx_workflow_locks_lock_key ON workflow_locks(lock_key);

COMMENT ON TABLE workflow_locks IS 'Verrous pour empêcher les exécutions concurrentes de workflows';
COMMENT ON COLUMN workflow_locks.is_locked IS 'Indique si le verrou est actuellement actif';
COMMENT ON COLUMN workflow_locks.is_active IS 'Indique si le verrou est valide (non expiré)';

-- ============================================================================
-- Table 2: workflow_cooldowns  
-- Protection contre les réactivations trop rapprochées (Faille #3)
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_cooldowns (
    cooldown_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(tasks_id) ON DELETE CASCADE,
    cooldown_type VARCHAR(50) NOT NULL, -- 'normal', 'aggressive', 'backoff'
    cooldown_until TIMESTAMP NOT NULL,
    failed_reactivation_attempts INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_cooldowns_task_id ON workflow_cooldowns(task_id);
CREATE INDEX IF NOT EXISTS idx_workflow_cooldowns_until ON workflow_cooldowns(cooldown_until);

COMMENT ON TABLE workflow_cooldowns IS 'Périodes de cooldown pour éviter les réactivations trop fréquentes';
COMMENT ON COLUMN workflow_cooldowns.cooldown_type IS 'Type de cooldown: normal (5min), aggressive (15min), backoff (exponentiel)';
COMMENT ON COLUMN workflow_cooldowns.cooldown_until IS 'Date jusqu\'à laquelle la tâche est en cooldown';
COMMENT ON COLUMN workflow_cooldowns.failed_reactivation_attempts IS 'Nombre de tentatives de réactivation échouées';

-- ============================================================================
-- Table 3: workflow_reactivations
-- Historique des réactivations
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_reactivations (
    reactivation_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(tasks_id) ON DELETE CASCADE,
    run_id INTEGER REFERENCES task_runs(tasks_runs_id) ON DELETE SET NULL,
    trigger_type VARCHAR(50) NOT NULL, -- 'update', 'status_change', 'manual'
    trigger_source VARCHAR(100),
    update_data JSONB,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_task_id ON workflow_reactivations(task_id);
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_status ON workflow_reactivations(status);
CREATE INDEX IF NOT EXISTS idx_workflow_reactivations_created_at ON workflow_reactivations(created_at);

COMMENT ON TABLE workflow_reactivations IS 'Historique de toutes les réactivations de workflows';
COMMENT ON COLUMN workflow_reactivations.trigger_type IS 'Type de déclencheur: update (commentaire), status_change, manual';

-- ============================================================================
-- Fonction: Nettoyer les anciens verrous (> 1 heure)
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_old_workflow_locks()
RETURNS void AS $$
BEGIN
    UPDATE workflow_locks 
    SET is_active = FALSE, released_at = NOW()
    WHERE is_active = TRUE 
      AND locked_at < NOW() - INTERVAL '1 hour';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_workflow_locks IS 'Libère automatiquement les verrous de plus d\'1 heure';

-- ============================================================================
-- Fonction: Nettoyer les cooldowns expirés
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_expired_cooldowns()
RETURNS void AS $$
BEGIN
    DELETE FROM workflow_cooldowns 
    WHERE cooldown_until < NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_expired_cooldowns IS 'Supprime les cooldowns expirés';

-- ============================================================================
-- Vue: État actuel des protections par tâche
-- ============================================================================

CREATE OR REPLACE VIEW v_task_protection_status AS
SELECT 
    t.tasks_id,
    t.monday_item_id,
    t.title,
    t.internal_status,
    -- Verrous actifs
    (SELECT COUNT(*) FROM workflow_locks wl 
     WHERE wl.task_id = t.tasks_id AND wl.is_active = TRUE) > 0 AS is_locked,
    (SELECT lock_owner FROM workflow_locks wl 
     WHERE wl.task_id = t.tasks_id AND wl.is_active = TRUE 
     ORDER BY locked_at DESC LIMIT 1) AS locked_by,
    -- Cooldown actif
    (SELECT COUNT(*) FROM workflow_cooldowns wc 
     WHERE wc.task_id = t.tasks_id AND wc.cooldown_until > NOW()) > 0 AS in_cooldown,
    (SELECT cooldown_until FROM workflow_cooldowns wc 
     WHERE wc.task_id = t.tasks_id AND wc.cooldown_until > NOW() 
     ORDER BY cooldown_until DESC LIMIT 1) AS cooldown_until,
    (SELECT cooldown_type FROM workflow_cooldowns wc 
     WHERE wc.task_id = t.tasks_id AND wc.cooldown_until > NOW() 
     ORDER BY cooldown_until DESC LIMIT 1) AS cooldown_type,
    -- Statistiques de réactivation
    (SELECT COUNT(*) FROM workflow_reactivations wr 
     WHERE wr.task_id = t.tasks_id) AS total_reactivations,
    (SELECT COUNT(*) FROM workflow_reactivations wr 
     WHERE wr.task_id = t.tasks_id AND wr.status = 'completed') AS successful_reactivations,
    (SELECT MAX(created_at) FROM workflow_reactivations wr 
     WHERE wr.task_id = t.tasks_id) AS last_reactivation_at
FROM tasks t;

COMMENT ON VIEW v_task_protection_status IS 'Vue d\'ensemble de l\'état de protection de chaque tâche';

-- ============================================================================
-- Données de test/validation
-- ============================================================================

-- Exemple de requêtes de vérification:
-- 
-- -- Vérifier les protections d'une tâche
-- SELECT * FROM v_task_protection_status WHERE monday_item_id = '5054186334';
--
-- -- Libérer manuellement un verrou
-- UPDATE workflow_locks SET is_active = FALSE WHERE task_id = X;
--
-- -- Supprimer un cooldown
-- DELETE FROM workflow_cooldowns WHERE task_id = X;
--
-- -- Historique des réactivations d'une tâche
-- SELECT * FROM workflow_reactivations WHERE task_id = X ORDER BY created_at DESC;

-- ============================================================================
-- FIN DU SCRIPT
-- ============================================================================

SELECT '✅ Tables de protection créées avec succès' AS result;

