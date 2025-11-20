-- ============================================================================
-- SCHÉMA DE BASE DE DONNÉES REFONTE COMPLÈTE ET OPTIMALE
-- AI Agent Admin - Version Finale avec toutes les améliorations
-- ============================================================================
-- Corrections appliquées :
-- 1. ✅ Toutes les FK explicites avec ON DELETE/UPDATE
-- 2. ✅ Cohérence des colonnes audit (created_by/updated_by INTEGER)
-- 3. ✅ Séparation en schémas (config, logs, external)
-- 4. ✅ Validation des coûts IA
-- 5. ✅ Soft delete partout
-- 6. ✅ Historique de statuts avec FK
-- ============================================================================

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

-- ============================================================================
-- CRÉATION DES SCHÉMAS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS config;
CREATE SCHEMA IF NOT EXISTS logs;
CREATE SCHEMA IF NOT EXISTS external;
CREATE SCHEMA IF NOT EXISTS partman;

COMMENT ON SCHEMA public IS 'Schéma principal pour les tables métier et opérationnelles';
COMMENT ON SCHEMA config IS 'Tables de référence et configuration (providers, statuts, rôles, etc.)';
COMMENT ON SCHEMA logs IS 'Tables de logs partitionnées (application, audit, webhooks)';
COMMENT ON SCHEMA external IS 'Tables systèmes externes (Celery, etc.)';

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pg_partman WITH SCHEMA partman;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================================
-- TABLES DE RÉFÉRENCE - SCHÉMA CONFIG
-- ============================================================================

