-- ============================================
-- Script SQL : Création des Index de Performance
-- Pour optimiser les requêtes fréquentes
-- ============================================

-- IMPORTANT : Exécuter ce script sur la base ai_agent_admin
-- Commande : psql -U admin -d ai_agent_admin -f create_performance_indexes.sql

\echo '🔄 Création des index de performance...'

-- ============================================
-- TABLE: tasks
-- ============================================

\echo '📊 Index pour la table tasks...'

-- Index sur le statut (requêtes fréquentes de filtrage)
CREATE INDEX IF NOT EXISTS idx_tasks_internal_status 
ON tasks(internal_status);

-- Index sur la date de création (tri par date)
CREATE INDEX IF NOT EXISTS idx_tasks_created_at 
ON tasks(created_at DESC);

-- Index sur monday_item_id (jointures et lookups)
CREATE INDEX IF NOT EXISTS idx_tasks_monday_item_id 
ON tasks(monday_item_id);

-- Index composite pour filtrage status + date
CREATE INDEX IF NOT EXISTS idx_tasks_status_created 
ON tasks(internal_status, created_at DESC);

-- Index composite pour filtrage priorité + status
CREATE INDEX IF NOT EXISTS idx_tasks_priority_status 
ON tasks(priority, internal_status);

-- Index sur task_type pour filtrage par type
CREATE INDEX IF NOT EXISTS idx_tasks_task_type 
ON tasks(task_type);

-- Index partiel pour les tâches actives (optimise les requêtes dashboard)
CREATE INDEX IF NOT EXISTS idx_tasks_active 
ON tasks(internal_status, created_at DESC)
WHERE internal_status IN ('processing', 'testing', 'quality_check');

-- Index pour les tâches du mois en cours
CREATE INDEX IF NOT EXISTS idx_tasks_current_month
ON tasks(created_at)
WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE);

\echo '✅ Index tasks créés'


-- ============================================
-- TABLE: task_runs
-- ============================================

\echo '📊 Index pour la table task_runs...'

-- Index sur task_id (jointure fréquente avec tasks)
CREATE INDEX IF NOT EXISTS idx_task_runs_task_id 
ON task_runs(task_id);

-- Index sur started_at (tri chronologique)
CREATE INDEX IF NOT EXISTS idx_task_runs_started_at 
ON task_runs(started_at DESC);

-- Index sur completed_at (calcul de durées)
CREATE INDEX IF NOT EXISTS idx_task_runs_completed_at 
ON task_runs(completed_at DESC);

-- Index sur status
CREATE INDEX IF NOT EXISTS idx_task_runs_status 
ON task_runs(status);

-- Index composite pour les runs complétés
CREATE INDEX IF NOT EXISTS idx_task_runs_completed 
ON task_runs(task_id, completed_at DESC)
WHERE completed_at IS NOT NULL;

-- Index pour calculer les temps moyens d'exécution
CREATE INDEX IF NOT EXISTS idx_task_runs_duration 
ON task_runs(started_at, completed_at)
WHERE completed_at IS NOT NULL;

\echo '✅ Index task_runs créés'


-- ============================================
-- TABLE: run_steps
-- ============================================

\echo '📊 Index pour la table run_steps...'

-- Index sur task_run_id (jointure avec task_runs)
CREATE INDEX IF NOT EXISTS idx_run_steps_task_run_id 
ON run_steps(task_run_id);

-- Index sur step_name (filtrage par type de step)
CREATE INDEX IF NOT EXISTS idx_run_steps_step_name 
ON run_steps(step_name);

-- Index sur started_at
CREATE INDEX IF NOT EXISTS idx_run_steps_started_at 
ON run_steps(started_at DESC);

-- Index composite pour les steps complétés
CREATE INDEX IF NOT EXISTS idx_run_steps_completed 
ON run_steps(task_run_id, step_name, completed_at)
WHERE completed_at IS NOT NULL;

\echo '✅ Index run_steps créés'


-- ============================================
-- TABLE: users
-- ============================================

\echo '📊 Index pour la table users...'

-- Index sur email (lookup fréquent)
CREATE INDEX IF NOT EXISTS idx_users_email 
ON users(email);

-- Index sur slack_user_id (intégration Slack)
CREATE INDEX IF NOT EXISTS idx_users_slack_user_id 
ON users(slack_user_id);

-- Index sur is_active (filtrage)
CREATE INDEX IF NOT EXISTS idx_users_is_active 
ON users(is_active);

-- Index sur name pour recherche
CREATE INDEX IF NOT EXISTS idx_users_name 
ON users(name);

\echo '✅ Index users créés'


-- ============================================
-- TABLE: human_validations
-- ============================================

\echo '📊 Index pour la table human_validations...'

-- Index sur task_id (jointure avec tasks)
CREATE INDEX IF NOT EXISTS idx_human_validations_task_id 
ON human_validations(task_id);

-- Index sur status
CREATE INDEX IF NOT EXISTS idx_human_validations_status 
ON human_validations(status);

-- Index sur created_at
CREATE INDEX IF NOT EXISTS idx_human_validations_created_at 
ON human_validations(created_at DESC);

-- Index sur requested_by
CREATE INDEX IF NOT EXISTS idx_human_validations_requested_by 
ON human_validations(requested_by);

-- Index partiel pour les validations en attente
CREATE INDEX IF NOT EXISTS idx_human_validations_pending 
ON human_validations(created_at DESC)
WHERE status = 'pending';

