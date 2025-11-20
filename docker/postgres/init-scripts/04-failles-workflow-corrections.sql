-- ============================================================================
-- SCRIPT 04: Corrections des Failles de Réactivation Workflow
-- ============================================================================
-- Description: Applique les corrections des 3 failles critiques
-- Exécution: Automatique au démarrage du container PostgreSQL (après init-db.sql)
-- Ordre: 04-failles-workflow-corrections.sql
-- ============================================================================

\echo '=========================================='
\echo '🛡️ Application des corrections de failles'
\echo '=========================================='

-- ============================================================================
-- VÉRIFICATION: S'assurer que les tables existent avant d'ajouter les colonnes
-- ============================================================================

DO $$
DECLARE
    tasks_exists boolean;
    task_runs_exists boolean;
BEGIN
    -- Vérifier l'existence de la table tasks
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'tasks'
    ) INTO tasks_exists;
    
    -- Vérifier l'existence de la table task_runs
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'task_runs'
    ) INTO task_runs_exists;
    
    IF tasks_exists THEN
        RAISE NOTICE '✅ Table tasks existe';
    ELSE
        RAISE EXCEPTION '❌ Table tasks n''existe pas - vérifier init-db.sql';
    END IF;
    
    IF task_runs_exists THEN
        RAISE NOTICE '✅ Table task_runs existe';
    ELSE
        RAISE EXCEPTION '❌ Table task_runs n''existe pas - vérifier init-db.sql';
    END IF;
END $$;

-- ============================================================================
-- FAILLE #1 : Gestion Incohérente des États du Workflow
-- ============================================================================

\echo ''
\echo '🔧 Faille #1: Ajout des champs de verrouillage et réactivation'

-- Ajout des colonnes avec vérification
DO $$
BEGIN
    -- reactivated_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tasks' AND column_name='reactivated_at') THEN
        ALTER TABLE tasks ADD COLUMN reactivated_at TIMESTAMPTZ;
        RAISE NOTICE '  ✅ Colonne reactivated_at ajoutée';
    END IF;
    
    -- reactivation_count
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tasks' AND column_name='reactivation_count') THEN
        ALTER TABLE tasks ADD COLUMN reactivation_count INTEGER DEFAULT 0 NOT NULL;
        RAISE NOTICE '  ✅ Colonne reactivation_count ajoutée';
    END IF;
    
    -- previous_status
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tasks' AND column_name='previous_status') THEN
        ALTER TABLE tasks ADD COLUMN previous_status VARCHAR(50);
        RAISE NOTICE '  ✅ Colonne previous_status ajoutée';
    END IF;
    
    -- is_locked
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tasks' AND column_name='is_locked') THEN
        ALTER TABLE tasks ADD COLUMN is_locked BOOLEAN DEFAULT FALSE NOT NULL;
        RAISE NOTICE '  ✅ Colonne is_locked ajoutée';
    END IF;
    
    -- locked_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tasks' AND column_name='locked_at') THEN
        ALTER TABLE tasks ADD COLUMN locked_at TIMESTAMPTZ;
        RAISE NOTICE '  ✅ Colonne locked_at ajoutée';
    END IF;
    
    -- locked_by
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tasks' AND column_name='locked_by') THEN
        ALTER TABLE tasks ADD COLUMN locked_by VARCHAR(255);
        RAISE NOTICE '  ✅ Colonne locked_by ajoutée';
    END IF;
END $$;

-- Index pour les verrous
CREATE INDEX IF NOT EXISTS idx_tasks_is_locked ON tasks(is_locked) WHERE is_locked = TRUE;
CREATE INDEX IF NOT EXISTS idx_tasks_reactivation ON tasks(reactivation_count) WHERE reactivation_count > 0;

\echo '  ✅ Index de verrouillage créés'

-- ============================================================================
-- FAILLE #2 : Duplication des Tâches Celery
-- ============================================================================

\echo ''
\echo '🔧 Faille #2: Ajout du suivi des tâches Celery'

DO $$
BEGIN
    -- active_task_ids
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='task_runs' AND column_name='active_task_ids') THEN
        ALTER TABLE task_runs ADD COLUMN active_task_ids JSONB DEFAULT '[]'::jsonb;
        RAISE NOTICE '  ✅ Colonne active_task_ids ajoutée';
    END IF;
    
    -- last_task_id
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='task_runs' AND column_name='last_task_id') THEN
        ALTER TABLE task_runs ADD COLUMN last_task_id VARCHAR(255);
        RAISE NOTICE '  ✅ Colonne last_task_id ajoutée';
    END IF;
    
    -- task_started_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='task_runs' AND column_name='task_started_at') THEN
        ALTER TABLE task_runs ADD COLUMN task_started_at TIMESTAMPTZ;
        RAISE NOTICE '  ✅ Colonne task_started_at ajoutée';
    END IF;
    
    -- is_reactivation
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='task_runs' AND column_name='is_reactivation') THEN
        ALTER TABLE task_runs ADD COLUMN is_reactivation BOOLEAN DEFAULT FALSE NOT NULL;
        RAISE NOTICE '  ✅ Colonne is_reactivation ajoutée';
    END IF;
