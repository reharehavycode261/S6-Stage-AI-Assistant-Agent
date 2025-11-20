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
CREATE EXTENSION IF NOT EXISTS pg_partman WITH SCHEMA partman;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
COMMENT ON SCHEMA public IS 'standard public schema';
CREATE FUNCTION public.auto_cleanup() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.status = 'completed' THEN
        DELETE FROM task_runs 
        WHERE task_id = NEW.task_id 
          AND status IN ('completed', 'failed')
          AND tasks_runs_id NOT IN (
              SELECT tasks_runs_id FROM task_runs 
              WHERE task_id = NEW.task_id 
              ORDER BY started_at DESC 
              LIMIT 10
          );
    END IF;
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.calculate_duration() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND OLD.completed_at IS NULL THEN
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at))::INTEGER;
    END IF;
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.check_rejection_limit() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                IF NEW.response_status = 'rejected' AND NEW.rejection_count >= 3 THEN
                    NEW.response_status := 'abandoned';
                    NEW.should_retry_workflow := FALSE;
                    NEW.comments := COALESCE(NEW.comments, '') || 
                        E'\n\n[SYSTÈME] Limite de 3 rejets atteinte. Passage en abandon automatique.';
                END IF;
                RETURN NEW;
            END;
            $$;
CREATE FUNCTION public.clean_expired_locks() RETURNS integer
    LANGUAGE plpgsql
    AS $$
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
$$;
COMMENT ON FUNCTION public.clean_expired_locks() IS 'Nettoie automatiquement les verrous de tâches expirés (plus de 30 minutes)';
CREATE FUNCTION public.cleanup_expired_contexts() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM task_context_memory
    WHERE expires_at IS NOT NULL 
    AND expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;
CREATE FUNCTION public.cleanup_old_data() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    DELETE FROM webhook_events WHERE received_at < NOW() - INTERVAL '6 months';
    DELETE FROM application_logs WHERE ts < NOW() - INTERVAL '3 months';
    DELETE FROM human_validations WHERE created_at < NOW() - INTERVAL '3 months';
    DELETE FROM validation_actions WHERE created_at < NOW() - INTERVAL '3 months';
    PERFORM mark_expired_validations();
    INSERT INTO application_logs (level, source_component, message)
    VALUES ('INFO', 'maintenance', 'Cleanup job executed successfully');
END;
$$;
COMMENT ON FUNCTION public.cleanup_old_data() IS 'Nettoie les données anciennes (logs, webhooks, validations)';
CREATE FUNCTION public.cleanup_old_logs() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    DELETE FROM webhook_events WHERE received_at < NOW() - INTERVAL '6 months';
    DELETE FROM application_logs WHERE ts < NOW() - INTERVAL '3 months';
    DELETE FROM human_validations WHERE created_at < NOW() - INTERVAL '3 months';
    DELETE FROM validation_actions WHERE created_at < NOW() - INTERVAL '3 months';
    PERFORM mark_expired_validations();
END;
$$;
CREATE FUNCTION public.cleanup_old_reactivations(retention_days integer DEFAULT 90) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM workflow_reactivations
    WHERE created_at < (NOW() - (retention_days || ' days')::INTERVAL)
      AND status IN ('completed', 'failed', 'cancelled');
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;
CREATE FUNCTION public.cleanup_old_update_triggers(days_to_keep integer DEFAULT 90) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM task_update_triggers
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep
      AND triggered_workflow = FALSE;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;
COMMENT ON FUNCTION public.cleanup_old_update_triggers(days_to_keep integer) IS 'Nettoie les anciens triggers qui n''ont pas déclenché de workflow (garde ceux qui ont déclenché un workflow)';
CREATE FUNCTION public.cleanup_old_workflow_queue_entries() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM workflow_queue
    WHERE completed_at < NOW() - INTERVAL '7 days'
    AND status IN ('completed', 'failed', 'cancelled', 'timeout');
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;
COMMENT ON FUNCTION public.cleanup_old_workflow_queue_entries() IS 'Nettoie les entrées de queue terminées depuis plus de 7 jours';
CREATE FUNCTION public.get_current_month_ai_stats() RETURNS TABLE(provider_name character varying, total_cost numeric, total_tokens bigint, total_calls bigint, unique_workflows bigint, avg_cost_per_call numeric)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        provider as provider_name,
        SUM(estimated_cost)::DECIMAL(10, 6) as total_cost,
        SUM(total_tokens) as total_tokens,
        COUNT(*)::BIGINT as total_calls,
        COUNT(DISTINCT workflow_id)::BIGINT as unique_workflows,
        AVG(estimated_cost)::DECIMAL(10, 6) as avg_cost_per_call
    FROM ai_usage_logs
    WHERE EXTRACT(YEAR FROM timestamp) = EXTRACT(YEAR FROM CURRENT_DATE)
      AND EXTRACT(MONTH FROM timestamp) = EXTRACT(MONTH FROM CURRENT_DATE)
      AND success = true
    GROUP BY provider
    ORDER BY total_cost DESC;