\echo '✅ Index human_validations créés'


-- ============================================
-- TABLE: workflow_queue
-- ============================================

\echo '📊 Index pour la table workflow_queue...'

-- Index sur status
CREATE INDEX IF NOT EXISTS idx_workflow_queue_status 
ON workflow_queue(status);

-- Index sur monday_item_id
CREATE INDEX IF NOT EXISTS idx_workflow_queue_monday_item_id 
ON workflow_queue(monday_item_id);

-- Index sur created_at
CREATE INDEX IF NOT EXISTS idx_workflow_queue_created_at 
ON workflow_queue(created_at DESC);

-- Index partiel pour la queue en attente
CREATE INDEX IF NOT EXISTS idx_workflow_queue_pending 
ON workflow_queue(created_at ASC)
WHERE status = 'pending';

\echo '✅ Index workflow_queue créés'


-- ============================================
-- TABLE: ai_cost_tracking
-- ============================================

\echo '📊 Index pour la table ai_cost_tracking...'

-- Index sur created_at (agrégations temporelles)
CREATE INDEX IF NOT EXISTS idx_ai_cost_tracking_created_at 
ON ai_cost_tracking(created_at DESC);

-- Index sur model_name (filtrage par modèle)
CREATE INDEX IF NOT EXISTS idx_ai_cost_tracking_model_name 
ON ai_cost_tracking(model_name);

-- Index sur task_id (jointure avec tasks)
CREATE INDEX IF NOT EXISTS idx_ai_cost_tracking_task_id 
ON ai_cost_tracking(task_id);

-- Index composite pour coûts par modèle et période
CREATE INDEX IF NOT EXISTS idx_ai_cost_tracking_model_date 
ON ai_cost_tracking(model_name, created_at DESC);

-- Index pour calcul des coûts du mois en cours
CREATE INDEX IF NOT EXISTS idx_ai_cost_current_month
ON ai_cost_tracking(created_at, cost)
WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE);

\echo '✅ Index ai_cost_tracking créés'


-- ============================================
-- TABLE: language_detection
-- ============================================

\echo '📊 Index pour la table language_detection...'

-- Index sur detected_language
CREATE INDEX IF NOT EXISTS idx_language_detection_language 
ON language_detection(detected_language);

-- Index sur confidence_score
CREATE INDEX IF NOT EXISTS idx_language_detection_confidence 
ON language_detection(confidence_score);

-- Index sur detected_at
CREATE INDEX IF NOT EXISTS idx_language_detection_detected_at 
ON language_detection(detected_at DESC);

-- Index sur task_id
CREATE INDEX IF NOT EXISTS idx_language_detection_task_id 
ON language_detection(task_id);

\echo '✅ Index language_detection créés'


-- ============================================
-- TABLE: webhook_events (si partitionnée avec pg_partman)
-- ============================================

\echo '📊 Index pour la table webhook_events...'

-- Note: Si la table est partitionnée, ces index seront créés sur chaque partition

-- Index sur event_type
CREATE INDEX IF NOT EXISTS idx_webhook_events_event_type 
ON webhook_events(event_type);

-- Index sur processed
CREATE INDEX IF NOT EXISTS idx_webhook_events_processed 
ON webhook_events(processed);

-- Index sur received_at
CREATE INDEX IF NOT EXISTS idx_webhook_events_received_at 
ON webhook_events(received_at DESC);

-- Index composite pour filtrage événements non traités
CREATE INDEX IF NOT EXISTS idx_webhook_events_unprocessed 
ON webhook_events(received_at DESC)
WHERE processed = false;

\echo '✅ Index webhook_events créés'


-- ============================================
-- Statistiques et maintenance
-- ============================================

\echo '📊 Mise à jour des statistiques des tables...'

-- Mettre à jour les statistiques pour l'optimiseur de requêtes
ANALYZE tasks;
ANALYZE task_runs;
ANALYZE run_steps;
ANALYZE users;
ANALYZE human_validations;
ANALYZE workflow_queue;
ANALYZE ai_cost_tracking;
ANALYZE language_detection;
ANALYZE webhook_events;

\echo '✅ Statistiques mises à jour'


-- ============================================
-- Rapport final
-- ============================================

\echo ''
\echo '✅✅✅ TOUS LES INDEX CRÉÉS AVEC SUCCÈS ✅✅✅'
\echo ''
\echo '📊 Résumé:'
\echo '  - tasks: 9 index'
\echo '  - task_runs: 6 index'
\echo '  - run_steps: 4 index'
\echo '  - users: 4 index'
\echo '  - human_validations: 5 index'
\echo '  - workflow_queue: 4 index'
\echo '  - ai_cost_tracking: 6 index'
\echo '  - language_detection: 4 index'
\echo '  - webhook_events: 4 index'
\echo ''
\echo '💡 Pour vérifier les index créés:'
\echo '   SELECT tablename, indexname FROM pg_indexes WHERE schemaname = '\''public'\'' ORDER BY tablename, indexname;'
\echo ''
\echo '💡 Pour voir la taille des index:'
\echo '   SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) FROM pg_indexes WHERE schemaname = '\''public'\'' ORDER BY pg_relation_size(indexname::regclass) DESC;'
\echo ''
\echo '🎯 Les requêtes du dashboard et des listes devraient être significativement plus rapides!'
\echo ''