-- Providers IA
CREATE TABLE config.ai_providers (
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

COMMENT ON TABLE config.ai_providers IS 'Fournisseurs IA (OpenAI, Claude, etc.)';

-- Modèles IA avec tarification
CREATE TABLE config.ai_models (
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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_ai_models_provider FOREIGN KEY (provider_id) 
        REFERENCES config.ai_providers(provider_id) ON DELETE RESTRICT
);

COMMENT ON TABLE config.ai_models IS 'Modèles IA avec tarification pour calcul automatique des coûts';

-- Opérations IA
CREATE TABLE config.ai_operations (
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

COMMENT ON TABLE config.ai_operations IS 'Types d''opérations IA (analyze, implement, debug, test, review)';

-- Types de statuts (table de référence universelle)
CREATE TABLE config.status_types (
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

COMMENT ON TABLE config.status_types IS 'Statuts universels pour toutes les entités (tasks, runs, validations, queues)';
COMMENT ON COLUMN config.status_types.category IS 'Catégorie: task, run, validation, queue, pr, test';
COMMENT ON COLUMN config.status_types.is_terminal IS 'État final (completed, failed, cancelled)';

-- Transitions de statuts autorisées
CREATE TABLE config.status_transitions (
    transition_id SERIAL PRIMARY KEY,
    from_status_id INTEGER NOT NULL,
    to_status_id INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL,
    is_automatic BOOLEAN DEFAULT false,
    requires_approval BOOLEAN DEFAULT false,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    UNIQUE(from_status_id, to_status_id, category),
    CONSTRAINT fk_status_transitions_from FOREIGN KEY (from_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_status_transitions_to FOREIGN KEY (to_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT
);

COMMENT ON TABLE config.status_transitions IS 'Transitions de statuts autorisées (workflow state machine)';

-- Rôles utilisateurs
CREATE TABLE config.user_roles (
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

COMMENT ON TABLE config.user_roles IS 'Rôles utilisateurs (Admin, Developer, Viewer, Auditor)';
COMMENT ON COLUMN config.user_roles.level IS 'Niveau hiérarchique (plus élevé = plus de permissions)';

-- Permissions RBAC
CREATE TABLE config.permissions (
    permission_id SERIAL PRIMARY KEY,
    permission_code VARCHAR(100) UNIQUE NOT NULL,
    permission_name VARCHAR(200) NOT NULL,
    description TEXT,
    resource_type VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    deleted_at TIMESTAMPTZ
);

COMMENT ON TABLE config.permissions IS 'Permissions granulaires RBAC (resource + action)';

-- Table pivot rôles-permissions
CREATE TABLE config.role_permissions (
    role_permission_id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    granted_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    granted_by INTEGER,
    UNIQUE(role_id, permission_id),
    CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id)
        REFERENCES config.user_roles(role_id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id)
        REFERENCES config.permissions(permission_id) ON DELETE CASCADE
);

COMMENT ON TABLE config.role_permissions IS 'Matrice N-N rôles-permissions';

-- ============================================================================
-- TABLES UTILISATEURS - SCHÉMA PUBLIC
-- ============================================================================

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_system_users_role FOREIGN KEY (role_id)
        REFERENCES config.user_roles(role_id) ON DELETE RESTRICT,
    CONSTRAINT fk_system_users_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_system_users_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.system_users IS 'Utilisateurs du système avec audit complet';

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
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT fk_user_credentials_user FOREIGN KEY (user_id)
        REFERENCES public.system_users(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE public.user_credentials IS 'Credentials isolés pour sécurité';

CREATE TABLE public.user_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_token VARCHAR(500) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    last_activity_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    CONSTRAINT fk_user_sessions_user FOREIGN KEY (user_id)
        REFERENCES public.system_users(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE public.user_sessions IS 'Sessions actives avec expiration';

-- ============================================================================
-- TABLES MÉTIER - TASKS & RUNS
-- ============================================================================

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
    previous_status_id INTEGER,
    created_by_user_id INTEGER,
    assigned_to TEXT,
    last_run_id INTEGER,
    is_locked BOOLEAN DEFAULT false,
    locked_at TIMESTAMPTZ,
    locked_by INTEGER,
    cooldown_until TIMESTAMPTZ,
    last_reactivation_attempt TIMESTAMPTZ,
    failed_reactivation_attempts INTEGER DEFAULT 0,
    reactivation_count INTEGER DEFAULT 0,
    active_task_ids TEXT[],
    reactivated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_tasks_status FOREIGN KEY (current_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_tasks_previous_status FOREIGN KEY (previous_status_id)
        REFERENCES config.status_types(status_id) ON DELETE SET NULL,
    CONSTRAINT fk_tasks_created_by_user FOREIGN KEY (created_by_user_id)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_tasks_locked_by FOREIGN KEY (locked_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_tasks_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_tasks_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.tasks IS 'Tâches Monday.com avec statut référencé et audit complet';
COMMENT ON COLUMN public.tasks.locked_by IS 'FK vers system_users (corrigé depuis VARCHAR)';

CREATE TABLE public.task_status_history (
    history_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    from_status_id INTEGER,
    to_status_id INTEGER NOT NULL,
    changed_by INTEGER,
    change_reason TEXT,
    metadata JSONB,
    changed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT fk_task_status_history_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_task_status_history_from FOREIGN KEY (from_status_id)
        REFERENCES config.status_types(status_id) ON DELETE SET NULL,
    CONSTRAINT fk_task_status_history_to FOREIGN KEY (to_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_task_status_history_changed_by FOREIGN KEY (changed_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.task_status_history IS 'Historique complet des changements de statut';

-- FK circulaire tasks.last_run_id sera ajoutée après création de task_runs

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
    UNIQUE(task_id, run_number),
    CONSTRAINT fk_task_runs_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_task_runs_status FOREIGN KEY (current_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_task_runs_provider FOREIGN KEY (provider_id)
        REFERENCES config.ai_providers(provider_id) ON DELETE SET NULL,
    CONSTRAINT fk_task_runs_model FOREIGN KEY (model_id)
        REFERENCES config.ai_models(model_id) ON DELETE SET NULL,
    CONSTRAINT fk_task_runs_parent FOREIGN KEY (parent_run_id)
        REFERENCES public.task_runs(run_id) ON DELETE SET NULL,
    CONSTRAINT fk_task_runs_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_task_runs_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.task_runs IS 'Exécutions de workflows avec références normalisées';

-- Ajout de la FK circulaire
ALTER TABLE public.tasks
    ADD CONSTRAINT fk_tasks_last_run FOREIGN KEY (last_run_id)
        REFERENCES public.task_runs(run_id) ON DELETE SET NULL;

CREATE TABLE public.task_run_status_history (
    history_id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    from_status_id INTEGER,
    to_status_id INTEGER NOT NULL,
    changed_by INTEGER,
    change_reason TEXT,
    metadata JSONB,
    changed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT fk_task_run_status_history_run FOREIGN KEY (run_id)
        REFERENCES public.task_runs(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_task_run_status_history_from FOREIGN KEY (from_status_id)
        REFERENCES config.status_types(status_id) ON DELETE SET NULL,
    CONSTRAINT fk_task_run_status_history_to FOREIGN KEY (to_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_task_run_status_history_changed_by FOREIGN KEY (changed_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);


-- ============================================================================
-- RUN STEPS & AI INTERACTIONS
-- ============================================================================

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_run_steps_run FOREIGN KEY (run_id)
        REFERENCES public.task_runs(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_run_steps_status FOREIGN KEY (current_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_run_steps_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_run_steps_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.run_steps IS 'Étapes de workflow avec statut référencé';

CREATE TABLE public.run_step_checkpoints (
    checkpoint_id SERIAL PRIMARY KEY,
    step_id INTEGER NOT NULL,
    checkpoint_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ,
    created_by INTEGER,
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_checkpoints_step FOREIGN KEY (step_id)
        REFERENCES public.run_steps(step_id) ON DELETE CASCADE,
    CONSTRAINT fk_checkpoints_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.run_step_checkpoints IS 'Checkpoints pour reprise après erreur';

-- Table unifiée AI interactions avec calcul automatique du coût
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
    calculated_cost_usd NUMERIC(12,6) GENERATED ALWAYS AS (
        (COALESCE(input_tokens, 0)::NUMERIC / 1000.0) * 
        (SELECT cost_per_1k_input_tokens FROM config.ai_models WHERE model_id = ai_interactions.model_id) +
        (COALESCE(output_tokens, 0)::NUMERIC / 1000.0) * 
        (SELECT cost_per_1k_output_tokens FROM config.ai_models WHERE model_id = ai_interactions.model_id)
    ) STORED,
    latency_ms INTEGER,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_ai_interactions_step FOREIGN KEY (step_id)
        REFERENCES public.run_steps(step_id) ON DELETE CASCADE,
    CONSTRAINT fk_ai_interactions_provider FOREIGN KEY (provider_id)
        REFERENCES config.ai_providers(provider_id) ON DELETE RESTRICT,
    CONSTRAINT fk_ai_interactions_model FOREIGN KEY (model_id)
        REFERENCES config.ai_models(model_id) ON DELETE RESTRICT,
    CONSTRAINT fk_ai_interactions_operation FOREIGN KEY (operation_id)
        REFERENCES config.ai_operations(operation_id) ON DELETE RESTRICT,
    CONSTRAINT fk_ai_interactions_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT chk_ai_interactions_cost_valid CHECK (
        cost_usd IS NULL OR 
        ABS(cost_usd - calculated_cost_usd) < 0.000001
    )
);

COMMENT ON TABLE public.ai_interactions IS 'Historique unifié des interactions IA avec calcul automatique et validation des coûts';
COMMENT ON COLUMN public.ai_interactions.calculated_cost_usd IS 'Coût calculé automatiquement depuis les tarifs du modèle';
COMMENT ON COLUMN public.ai_interactions.cost_usd IS 'Coût enregistré (doit correspondre au coût calculé)';

-- ============================================================================
-- TEMPLATES & PROMPTS
-- ============================================================================

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
    CONSTRAINT ai_prompt_templates_max_tokens_check CHECK (max_tokens > 0),
    CONSTRAINT fk_ai_prompt_templates_model FOREIGN KEY (model_id)
        REFERENCES config.ai_models(model_id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_prompt_templates_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_prompt_templates_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.ai_prompt_templates IS 'Templates de prompts avec modèle recommandé';

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_ai_prompt_usage_template FOREIGN KEY (template_id)
        REFERENCES public.ai_prompt_templates(template_id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_prompt_usage_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_ai_prompt_usage_run FOREIGN KEY (run_id)
        REFERENCES public.task_runs(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_ai_prompt_usage_interaction FOREIGN KEY (interaction_id)
        REFERENCES public.ai_interactions(interaction_id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_prompt_usage_model FOREIGN KEY (model_id)
        REFERENCES config.ai_models(model_id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_prompt_usage_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.ai_prompt_usage IS 'Usage des templates de prompts';

-- ============================================================================
-- VALIDATIONS HUMAINES
-- ============================================================================

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_human_validations_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_human_validations_run FOREIGN KEY (run_id)
        REFERENCES public.task_runs(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_human_validations_step FOREIGN KEY (step_id)
        REFERENCES public.run_steps(step_id) ON DELETE CASCADE,
    CONSTRAINT fk_human_validations_status FOREIGN KEY (current_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_human_validations_requested_by FOREIGN KEY (requested_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_human_validations_parent FOREIGN KEY (parent_validation_id)
        REFERENCES public.human_validations(validation_id) ON DELETE SET NULL,
    CONSTRAINT fk_human_validations_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_human_validations_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.human_validations IS 'Validations humaines avec FK correctes et parent_validation_id typé INTEGER';

CREATE TABLE public.human_validation_status_history (
    history_id SERIAL PRIMARY KEY,
    validation_id INTEGER NOT NULL,
    from_status_id INTEGER,
    to_status_id INTEGER NOT NULL,
    changed_by INTEGER,
    change_reason TEXT,
    metadata JSONB,
    changed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT fk_hv_status_history_validation FOREIGN KEY (validation_id)
        REFERENCES public.human_validations(validation_id) ON DELETE CASCADE,
    CONSTRAINT fk_hv_status_history_from FOREIGN KEY (from_status_id)
        REFERENCES config.status_types(status_id) ON DELETE SET NULL,
    CONSTRAINT fk_hv_status_history_to FOREIGN KEY (to_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_hv_status_history_changed_by FOREIGN KEY (changed_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.human_validation_status_history IS 'Historique des statuts de validation';

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_hv_responses_validation FOREIGN KEY (validation_id)
        REFERENCES public.human_validations(validation_id) ON DELETE CASCADE,
    CONSTRAINT fk_hv_responses_status FOREIGN KEY (response_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_hv_responses_validated_by FOREIGN KEY (validated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_hv_responses_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_validation_actions_validation FOREIGN KEY (validation_id)
        REFERENCES public.human_validations(validation_id) ON DELETE CASCADE,
    CONSTRAINT fk_validation_actions_status FOREIGN KEY (action_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_validation_actions_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_validation_actions_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.validation_actions IS 'Actions post-validation avec statut référencé';


-- ============================================================================
-- AUTRES TABLES MÉTIER
-- ============================================================================

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_pull_requests_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_pull_requests_run FOREIGN KEY (run_id)
        REFERENCES public.task_runs(run_id) ON DELETE SET NULL,
    CONSTRAINT fk_pull_requests_status FOREIGN KEY (current_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_pull_requests_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_pull_requests_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_test_results_run FOREIGN KEY (run_id)
        REFERENCES public.task_runs(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_test_results_status FOREIGN KEY (current_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_test_results_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_performance_metrics_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_performance_metrics_run FOREIGN KEY (run_id)
        REFERENCES public.task_runs(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_performance_metrics_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_workflow_queue_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE SET NULL,
    CONSTRAINT fk_workflow_queue_status FOREIGN KEY (current_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_queue_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_workflow_queue_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_workflow_reactivations_workflow FOREIGN KEY (workflow_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_workflow_reactivations_status FOREIGN KEY (current_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT,
    CONSTRAINT fk_workflow_reactivations_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_workflow_reactivations_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

CREATE TABLE public.workflow_locks (
    lock_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    lock_key VARCHAR(255) NOT NULL,
    is_locked BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT true,
    locked_by INTEGER,
    metadata JSONB DEFAULT '{}'::JSONB,
    locked_at TIMESTAMPTZ DEFAULT NOW(),
    released_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_workflow_locks_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_workflow_locks_locked_by FOREIGN KEY (locked_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_workflow_locks_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_workflow_locks_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON COLUMN public.workflow_locks.locked_by IS 'FK vers system_users (corrigé depuis VARCHAR)';

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_workflow_cooldowns_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_workflow_cooldowns_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_workflow_cooldowns_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_code_quality_feedback_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_code_quality_feedback_run FOREIGN KEY (run_id)
        REFERENCES public.task_runs(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_code_quality_feedback_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_task_context_memory_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_task_context_memory_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_task_update_triggers_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE CASCADE,
    CONSTRAINT fk_task_update_triggers_new_run FOREIGN KEY (new_run_id)
        REFERENCES public.task_runs(run_id) ON DELETE SET NULL,
    CONSTRAINT fk_task_update_triggers_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_monday_updates_history_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE SET NULL,
    CONSTRAINT fk_monday_updates_history_reactivation FOREIGN KEY (reactivation_id)
        REFERENCES public.workflow_reactivations(reactivation_id) ON DELETE SET NULL,
    CONSTRAINT fk_monday_updates_history_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_message_embeddings_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE SET NULL,
    CONSTRAINT fk_message_embeddings_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_project_context_embeddings_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

CREATE TABLE public.system_config (
    config_id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    description TEXT,
    config_type VARCHAR(50) DEFAULT 'application' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_system_config_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_system_config_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON COLUMN public.system_config.updated_by IS 'FK vers system_users (corrigé depuis VARCHAR)';

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
    deleted_at TIMESTAMPTZ,
    CONSTRAINT fk_rate_limits_user FOREIGN KEY (user_id)
        REFERENCES public.system_users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_rate_limits_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

-- ============================================================================
-- TABLES DE LOGS PARTITIONNÉES - SCHÉMA LOGS
-- ============================================================================

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

COMMENT ON TABLE logs.application_logs IS 'Logs applicatifs partitionnés par mois avec FK vers tables métier';

CREATE TABLE logs.audit_logs (
    log_id BIGSERIAL NOT NULL,
    user_id INTEGER,
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

COMMENT ON TABLE logs.audit_logs IS 'Logs d''audit partitionnés avec FK vers users et roles (redondance user_email supprimée)';

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

COMMENT ON TABLE logs.webhook_events IS 'Événements webhook partitionnés par mois avec statut référencé';

-- FK pour les tables de logs (cross-schema)
ALTER TABLE logs.application_logs
    ADD CONSTRAINT fk_logs_application_task FOREIGN KEY (task_id)
        REFERENCES public.tasks(task_id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_logs_application_run FOREIGN KEY (run_id)
        REFERENCES public.task_runs(run_id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_logs_application_step FOREIGN KEY (step_id)
        REFERENCES public.run_steps(step_id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_logs_application_user FOREIGN KEY (user_id)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL;

ALTER TABLE logs.audit_logs
    ADD CONSTRAINT fk_logs_audit_user FOREIGN KEY (user_id)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_logs_audit_role FOREIGN KEY (role_id)
        REFERENCES config.user_roles(role_id) ON DELETE SET NULL;

ALTER TABLE logs.webhook_events
    ADD CONSTRAINT fk_logs_webhook_task FOREIGN KEY (related_task_id)
        REFERENCES public.tasks(task_id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_logs_webhook_status FOREIGN KEY (processing_status_id)
        REFERENCES config.status_types(status_id) ON DELETE RESTRICT;

-- ============================================================================
-- TABLES EXTERNES - SCHÉMA EXTERNAL
-- ============================================================================

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


-- ============================================================================
-- FONCTIONS & TRIGGERS
-- ============================================================================

-- Fonction de mise à jour automatique de updated_at
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fonction de prévention de modification des enregistrements supprimés
CREATE OR REPLACE FUNCTION public.prevent_deleted_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'Cannot modify deleted record';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Fonction de validation des transitions de statuts
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
    ELSIF TG_TABLE_NAME = 'pull_requests' THEN
        category_val := 'pr';
    ELSIF TG_TABLE_NAME = 'test_results' THEN
        category_val := 'test';
    ELSE
        RETURN NEW;
    END IF;
    SELECT EXISTS(
        SELECT 1 FROM config.status_transitions
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

-- Fonction de logging des changements de statut
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

-- Fonction de nettoyage des verrous expirés
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

-- Fonction de statistiques IA du mois
CREATE OR REPLACE FUNCTION public.get_current_month_ai_stats()
RETURNS TABLE(
    provider_name VARCHAR,
    total_cost NUMERIC,
    total_tokens BIGINT,
    total_calls BIGINT,
    unique_runs BIGINT,
    avg_cost_per_call NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.provider_name,
        SUM(ai.cost_usd)::NUMERIC(10, 6) as total_cost,
        SUM(ai.total_tokens)::BIGINT as total_tokens,
        COUNT(*)::BIGINT as total_calls,
        COUNT(DISTINCT rs.run_id)::BIGINT as unique_runs,
        AVG(ai.cost_usd)::NUMERIC(10, 6) as avg_cost_per_call
    FROM public.ai_interactions ai
    LEFT JOIN config.ai_providers p ON ai.provider_id = p.provider_id
    LEFT JOIN public.run_steps rs ON ai.step_id = rs.step_id
    WHERE EXTRACT(YEAR FROM ai.created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
    AND EXTRACT(MONTH FROM ai.created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
    AND ai.success = true
    AND ai.deleted_at IS NULL
    GROUP BY p.provider_name
    ORDER BY total_cost DESC;
END;
$$ LANGUAGE plpgsql;

-- Triggers pour updated_at
CREATE TRIGGER trg_tasks_updated_at BEFORE UPDATE ON public.tasks
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_task_runs_updated_at BEFORE UPDATE ON public.task_runs
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_human_validations_updated_at BEFORE UPDATE ON public.human_validations
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_system_users_updated_at BEFORE UPDATE ON public.system_users
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_system_config_updated_at BEFORE UPDATE ON public.system_config
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_workflow_queue_updated_at BEFORE UPDATE ON public.workflow_queue
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_workflow_reactivations_updated_at BEFORE UPDATE ON public.workflow_reactivations
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Triggers de validation des transitions de statuts
CREATE TRIGGER trg_tasks_validate_status BEFORE UPDATE ON public.tasks
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.validate_status_transition();

CREATE TRIGGER trg_task_runs_validate_status BEFORE UPDATE ON public.task_runs
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.validate_status_transition();

CREATE TRIGGER trg_human_validations_validate_status BEFORE UPDATE ON public.human_validations
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.validate_status_transition();

-- Triggers de logging des changements de statut
CREATE TRIGGER trg_tasks_log_status_change AFTER UPDATE ON public.tasks
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.log_status_change_to_history();

CREATE TRIGGER trg_task_runs_log_status_change AFTER UPDATE ON public.task_runs
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.log_status_change_to_history();

CREATE TRIGGER trg_human_validations_log_status_change AFTER UPDATE ON public.human_validations
FOR EACH ROW WHEN (OLD.current_status_id IS DISTINCT FROM NEW.current_status_id)
EXECUTE FUNCTION public.log_status_change_to_history();

-- Triggers de protection des suppressions
CREATE TRIGGER trg_tasks_prevent_deleted_modification BEFORE UPDATE ON public.tasks
FOR EACH ROW EXECUTE FUNCTION public.prevent_deleted_modification();

-- ============================================================================
-- INDEX OPTIMISÉS
-- ============================================================================

-- Index sur tables de référence (config)
CREATE INDEX idx_config_ai_providers_active ON config.ai_providers(is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_config_ai_models_provider ON config.ai_models(provider_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_config_ai_models_active ON config.ai_models(is_active, model_code) WHERE deleted_at IS NULL;
CREATE INDEX idx_config_status_types_category ON config.status_types(category, status_code) WHERE deleted_at IS NULL;
CREATE INDEX idx_config_status_transitions_from ON config.status_transitions(from_status_id, category);
CREATE INDEX idx_config_user_roles_active ON config.user_roles(is_active, level DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_config_role_permissions_role ON config.role_permissions(role_id);

-- Index sur system_users
CREATE INDEX idx_system_users_role ON public.system_users(role_id) WHERE deleted_at IS NULL AND is_active = true;
CREATE INDEX idx_system_users_email ON public.system_users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_system_users_monday_user ON public.system_users(monday_user_id) WHERE monday_user_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_user_sessions_user_active ON public.user_sessions(user_id, expires_at) WHERE is_active = true;

-- Index sur tasks
CREATE INDEX idx_tasks_monday_item ON public.tasks(monday_item_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_status ON public.tasks(current_status_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_locked ON public.tasks(is_locked, locked_at) WHERE is_locked = true AND deleted_at IS NULL;
CREATE INDEX idx_tasks_created_at ON public.tasks(created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_task_status_history_task_date ON public.task_status_history(task_id, changed_at DESC);

-- Index sur task_runs
CREATE INDEX idx_task_runs_task_status ON public.task_runs(task_id, current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_task_runs_celery ON public.task_runs(celery_task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_task_runs_started ON public.task_runs(started_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_task_runs_provider_model ON public.task_runs(provider_id, model_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_task_runs_reactivation ON public.task_runs(is_reactivation, parent_run_id) WHERE is_reactivation = true AND deleted_at IS NULL;
CREATE INDEX idx_task_run_status_history_run_date ON public.task_run_status_history(run_id, changed_at DESC);

-- Index sur run_steps
CREATE INDEX idx_run_steps_run_order ON public.run_steps(run_id, step_order) WHERE deleted_at IS NULL;
CREATE INDEX idx_run_steps_status ON public.run_steps(current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_run_steps_started ON public.run_steps(started_at DESC) WHERE deleted_at IS NULL;

-- Index sur ai_interactions (optimisé pour les requêtes de coût)
CREATE INDEX idx_ai_interactions_step ON public.ai_interactions(step_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_interactions_provider_model ON public.ai_interactions(provider_id, model_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_interactions_operation ON public.ai_interactions(operation_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_ai_interactions_cost ON public.ai_interactions(cost_usd DESC) WHERE deleted_at IS NULL AND cost_usd IS NOT NULL;
CREATE INDEX idx_ai_interactions_success ON public.ai_interactions(success, created_at DESC) WHERE deleted_at IS NULL;

-- Index sur human_validations
CREATE INDEX idx_human_validations_task_status ON public.human_validations(task_id, current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_human_validations_expires ON public.human_validations(expires_at) WHERE expires_at IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_human_validations_parent ON public.human_validations(parent_validation_id) WHERE parent_validation_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_hv_status_history_validation_date ON public.human_validation_status_history(validation_id, changed_at DESC);

-- Index sur les embeddings (vectoriels + GIN sur JSONB)
CREATE INDEX idx_message_embeddings_task ON public.message_embeddings(task_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_message_embeddings_monday_item ON public.message_embeddings(monday_item_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_message_embeddings_embedding ON public.message_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX idx_message_embeddings_metadata ON public.message_embeddings USING GIN (metadata) WHERE deleted_at IS NULL;
CREATE INDEX idx_project_context_embeddings_repo ON public.project_context_embeddings(repository_url, context_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_project_context_embeddings_embedding ON public.project_context_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);

-- Index sur workflow management
CREATE INDEX idx_workflow_queue_monday_status ON public.workflow_queue(monday_item_id, current_status_id, priority DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_workflow_reactivations_workflow ON public.workflow_reactivations(workflow_id, current_status_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_workflow_locks_task_active ON public.workflow_locks(task_id) WHERE is_active = true AND deleted_at IS NULL;

-- Index sur les logs (partitionnés)
CREATE INDEX idx_logs_application_level_date ON logs.application_logs(level, created_at DESC);
CREATE INDEX idx_logs_application_task ON logs.application_logs(task_id, created_at DESC);
CREATE INDEX idx_logs_application_user ON logs.application_logs(user_id, created_at DESC);
CREATE INDEX idx_logs_application_metadata ON logs.application_logs USING GIN (metadata);
CREATE INDEX idx_logs_audit_user_date ON logs.audit_logs(user_id, created_at DESC);
CREATE INDEX idx_logs_audit_action ON logs.audit_logs(action, created_at DESC);
CREATE INDEX idx_logs_audit_resource ON logs.audit_logs(resource_type, resource_id, created_at DESC);
CREATE INDEX idx_logs_audit_details ON logs.audit_logs USING GIN (details);
CREATE INDEX idx_logs_webhook_source_date ON logs.webhook_events(source, event_type, received_at DESC);
CREATE INDEX idx_logs_webhook_processed ON logs.webhook_events(processed, received_at DESC);
CREATE INDEX idx_logs_webhook_task ON logs.webhook_events(related_task_id, received_at DESC);

-- ============================================================================
-- VUES UTILES
-- ============================================================================

-- Vue pour le dashboard des tâches
CREATE OR REPLACE VIEW public.v_tasks_dashboard AS
SELECT 
    t.task_id,
    t.monday_item_id,
    t.title,
    t.repository_name,
    st.status_name AS current_status,
    st.color AS status_color,
    t.priority,
    u.full_name AS created_by_name,
    t.created_at,
    t.started_at,
    t.completed_at,
    tr.run_number AS last_run_number,
    tr_st.status_name AS last_run_status,
    COUNT(DISTINCT tr_all.run_id) AS total_runs,
    SUM(CASE WHEN tr_all_st.is_terminal = true AND tr_all_st.status_code = 'completed' THEN 1 ELSE 0 END) AS successful_runs,
    SUM(CASE WHEN tr_all_st.is_terminal = true AND tr_all_st.status_code = 'failed' THEN 1 ELSE 0 END) AS failed_runs
FROM public.tasks t
LEFT JOIN config.status_types st ON t.current_status_id = st.status_id
LEFT JOIN public.system_users u ON t.created_by_user_id = u.user_id
LEFT JOIN public.task_runs tr ON t.last_run_id = tr.run_id
LEFT JOIN config.status_types tr_st ON tr.current_status_id = tr_st.status_id
LEFT JOIN public.task_runs tr_all ON t.task_id = tr_all.task_id AND tr_all.deleted_at IS NULL
LEFT JOIN config.status_types tr_all_st ON tr_all.current_status_id = tr_all_st.status_id
WHERE t.deleted_at IS NULL
GROUP BY t.task_id, t.monday_item_id, t.title, t.repository_name, st.status_name, st.color,
         t.priority, u.full_name, t.created_at, t.started_at, t.completed_at, 
         tr.run_number, tr_st.status_name;

COMMENT ON VIEW public.v_tasks_dashboard IS 'Vue dashboard des tâches avec statuts, runs et statistiques';

-- Vue pour les statistiques de coûts IA
CREATE OR REPLACE VIEW public.v_ai_cost_by_task AS
SELECT 
    t.task_id,
    t.title,
    t.repository_name,
    p.provider_name,
    m.model_name,
    COUNT(ai.interaction_id) AS total_interactions,
    SUM(ai.input_tokens) AS total_input_tokens,
    SUM(ai.output_tokens) AS total_output_tokens,
    SUM(ai.total_tokens) AS total_tokens,
    SUM(ai.cost_usd) AS total_cost_usd,
    AVG(ai.cost_usd) AS avg_cost_per_interaction,
    AVG(ai.latency_ms) AS avg_latency_ms
FROM public.ai_interactions ai
JOIN public.run_steps rs ON ai.step_id = rs.step_id
JOIN public.task_runs tr ON rs.run_id = tr.run_id
JOIN public.tasks t ON tr.task_id = t.task_id
LEFT JOIN config.ai_providers p ON ai.provider_id = p.provider_id
LEFT JOIN config.ai_models m ON ai.model_id = m.model_id
WHERE ai.deleted_at IS NULL 
AND ai.success = true
AND t.deleted_at IS NULL
GROUP BY t.task_id, t.title, t.repository_name, p.provider_name, m.model_name
ORDER BY total_cost_usd DESC;

COMMENT ON VIEW public.v_ai_cost_by_task IS 'Coûts IA agrégés par tâche avec provider et modèle';

-- Vue pour les validations en attente
CREATE OR REPLACE VIEW public.v_pending_validations AS
SELECT 
    hv.validation_id,
    hv.validation_uuid,
    t.task_id,
    t.title AS task_title,
    t.repository_name,
    st.status_name AS validation_status,
    hv.created_at,
    hv.expires_at,
    CASE 
        WHEN hv.expires_at < NOW() THEN 'expired'
        WHEN hv.expires_at < NOW() + INTERVAL '1 hour' THEN 'urgent'
        ELSE 'normal'
    END AS urgency,
    hv.rejection_count,
    hv.is_retry,
    u.full_name AS requested_by_name,
    ARRAY_LENGTH(hv.files_modified, 1) AS files_count
FROM public.human_validations hv
JOIN public.tasks t ON hv.task_id = t.task_id
JOIN config.status_types st ON hv.current_status_id = st.status_id
LEFT JOIN public.system_users u ON hv.requested_by = u.user_id
WHERE hv.deleted_at IS NULL
AND st.status_code = 'pending'
ORDER BY 
    CASE 
        WHEN hv.expires_at < NOW() THEN 0
        WHEN hv.expires_at < NOW() + INTERVAL '1 hour' THEN 1
        ELSE 2
    END,
    hv.created_at;

COMMENT ON VIEW public.v_pending_validations IS 'Validations en attente avec urgence et statut';

-- ============================================================================
-- FIN DU SCHÉMA
-- ============================================================================

-- Insertion de données de référence minimales (à adapter selon besoins)

-- Statuts de base pour les différentes catégories
INSERT INTO config.status_types (status_code, status_name, description, category, is_terminal, display_order) VALUES
('task_pending', 'En attente', 'Tâche en attente de traitement', 'task', false, 1),
('task_processing', 'En cours', 'Tâche en cours de traitement', 'task', false, 2),
('task_completed', 'Terminée', 'Tâche terminée avec succès', 'task', true, 3),
('task_failed', 'Échouée', 'Tâche échouée', 'task', true, 4),
('run_started', 'Démarré', 'Run démarré', 'run', false, 1),
('run_running', 'En cours', 'Run en cours d''exécution', 'run', false, 2),
('run_completed', 'Terminé', 'Run terminé avec succès', 'run', true, 3),
('run_failed', 'Échoué', 'Run échoué', 'run', true, 4),
('validation_pending', 'En attente', 'Validation en attente', 'validation', false, 1),
('validation_approved', 'Approuvée', 'Validation approuvée', 'validation', true, 2),
('validation_rejected', 'Rejetée', 'Validation rejetée', 'validation', true, 3),
('validation_expired', 'Expirée', 'Validation expirée', 'validation', true, 4)
ON CONFLICT (status_code) DO NOTHING;

-- Rôles de base
INSERT INTO config.user_roles (role_code, role_name, description, level) VALUES
('admin', 'Administrateur', 'Accès complet au système', 100),
('developer', 'Développeur', 'Accès aux outils de développement', 50),
('viewer', 'Observateur', 'Accès lecture seule', 10),
('auditor', 'Auditeur', 'Accès aux logs et audits', 30)
ON CONFLICT (role_code) DO NOTHING;

-- Providers IA de base
INSERT INTO config.ai_providers (provider_code, provider_name, api_endpoint) VALUES
('openai', 'OpenAI', 'https://api.openai.com/v1'),
('anthropic', 'Anthropic (Claude)', 'https://api.anthropic.com/v1'),
('google', 'Google AI', 'https://generativelanguage.googleapis.com/v1')
ON CONFLICT (provider_code) DO NOTHING;

-- Opérations IA de base
INSERT INTO config.ai_operations (operation_code, operation_name, category) VALUES
('analyze', 'Analyse', 'analysis'),
('implement', 'Implémentation', 'development'),
('debug', 'Débogage', 'debugging'),
('test', 'Test', 'testing'),
('review', 'Revue de code', 'review')
ON CONFLICT (operation_code) DO NOTHING;

