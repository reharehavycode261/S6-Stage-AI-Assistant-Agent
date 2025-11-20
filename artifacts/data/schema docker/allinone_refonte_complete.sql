SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;
CREATE SCHEMA IF NOT EXISTS partman;
CREATE SCHEMA IF NOT EXISTS logs;
CREATE SCHEMA IF NOT EXISTS external;
CREATE EXTENSION IF NOT EXISTS pg_partman WITH SCHEMA partman;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
COMMENT ON SCHEMA public IS 'Schéma principal pour les tables métier';
COMMENT ON SCHEMA logs IS 'Schéma pour les tables de logs et audit partitionnées';
COMMENT ON SCHEMA external IS 'Schéma pour les tables externes (Celery, etc.)';
CREATE TABLE public.ai_providers (
    provider_id SERIAL PRIMARY KEY,
    provider_code VARCHAR(50) UNIQUE NOT NULL,
    provider_name VARCHAR(100) NOT NULL,
    description TEXT,
    api_endpoint VARCHAR(500),
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.ai_providers IS 'Table de référence pour les fournisseurs IA (OpenAI, Claude, etc.)';
CREATE TABLE public.ai_models (
    model_id SERIAL PRIMARY KEY,
    provider_id INTEGER NOT NULL,
    model_code VARCHAR(100) UNIQUE NOT NULL,
    model_name VARCHAR(200) NOT NULL,
    description TEXT,
    context_window INTEGER,
    max_tokens INTEGER,
    cost_per_1k_input_tokens NUMERIC(10,6),
    cost_per_1k_output_tokens NUMERIC(10,6),
    is_active BOOLEAN DEFAULT true NOT NULL,
    supports_functions BOOLEAN DEFAULT false,
    supports_vision BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.ai_models IS 'Table de référence pour les modèles IA avec tarification';
CREATE TABLE public.ai_operations (
    operation_id SERIAL PRIMARY KEY,
    operation_code VARCHAR(50) UNIQUE NOT NULL,
    operation_name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.ai_operations IS 'Table de référence pour les types d''opérations IA (analyze, implement, debug, etc.)';
CREATE TABLE public.status_types (
    status_id SERIAL PRIMARY KEY,
    status_code VARCHAR(50) UNIQUE NOT NULL,
    status_name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    color VARCHAR(20),
    icon VARCHAR(50),
    is_terminal BOOLEAN DEFAULT false,
    display_order INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.status_types IS 'Table de référence pour tous les statuts du système (tasks, validations, runs, etc.)';
COMMENT ON COLUMN public.status_types.category IS 'Catégorie: task, validation, run, queue, etc.';
COMMENT ON COLUMN public.status_types.is_terminal IS 'Indique si c''est un état final';
CREATE TABLE public.status_transitions (
    transition_id SERIAL PRIMARY KEY,
    from_status_id INTEGER NOT NULL,
    to_status_id INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL,
    is_automatic BOOLEAN DEFAULT false,
    requires_approval BOOLEAN DEFAULT false,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    UNIQUE(from_status_id, to_status_id, category)
);
COMMENT ON TABLE public.status_transitions IS 'Définit les transitions de statuts autorisées (workflow states)';
CREATE TABLE public.user_roles (
    role_id SERIAL PRIMARY KEY,
    role_code VARCHAR(50) UNIQUE NOT NULL,
    role_name VARCHAR(100) NOT NULL,
    description TEXT,
    level INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.user_roles IS 'Table de référence pour les rôles utilisateurs (Admin, Developer, Viewer, Auditor)';
COMMENT ON COLUMN public.user_roles.level IS 'Niveau hiérarchique du rôle (plus élevé = plus de permissions)';
CREATE TABLE public.permissions (
    permission_id SERIAL PRIMARY KEY,
    permission_code VARCHAR(100) UNIQUE NOT NULL,
    permission_name VARCHAR(200) NOT NULL,
    description TEXT,
    resource_type VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.permissions IS 'Table de référence pour les permissions RBAC';
COMMENT ON COLUMN public.permissions.resource_type IS 'Type de ressource (task, validation, config, etc.)';
COMMENT ON COLUMN public.permissions.action IS 'Action (create, read, update, delete, execute, etc.)';
CREATE TABLE public.role_permissions (
    role_permission_id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    granted_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    granted_by INTEGER,
    UNIQUE(role_id, permission_id)
);
COMMENT ON TABLE public.role_permissions IS 'Table pivot pour la relation N-N entre rôles et permissions';
CREATE TABLE public.system_users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(200),
    role_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    monday_user_id BIGINT UNIQUE,
    api_usage_limit INTEGER DEFAULT 1000,
    monthly_reset_day INTEGER DEFAULT 1,
    notification_preferences JSONB DEFAULT '{"email_on_failure": true, "email_on_completion": true}'::JSONB,
    preferences JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    last_login_at TIMESTAMPTZ,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.system_users IS 'Utilisateurs du système avec référence au rôle';
CREATE TABLE public.user_credentials (
    credential_id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    password_salt VARCHAR(100),
    must_change_password BOOLEAN DEFAULT false,
    password_expires_at TIMESTAMPTZ,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_password_change TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
COMMENT ON TABLE public.user_credentials IS 'Credentials séparés pour la sécurité (mots de passe, tokens)';
CREATE TABLE public.user_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_token VARCHAR(500) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    last_activity_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL
);
COMMENT ON TABLE public.user_sessions IS 'Sessions utilisateur actives pour l''authentification';
CREATE TABLE public.tasks (
    task_id SERIAL PRIMARY KEY,
    monday_item_id BIGINT UNIQUE NOT NULL,
    monday_board_id BIGINT,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    priority VARCHAR(50),
    repository_url VARCHAR(500) NOT NULL,
    repository_name VARCHAR(200),
    default_branch VARCHAR(100) DEFAULT 'main',
    monday_status VARCHAR(100),
    current_status_id INTEGER NOT NULL,
    created_by_user_id INTEGER,
    assigned_to TEXT,
    last_run_id INTEGER,
    is_locked BOOLEAN DEFAULT false,
    locked_at TIMESTAMPTZ,
    locked_by VARCHAR(255),
    cooldown_until TIMESTAMPTZ,
    last_reactivation_attempt TIMESTAMPTZ,
    failed_reactivation_attempts INTEGER DEFAULT 0,
    reactivation_count INTEGER DEFAULT 0,
    active_task_ids TEXT[],
    reactivated_at TIMESTAMPTZ,
    previous_status_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.tasks IS 'Tâches provenant de Monday.com avec statut référencé';
COMMENT ON COLUMN public.tasks.task_id IS 'ID interne PK de la base de données';
COMMENT ON COLUMN public.tasks.monday_item_id IS 'ID de l''item Monday.com (unique)';
COMMENT ON COLUMN public.tasks.current_status_id IS 'FK vers status_types pour le statut actuel';
COMMENT ON COLUMN public.tasks.previous_status_id IS 'FK vers status_types pour le statut précédent';
CREATE TABLE public.task_status_history (
    history_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    from_status_id INTEGER,
    to_status_id INTEGER NOT NULL,
    changed_by INTEGER,
    change_reason TEXT,
    metadata JSONB,
    changed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
COMMENT ON TABLE public.task_status_history IS 'Historique des changements de statut des tâches';
CREATE TABLE public.task_runs (
    run_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    run_number INTEGER NOT NULL,
    current_status_id INTEGER NOT NULL,
    celery_task_id VARCHAR(255) UNIQUE,
    current_node VARCHAR(100),
    progress_percentage INTEGER DEFAULT 0,
    provider_id INTEGER,
    model_id INTEGER,
    result JSONB,
    error_message TEXT,
    git_branch_name VARCHAR(255),
    pull_request_url VARCHAR(500),
    last_merged_pr_url VARCHAR(500),
    active_task_ids TEXT[],
    last_task_id VARCHAR(255),
    task_started_at TIMESTAMPTZ,
    is_reactivation BOOLEAN DEFAULT false NOT NULL,
    parent_run_id INTEGER,
    reactivation_count INTEGER DEFAULT 0 NOT NULL,
    browser_qa_results JSONB,
    started_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ,
    UNIQUE(task_id, run_number)
);
COMMENT ON TABLE public.task_runs IS 'Exécutions de workflows avec références normalisées';
COMMENT ON COLUMN public.task_runs.provider_id IS 'FK vers ai_providers';
COMMENT ON COLUMN public.task_runs.model_id IS 'FK vers ai_models';
CREATE TABLE public.task_run_status_history (
    history_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    from_status_id INTEGER,
    to_status_id INTEGER NOT NULL,
    changed_by INTEGER,
    change_reason TEXT,
    metadata JSONB,
    changed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
COMMENT ON TABLE public.task_run_status_history IS 'Historique des changements de statut des runs';
CREATE TABLE public.run_steps (
    step_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    node_name VARCHAR(100) NOT NULL,
    step_order INTEGER NOT NULL,
    current_status_id INTEGER NOT NULL,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    max_retries INTEGER DEFAULT 3 NOT NULL,
    input_data JSONB,
    output_data JSONB,
    output_log TEXT,
    error_details TEXT,
    checkpoint_data JSONB,
    checkpoint_saved_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.run_steps IS 'Étapes individuelles d''un workflow avec statut référencé';
CREATE TABLE public.run_step_checkpoints (
    checkpoint_id SERIAL PRIMARY KEY,
    step_id INTEGER NOT NULL,
    checkpoint_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ,
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.run_step_checkpoints IS 'Checkpoints pour la reprise après erreur';
CREATE TABLE public.ai_interactions (
    interaction_id SERIAL PRIMARY KEY,
    step_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    operation_id INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER GENERATED ALWAYS AS (COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) STORED,
    cost_usd NUMERIC(12,6),
    latency_ms INTEGER,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.ai_interactions IS 'Historique unifié des interactions IA avec références normalisées';
COMMENT ON COLUMN public.ai_interactions.provider_id IS 'FK vers ai_providers';
COMMENT ON COLUMN public.ai_interactions.model_id IS 'FK vers ai_models';
COMMENT ON COLUMN public.ai_interactions.operation_id IS 'FK vers ai_operations';
CREATE TABLE public.ai_prompt_templates (
    template_id SERIAL PRIMARY KEY,
    template_code VARCHAR(100) UNIQUE NOT NULL,
    template_name VARCHAR(255) NOT NULL,
    template_category VARCHAR(100),
    prompt_text TEXT NOT NULL,
    model_id INTEGER,
    temperature NUMERIC(3,2),
    max_tokens INTEGER,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    avg_cost_usd NUMERIC(10,6),
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ai_prompt_templates_max_tokens_check CHECK (max_tokens > 0)
);
COMMENT ON TABLE public.ai_prompt_templates IS 'Templates de prompts avec référence au modèle recommandé';
CREATE TABLE public.ai_prompt_usage (
    usage_id SERIAL PRIMARY KEY,
    template_id INTEGER,
    task_id INTEGER,
    run_id INTEGER,
    interaction_id INTEGER,
    model_id INTEGER,
    temperature_used NUMERIC(3,2),
    max_tokens_used INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER GENERATED ALWAYS AS (COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) STORED,
    cost_usd NUMERIC(10,6),
    execution_time_ms INTEGER,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    executed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.ai_prompt_usage IS 'Usage des templates de prompts';
CREATE TABLE public.human_validations (
    validation_id SERIAL PRIMARY KEY,
    validation_uuid VARCHAR(100) UNIQUE NOT NULL,
    task_id INTEGER NOT NULL,
    run_id INTEGER,
    step_id INTEGER,
    task_title VARCHAR(500) NOT NULL,
    task_description TEXT,
    original_request TEXT NOT NULL,
    current_status_id INTEGER NOT NULL,
    generated_code JSONB NOT NULL,
    code_summary TEXT NOT NULL,
    files_modified TEXT[] NOT NULL,
    implementation_notes TEXT,
    test_results JSONB,
    pr_info JSONB,
    workflow_id VARCHAR(255),
    requested_by INTEGER,
    rejection_count INTEGER DEFAULT 0 NOT NULL,
    modification_instructions TEXT,
    is_retry BOOLEAN DEFAULT false NOT NULL,
    parent_validation_id INTEGER,
    user_email VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    expires_at TIMESTAMPTZ,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.human_validations IS 'Demandes de validation humaine avec statut référencé et FK correctes';
COMMENT ON COLUMN public.human_validations.validation_uuid IS 'UUID unique pour tracking externe';
COMMENT ON COLUMN public.human_validations.parent_validation_id IS 'FK vers human_validations pour les retries';
CREATE TABLE public.human_validation_status_history (
    history_id SERIAL PRIMARY KEY,
    validation_id INTEGER NOT NULL,
    from_status_id INTEGER,
    to_status_id INTEGER NOT NULL,
    changed_by INTEGER,
    change_reason TEXT,
    metadata JSONB,
    changed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
COMMENT ON TABLE public.human_validation_status_history IS 'Historique des changements de statut des validations';
CREATE TABLE public.human_validation_responses (
    response_id SERIAL PRIMARY KEY,
    validation_id INTEGER NOT NULL,
    validation_uuid VARCHAR(100) NOT NULL,
    response_status_id INTEGER NOT NULL,
    comments TEXT,
    suggested_changes TEXT,
    approval_notes TEXT,
    validated_by INTEGER,
    should_merge BOOLEAN DEFAULT false NOT NULL,
    should_continue_workflow BOOLEAN DEFAULT true NOT NULL,
    validation_duration_seconds INTEGER,
    user_agent TEXT,
    ip_address INET,
    rejection_count INTEGER DEFAULT 0 NOT NULL,
    modification_instructions TEXT,
    should_retry_workflow BOOLEAN DEFAULT false NOT NULL,
    validated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.human_validation_responses IS 'Réponses des validateurs avec statut référencé';
CREATE TABLE public.validation_actions (
    action_id SERIAL PRIMARY KEY,
    validation_id INTEGER NOT NULL,
    validation_uuid VARCHAR(100) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    action_status_id INTEGER NOT NULL,
    action_data JSONB,
    result_data JSONB,
    merge_commit_hash VARCHAR(100),
    merge_commit_url VARCHAR(500),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.validation_actions IS 'Actions suite aux validations (merge, reject, etc.) avec statut référencé';
CREATE TABLE public.pull_requests (
    pr_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    run_id INTEGER,
    github_pr_number INTEGER,
    github_pr_url VARCHAR(500),
    pr_title VARCHAR(500),
    pr_description TEXT,
    current_status_id INTEGER NOT NULL,
    mergeable BOOLEAN,
    conflicts BOOLEAN DEFAULT false,
    reviews_required INTEGER DEFAULT 1,
    reviews_approved INTEGER DEFAULT 0,
    head_sha CHAR(40),
    base_branch VARCHAR(100) DEFAULT 'main',
    feature_branch VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    merged_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.pull_requests IS 'Pull Requests avec statut référencé';
CREATE TABLE public.test_results (
    test_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    current_status_id INTEGER NOT NULL,
    tests_total INTEGER DEFAULT 0,
    tests_passed INTEGER DEFAULT 0,
    tests_failed INTEGER DEFAULT 0,
    tests_skipped INTEGER DEFAULT 0,
    coverage_percentage NUMERIC(5,2),
    pytest_report JSONB,
    security_scan_report JSONB,
    duration_seconds INTEGER,
    executed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.test_results IS 'Résultats des tests avec statut référencé';
CREATE TABLE public.performance_metrics (
    metric_id SERIAL PRIMARY KEY,
    task_id INTEGER,
    run_id INTEGER,
    total_duration_seconds INTEGER,
    queue_wait_time_seconds INTEGER,
    ai_processing_time_seconds INTEGER,
    testing_time_seconds INTEGER,
    total_ai_calls INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    total_ai_cost NUMERIC(12,6) DEFAULT 0.0,
    code_lines_generated INTEGER DEFAULT 0,
    test_coverage_final NUMERIC(5,2),
    security_issues_found INTEGER DEFAULT 0,
    retry_attempts INTEGER DEFAULT 0,
    success_rate NUMERIC(5,2),
    recorded_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.performance_metrics IS 'Métriques de performance agrégées';
CREATE TABLE public.workflow_queue (
    queue_id VARCHAR(50) PRIMARY KEY,
    monday_item_id BIGINT NOT NULL,
    task_id INTEGER,
    current_status_id INTEGER NOT NULL,
    priority INTEGER DEFAULT 5 NOT NULL,
    celery_task_id VARCHAR(255),
    error TEXT,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    payload JSONB NOT NULL,
    queued_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.workflow_queue IS 'Queue de workflows avec statut référencé';
CREATE TABLE public.workflow_reactivations (
    reactivation_id SERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL,
    task_id VARCHAR(255),
    trigger_type VARCHAR(50) NOT NULL,
    current_status_id INTEGER NOT NULL,
    update_data JSONB,
    error_message TEXT,
    reactivated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.workflow_reactivations IS 'Réactivations de workflow avec statut référencé';
CREATE TABLE public.workflow_locks (
    lock_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    lock_key VARCHAR(255) NOT NULL,
    is_locked BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT true,
    lock_owner VARCHAR(255),
    metadata JSONB DEFAULT '{}'::JSONB,
    locked_at TIMESTAMPTZ DEFAULT NOW(),
    released_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.workflow_locks IS 'Verrouillage des workflows';
CREATE TABLE public.workflow_cooldowns (
    cooldown_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    cooldown_type VARCHAR(50) NOT NULL,
    cooldown_until TIMESTAMPTZ NOT NULL,
    failed_reactivation_attempts INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.workflow_cooldowns IS 'Cooldowns pour éviter les réactivations répétées';
CREATE TABLE public.code_quality_feedback (
    feedback_id SERIAL PRIMARY KEY,
    task_id INTEGER,
    run_id INTEGER,
    file_path VARCHAR(500),
    line_number INTEGER,
    category VARCHAR(100),
    severity VARCHAR(50),
    message TEXT NOT NULL,
    suggestion TEXT,
    source VARCHAR(100),
    fixed BOOLEAN DEFAULT false,
    auto_fixable BOOLEAN DEFAULT false,
    code_snippet TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.code_quality_feedback IS 'Feedback qualité code';
CREATE TABLE public.task_context_memory (
    memory_id SERIAL PRIMARY KEY,
    task_id INTEGER,
    context_key VARCHAR(255) NOT NULL,
    context_value JSONB NOT NULL,
    relevance_score NUMERIC(3,2) DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    accessed_at TIMESTAMPTZ,
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.task_context_memory IS 'Mémoire contextuelle des tâches';
CREATE TABLE public.task_update_triggers (
    trigger_id SERIAL PRIMARY KEY,
    task_id INTEGER,
    monday_update_id BIGINT,
    update_content TEXT,
    trigger_type VARCHAR(50),
    action_taken VARCHAR(100),
    new_run_id INTEGER,
    metadata JSONB,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.task_update_triggers IS 'Triggers de mise à jour depuis Monday.com';
CREATE TABLE public.monday_updates_history (
    update_history_id SERIAL PRIMARY KEY,
    monday_item_id BIGINT NOT NULL,
    update_id BIGINT,
    update_text TEXT,
    update_author VARCHAR(255),
    update_created_at TIMESTAMPTZ,
    task_id INTEGER,
    triggered_reactivation BOOLEAN DEFAULT false,
    reactivation_id INTEGER,
    processed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.monday_updates_history IS 'Historique des updates Monday.com';
CREATE TABLE public.message_embeddings (
    id SERIAL PRIMARY KEY,
    monday_item_id VARCHAR(50),
    monday_update_id VARCHAR(100) UNIQUE,
    task_id INTEGER,
    message_text TEXT NOT NULL,
    message_language VARCHAR(10),
    cleaned_text TEXT,
    embedding vector(1536) NOT NULL,
    message_type VARCHAR(50) DEFAULT 'user_message',
    intent_type VARCHAR(50),
    user_id VARCHAR(100),
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.message_embeddings IS 'Embeddings vectoriels des messages';
COMMENT ON COLUMN public.message_embeddings.embedding IS 'Vecteur 1536 dimensions (OpenAI text-embedding-3-small)';
CREATE TABLE public.project_context_embeddings (
    id SERIAL PRIMARY KEY,
    repository_url TEXT NOT NULL,
    repository_name VARCHAR(255),
    context_text TEXT NOT NULL,
    context_type VARCHAR(50) NOT NULL,
    file_path TEXT,
    embedding vector(1536) NOT NULL,
    metadata JSONB DEFAULT '{}'::JSONB,
    language VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.project_context_embeddings IS 'Embeddings du contexte de projet';
CREATE TABLE public.system_config (
    config_id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    description TEXT,
    config_type VARCHAR(50) DEFAULT 'application' NOT NULL,
    updated_by_user VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.system_config IS 'Configuration système avec audit complet';
CREATE TABLE public.rate_limits (
    rate_limit_id SERIAL PRIMARY KEY,
    resource_identifier VARCHAR(255) NOT NULL,
    user_id INTEGER,
    max_requests INTEGER NOT NULL,
    limit_window VARCHAR(50) NOT NULL,
    current_requests INTEGER DEFAULT 0,
    window_start TIMESTAMPTZ DEFAULT NOW(),
    last_request_at TIMESTAMPTZ,
    exceeded_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    deleted_at TIMESTAMPTZ
);
COMMENT ON TABLE public.rate_limits IS 'Limitation de taux pour les API';
CREATE TABLE logs.application_logs (
    log_id BIGSERIAL NOT NULL,
    task_id INTEGER,
    run_id INTEGER,
    step_id INTEGER,
    level VARCHAR(20) NOT NULL,
    source_component VARCHAR(100),
    action VARCHAR(100),
    message TEXT NOT NULL,
    metadata JSONB,
    user_id INTEGER,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT application_logs_level_chk CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))
) PARTITION BY RANGE (created_at);
COMMENT ON TABLE logs.application_logs IS 'Logs applicatifs partitionnés par mois';
CREATE TABLE logs.audit_logs (
    log_id BIGSERIAL NOT NULL,
    user_id INTEGER,
    user_email VARCHAR(255) NOT NULL,
    role_id INTEGER,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    details JSONB DEFAULT '{}'::JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(20) DEFAULT 'success',
    severity VARCHAR(20) DEFAULT 'low',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT audit_logs_severity_check CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT audit_logs_status_check CHECK (status IN ('success', 'failed', 'warning'))
) PARTITION BY RANGE (created_at);
COMMENT ON TABLE logs.audit_logs IS 'Logs d''audit partitionnés par mois avec références normalisées';
CREATE TABLE logs.webhook_events (
    event_id BIGSERIAL NOT NULL,
    source VARCHAR(50) NOT NULL,
    event_type VARCHAR(100),
    payload JSONB NOT NULL,
    headers JSONB,
    signature TEXT,
    processed BOOLEAN DEFAULT false NOT NULL,
    processing_status_id INTEGER NOT NULL,
    error_message TEXT,
    related_task_id INTEGER,
    received_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    processed_at TIMESTAMPTZ
) PARTITION BY RANGE (received_at);
COMMENT ON TABLE logs.webhook_events IS 'Événements webhook partitionnés par mois';
CREATE TABLE external.celery_taskmeta (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(155) UNIQUE,
    status VARCHAR(50),
    result BYTEA,
    date_done TIMESTAMP,
    traceback TEXT,
    name VARCHAR(155),
    args BYTEA,
    kwargs BYTEA,
    worker VARCHAR(155),
    retries INTEGER,
    queue VARCHAR(155)
);
COMMENT ON TABLE external.celery_taskmeta IS 'Métadonnées Celery isolées du schéma principal';
CREATE TABLE external.celery_tasksetmeta (
    id SERIAL PRIMARY KEY,
    taskset_id VARCHAR(155) UNIQUE,
    result BYTEA,
    date_done TIMESTAMP
);
COMMENT ON TABLE external.celery_tasksetmeta IS 'Métadonnées Celery taskset isolées';
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION public.prevent_deleted_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'Cannot modify deleted record';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION public.validate_status_transition()
RETURNS TRIGGER AS $$
DECLARE
    transition_exists BOOLEAN;
    category_val VARCHAR(50);
BEGIN
    IF NEW.current_status_id = OLD.current_status_id THEN
        RETURN NEW;
    END IF;
    IF TG_TABLE_NAME = 'tasks' THEN
        category_val := 'task';
    ELSIF TG_TABLE_NAME = 'task_runs' THEN
        category_val := 'run';
    ELSIF TG_TABLE_NAME = 'human_validations' THEN
        category_val := 'validation';
    ELSIF TG_TABLE_NAME = 'workflow_queue' THEN
        category_val := 'queue';
    ELSE
        RETURN NEW;
    END IF;
    SELECT EXISTS(
        SELECT 1 FROM public.status_transitions
        WHERE from_status_id = OLD.current_status_id
        AND to_status_id = NEW.current_status_id
        AND category = category_val
    ) INTO transition_exists;
    IF NOT transition_exists THEN
        RAISE EXCEPTION 'Invalid status transition from % to % for category %',
            OLD.current_status_id, NEW.current_status_id, category_val;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION public.log_status_change_to_history()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_TABLE_NAME = 'tasks' THEN
        INSERT INTO public.task_status_history (task_id, from_status_id, to_status_id, changed_by, changed_at)
        VALUES (NEW.task_id, OLD.current_status_id, NEW.current_status_id, NEW.updated_by, NOW());
    ELSIF TG_TABLE_NAME = 'task_runs' THEN
        INSERT INTO public.task_run_status_history (run_id, from_status_id, to_status_id, changed_by, changed_at)
        VALUES (NEW.run_id, OLD.current_status_id, NEW.current_status_id, NEW.updated_by, NOW());
    ELSIF TG_TABLE_NAME = 'human_validations' THEN
        INSERT INTO public.human_validation_status_history (validation_id, from_status_id, to_status_id, changed_by, changed_at)
        VALUES (NEW.validation_id, OLD.current_status_id, NEW.current_status_id, NEW.updated_by, NOW());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION public.clean_expired_locks()
RETURNS INTEGER AS $$
DECLARE
    cleaned_count INTEGER;
BEGIN
    UPDATE public.tasks
    SET is_locked = FALSE,
        locked_at = NULL,
        locked_by = NULL,
        updated_at = NOW()
    WHERE is_locked = TRUE
    AND locked_at < (NOW() - INTERVAL '30 minutes')
    AND deleted_at IS NULL;
    GET DIAGNOSTICS cleaned_count = ROW_COUNT;
    RETURN cleaned_count;
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION public.cleanup_expired_contexts()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    UPDATE public.task_context_memory
    SET deleted_at = NOW()
    WHERE deleted_at IS NULL
    AND created_at < NOW() - INTERVAL '90 days';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION public.get_current_month_ai_stats()
RETURNS TABLE(
    provider_name VARCHAR,
    total_cost NUMERIC,
    total_tokens BIGINT,
    total_calls BIGINT,
    unique_tasks BIGINT,
    avg_cost_per_call NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.provider_name,
        SUM(ai.cost_usd)::NUMERIC(10, 6) as total_cost,
        SUM(ai.total_tokens)::BIGINT as total_tokens,
        COUNT(*)::BIGINT as total_calls,
        COUNT(DISTINCT COALESCE(rs.run_id, 0))::BIGINT as unique_tasks,
        AVG(ai.cost_usd)::NUMERIC(10, 6) as avg_cost_per_call
    FROM public.ai_interactions ai
    LEFT JOIN public.ai_providers p ON ai.provider_id = p.provider_id
    LEFT JOIN public.run_steps rs ON ai.step_id = rs.step_id
    WHERE EXTRACT(YEAR FROM ai.created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
    AND EXTRACT(MONTH FROM ai.created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
    AND ai.success = true
    AND ai.deleted_at IS NULL
    GROUP BY p.provider_name
    ORDER BY total_cost DESC;
END;
$$ LANGUAGE plpgsql;
CREATE INDEX idx_ai_providers_active ON public.ai_providers(is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_models_provider ON public.ai_models(provider_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_models_active ON public.ai_models(is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_status_types_category ON public.status_types(category) WHERE deleted_at IS NULL;
CREATE INDEX idx_status_transitions_from ON public.status_transitions(from_status_id, category);
CREATE INDEX idx_status_transitions_to ON public.status_transitions(to_status_id, category);
CREATE INDEX idx_user_roles_active ON public.user_roles(is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_role_permissions_role ON public.role_permissions(role_id);
CREATE INDEX idx_role_permissions_permission ON public.role_permissions(permission_id);
CREATE INDEX idx_system_users_role ON public.system_users(role_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_system_users_email ON public.system_users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_system_users_active ON public.system_users(is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_user_credentials_user ON public.user_credentials(user_id);
CREATE INDEX idx_user_sessions_user ON public.user_sessions(user_id) WHERE is_active = true;
CREATE INDEX idx_user_sessions_expires ON public.user_sessions(expires_at) WHERE is_active = true;
CREATE INDEX idx_tasks_monday_item ON public.tasks(monday_item_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_status ON public.tasks(current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_created_at ON public.tasks(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_locked ON public.tasks(is_locked, locked_at) WHERE is_locked = true AND deleted_at IS NULL;
CREATE INDEX idx_tasks_cooldown ON public.tasks(cooldown_until) WHERE cooldown_until IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_task_status_history_task ON public.task_status_history(task_id, changed_at DESC);
CREATE INDEX idx_task_status_history_status ON public.task_status_history(to_status_id, changed_at DESC);
CREATE INDEX idx_task_runs_task ON public.task_runs(task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_task_runs_status ON public.task_runs(current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_task_runs_celery ON public.task_runs(celery_task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_task_runs_started ON public.task_runs(started_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_task_runs_reactivation ON public.task_runs(is_reactivation, parent_run_id) WHERE is_reactivation = true AND deleted_at IS NULL;
CREATE INDEX idx_task_run_status_history_run ON public.task_run_status_history(run_id, changed_at DESC);
CREATE INDEX idx_run_steps_run ON public.run_steps(run_id, step_order) WHERE deleted_at IS NULL;
CREATE INDEX idx_run_steps_status ON public.run_steps(current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_run_steps_started ON public.run_steps(started_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_interactions_step ON public.ai_interactions(step_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_interactions_provider ON public.ai_interactions(provider_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_interactions_model ON public.ai_interactions(model_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_interactions_operation ON public.ai_interactions(operation_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_interactions_created ON public.ai_interactions(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_interactions_cost ON public.ai_interactions(cost_usd DESC) WHERE deleted_at IS NULL AND cost_usd IS NOT NULL;
CREATE INDEX idx_ai_prompt_templates_active ON public.ai_prompt_templates(is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_prompt_templates_category ON public.ai_prompt_templates(template_category) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_prompt_usage_template ON public.ai_prompt_usage(template_id, executed_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_prompt_usage_task ON public.ai_prompt_usage(task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_human_validations_task ON public.human_validations(task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_human_validations_status ON public.human_validations(current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_human_validations_created ON public.human_validations(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_human_validations_expires ON public.human_validations(expires_at) WHERE expires_at IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_human_validations_parent ON public.human_validations(parent_validation_id) WHERE parent_validation_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_human_validation_status_history_validation ON public.human_validation_status_history(validation_id, changed_at DESC);
CREATE INDEX idx_human_validation_responses_validation ON public.human_validation_responses(validation_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_human_validation_responses_status ON public.human_validation_responses(response_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_validation_actions_validation ON public.validation_actions(validation_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_validation_actions_status ON public.validation_actions(action_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_pull_requests_task ON public.pull_requests(task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_pull_requests_status ON public.pull_requests(current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_pull_requests_created ON public.pull_requests(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_test_results_run ON public.test_results(run_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_test_results_status ON public.test_results(current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_performance_metrics_task ON public.performance_metrics(task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_performance_metrics_recorded ON public.performance_metrics(recorded_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_workflow_queue_monday ON public.workflow_queue(monday_item_id, queued_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_workflow_queue_status ON public.workflow_queue(current_status_id, priority DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_workflow_reactivations_workflow ON public.workflow_reactivations(workflow_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_workflow_reactivations_status ON public.workflow_reactivations(current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_workflow_reactivations_created ON public.workflow_reactivations(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_workflow_locks_task ON public.workflow_locks(task_id) WHERE is_active = true AND deleted_at IS NULL;
CREATE INDEX idx_workflow_cooldowns_task ON public.workflow_cooldowns(task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_workflow_cooldowns_until ON public.workflow_cooldowns(cooldown_until) WHERE deleted_at IS NULL;
CREATE INDEX idx_message_embeddings_task ON public.message_embeddings(task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_message_embeddings_created ON public.message_embeddings(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_message_embeddings_monday_item ON public.message_embeddings(monday_item_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_message_embeddings_embedding ON public.message_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
COMMENT ON INDEX public.idx_message_embeddings_embedding IS 'Index HNSW pour recherche vectorielle rapide';
CREATE INDEX idx_message_embeddings_metadata ON public.message_embeddings USING GIN (metadata) WHERE deleted_at IS NULL;
CREATE INDEX idx_project_context_embeddings_repo ON public.project_context_embeddings(repository_url) WHERE deleted_at IS NULL;
CREATE INDEX idx_project_context_embeddings_type ON public.project_context_embeddings(context_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_project_context_embeddings_embedding ON public.project_context_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX idx_system_config_type ON public.system_config(config_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_logs_application_level ON logs.application_logs(level, created_at DESC);
CREATE INDEX idx_logs_application_task ON logs.application_logs(task_id, created_at DESC);
CREATE INDEX idx_logs_application_user ON logs.application_logs(user_id, created_at DESC);
CREATE INDEX idx_logs_application_component ON logs.application_logs(source_component, created_at DESC);
CREATE INDEX idx_logs_application_metadata ON logs.application_logs USING GIN (metadata);
CREATE INDEX idx_logs_audit_user ON logs.audit_logs(user_id, created_at DESC);
CREATE INDEX idx_logs_audit_action ON logs.audit_logs(action, created_at DESC);
CREATE INDEX idx_logs_audit_resource ON logs.audit_logs(resource_type, resource_id, created_at DESC);
CREATE INDEX idx_logs_audit_severity ON logs.audit_logs(severity, created_at DESC);
CREATE INDEX idx_logs_audit_details ON logs.audit_logs USING GIN (details);
CREATE INDEX idx_logs_webhook_source ON logs.webhook_events(source, event_type, received_at DESC);
CREATE INDEX idx_logs_webhook_processed ON logs.webhook_events(processed, received_at DESC);
CREATE INDEX idx_logs_webhook_task ON logs.webhook_events(related_task_id, received_at DESC);
CREATE INDEX idx_logs_webhook_status ON logs.webhook_events(processing_status_id, received_at DESC);
ALTER TABLE public.ai_models
    ADD CONSTRAINT fk_ai_models_provider FOREIGN KEY (provider_id) REFERENCES public.ai_providers(provider_id) ON DELETE RESTRICT;
ALTER TABLE public.ai_models
    ADD CONSTRAINT fk_ai_models_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.ai_models
    ADD CONSTRAINT fk_ai_models_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.ai_providers
    ADD CONSTRAINT fk_ai_providers_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.ai_providers
    ADD CONSTRAINT fk_ai_providers_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.status_transitions
    ADD CONSTRAINT fk_status_transitions_from FOREIGN KEY (from_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.status_transitions
    ADD CONSTRAINT fk_status_transitions_to FOREIGN KEY (to_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.role_permissions
    ADD CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id) REFERENCES public.user_roles(role_id) ON DELETE CASCADE;
ALTER TABLE public.role_permissions
    ADD CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES public.permissions(permission_id) ON DELETE CASCADE;
ALTER TABLE public.role_permissions
    ADD CONSTRAINT fk_role_permissions_granted_by FOREIGN KEY (granted_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.system_users
    ADD CONSTRAINT fk_system_users_role FOREIGN KEY (role_id) REFERENCES public.user_roles(role_id) ON DELETE RESTRICT;
ALTER TABLE public.system_users
    ADD CONSTRAINT fk_system_users_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.system_users
    ADD CONSTRAINT fk_system_users_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.user_credentials
    ADD CONSTRAINT fk_user_credentials_user FOREIGN KEY (user_id) REFERENCES public.system_users(user_id) ON DELETE CASCADE;
ALTER TABLE public.user_sessions
    ADD CONSTRAINT fk_user_sessions_user FOREIGN KEY (user_id) REFERENCES public.system_users(user_id) ON DELETE CASCADE;
ALTER TABLE public.tasks
    ADD CONSTRAINT fk_tasks_status FOREIGN KEY (current_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.tasks
    ADD CONSTRAINT fk_tasks_previous_status FOREIGN KEY (previous_status_id) REFERENCES public.status_types(status_id) ON DELETE SET NULL;
ALTER TABLE public.tasks
    ADD CONSTRAINT fk_tasks_created_by_user FOREIGN KEY (created_by_user_id) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.tasks
    ADD CONSTRAINT fk_tasks_last_run FOREIGN KEY (last_run_id) REFERENCES public.task_runs(run_id) ON DELETE SET NULL;
ALTER TABLE public.tasks
    ADD CONSTRAINT fk_tasks_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.tasks
    ADD CONSTRAINT fk_tasks_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.task_status_history
    ADD CONSTRAINT fk_task_status_history_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.task_status_history
    ADD CONSTRAINT fk_task_status_history_from_status FOREIGN KEY (from_status_id) REFERENCES public.status_types(status_id) ON DELETE SET NULL;
ALTER TABLE public.task_status_history
    ADD CONSTRAINT fk_task_status_history_to_status FOREIGN KEY (to_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.task_status_history
    ADD CONSTRAINT fk_task_status_history_changed_by FOREIGN KEY (changed_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.task_runs
    ADD CONSTRAINT fk_task_runs_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.task_runs
    ADD CONSTRAINT fk_task_runs_status FOREIGN KEY (current_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.task_runs
    ADD CONSTRAINT fk_task_runs_provider FOREIGN KEY (provider_id) REFERENCES public.ai_providers(provider_id) ON DELETE SET NULL;
ALTER TABLE public.task_runs
    ADD CONSTRAINT fk_task_runs_model FOREIGN KEY (model_id) REFERENCES public.ai_models(model_id) ON DELETE SET NULL;
ALTER TABLE public.task_runs
    ADD CONSTRAINT fk_task_runs_parent FOREIGN KEY (parent_run_id) REFERENCES public.task_runs(run_id) ON DELETE SET NULL;
ALTER TABLE public.task_runs
    ADD CONSTRAINT fk_task_runs_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.task_runs
    ADD CONSTRAINT fk_task_runs_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.task_run_status_history
    ADD CONSTRAINT fk_task_run_status_history_run FOREIGN KEY (run_id) REFERENCES public.task_runs(run_id) ON DELETE CASCADE;
ALTER TABLE public.task_run_status_history
    ADD CONSTRAINT fk_task_run_status_history_from_status FOREIGN KEY (from_status_id) REFERENCES public.status_types(status_id) ON DELETE SET NULL;
ALTER TABLE public.task_run_status_history
    ADD CONSTRAINT fk_task_run_status_history_to_status FOREIGN KEY (to_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.task_run_status_history
    ADD CONSTRAINT fk_task_run_status_history_changed_by FOREIGN KEY (changed_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.run_steps
    ADD CONSTRAINT fk_run_steps_run FOREIGN KEY (run_id) REFERENCES public.task_runs(run_id) ON DELETE CASCADE;
ALTER TABLE public.run_steps
    ADD CONSTRAINT fk_run_steps_status FOREIGN KEY (current_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.run_steps
    ADD CONSTRAINT fk_run_steps_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.run_steps
    ADD CONSTRAINT fk_run_steps_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.run_step_checkpoints
    ADD CONSTRAINT fk_run_step_checkpoints_step FOREIGN KEY (step_id) REFERENCES public.run_steps(step_id) ON DELETE CASCADE;
ALTER TABLE public.run_step_checkpoints
    ADD CONSTRAINT fk_run_step_checkpoints_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.ai_interactions
    ADD CONSTRAINT fk_ai_interactions_step FOREIGN KEY (step_id) REFERENCES public.run_steps(step_id) ON DELETE CASCADE;
ALTER TABLE public.ai_interactions
    ADD CONSTRAINT fk_ai_interactions_provider FOREIGN KEY (provider_id) REFERENCES public.ai_providers(provider_id) ON DELETE RESTRICT;
ALTER TABLE public.ai_interactions
    ADD CONSTRAINT fk_ai_interactions_model FOREIGN KEY (model_id) REFERENCES public.ai_models(model_id) ON DELETE RESTRICT;
ALTER TABLE public.ai_interactions
    ADD CONSTRAINT fk_ai_interactions_operation FOREIGN KEY (operation_id) REFERENCES public.ai_operations(operation_id) ON DELETE RESTRICT;
ALTER TABLE public.ai_interactions
    ADD CONSTRAINT fk_ai_interactions_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.ai_prompt_templates
    ADD CONSTRAINT fk_ai_prompt_templates_model FOREIGN KEY (model_id) REFERENCES public.ai_models(model_id) ON DELETE SET NULL;
ALTER TABLE public.ai_prompt_templates
    ADD CONSTRAINT fk_ai_prompt_templates_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.ai_prompt_templates
    ADD CONSTRAINT fk_ai_prompt_templates_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.ai_prompt_usage
    ADD CONSTRAINT fk_ai_prompt_usage_template FOREIGN KEY (template_id) REFERENCES public.ai_prompt_templates(template_id) ON DELETE SET NULL;
ALTER TABLE public.ai_prompt_usage
    ADD CONSTRAINT fk_ai_prompt_usage_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.ai_prompt_usage
    ADD CONSTRAINT fk_ai_prompt_usage_run FOREIGN KEY (run_id) REFERENCES public.task_runs(run_id) ON DELETE CASCADE;
ALTER TABLE public.ai_prompt_usage
    ADD CONSTRAINT fk_ai_prompt_usage_interaction FOREIGN KEY (interaction_id) REFERENCES public.ai_interactions(interaction_id) ON DELETE SET NULL;
ALTER TABLE public.ai_prompt_usage
    ADD CONSTRAINT fk_ai_prompt_usage_model FOREIGN KEY (model_id) REFERENCES public.ai_models(model_id) ON DELETE SET NULL;
ALTER TABLE public.ai_prompt_usage
    ADD CONSTRAINT fk_ai_prompt_usage_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.human_validations
    ADD CONSTRAINT fk_human_validations_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.human_validations
    ADD CONSTRAINT fk_human_validations_run FOREIGN KEY (run_id) REFERENCES public.task_runs(run_id) ON DELETE CASCADE;
ALTER TABLE public.human_validations
    ADD CONSTRAINT fk_human_validations_step FOREIGN KEY (step_id) REFERENCES public.run_steps(step_id) ON DELETE CASCADE;
ALTER TABLE public.human_validations
    ADD CONSTRAINT fk_human_validations_status FOREIGN KEY (current_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.human_validations
    ADD CONSTRAINT fk_human_validations_requested_by FOREIGN KEY (requested_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.human_validations
    ADD CONSTRAINT fk_human_validations_parent FOREIGN KEY (parent_validation_id) REFERENCES public.human_validations(validation_id) ON DELETE SET NULL;
ALTER TABLE public.human_validations
    ADD CONSTRAINT fk_human_validations_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.human_validations
    ADD CONSTRAINT fk_human_validations_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.human_validation_status_history
    ADD CONSTRAINT fk_human_validation_status_history_validation FOREIGN KEY (validation_id) REFERENCES public.human_validations(validation_id) ON DELETE CASCADE;
ALTER TABLE public.human_validation_status_history
    ADD CONSTRAINT fk_human_validation_status_history_from_status FOREIGN KEY (from_status_id) REFERENCES public.status_types(status_id) ON DELETE SET NULL;
ALTER TABLE public.human_validation_status_history
    ADD CONSTRAINT fk_human_validation_status_history_to_status FOREIGN KEY (to_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.human_validation_status_history
    ADD CONSTRAINT fk_human_validation_status_history_changed_by FOREIGN KEY (changed_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.human_validation_responses
    ADD CONSTRAINT fk_human_validation_responses_validation FOREIGN KEY (validation_id) REFERENCES public.human_validations(validation_id) ON DELETE CASCADE;
ALTER TABLE public.human_validation_responses
    ADD CONSTRAINT fk_human_validation_responses_status FOREIGN KEY (response_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.human_validation_responses
    ADD CONSTRAINT fk_human_validation_responses_validated_by FOREIGN KEY (validated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.human_validation_responses
    ADD CONSTRAINT fk_human_validation_responses_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.validation_actions
    ADD CONSTRAINT fk_validation_actions_validation FOREIGN KEY (validation_id) REFERENCES public.human_validations(validation_id) ON DELETE CASCADE;
ALTER TABLE public.validation_actions
    ADD CONSTRAINT fk_validation_actions_status FOREIGN KEY (action_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.validation_actions
    ADD CONSTRAINT fk_validation_actions_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.validation_actions
    ADD CONSTRAINT fk_validation_actions_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.pull_requests
    ADD CONSTRAINT fk_pull_requests_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.pull_requests
    ADD CONSTRAINT fk_pull_requests_run FOREIGN KEY (run_id) REFERENCES public.task_runs(run_id) ON DELETE SET NULL;
ALTER TABLE public.pull_requests
    ADD CONSTRAINT fk_pull_requests_status FOREIGN KEY (current_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.pull_requests
    ADD CONSTRAINT fk_pull_requests_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.pull_requests
    ADD CONSTRAINT fk_pull_requests_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.test_results
    ADD CONSTRAINT fk_test_results_run FOREIGN KEY (run_id) REFERENCES public.task_runs(run_id) ON DELETE CASCADE;
ALTER TABLE public.test_results
    ADD CONSTRAINT fk_test_results_status FOREIGN KEY (current_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.test_results
    ADD CONSTRAINT fk_test_results_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.performance_metrics
    ADD CONSTRAINT fk_performance_metrics_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.performance_metrics
    ADD CONSTRAINT fk_performance_metrics_run FOREIGN KEY (run_id) REFERENCES public.task_runs(run_id) ON DELETE CASCADE;
ALTER TABLE public.performance_metrics
    ADD CONSTRAINT fk_performance_metrics_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.workflow_queue
    ADD CONSTRAINT fk_workflow_queue_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE SET NULL;
ALTER TABLE public.workflow_queue
    ADD CONSTRAINT fk_workflow_queue_status FOREIGN KEY (current_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.workflow_queue
    ADD CONSTRAINT fk_workflow_queue_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.workflow_queue
    ADD CONSTRAINT fk_workflow_queue_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.workflow_reactivations
    ADD CONSTRAINT fk_workflow_reactivations_workflow FOREIGN KEY (workflow_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.workflow_reactivations
    ADD CONSTRAINT fk_workflow_reactivations_status FOREIGN KEY (current_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
ALTER TABLE public.workflow_reactivations
    ADD CONSTRAINT fk_workflow_reactivations_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.workflow_reactivations
    ADD CONSTRAINT fk_workflow_reactivations_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.workflow_locks
    ADD CONSTRAINT fk_workflow_locks_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.workflow_locks
    ADD CONSTRAINT fk_workflow_locks_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.workflow_locks
    ADD CONSTRAINT fk_workflow_locks_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.workflow_cooldowns
    ADD CONSTRAINT fk_workflow_cooldowns_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.workflow_cooldowns
    ADD CONSTRAINT fk_workflow_cooldowns_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.workflow_cooldowns
    ADD CONSTRAINT fk_workflow_cooldowns_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.code_quality_feedback
    ADD CONSTRAINT fk_code_quality_feedback_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.code_quality_feedback
    ADD CONSTRAINT fk_code_quality_feedback_run FOREIGN KEY (run_id) REFERENCES public.task_runs(run_id) ON DELETE CASCADE;
ALTER TABLE public.code_quality_feedback
    ADD CONSTRAINT fk_code_quality_feedback_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.task_context_memory
    ADD CONSTRAINT fk_task_context_memory_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.task_context_memory
    ADD CONSTRAINT fk_task_context_memory_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.task_update_triggers
    ADD CONSTRAINT fk_task_update_triggers_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.task_update_triggers
    ADD CONSTRAINT fk_task_update_triggers_new_run FOREIGN KEY (new_run_id) REFERENCES public.task_runs(run_id) ON DELETE SET NULL;
ALTER TABLE public.task_update_triggers
    ADD CONSTRAINT fk_task_update_triggers_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.monday_updates_history
    ADD CONSTRAINT fk_monday_updates_history_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE SET NULL;
ALTER TABLE public.monday_updates_history
    ADD CONSTRAINT fk_monday_updates_history_reactivation FOREIGN KEY (reactivation_id) REFERENCES public.workflow_reactivations(reactivation_id) ON DELETE SET NULL;
ALTER TABLE public.monday_updates_history
    ADD CONSTRAINT fk_monday_updates_history_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.message_embeddings
    ADD CONSTRAINT fk_message_embeddings_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE SET NULL;
ALTER TABLE public.message_embeddings
    ADD CONSTRAINT fk_message_embeddings_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.project_context_embeddings
    ADD CONSTRAINT fk_project_context_embeddings_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.system_config
    ADD CONSTRAINT fk_system_config_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.system_config
    ADD CONSTRAINT fk_system_config_updated_by FOREIGN KEY (updated_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.rate_limits
    ADD CONSTRAINT fk_rate_limits_user FOREIGN KEY (user_id) REFERENCES public.system_users(user_id) ON DELETE CASCADE;
ALTER TABLE public.rate_limits
    ADD CONSTRAINT fk_rate_limits_created_by FOREIGN KEY (created_by) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE logs.application_logs
    ADD CONSTRAINT fk_logs_application_task FOREIGN KEY (task_id) REFERENCES public.tasks(task_id) ON DELETE SET NULL;
ALTER TABLE logs.application_logs
    ADD CONSTRAINT fk_logs_application_run FOREIGN KEY (run_id) REFERENCES public.task_runs(run_id) ON DELETE SET NULL;
ALTER TABLE logs.application_logs
    ADD CONSTRAINT fk_logs_application_step FOREIGN KEY (step_id) REFERENCES public.run_steps(step_id) ON DELETE SET NULL;
ALTER TABLE logs.application_logs
    ADD CONSTRAINT fk_logs_application_user FOREIGN KEY (user_id) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE logs.audit_logs
    ADD CONSTRAINT fk_logs_audit_user FOREIGN KEY (user_id) REFERENCES public.system_users(user_id) ON DELETE SET NULL;
ALTER TABLE logs.audit_logs
    ADD CONSTRAINT fk_logs_audit_role FOREIGN KEY (role_id) REFERENCES public.user_roles(role_id) ON DELETE SET NULL;
ALTER TABLE logs.webhook_events
    ADD CONSTRAINT fk_logs_webhook_task FOREIGN KEY (related_task_id) REFERENCES public.tasks(task_id) ON DELETE SET NULL;
ALTER TABLE logs.webhook_events
    ADD CONSTRAINT fk_logs_webhook_status FOREIGN KEY (processing_status_id) REFERENCES public.status_types(status_id) ON DELETE RESTRICT;
CREATE TRIGGER trg_tasks_updated_at BEFORE UPDATE ON public.tasks
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER trg_tasks_validate_status BEFORE UPDATE ON public.tasks
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.validate_status_transition();
CREATE TRIGGER trg_tasks_log_status_change AFTER UPDATE ON public.tasks
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.log_status_change_to_history();
CREATE TRIGGER trg_tasks_prevent_deleted_modification BEFORE UPDATE ON public.tasks
FOR EACH ROW EXECUTE FUNCTION public.prevent_deleted_modification();
CREATE TRIGGER trg_task_runs_updated_at BEFORE UPDATE ON public.task_runs
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER trg_task_runs_validate_status BEFORE UPDATE ON public.task_runs
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.validate_status_transition();
CREATE TRIGGER trg_task_runs_log_status_change AFTER UPDATE ON public.task_runs
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.log_status_change_to_history();
CREATE TRIGGER trg_human_validations_updated_at BEFORE UPDATE ON public.human_validations
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER trg_human_validations_validate_status BEFORE UPDATE ON public.human_validations
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.validate_status_transition();
CREATE TRIGGER trg_human_validations_log_status_change AFTER UPDATE ON public.human_validations
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.log_status_change_to_history();
CREATE TRIGGER trg_system_users_updated_at BEFORE UPDATE ON public.system_users
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER trg_system_config_updated_at BEFORE UPDATE ON public.system_config
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER trg_workflow_queue_updated_at BEFORE UPDATE ON public.workflow_queue
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
CREATE TRIGGER trg_workflow_reactivations_updated_at BEFORE UPDATE ON public.workflow_reactivations
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

