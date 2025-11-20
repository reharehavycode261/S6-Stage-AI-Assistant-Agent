-- ============================================
-- Script SQL : Ajouter UNIQUEMENT les Index Manquants
-- Analyse de la base existante : 164 index déjà présents
-- Ce script ajoute seulement les index qui amélioreront les performances
-- ============================================

\echo '🔍 Ajout des index manquants pour optimisation...'
\echo ''

-- ============================================
-- TABLE: tasks - Index manquants uniquement
-- ============================================

\echo '📊 Ajout des index manquants sur tasks...'

-- Index sur internal_status complet (l'existant est partiel)
CREATE INDEX IF NOT EXISTS idx_tasks_internal_status_full 
ON tasks(internal_status);

-- Index sur priority (manquant)
CREATE INDEX IF NOT EXISTS idx_tasks_priority 
ON tasks(priority);

-- Index sur task_type si la colonne existe (manquant)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name='tasks' AND column_name='task_type') THEN
        CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);
    END IF;
END$$;

-- Index composite status + created pour dashboard (manquant)
CREATE INDEX IF NOT EXISTS idx_tasks_status_created_combo 
ON tasks(internal_status, created_at DESC);

-- Index composite priority + status pour filtres (manquant)
CREATE INDEX IF NOT EXISTS idx_tasks_priority_status_combo 
ON tasks(priority, internal_status);

-- Index pour les tâches du mois en cours (optimisation dashboard)
CREATE INDEX IF NOT EXISTS idx_tasks_current_month
ON tasks(created_at)
WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE);

\echo '✅ Index tasks ajoutés'
\echo ''

-- ============================================
-- TABLE: task_runs - Index manquants
-- ============================================

\echo '📊 Ajout des index manquants sur task_runs...'

-- Index sur task_id seul (pour jointures)
CREATE INDEX IF NOT EXISTS idx_task_runs_task_id_only 
ON task_runs(task_id);

-- Index sur started_at seul
CREATE INDEX IF NOT EXISTS idx_task_runs_started_at_only 
ON task_runs(started_at DESC);

-- Index sur completed_at
CREATE INDEX IF NOT EXISTS idx_task_runs_completed_at 
ON task_runs(completed_at DESC);

-- Index pour runs complétés (calcul de durées)
CREATE INDEX IF NOT EXISTS idx_task_runs_completed_only 
ON task_runs(task_id, completed_at DESC)
WHERE completed_at IS NOT NULL;

-- Index pour calcul des temps moyens
CREATE INDEX IF NOT EXISTS idx_task_runs_duration_calc 
ON task_runs(started_at, completed_at)
WHERE completed_at IS NOT NULL;

\echo '✅ Index task_runs ajoutés'
\echo ''

-- ============================================
-- TABLE: run_steps - Index manquants
-- ============================================

\echo '📊 Ajout des index manquants sur run_steps...'

-- Vérifier que la table existe
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'run_steps') THEN
        
        -- Index sur task_run_id
        CREATE INDEX IF NOT EXISTS idx_run_steps_task_run_id 
        ON run_steps(task_run_id);
        
        -- Index sur step_name si la colonne existe
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='run_steps' AND column_name='step_name') THEN
            CREATE INDEX IF NOT EXISTS idx_run_steps_step_name 
            ON run_steps(step_name);
        END IF;
        
        -- Index sur started_at
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='run_steps' AND column_name='started_at') THEN
            CREATE INDEX IF NOT EXISTS idx_run_steps_started_at 
            ON run_steps(started_at DESC);
        END IF;
        
        -- Index pour steps complétés
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='run_steps' AND column_name='completed_at') THEN
            CREATE INDEX IF NOT EXISTS idx_run_steps_completed 
            ON run_steps(task_run_id, completed_at)
            WHERE completed_at IS NOT NULL;
        END IF;
        
        RAISE NOTICE '✅ Index run_steps ajoutés';
    END IF;
END$$;

\echo ''

-- ============================================
-- TABLE: users (system_users) - Index manquants
-- ============================================

\echo '📊 Ajout des index manquants sur users...'