END $$;

-- Index pour les tâches actives
CREATE INDEX IF NOT EXISTS idx_task_runs_active_tasks ON task_runs USING GIN (active_task_ids) 
WHERE jsonb_array_length(active_task_ids) > 0;

CREATE INDEX IF NOT EXISTS idx_task_runs_is_reactivation ON task_runs(is_reactivation) 
WHERE is_reactivation = TRUE;

\echo '  ✅ Index Celery créés'

-- ============================================================================
-- FAILLE #3 : Cascade de Réactivations (Cooldown)
-- ============================================================================

\echo ''
\echo '🔧 Faille #3: Ajout des champs de cooldown'

DO $$
BEGIN
    -- last_reactivation_attempt
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tasks' AND column_name='last_reactivation_attempt') THEN
        ALTER TABLE tasks ADD COLUMN last_reactivation_attempt TIMESTAMPTZ;
        RAISE NOTICE '  ✅ Colonne last_reactivation_attempt ajoutée';
    END IF;
    
    -- cooldown_until
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tasks' AND column_name='cooldown_until') THEN
        ALTER TABLE tasks ADD COLUMN cooldown_until TIMESTAMPTZ;
        RAISE NOTICE '  ✅ Colonne cooldown_until ajoutée';
    END IF;
    
    -- failed_reactivation_attempts
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tasks' AND column_name='failed_reactivation_attempts') THEN
        ALTER TABLE tasks ADD COLUMN failed_reactivation_attempts INTEGER DEFAULT 0 NOT NULL;
        RAISE NOTICE '  ✅ Colonne failed_reactivation_attempts ajoutée';
    END IF;
END $$;

-- Index pour les cooldowns
-- Note: NOW() n'est pas IMMUTABLE, donc on ne peut pas l'utiliser dans un index predicate
CREATE INDEX IF NOT EXISTS idx_tasks_cooldown ON tasks(cooldown_until) 
WHERE cooldown_until IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_failed_attempts ON tasks(failed_reactivation_attempts) 
WHERE failed_reactivation_attempts > 0;

\echo '  ✅ Index cooldown créés'

-- ============================================================================
-- FONCTIONS UTILITAIRES
-- ============================================================================

\echo ''
\echo '🔧 Création des fonctions utilitaires'

-- Fonction de nettoyage des verrous expirés
CREATE OR REPLACE FUNCTION clean_expired_locks() 
RETURNS INTEGER AS $func$
DECLARE
    cleaned_count INTEGER;
BEGIN
    UPDATE tasks
    SET is_locked = FALSE,
        locked_at = NULL,
        locked_by = NULL
    WHERE is_locked = TRUE 
      AND locked_at < (NOW() - INTERVAL '30 minutes');
    
    GET DIAGNOSTICS cleaned_count = ROW_COUNT;
    
    RETURN cleaned_count;
END;
$func$ LANGUAGE plpgsql;

\echo '  ✅ Fonction clean_expired_locks() créée'

-- Trigger de réinitialisation des échecs
CREATE OR REPLACE FUNCTION reset_failed_attempts_on_success()
RETURNS TRIGGER AS $func$
BEGIN
    IF NEW.internal_status = 'completed' AND OLD.internal_status != 'completed' THEN
        NEW.failed_reactivation_attempts = 0;
        NEW.cooldown_until = NULL;
    END IF;
    
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_reset_failed_attempts ON tasks;
CREATE TRIGGER trigger_reset_failed_attempts
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    WHEN (NEW.internal_status = 'completed')
    EXECUTE FUNCTION reset_failed_attempts_on_success();

\echo '  ✅ Trigger reset_failed_attempts_on_success créé'

-- ============================================================================
-- VUES UTILITAIRES
-- ============================================================================

\echo ''
\echo '🔧 Création des vues de monitoring'

-- Vue des tâches réactivables
CREATE OR REPLACE VIEW v_tasks_reactivable AS
SELECT 
    t.tasks_id,
    t.title,
    t.internal_status,
    t.reactivation_count,
    t.is_locked,
    t.cooldown_until,
    t.failed_reactivation_attempts,
    CASE 
        WHEN t.is_locked THEN 'LOCKED'
        WHEN t.cooldown_until > NOW() THEN 'COOLDOWN'
        WHEN t.internal_status IN ('processing', 'pending') THEN 'ALREADY_ACTIVE'
        WHEN t.reactivation_count >= 5 THEN 'MAX_REACTIVATIONS'
        ELSE 'REACTIVABLE'
    END AS reactivation_status,
    CASE 
        WHEN t.cooldown_until > NOW() THEN 
            EXTRACT(EPOCH FROM (t.cooldown_until - NOW()))::INTEGER
        ELSE 0
    END AS cooldown_remaining_seconds
FROM tasks t
WHERE t.internal_status IN ('completed', 'failed');

\echo '  ✅ Vue v_tasks_reactivable créée'