END;
$$;
COMMENT ON FUNCTION public.get_current_month_ai_stats() IS 'Statistiques IA du mois en cours par provider';
CREATE FUNCTION public.get_expensive_workflows(cost_threshold numeric DEFAULT 1.0) RETURNS TABLE(workflow_id character varying, task_id character varying, total_cost numeric, total_tokens bigint, ai_calls_count bigint, started_at timestamp with time zone, duration_minutes integer, providers_used text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        w.workflow_id,
        w.task_id,
        w.total_workflow_cost,
        w.total_tokens,
        w.total_ai_calls,
        w.started_at,
        (w.duration_seconds / 60)::INTEGER as duration_minutes,
        w.providers_used
    FROM ai_cost_by_workflow w
    WHERE w.total_workflow_cost >= cost_threshold
    ORDER BY w.total_workflow_cost DESC
    LIMIT 50;
END;
$$;
COMMENT ON FUNCTION public.get_expensive_workflows(cost_threshold numeric) IS 'Trouve les workflows qui dépassent un seuil de coût';
CREATE FUNCTION public.get_task_reactivation_stats(p_task_id bigint) RETURNS TABLE(total_reactivations bigint, successful_reactivations bigint, failed_reactivations bigint, avg_duration_ms numeric, last_reactivation_at timestamp with time zone, most_common_trigger character varying)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_reactivations,
        COUNT(*) FILTER (WHERE success = TRUE) as successful_reactivations,
        COUNT(*) FILTER (WHERE success = FALSE) as failed_reactivations,
        AVG(duration_ms) as avg_duration_ms,
        MAX(created_at) as last_reactivation_at,
        (
            SELECT trigger_type 
            FROM workflow_reactivations 
            WHERE task_id = p_task_id 
            GROUP BY trigger_type 
            ORDER BY COUNT(*) DESC 
            LIMIT 1
        ) as most_common_trigger
    FROM workflow_reactivations
    WHERE task_id = p_task_id;
END;
$$;
CREATE FUNCTION public.get_validation_stats() RETURNS TABLE(total_validations bigint, pending_validations bigint, approved_validations bigint, rejected_validations bigint, expired_validations bigint, avg_validation_time_minutes numeric, urgent_validations bigint)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_validations,
        COUNT(*) FILTER (WHERE status = 'pending') as pending_validations,
        COUNT(*) FILTER (WHERE status = 'approved') as approved_validations,
        COUNT(*) FILTER (WHERE status = 'rejected') as rejected_validations,
        COUNT(*) FILTER (WHERE status = 'expired') as expired_validations,
        ROUND(AVG(
            CASE 
                WHEN hvr.validated_at IS NOT NULL AND hv.created_at IS NOT NULL
                THEN EXTRACT(EPOCH FROM (hvr.validated_at - hv.created_at)) / 60.0
                ELSE NULL
            END
        ), 2) as avg_validation_time_minutes,
        COUNT(*) FILTER (
            WHERE status = 'pending' 
              AND expires_at IS NOT NULL 
              AND expires_at < NOW() + INTERVAL '1 hour'
        ) as urgent_validations
    FROM human_validations hv
    LEFT JOIN human_validation_responses hvr ON hv.human_validations_id = hvr.human_validation_id
    WHERE hv.created_at >= NOW() - INTERVAL '30 days'; -- Stats des 30 derniers jours
END;
$$;
COMMENT ON FUNCTION public.get_validation_stats() IS 'Retourne les statistiques de validation pour le dashboard';
CREATE FUNCTION public.get_workflow_reactivation_history(p_task_id bigint) RETURNS TABLE(run_id bigint, run_number integer, is_reactivation boolean, parent_run_id bigint, depth integer, status character varying, started_at timestamp with time zone, completed_at timestamp with time zone, duration_seconds integer, path_string text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE reactivation_chain AS (
        SELECT 
            tr.tasks_runs_id,
            tr.run_number,
            tr.is_reactivation,
            tr.parent_run_id,
            0 AS depth,
            tr.status,
            tr.started_at,
            tr.completed_at,
            tr.duration_seconds,
            tr.tasks_runs_id::TEXT AS path_string
        FROM task_runs tr
        WHERE tr.task_id = p_task_id
          AND tr.parent_run_id IS NULL
        UNION ALL
        SELECT 
            tr.tasks_runs_id,
            tr.run_number,
            tr.is_reactivation,
            tr.parent_run_id,
            rc.depth + 1,
            tr.status,
            tr.started_at,
            tr.completed_at,
            tr.duration_seconds,
            rc.path_string || ' -> ' || tr.tasks_runs_id::TEXT
        FROM task_runs tr
        INNER JOIN reactivation_chain rc ON tr.parent_run_id = rc.tasks_runs_id
        WHERE tr.task_id = p_task_id
          AND rc.depth < 20
    )
    SELECT * FROM reactivation_chain
    ORDER BY depth, started_at;
END;
$$;
COMMENT ON FUNCTION public.get_workflow_reactivation_history(p_task_id bigint) IS 'Retourne l''historique complet des réactivations d''un workflow donné';
CREATE FUNCTION public.health_check() RETURNS TABLE(metric_name text, metric_value numeric, status text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 'pending_tasks_old' as metric_name,
           COUNT(*)::NUMERIC as metric_value,
           CASE WHEN COUNT(*) > 100 THEN 'WARNING' ELSE 'OK' END as status
    FROM tasks 
    WHERE internal_status = 'pending' 
      AND created_at < NOW() - INTERVAL '1 hour';
    RETURN QUERY
    SELECT 'database_size_mb' as metric_name,
           pg_database_size(current_database())::NUMERIC / 1024 / 1024 as metric_value,
           'INFO' as status;
    RETURN QUERY
    SELECT 'success_rate_24h' as metric_name,
           (COUNT(*) FILTER (WHERE tr.status = 'completed')::NUMERIC / NULLIF(COUNT(*), 0) * 100) as metric_value,
           CASE 
               WHEN (COUNT(*) FILTER (WHERE tr.status = 'completed')::NUMERIC / NULLIF(COUNT(*), 0) * 100) < 80 
               THEN 'WARNING' 
               ELSE 'OK' 
           END as status
    FROM tasks t
    LEFT JOIN task_runs tr ON tr.task_id = t.tasks_id AND tr.tasks_runs_id = t.last_run_id
    WHERE t.created_at >= NOW() - INTERVAL '24 hours';
END;
$$;
CREATE FUNCTION public.log_critical_changes() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_TABLE_NAME = 'tasks' AND OLD.internal_status != NEW.internal_status THEN
        INSERT INTO application_logs (
            task_id, level, source_component, action, message, metadata
        ) VALUES (
            NEW.tasks_id, 'INFO', 'trigger', 'status_change',
            format('Task status changed from %s to %s', OLD.internal_status, NEW.internal_status),
            jsonb_build_object(
                'old_status', OLD.internal_status,
                'new_status', NEW.internal_status,
                'task_title', NEW.title
            )
        );
    END IF;
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.mark_expired_validations() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE human_validations 
    SET status = 'expired', 
        updated_at = NOW()
    WHERE status = 'pending' 
      AND expires_at IS NOT NULL 
      AND expires_at < NOW();
    GET DIAGNOSTICS expired_count = ROW_COUNT;
    IF expired_count > 0 THEN
        INSERT INTO application_logs (level, component, message, metadata)
        VALUES ('INFO', 'human_validation', 'Marked expired validations', 
                jsonb_build_object('expired_count', expired_count));
    END IF;
    RETURN expired_count;
END;
$$;
COMMENT ON FUNCTION public.mark_expired_validations() IS 'Marque automatiquement les validations expirées';
CREATE FUNCTION public.optimize_database() RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    table_name TEXT;
BEGIN
    FOR table_name IN 
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
          AND tablename IN ('tasks', 'task_runs', 'run_steps', 'ai_interactions')
    LOOP
        EXECUTE format('ANALYZE %I', table_name);
    END LOOP;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dashboard_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_realtime_monitoring;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_cost_analysis;
    INSERT INTO application_logs (level, source_component, action, message)
    VALUES ('INFO', 'maintenance', 'optimize_database', 'Database optimization completed');
END;
$$;
CREATE FUNCTION public.reset_failed_attempts_on_success() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.internal_status = 'completed' AND OLD.internal_status != 'completed' THEN
        NEW.failed_reactivation_attempts = 0;
        NEW.cooldown_until = NULL;
    END IF;
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.reset_monthly_user_quotas() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    reset_count INTEGER;
BEGIN
    UPDATE system_users
    SET tokens_used_this_month = 0,
        last_active_at = NOW()
    WHERE is_active = TRUE
    AND DATE_PART('day', NOW()) = monthly_reset_day;
    GET DIAGNOSTICS reset_count = ROW_COUNT;
    RETURN reset_count;
END;
$$;
CREATE FUNCTION public.search_similar_context(query_embedding public.vector, repo_url text DEFAULT NULL::text, match_threshold double precision DEFAULT 0.6, match_count integer DEFAULT 3) RETURNS TABLE(id integer, context_text text, context_type character varying, file_path text, similarity double precision, repository_url text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pce.id,
        pce.context_text,
        pce.context_type,
        pce.file_path,
        1 - (pce.embedding <=> query_embedding) AS similarity,
        pce.repository_url
    FROM project_context_embeddings pce
    WHERE 
        (repo_url IS NULL OR pce.repository_url = repo_url)
        AND (1 - (pce.embedding <=> query_embedding)) > match_threshold
    ORDER BY pce.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
CREATE FUNCTION public.search_similar_messages(query_embedding public.vector, match_threshold double precision DEFAULT 0.7, match_count integer DEFAULT 5, filter_item_id character varying DEFAULT NULL::character varying) RETURNS TABLE(id integer, monday_item_id character varying, message_text text, cleaned_text text, message_type character varying, intent_type character varying, similarity double precision, created_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        me.id,
        me.monday_item_id,
        me.message_text,
        me.cleaned_text,
        me.message_type,
        me.intent_type,
        1 - (me.embedding <=> query_embedding) AS similarity,
        me.created_at
    FROM message_embeddings me
    WHERE 
        (filter_item_id IS NULL OR me.monday_item_id = filter_item_id)
        AND (1 - (me.embedding <=> query_embedding)) > match_threshold
    ORDER BY me.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
CREATE FUNCTION public.sync_task_last_run() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE tasks 
    SET last_run_id = NEW.tasks_runs_id,
        updated_at = NOW()
    WHERE tasks_id = NEW.task_id;
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.sync_task_status() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            DECLARE
                current_task_status TEXT;
            BEGIN
                SELECT internal_status INTO current_task_status FROM tasks WHERE tasks_id = NEW.task_id;
                IF NEW.status = 'completed' AND current_task_status != 'completed' THEN
                    UPDATE tasks 
                    SET internal_status = 'completed',
                        completed_at = NEW.completed_at,
                        updated_at = NOW()
                    WHERE tasks_id = NEW.task_id;
                ELSIF NEW.status = 'failed' AND current_task_status != 'failed' THEN
                    UPDATE tasks 
                    SET internal_status = 'failed',
                        updated_at = NOW()
                    WHERE tasks_id = NEW.task_id;
                ELSIF NEW.status IN ('running', 'started') AND current_task_status = 'pending' THEN
                    UPDATE tasks 
                    SET internal_status = 'processing',
                        started_at = COALESCE(started_at, NEW.started_at),
                        updated_at = NOW()
                    WHERE tasks_id = NEW.task_id;
                END IF;
                RETURN NEW;
            END;
            $$;
CREATE FUNCTION public.sync_validation_status() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE human_validations 
    SET status = NEW.response_status,
        updated_at = NOW()
    WHERE human_validations_id = NEW.human_validation_id;
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION public.sync_validation_status() IS 'Synchronise automatiquement le statut de validation avec les réponses';
CREATE FUNCTION public.trg_touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.update_message_embeddings_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.update_prompt_template_stats() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE ai_prompt_templates
    SET 
        usage_count = usage_count + 1,
        avg_cost_usd = (
            SELECT AVG(cost_usd)
            FROM ai_prompt_usage
            WHERE template_id = NEW.template_id AND cost_usd IS NOT NULL
        ),
        updated_at = NOW()
    WHERE template_id = NEW.template_id;
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.update_reactivation_duration() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
        NEW.duration_ms := EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.update_users_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.update_workflow_queue_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;
CREATE FUNCTION public.update_workflow_reactivations_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION public.update_workflow_reactivations_updated_at() IS 'Met à jour automatiquement le champ updated_at lors de chaque modification';
CREATE FUNCTION public.validate_status_transition() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
    IF OLD.internal_status = NEW.internal_status THEN
        RETURN NEW;
    END IF;
    IF OLD.internal_status IS NOT NULL AND 
       NOT (valid_transitions->OLD.internal_status ? NEW.internal_status) THEN
        RAISE EXCEPTION 'Invalid status transition from % to %', 
            OLD.internal_status, NEW.internal_status;
    END IF;
    RETURN NEW;
END;
$$;
SET default_tablespace = '';
SET default_table_access_method = heap;