DO $$
BEGIN
    -- Vérifier si table users existe
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
        RAISE NOTICE '✅ Index users ajoutés';
    
    -- Sinon vérifier system_users
    ELSIF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'system_users') THEN
        CREATE INDEX IF NOT EXISTS idx_system_users_email ON system_users(email);
        
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='system_users' AND column_name='is_active') THEN
            CREATE INDEX IF NOT EXISTS idx_system_users_is_active ON system_users(is_active);
        END IF;
        
        RAISE NOTICE '✅ Index system_users ajoutés';
    END IF;
END$$;

\echo ''

-- ============================================
-- TABLE: workflow_queue - Index manquants
-- ============================================

\echo '📊 Ajout des index manquants sur workflow_queue...'

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'workflow_queue') THEN
        
        -- Index sur status
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='workflow_queue' AND column_name='status') THEN
            CREATE INDEX IF NOT EXISTS idx_workflow_queue_status 
            ON workflow_queue(status);
        END IF;
        
        -- Index sur monday_item_id
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='workflow_queue' AND column_name='monday_item_id') THEN
            CREATE INDEX IF NOT EXISTS idx_workflow_queue_monday_item_id 
            ON workflow_queue(monday_item_id);
        END IF;
        
        -- Index sur created_at
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='workflow_queue' AND column_name='created_at') THEN
            CREATE INDEX IF NOT EXISTS idx_workflow_queue_created_at 
            ON workflow_queue(created_at DESC);
        END IF;
        
        -- Index partiel pour queue en attente
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='workflow_queue' AND column_name='status' 
                   AND column_name='created_at') THEN
            CREATE INDEX IF NOT EXISTS idx_workflow_queue_pending 
            ON workflow_queue(created_at ASC)
            WHERE status = 'pending';
        END IF;
        
        RAISE NOTICE '✅ Index workflow_queue ajoutés';
    END IF;
END$$;

\echo ''

-- ============================================
-- TABLE: webhook_events - Index manquants
-- ============================================

\echo '📊 Ajout des index manquants sur webhook_events...'

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'webhook_events') THEN
        
        -- Index sur event_type
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='webhook_events' AND column_name='event_type') THEN
            CREATE INDEX IF NOT EXISTS idx_webhook_events_event_type 
            ON webhook_events(event_type);
        END IF;
        
        -- Index sur processed
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='webhook_events' AND column_name='processed') THEN
            CREATE INDEX IF NOT EXISTS idx_webhook_events_processed 
            ON webhook_events(processed);
        END IF;
        
        -- Index sur received_at
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='webhook_events' AND column_name='received_at') THEN
            CREATE INDEX IF NOT EXISTS idx_webhook_events_received_at 
            ON webhook_events(received_at DESC);
        END IF;
        
        RAISE NOTICE '✅ Index webhook_events ajoutés';
    END IF;
END$$;

\echo ''

-- ============================================
-- Mise à jour des statistiques
-- ============================================

\echo '📊 Mise à jour des statistiques PostgreSQL...'

ANALYZE tasks;
ANALYZE task_runs;
ANALYZE run_steps;
ANALYZE human_validations;
ANALYZE workflow_queue;
ANALYZE webhook_events;

\echo '✅ Statistiques mises à jour'
\echo ''

-- ============================================
-- Rapport final
-- ============================================

\echo '============================================'
\echo '   ✅ INDEX MANQUANTS AJOUTÉS'
\echo '============================================'
\echo ''
\echo '📊 Résumé:'
\echo '  - Index existants conservés: ~164'
\echo '  - Nouveaux index ajoutés: ~15-20'
\echo '  - Total après optimisation: ~180-184'
\echo ''
\echo '💡 Les index utilisent IF NOT EXISTS pour éviter les erreurs'
\echo '💡 Seuls les index manquants ont été créés'
\echo '💡 Les index existants sont préservés'
\echo ''
\echo '🎯 Performances améliorées pour:'
\echo '  - Dashboard metrics (requêtes du mois en cours)'
\echo '  - Liste des tâches (filtres combinés)'
\echo '  - Calculs de durées (temps moyens)'
\echo '  - Jointures optimisées'
\echo ''
\echo '✅ TERMINÉ !'
\echo ''