-- Vue des tâches Celery actives
CREATE OR REPLACE VIEW v_active_celery_tasks AS
SELECT 
    tr.tasks_runs_id,
    tr.task_id,
    tr.celery_task_id,
    tr.active_task_ids,
    jsonb_array_length(tr.active_task_ids) AS active_tasks_count,
    tr.last_task_id,
    tr.task_started_at,
    tr.status,
    tr.is_reactivation,
    t.title AS task_title,
    t.is_locked,
    t.locked_by
FROM task_runs tr
JOIN tasks t ON tr.task_id = t.tasks_id
WHERE jsonb_array_length(tr.active_task_ids) > 0
   OR tr.status IN ('started', 'running');

\echo '  ✅ Vue v_active_celery_tasks créée'

-- Vue des statistiques
CREATE OR REPLACE VIEW v_reactivation_stats AS
SELECT 
    COUNT(*) AS total_tasks,
    COUNT(*) FILTER (WHERE reactivation_count > 0) AS reactivated_tasks,
    COUNT(*) FILTER (WHERE is_locked = TRUE) AS locked_tasks,
    COUNT(*) FILTER (WHERE cooldown_until > NOW()) AS tasks_in_cooldown,
    COUNT(*) FILTER (WHERE failed_reactivation_attempts > 0) AS tasks_with_failures,
    AVG(reactivation_count) FILTER (WHERE reactivation_count > 0) AS avg_reactivations,
    MAX(reactivation_count) AS max_reactivations,
    COUNT(*) FILTER (WHERE reactivation_count >= 5) AS max_reactivations_reached
FROM tasks;

\echo '  ✅ Vue v_reactivation_stats créée'

-- ============================================================================
-- INITIALISATION DES DONNÉES EXISTANTES
-- ============================================================================

\echo ''
\echo '🔧 Initialisation des valeurs par défaut'

-- Mettre à jour les valeurs NULL vers les valeurs par défaut
UPDATE tasks 
SET 
    reactivation_count = COALESCE(reactivation_count, 0),
    is_locked = COALESCE(is_locked, FALSE),
    failed_reactivation_attempts = COALESCE(failed_reactivation_attempts, 0)
WHERE reactivation_count IS NULL 
   OR is_locked IS NULL 
   OR failed_reactivation_attempts IS NULL;

UPDATE task_runs
SET 
    active_task_ids = COALESCE(active_task_ids, '[]'::jsonb),
    is_reactivation = COALESCE(is_reactivation, FALSE)
WHERE active_task_ids IS NULL 
   OR is_reactivation IS NULL;

\echo '  ✅ Valeurs par défaut appliquées'

-- ============================================================================
-- VALIDATION FINALE
-- ============================================================================

\echo ''
\echo '🔍 Validation de la migration'

DO $$
DECLARE
    tasks_columns_count INTEGER;
    task_runs_columns_count INTEGER;
    expected_tasks_columns INTEGER := 9;
    expected_task_runs_columns INTEGER := 4;
BEGIN
    -- Compter les nouvelles colonnes de tasks
    SELECT COUNT(*) INTO tasks_columns_count
    FROM information_schema.columns
    WHERE table_name = 'tasks'
      AND column_name IN (
        'reactivated_at', 'reactivation_count', 'previous_status',
        'is_locked', 'locked_at', 'locked_by',
        'last_reactivation_attempt', 'cooldown_until', 'failed_reactivation_attempts'
      );
    
    -- Compter les nouvelles colonnes de task_runs
    SELECT COUNT(*) INTO task_runs_columns_count
    FROM information_schema.columns
    WHERE table_name = 'task_runs'
      AND column_name IN (
        'active_task_ids', 'last_task_id', 'task_started_at', 'is_reactivation'
      );
    
    IF tasks_columns_count = expected_tasks_columns THEN
        RAISE NOTICE '  ✅ tasks: %/% colonnes ajoutées', tasks_columns_count, expected_tasks_columns;
    ELSE
        RAISE WARNING '  ⚠️ tasks: %/% colonnes (attendu: %)', tasks_columns_count, expected_tasks_columns, expected_tasks_columns;
    END IF;
    
    IF task_runs_columns_count = expected_task_runs_columns THEN
        RAISE NOTICE '  ✅ task_runs: %/% colonnes ajoutées', task_runs_columns_count, expected_task_runs_columns;
    ELSE
        RAISE WARNING '  ⚠️ task_runs: %/% colonnes (attendu: %)', task_runs_columns_count, expected_task_runs_columns, expected_task_runs_columns;
    END IF;
    
    IF tasks_columns_count = expected_tasks_columns AND task_runs_columns_count = expected_task_runs_columns THEN
        RAISE NOTICE '  🎉 Migration complète réussie!';
    END IF;
END $$;

\echo ''
\echo '=========================================='
\echo '✅ Corrections des failles appliquées!'
\echo '=========================================='
\echo 'Faille #1: Verrouillage ✅'
\echo 'Faille #2: Suivi Celery ✅'
\echo 'Faille #3: Cooldown ✅'
\echo '=========================================='
\echo ''

