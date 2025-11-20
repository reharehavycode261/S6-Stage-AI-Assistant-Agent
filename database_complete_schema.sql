--
-- PostgreSQL database dump
--

\restrict Tvdn84Qbff0sUswZoBBFlfgVsfr6OgDwyQSjcwAVcvVwdRwlVUPbmNEw2aInXT8

-- Dumped from database version 15.14
-- Dumped by pg_dump version 15.14

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

--
-- Name: partman; Type: SCHEMA; Schema: -; Owner: admin
--

CREATE SCHEMA partman;


ALTER SCHEMA partman OWNER TO admin;

--
-- Name: pg_partman; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_partman WITH SCHEMA partman;


--
-- Name: EXTENSION pg_partman; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_partman IS 'Extension to manage partitioned tables by time or ID';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: auto_cleanup(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.auto_cleanup() OWNER TO admin;

--
-- Name: calculate_duration(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.calculate_duration() OWNER TO admin;

--
-- Name: check_rejection_limit(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.check_rejection_limit() OWNER TO admin;

--
-- Name: clean_expired_locks(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.clean_expired_locks() OWNER TO admin;

--
-- Name: FUNCTION clean_expired_locks(); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.clean_expired_locks() IS 'Nettoie automatiquement les verrous de tâches expirés (plus de 30 minutes)';


--
-- Name: cleanup_expired_contexts(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.cleanup_expired_contexts() OWNER TO admin;

--
-- Name: cleanup_old_data(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.cleanup_old_data() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Nettoyage des webhooks anciens (6 mois)
    DELETE FROM webhook_events WHERE received_at < NOW() - INTERVAL '6 months';
    
    -- Nettoyage des logs anciens (3 mois)
    DELETE FROM application_logs WHERE ts < NOW() - INTERVAL '3 months';
    
    -- Nettoyage des anciennes validations (3 mois)
    DELETE FROM human_validations WHERE created_at < NOW() - INTERVAL '3 months';
    DELETE FROM validation_actions WHERE created_at < NOW() - INTERVAL '3 months';
    
    -- Marquer les validations expirées
    PERFORM mark_expired_validations();
    
    -- Log le nettoyage
    INSERT INTO application_logs (level, source_component, message)
    VALUES ('INFO', 'maintenance', 'Cleanup job executed successfully');
END;
$$;


ALTER FUNCTION public.cleanup_old_data() OWNER TO admin;

--
-- Name: FUNCTION cleanup_old_data(); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.cleanup_old_data() IS 'Nettoie les données anciennes (logs, webhooks, validations)';


--
-- Name: cleanup_old_logs(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.cleanup_old_logs() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Nettoyage existant
    DELETE FROM webhook_events WHERE received_at < NOW() - INTERVAL '6 months';
    DELETE FROM application_logs WHERE ts < NOW() - INTERVAL '3 months';
    
    -- Nouveau: nettoyer les anciennes validations
    DELETE FROM human_validations WHERE created_at < NOW() - INTERVAL '3 months';
    DELETE FROM validation_actions WHERE created_at < NOW() - INTERVAL '3 months';
    
    -- Marquer les validations expirées
    PERFORM mark_expired_validations();
END;
$$;


ALTER FUNCTION public.cleanup_old_logs() OWNER TO admin;

--
-- Name: cleanup_old_reactivations(integer); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.cleanup_old_reactivations(retention_days integer) OWNER TO admin;

--
-- Name: cleanup_old_update_triggers(integer); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.cleanup_old_update_triggers(days_to_keep integer DEFAULT 90) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Supprimer les triggers plus anciens que X jours qui n'ont PAS déclenché de workflow
    DELETE FROM task_update_triggers
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep
      AND triggered_workflow = FALSE;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$;


ALTER FUNCTION public.cleanup_old_update_triggers(days_to_keep integer) OWNER TO admin;

--
-- Name: FUNCTION cleanup_old_update_triggers(days_to_keep integer); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.cleanup_old_update_triggers(days_to_keep integer) IS 'Nettoie les anciens triggers qui n''ont pas déclenché de workflow (garde ceux qui ont déclenché un workflow)';


--
-- Name: cleanup_old_workflow_queue_entries(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.cleanup_old_workflow_queue_entries() OWNER TO admin;

--
-- Name: FUNCTION cleanup_old_workflow_queue_entries(); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.cleanup_old_workflow_queue_entries() IS 'Nettoie les entrées de queue terminées depuis plus de 7 jours';


--
-- Name: get_current_month_ai_stats(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.get_current_month_ai_stats() OWNER TO admin;

--
-- Name: FUNCTION get_current_month_ai_stats(); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.get_current_month_ai_stats() IS 'Statistiques IA du mois en cours par provider';


--
-- Name: get_expensive_workflows(numeric); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.get_expensive_workflows(cost_threshold numeric) OWNER TO admin;

--
-- Name: FUNCTION get_expensive_workflows(cost_threshold numeric); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.get_expensive_workflows(cost_threshold numeric) IS 'Trouve les workflows qui dépassent un seuil de coût';


--
-- Name: get_task_reactivation_stats(bigint); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.get_task_reactivation_stats(p_task_id bigint) OWNER TO admin;

--
-- Name: get_validation_stats(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.get_validation_stats() OWNER TO admin;

--
-- Name: FUNCTION get_validation_stats(); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.get_validation_stats() IS 'Retourne les statistiques de validation pour le dashboard';


--
-- Name: get_workflow_reactivation_history(bigint); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.get_workflow_reactivation_history(p_task_id bigint) RETURNS TABLE(run_id bigint, run_number integer, is_reactivation boolean, parent_run_id bigint, depth integer, status character varying, started_at timestamp with time zone, completed_at timestamp with time zone, duration_seconds integer, path_string text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE reactivation_chain AS (
        -- Racine
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
        
        -- Récursion
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


ALTER FUNCTION public.get_workflow_reactivation_history(p_task_id bigint) OWNER TO admin;

--
-- Name: FUNCTION get_workflow_reactivation_history(p_task_id bigint); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.get_workflow_reactivation_history(p_task_id bigint) IS 'Retourne l''historique complet des réactivations d''un workflow donné';


--
-- Name: health_check(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.health_check() RETURNS TABLE(metric_name text, metric_value numeric, status text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Tâches en attente trop longtemps
    RETURN QUERY
    SELECT 'pending_tasks_old' as metric_name,
           COUNT(*)::NUMERIC as metric_value,
           CASE WHEN COUNT(*) > 100 THEN 'WARNING' ELSE 'OK' END as status
    FROM tasks 
    WHERE internal_status = 'pending' 
      AND created_at < NOW() - INTERVAL '1 hour';
    
    -- Utilisation de l'espace disque
    RETURN QUERY
    SELECT 'database_size_mb' as metric_name,
           pg_database_size(current_database())::NUMERIC / 1024 / 1024 as metric_value,
           'INFO' as status;
    
    -- Taux de succès des 24 dernières heures
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


ALTER FUNCTION public.health_check() OWNER TO admin;

--
-- Name: log_critical_changes(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.log_critical_changes() OWNER TO admin;

--
-- Name: mark_expired_validations(); Type: FUNCTION; Schema: public; Owner: admin
--

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
    
    -- Log l'opération
    IF expired_count > 0 THEN
        INSERT INTO application_logs (level, component, message, metadata)
        VALUES ('INFO', 'human_validation', 'Marked expired validations', 
                jsonb_build_object('expired_count', expired_count));
    END IF;
    
    RETURN expired_count;
END;
$$;


ALTER FUNCTION public.mark_expired_validations() OWNER TO admin;

--
-- Name: FUNCTION mark_expired_validations(); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.mark_expired_validations() IS 'Marque automatiquement les validations expirées';


--
-- Name: optimize_database(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.optimize_database() OWNER TO admin;

--
-- Name: reset_failed_attempts_on_success(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.reset_failed_attempts_on_success() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Si le statut passe à 'completed', réinitialiser les échecs
    IF NEW.internal_status = 'completed' AND OLD.internal_status != 'completed' THEN
        NEW.failed_reactivation_attempts = 0;
        NEW.cooldown_until = NULL;
    END IF;
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.reset_failed_attempts_on_success() OWNER TO admin;

--
-- Name: reset_monthly_user_quotas(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.reset_monthly_user_quotas() OWNER TO admin;

--
-- Name: search_similar_context(public.vector, text, double precision, integer); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.search_similar_context(query_embedding public.vector, repo_url text, match_threshold double precision, match_count integer) OWNER TO admin;

--
-- Name: search_similar_messages(public.vector, double precision, integer, character varying); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.search_similar_messages(query_embedding public.vector, match_threshold double precision, match_count integer, filter_item_id character varying) OWNER TO admin;

--
-- Name: sync_task_last_run(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.sync_task_last_run() OWNER TO admin;

--
-- Name: sync_task_status(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.sync_task_status() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            DECLARE
                current_task_status TEXT;
            BEGIN
                -- Récupérer le statut actuel
                SELECT internal_status INTO current_task_status FROM tasks WHERE tasks_id = NEW.task_id;
                
                -- RÈGLE: Seulement faire l'UPDATE si le statut doit VRAIMENT changer
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

                -- CORRECTION CRUCIALE: Seulement si statut actuel = pending
                ELSIF NEW.status IN ('running', 'started') AND current_task_status = 'pending' THEN
                    UPDATE tasks 
                    SET internal_status = 'processing',
                        started_at = COALESCE(started_at, NEW.started_at),
                        updated_at = NOW()
                    WHERE tasks_id = NEW.task_id;
                    
                -- Si statut actuel != pending, ne rien faire (idempotent)
                END IF;

                RETURN NEW;
            END;
            $$;


ALTER FUNCTION public.sync_task_status() OWNER TO admin;

--
-- Name: sync_validation_status(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.sync_validation_status() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Quand une réponse est créée, mettre à jour le statut de la validation
    UPDATE human_validations 
    SET status = NEW.response_status,
        updated_at = NOW()
    WHERE human_validations_id = NEW.human_validation_id;
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.sync_validation_status() OWNER TO admin;

--
-- Name: FUNCTION sync_validation_status(); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.sync_validation_status() IS 'Synchronise automatiquement le statut de validation avec les réponses';


--
-- Name: trg_touch_updated_at(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.trg_touch_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.trg_touch_updated_at() OWNER TO admin;

--
-- Name: update_message_embeddings_updated_at(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.update_message_embeddings_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_message_embeddings_updated_at() OWNER TO admin;

--
-- Name: update_prompt_template_stats(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.update_prompt_template_stats() OWNER TO admin;

--
-- Name: update_reactivation_duration(); Type: FUNCTION; Schema: public; Owner: admin
--

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


ALTER FUNCTION public.update_reactivation_duration() OWNER TO admin;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO admin;

--
-- Name: update_users_updated_at(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.update_users_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_users_updated_at() OWNER TO admin;

--
-- Name: update_workflow_queue_timestamp(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.update_workflow_queue_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_workflow_queue_timestamp() OWNER TO admin;

--
-- Name: update_workflow_reactivations_updated_at(); Type: FUNCTION; Schema: public; Owner: admin
--

CREATE FUNCTION public.update_workflow_reactivations_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_workflow_reactivations_updated_at() OWNER TO admin;

--
-- Name: FUNCTION update_workflow_reactivations_updated_at(); Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON FUNCTION public.update_workflow_reactivations_updated_at() IS 'Met à jour automatiquement le champ updated_at lors de chaque modification';


--
-- Name: validate_status_transition(); Type: FUNCTION; Schema: public; Owner: admin
--

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
$$;


ALTER FUNCTION public.validate_status_transition() OWNER TO admin;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_code_generations; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.ai_code_generations (
    ai_code_generations_id bigint NOT NULL,
    task_run_id bigint NOT NULL,
    provider character varying(50) NOT NULL,
    model character varying(100) NOT NULL,
    generation_type character varying(50),
    prompt text NOT NULL,
    generated_code text,
    tokens_used integer,
    response_time_ms integer,
    cost_estimate numeric(12,6),
    compilation_successful boolean,
    syntax_valid boolean,
    files_modified jsonb,
    generated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ai_code_generations OWNER TO admin;

--
-- Name: TABLE ai_code_generations; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.ai_code_generations IS 'Historique des générations de code par IA';


--
-- Name: ai_code_generations_ai_code_generations_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.ai_code_generations ALTER COLUMN ai_code_generations_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.ai_code_generations_ai_code_generations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ai_usage_logs; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.ai_usage_logs (
    id integer NOT NULL,
    workflow_id character varying(255) NOT NULL,
    task_id character varying(255) NOT NULL,
    provider character varying(50) NOT NULL,
    model character varying(100) NOT NULL,
    operation character varying(100) NOT NULL,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    total_tokens integer DEFAULT 0 NOT NULL,
    estimated_cost numeric(10,6) DEFAULT 0.0 NOT NULL,
    "timestamp" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    duration_seconds numeric(8,3),
    success boolean DEFAULT true NOT NULL,
    error_message text,
    CONSTRAINT ai_usage_logs_cost_positive CHECK ((estimated_cost >= (0)::numeric)),
    CONSTRAINT ai_usage_logs_tokens_coherent CHECK ((total_tokens = (input_tokens + output_tokens))),
    CONSTRAINT ai_usage_logs_tokens_positive CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND (total_tokens >= 0)))
);


ALTER TABLE public.ai_usage_logs OWNER TO admin;

--
-- Name: TABLE ai_usage_logs; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.ai_usage_logs IS 'Logs des usages IA avec tracking des tokens et coûts';


--
-- Name: COLUMN ai_usage_logs.workflow_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.workflow_id IS 'ID du workflow parent';


--
-- Name: COLUMN ai_usage_logs.task_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.task_id IS 'ID de la tâche Monday.com';


--
-- Name: COLUMN ai_usage_logs.provider; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.provider IS 'Provider IA utilisé (claude, openai, etc.)';


--
-- Name: COLUMN ai_usage_logs.model; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.model IS 'Modèle spécifique utilisé';


--
-- Name: COLUMN ai_usage_logs.operation; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.operation IS 'Type d''opération (analyze, implement, debug, etc.)';


--
-- Name: COLUMN ai_usage_logs.input_tokens; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.input_tokens IS 'Nombre de tokens en input (prompt)';


--
-- Name: COLUMN ai_usage_logs.output_tokens; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.output_tokens IS 'Nombre de tokens en output (réponse)';


--
-- Name: COLUMN ai_usage_logs.total_tokens; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.total_tokens IS 'Total des tokens (input + output)';


--
-- Name: COLUMN ai_usage_logs.estimated_cost; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.estimated_cost IS 'Coût estimé en USD';


--
-- Name: COLUMN ai_usage_logs.duration_seconds; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.ai_usage_logs.duration_seconds IS 'Durée de l''appel IA en secondes';


--
-- Name: CONSTRAINT ai_usage_logs_cost_positive ON ai_usage_logs; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON CONSTRAINT ai_usage_logs_cost_positive ON public.ai_usage_logs IS 'Les coûts ne peuvent pas être négatifs';


--
-- Name: CONSTRAINT ai_usage_logs_tokens_coherent ON ai_usage_logs; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON CONSTRAINT ai_usage_logs_tokens_coherent ON public.ai_usage_logs IS 'total_tokens doit égaler input_tokens + output_tokens';


--
-- Name: CONSTRAINT ai_usage_logs_tokens_positive ON ai_usage_logs; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON CONSTRAINT ai_usage_logs_tokens_positive ON public.ai_usage_logs IS 'Les tokens ne peuvent pas être négatifs';


--
-- Name: ai_cost_by_workflow; Type: VIEW; Schema: public; Owner: admin
--

CREATE VIEW public.ai_cost_by_workflow AS
 SELECT ai_usage_logs.workflow_id,
    ai_usage_logs.task_id,
    count(*) AS total_ai_calls,
    sum(ai_usage_logs.input_tokens) AS total_input_tokens,
    sum(ai_usage_logs.output_tokens) AS total_output_tokens,
    sum(ai_usage_logs.total_tokens) AS total_tokens,
    sum(ai_usage_logs.estimated_cost) AS total_workflow_cost,
    min(ai_usage_logs."timestamp") AS started_at,
    max(ai_usage_logs."timestamp") AS last_ai_call,
    EXTRACT(epoch FROM (max(ai_usage_logs."timestamp") - min(ai_usage_logs."timestamp"))) AS duration_seconds,
    string_agg(DISTINCT (ai_usage_logs.provider)::text, ', '::text) AS providers_used,
    string_agg(DISTINCT (ai_usage_logs.operation)::text, ', '::text) AS operations_performed
   FROM public.ai_usage_logs
  WHERE (ai_usage_logs.success = true)
  GROUP BY ai_usage_logs.workflow_id, ai_usage_logs.task_id
  ORDER BY (sum(ai_usage_logs.estimated_cost)) DESC;


ALTER TABLE public.ai_cost_by_workflow OWNER TO admin;

--
-- Name: VIEW ai_cost_by_workflow; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON VIEW public.ai_cost_by_workflow IS 'Coûts agrégés par workflow avec métriques de performance';


--
-- Name: ai_cost_daily_summary; Type: VIEW; Schema: public; Owner: admin
--

CREATE VIEW public.ai_cost_daily_summary AS
 SELECT date(ai_usage_logs."timestamp") AS usage_date,
    ai_usage_logs.provider,
    count(*) AS total_calls,
    sum(ai_usage_logs.input_tokens) AS total_input_tokens,
    sum(ai_usage_logs.output_tokens) AS total_output_tokens,
    sum(ai_usage_logs.total_tokens) AS total_tokens,
    sum(ai_usage_logs.estimated_cost) AS total_cost,
    avg(ai_usage_logs.estimated_cost) AS avg_cost_per_call,
    count(DISTINCT ai_usage_logs.workflow_id) AS unique_workflows,
    count(DISTINCT ai_usage_logs.task_id) AS unique_tasks
   FROM public.ai_usage_logs
  WHERE (ai_usage_logs.success = true)
  GROUP BY (date(ai_usage_logs."timestamp")), ai_usage_logs.provider
  ORDER BY (date(ai_usage_logs."timestamp")) DESC, (sum(ai_usage_logs.estimated_cost)) DESC;


ALTER TABLE public.ai_cost_daily_summary OWNER TO admin;

--
-- Name: VIEW ai_cost_daily_summary; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON VIEW public.ai_cost_daily_summary IS 'Résumé quotidien des coûts IA par provider';


--
-- Name: ai_cost_tracking; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.ai_cost_tracking (
    ai_cost_tracking_id bigint NOT NULL,
    task_id bigint,
    task_run_id bigint,
    provider character varying(50) NOT NULL,
    model character varying(100) NOT NULL,
    operation_type character varying(50),
    prompt_tokens integer NOT NULL,
    completion_tokens integer NOT NULL,
    total_tokens integer NOT NULL,
    cost_usd numeric(12,6) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ai_cost_tracking OWNER TO admin;

--
-- Name: TABLE ai_cost_tracking; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.ai_cost_tracking IS 'Tracking des coûts d''utilisation des API IA';


--
-- Name: ai_cost_tracking_ai_cost_tracking_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.ai_cost_tracking ALTER COLUMN ai_cost_tracking_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.ai_cost_tracking_ai_cost_tracking_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ai_interactions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.ai_interactions (
    ai_interactions_id bigint NOT NULL,
    run_step_id bigint NOT NULL,
    ai_provider character varying(50) NOT NULL,
    model_name character varying(100) NOT NULL,
    prompt text NOT NULL,
    response text,
    token_usage jsonb,
    latency_ms integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ai_interactions OWNER TO admin;

--
-- Name: TABLE ai_interactions; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.ai_interactions IS 'Historique des interactions avec les modèles IA';


--
-- Name: ai_interactions_ai_interactions_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.ai_interactions ALTER COLUMN ai_interactions_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.ai_interactions_ai_interactions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ai_prompt_templates; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.ai_prompt_templates (
    template_id integer NOT NULL,
    template_name character varying(255) NOT NULL,
    template_category character varying(100),
    prompt_text text NOT NULL,
    model_recommended character varying(100),
    temperature numeric(3,2),
    max_tokens integer,
    description text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by integer,
    is_active boolean DEFAULT true,
    avg_cost_usd numeric(10,6),
    usage_count integer DEFAULT 0,
    CONSTRAINT ai_prompt_templates_max_tokens_check CHECK ((max_tokens > 0))
);


ALTER TABLE public.ai_prompt_templates OWNER TO admin;

--
-- Name: ai_prompt_templates_template_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.ai_prompt_templates_template_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ai_prompt_templates_template_id_seq OWNER TO admin;

--
-- Name: ai_prompt_templates_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.ai_prompt_templates_template_id_seq OWNED BY public.ai_prompt_templates.template_id;


--
-- Name: ai_prompt_usage; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.ai_prompt_usage (
    usage_id bigint NOT NULL,
    template_id integer,
    task_id bigint,
    task_run_id bigint,
    executed_at timestamp with time zone DEFAULT now(),
    model_used character varying(100),
    temperature_used numeric(3,2),
    max_tokens_used integer,
    input_tokens integer,
    output_tokens integer,
    total_tokens integer GENERATED ALWAYS AS ((COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0))) STORED,
    cost_usd numeric(10,6),
    execution_time_ms integer,
    success boolean DEFAULT true,
    error_message text
);


ALTER TABLE public.ai_prompt_usage OWNER TO admin;

--
-- Name: ai_prompt_usage_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.ai_prompt_usage_usage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ai_prompt_usage_usage_id_seq OWNER TO admin;

--
-- Name: ai_prompt_usage_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.ai_prompt_usage_usage_id_seq OWNED BY public.ai_prompt_usage.usage_id;


--
-- Name: ai_usage_logs_backup; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.ai_usage_logs_backup (
    id integer,
    workflow_id character varying(255),
    task_id character varying(255),
    provider character varying(50),
    model character varying(100),
    operation character varying(100),
    input_tokens integer,
    output_tokens integer,
    total_tokens integer,
    estimated_cost numeric(10,6),
    "timestamp" timestamp with time zone,
    duration_seconds numeric(8,3),
    success boolean,
    error_message text
);


ALTER TABLE public.ai_usage_logs_backup OWNER TO admin;

--
-- Name: ai_usage_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.ai_usage_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ai_usage_logs_id_seq OWNER TO admin;

--
-- Name: ai_usage_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.ai_usage_logs_id_seq OWNED BY public.ai_usage_logs.id;


--
-- Name: application_logs; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.application_logs (
    application_logs_id bigint NOT NULL,
    task_id bigint,
    task_run_id bigint,
    run_step_id bigint,
    level character varying(20) NOT NULL,
    source_component character varying(100),
    action character varying(100),
    message text NOT NULL,
    metadata jsonb,
    user_id bigint,
    ip_address inet,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT application_logs_level_chk CHECK (((level)::text = ANY ((ARRAY['DEBUG'::character varying, 'INFO'::character varying, 'WARNING'::character varying, 'ERROR'::character varying, 'CRITICAL'::character varying])::text[])))
);


ALTER TABLE public.application_logs OWNER TO admin;

--
-- Name: TABLE application_logs; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.application_logs IS 'Logs structurés de l''application pour audit et debug';


--
-- Name: application_logs_application_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.application_logs ALTER COLUMN application_logs_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.application_logs_application_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.audit_logs (
    id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    action character varying(100) NOT NULL,
    user_id integer,
    user_email character varying(255) NOT NULL,
    user_role character varying(50) NOT NULL,
    resource_type character varying(100),
    resource_id character varying(255),
    details jsonb DEFAULT '{}'::jsonb,
    ip_address character varying(45),
    user_agent text,
    status character varying(20) DEFAULT 'success'::character varying,
    severity character varying(20) DEFAULT 'low'::character varying,
    CONSTRAINT audit_logs_severity_check CHECK (((severity)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying, 'critical'::character varying])::text[]))),
    CONSTRAINT audit_logs_status_check CHECK (((status)::text = ANY ((ARRAY['success'::character varying, 'failed'::character varying, 'warning'::character varying])::text[])))
);


ALTER TABLE public.audit_logs OWNER TO admin;

--
-- Name: TABLE audit_logs; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.audit_logs IS 'Table des logs d''audit pour traçabilité complète (qui/quoi/quand)';


--
-- Name: COLUMN audit_logs.action; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.audit_logs.action IS 'Type d''action effectuée (ex: user_login, secret_viewed, config_updated)';


--
-- Name: COLUMN audit_logs.details; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.audit_logs.details IS 'Détails supplémentaires au format JSON';


--
-- Name: COLUMN audit_logs.status; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.audit_logs.status IS 'Résultat de l''action: success, failed, warning';


--
-- Name: COLUMN audit_logs.severity; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.audit_logs.severity IS 'Niveau de gravité: low, medium, high, critical';


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.audit_logs_id_seq OWNER TO admin;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: celery_taskmeta; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.celery_taskmeta (
    id integer NOT NULL,
    task_id character varying(155),
    status character varying(50),
    result bytea,
    date_done timestamp without time zone,
    traceback text,
    name character varying(155),
    args bytea,
    kwargs bytea,
    worker character varying(155),
    retries integer,
    queue character varying(155)
);


ALTER TABLE public.celery_taskmeta OWNER TO admin;

--
-- Name: celery_tasksetmeta; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.celery_tasksetmeta (
    id integer NOT NULL,
    taskset_id character varying(155),
    result bytea,
    date_done timestamp without time zone
);


ALTER TABLE public.celery_tasksetmeta OWNER TO admin;

--
-- Name: code_quality_feedback; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.code_quality_feedback (
    feedback_id bigint NOT NULL,
    task_id bigint,
    task_run_id bigint,
    file_path character varying(500),
    line_number integer,
    category character varying(100),
    severity character varying(50),
    message text NOT NULL,
    suggestion text,
    source character varying(100),
    fixed boolean DEFAULT false,
    auto_fixable boolean DEFAULT false,
    code_snippet text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.code_quality_feedback OWNER TO admin;

--
-- Name: code_quality_feedback_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.code_quality_feedback_feedback_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.code_quality_feedback_feedback_id_seq OWNER TO admin;

--
-- Name: code_quality_feedback_feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.code_quality_feedback_feedback_id_seq OWNED BY public.code_quality_feedback.feedback_id;


--
-- Name: human_validation_responses; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.human_validation_responses (
    human_validation_responses_id bigint NOT NULL,
    human_validation_id bigint NOT NULL,
    validation_id character varying(100) NOT NULL,
    response_status character varying(50) NOT NULL,
    comments text,
    suggested_changes text,
    approval_notes text,
    validated_by character varying(100),
    validated_at timestamp with time zone DEFAULT now() NOT NULL,
    should_merge boolean DEFAULT false NOT NULL,
    should_continue_workflow boolean DEFAULT true NOT NULL,
    validation_duration_seconds integer,
    user_agent text,
    ip_address inet,
    rejection_count integer DEFAULT 0 NOT NULL,
    modification_instructions text,
    should_retry_workflow boolean DEFAULT false NOT NULL,
    CONSTRAINT human_validation_responses_status_chk CHECK (((response_status)::text = ANY ((ARRAY['approved'::character varying, 'rejected'::character varying, 'abandoned'::character varying, 'expired'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.human_validation_responses OWNER TO admin;

--
-- Name: TABLE human_validation_responses; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.human_validation_responses IS 'Réponses des validateurs humains (approbation/rejet)';


--
-- Name: human_validation_responses_human_validation_responses_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.human_validation_responses ALTER COLUMN human_validation_responses_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.human_validation_responses_human_validation_responses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: human_validations; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.human_validations (
    human_validations_id bigint NOT NULL,
    validation_id character varying(100) NOT NULL,
    task_id bigint NOT NULL,
    task_run_id bigint,
    run_step_id bigint,
    task_title character varying(500) NOT NULL,
    task_description text,
    original_request text NOT NULL,
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    generated_code jsonb NOT NULL,
    code_summary text NOT NULL,
    files_modified text[] NOT NULL,
    implementation_notes text,
    test_results jsonb,
    pr_info jsonb,
    workflow_id character varying(255),
    requested_by character varying(100) DEFAULT 'ai_agent'::character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone,
    rejection_count integer DEFAULT 0 NOT NULL,
    modification_instructions text,
    is_retry boolean DEFAULT false NOT NULL,
    parent_validation_id character varying(100),
    user_email character varying(100),
    CONSTRAINT human_validations_status_chk CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'approved'::character varying, 'rejected'::character varying, 'abandoned'::character varying, 'expired'::character varying, 'cancelled'::character varying])::text[])))
);


ALTER TABLE public.human_validations OWNER TO admin;

--
-- Name: TABLE human_validations; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.human_validations IS 'Demandes de validation humaine pour les codes générés par l''IA';


--
-- Name: COLUMN human_validations.validation_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.human_validations.validation_id IS 'ID unique généré par l''application pour tracking';


--
-- Name: COLUMN human_validations.task_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.human_validations.task_id IS 'FK vers tasks.tasks_id (ID DB, PAS Monday item ID)';


--
-- Name: COLUMN human_validations.generated_code; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.human_validations.generated_code IS 'Code généré au format JSON {"filename": "content"}';


--
-- Name: COLUMN human_validations.files_modified; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.human_validations.files_modified IS 'Array PostgreSQL des fichiers modifiés';


--
-- Name: COLUMN human_validations.expires_at; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.human_validations.expires_at IS 'Date limite pour la validation (24h par défaut)';


--
-- Name: COLUMN human_validations.user_email; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.human_validations.user_email IS 'Email de l''utilisateur pour notifications de timeout';


--
-- Name: human_validations_human_validations_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.human_validations ALTER COLUMN human_validations_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.human_validations_human_validations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: message_embeddings; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.message_embeddings (
    id integer NOT NULL,
    monday_item_id character varying(50),
    monday_update_id character varying(100),
    task_id integer,
    message_text text NOT NULL,
    message_language character varying(10),
    cleaned_text text,
    embedding public.vector(1536) NOT NULL,
    message_type character varying(50) DEFAULT 'user_message'::character varying,
    intent_type character varying(50),
    user_id character varying(100),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.message_embeddings OWNER TO admin;

--
-- Name: TABLE message_embeddings; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.message_embeddings IS 'Stockage des embeddings vectoriels des messages utilisateurs pour recherche sémantique multilingue';


--
-- Name: COLUMN message_embeddings.embedding; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.message_embeddings.embedding IS 'Vecteur d''embedding 1536 dimensions (OpenAI text-embedding-3-small)';


--
-- Name: message_embeddings_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.message_embeddings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.message_embeddings_id_seq OWNER TO admin;

--
-- Name: message_embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.message_embeddings_id_seq OWNED BY public.message_embeddings.id;


--
-- Name: monday_updates_history; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.monday_updates_history (
    update_history_id bigint NOT NULL,
    monday_item_id bigint NOT NULL,
    update_id bigint,
    update_text text,
    update_author character varying(255),
    update_created_at timestamp with time zone,
    task_id bigint,
    triggered_reactivation boolean DEFAULT false,
    reactivation_id bigint,
    processed boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.monday_updates_history OWNER TO admin;

--
-- Name: monday_updates_history_update_history_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.monday_updates_history_update_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.monday_updates_history_update_history_id_seq OWNER TO admin;

--
-- Name: monday_updates_history_update_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.monday_updates_history_update_history_id_seq OWNED BY public.monday_updates_history.update_history_id;


--
-- Name: performance_metrics; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.performance_metrics (
    performance_metrics_id bigint NOT NULL,
    task_id bigint,
    task_run_id bigint,
    total_duration_seconds integer,
    queue_wait_time_seconds integer,
    ai_processing_time_seconds integer,
    testing_time_seconds integer,
    total_ai_calls integer DEFAULT 0,
    total_tokens_used integer DEFAULT 0,
    total_ai_cost numeric(12,6) DEFAULT 0.0,
    code_lines_generated integer DEFAULT 0,
    test_coverage_final numeric(5,2),
    security_issues_found integer DEFAULT 0,
    retry_attempts integer DEFAULT 0,
    success_rate numeric(5,2),
    recorded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.performance_metrics OWNER TO admin;

--
-- Name: TABLE performance_metrics; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.performance_metrics IS 'Métriques de performance agrégées par workflow';


--
-- Name: performance_metrics_performance_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.performance_metrics ALTER COLUMN performance_metrics_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.performance_metrics_performance_metrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: project_context_embeddings; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.project_context_embeddings (
    id integer NOT NULL,
    repository_url text NOT NULL,
    repository_name character varying(255),
    context_text text NOT NULL,
    context_type character varying(50) NOT NULL,
    file_path text,
    embedding public.vector(1536) NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    language character varying(10),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.project_context_embeddings OWNER TO admin;

--
-- Name: TABLE project_context_embeddings; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.project_context_embeddings IS 'Stockage des embeddings du contexte de projet (README, code, docs) pour enrichir les réponses';


--
-- Name: project_context_embeddings_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.project_context_embeddings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.project_context_embeddings_id_seq OWNER TO admin;

--
-- Name: project_context_embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.project_context_embeddings_id_seq OWNED BY public.project_context_embeddings.id;


--
-- Name: pull_requests; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.pull_requests (
    pull_requests_id bigint NOT NULL,
    task_id bigint NOT NULL,
    task_run_id bigint,
    github_pr_number integer,
    github_pr_url character varying(500),
    pr_title character varying(500),
    pr_description text,
    pr_status character varying(50),
    mergeable boolean,
    conflicts boolean DEFAULT false,
    reviews_required integer DEFAULT 1,
    reviews_approved integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    merged_at timestamp with time zone,
    closed_at timestamp with time zone,
    head_sha character(40),
    base_branch character varying(100) DEFAULT 'main'::character varying,
    feature_branch character varying(100)
);


ALTER TABLE public.pull_requests OWNER TO admin;

--
-- Name: TABLE pull_requests; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.pull_requests IS 'Pull Requests créées par l''agent IA';


--
-- Name: pull_requests_pull_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.pull_requests ALTER COLUMN pull_requests_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.pull_requests_pull_requests_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rate_limits; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.rate_limits (
    rate_limit_id bigint NOT NULL,
    resource_identifier character varying(255) NOT NULL,
    user_id bigint,
    max_requests integer NOT NULL,
    limit_window character varying(50) NOT NULL,
    current_requests integer DEFAULT 0,
    window_start timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    last_request_at timestamp with time zone,
    exceeded_count integer DEFAULT 0
);


ALTER TABLE public.rate_limits OWNER TO admin;

--
-- Name: rate_limits_rate_limit_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.rate_limits_rate_limit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.rate_limits_rate_limit_id_seq OWNER TO admin;

--
-- Name: rate_limits_rate_limit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.rate_limits_rate_limit_id_seq OWNED BY public.rate_limits.rate_limit_id;


--
-- Name: run_step_checkpoints; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.run_step_checkpoints (
    checkpoint_id bigint NOT NULL,
    step_id bigint NOT NULL,
    checkpoint_data jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone
);


ALTER TABLE public.run_step_checkpoints OWNER TO admin;

--
-- Name: TABLE run_step_checkpoints; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.run_step_checkpoints IS 'Checkpoints pour la reprise après erreur';


--
-- Name: run_step_checkpoints_checkpoint_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.run_step_checkpoints ALTER COLUMN checkpoint_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.run_step_checkpoints_checkpoint_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: run_steps; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.run_steps (
    run_steps_id bigint NOT NULL,
    task_run_id bigint NOT NULL,
    node_name character varying(100) NOT NULL,
    step_order integer NOT NULL,
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    retry_count integer DEFAULT 0 NOT NULL,
    max_retries integer DEFAULT 3 NOT NULL,
    input_data jsonb,
    output_data jsonb,
    output_log text,
    error_details text,
    checkpoint_data jsonb,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    checkpoint_saved_at timestamp with time zone,
    duration_seconds integer,
    CONSTRAINT run_steps_status_chk CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying, 'completed'::character varying, 'failed'::character varying, 'skipped'::character varying, 'retry'::character varying])::text[])))
);


ALTER TABLE public.run_steps OWNER TO admin;

--
-- Name: TABLE run_steps; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.run_steps IS 'Étapes individuelles d''un workflow (nœuds LangGraph)';


--
-- Name: run_steps_run_steps_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.run_steps ALTER COLUMN run_steps_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.run_steps_run_steps_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: system_config; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.system_config (
    system_config_id bigint NOT NULL,
    key character varying(100) NOT NULL,
    value jsonb NOT NULL,
    description text,
    config_type character varying(50) DEFAULT 'application'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by character varying(100)
);


ALTER TABLE public.system_config OWNER TO admin;

--
-- Name: TABLE system_config; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.system_config IS 'Configuration système versionnée';


--
-- Name: system_config_system_config_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.system_config ALTER COLUMN system_config_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.system_config_system_config_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: system_users; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.system_users (
    user_id bigint NOT NULL,
    username character varying(100) NOT NULL,
    email character varying(255) NOT NULL,
    full_name character varying(200),
    role character varying(50) DEFAULT 'user'::character varying,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    last_login_at timestamp with time zone,
    preferences jsonb DEFAULT '{}'::jsonb,
    monday_user_id bigint,
    api_usage_limit integer DEFAULT 1000,
    monthly_reset_day integer DEFAULT 1,
    notification_preferences jsonb DEFAULT '{"email_on_failure": true, "email_on_completion": true}'::jsonb
);


ALTER TABLE public.system_users OWNER TO admin;

--
-- Name: system_users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.system_users_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.system_users_user_id_seq OWNER TO admin;

--
-- Name: system_users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.system_users_user_id_seq OWNED BY public.system_users.user_id;


--
-- Name: task_context_memory; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.task_context_memory (
    memory_id bigint NOT NULL,
    task_id bigint,
    context_key character varying(255) NOT NULL,
    context_value jsonb NOT NULL,
    relevance_score numeric(3,2) DEFAULT 1.0,
    created_at timestamp with time zone DEFAULT now(),
    accessed_at timestamp with time zone,
    access_count integer DEFAULT 0
);


ALTER TABLE public.task_context_memory OWNER TO admin;

--
-- Name: task_context_memory_memory_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.task_context_memory_memory_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.task_context_memory_memory_id_seq OWNER TO admin;

--
-- Name: task_context_memory_memory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.task_context_memory_memory_id_seq OWNED BY public.task_context_memory.memory_id;


--
-- Name: task_id_sequence; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.task_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.task_id_sequence OWNER TO admin;

--
-- Name: task_runs; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.task_runs (
    tasks_runs_id bigint NOT NULL,
    task_id bigint,
    run_number integer,
    status character varying(50) DEFAULT 'started'::character varying NOT NULL,
    celery_task_id character varying(255),
    current_node character varying(100),
    progress_percentage integer DEFAULT 0,
    ai_provider character varying(50),
    model_name character varying(100),
    result jsonb,
    error_message text,
    git_branch_name character varying(255),
    pull_request_url character varying(500),
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    duration_seconds integer,
    last_merged_pr_url character varying(500),
    active_task_ids text[],
    last_task_id character varying(255),
    task_started_at timestamp with time zone,
    is_reactivation boolean DEFAULT false NOT NULL,
    parent_run_id bigint,
    reactivation_count integer DEFAULT 0 NOT NULL,
    browser_qa_results jsonb,
    CONSTRAINT task_runs_status_chk CHECK (((status)::text = ANY ((ARRAY['started'::character varying, 'running'::character varying, 'completed'::character varying, 'failed'::character varying, 'retry'::character varying])::text[])))
);


ALTER TABLE public.task_runs OWNER TO admin;

--
-- Name: TABLE task_runs; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.task_runs IS 'Exécutions de workflows (jobs Celery)';


--
-- Name: COLUMN task_runs.celery_task_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.task_runs.celery_task_id IS 'ID de la tâche Celery (UUID)';


--
-- Name: COLUMN task_runs.last_merged_pr_url; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.task_runs.last_merged_pr_url IS 'URL de la dernière PR fusionnée (pour résolution repository)';


--
-- Name: COLUMN task_runs.active_task_ids; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.task_runs.active_task_ids IS 'Liste des IDs de tâches Celery actives (array JSON)';


--
-- Name: COLUMN task_runs.last_task_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.task_runs.last_task_id IS 'ID de la dernière tâche Celery lancée';


--
-- Name: COLUMN task_runs.task_started_at; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.task_runs.task_started_at IS 'Date de démarrage de la dernière tâche Celery';


--
-- Name: COLUMN task_runs.is_reactivation; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.task_runs.is_reactivation IS 'Indique si ce run est une réactivation';


--
-- Name: COLUMN task_runs.parent_run_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.task_runs.parent_run_id IS 'ID du run parent pour les réactivations (permet de tracer la lignée des workflows)';


--
-- Name: COLUMN task_runs.browser_qa_results; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.task_runs.browser_qa_results IS 'Résultats des tests Browser QA automatisés (Chrome DevTools MCP)';


--
-- Name: task_runs_tasks_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.task_runs ALTER COLUMN tasks_runs_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.task_runs_tasks_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: task_update_triggers; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.task_update_triggers (
    trigger_id bigint NOT NULL,
    task_id bigint,
    monday_update_id bigint,
    update_content text,
    triggered_at timestamp with time zone DEFAULT now(),
    trigger_type character varying(50),
    action_taken character varying(100),
    new_run_id bigint,
    metadata jsonb
);


ALTER TABLE public.task_update_triggers OWNER TO admin;

--
-- Name: task_update_triggers_trigger_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.task_update_triggers_trigger_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.task_update_triggers_trigger_id_seq OWNER TO admin;

--
-- Name: task_update_triggers_trigger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.task_update_triggers_trigger_id_seq OWNED BY public.task_update_triggers.trigger_id;


--
-- Name: tasks; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.tasks (
    tasks_id bigint NOT NULL,
    monday_item_id bigint NOT NULL,
    monday_board_id bigint,
    title character varying(500) NOT NULL,
    description text,
    priority character varying(50),
    repository_url character varying(500) NOT NULL,
    repository_name character varying(200),
    default_branch character varying(100) DEFAULT 'main'::character varying,
    monday_status character varying(100),
    internal_status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    created_by_user_id bigint,
    assigned_to text,
    last_run_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    is_locked boolean DEFAULT false,
    locked_at timestamp without time zone,
    locked_by character varying(255),
    cooldown_until timestamp without time zone,
    last_reactivation_attempt timestamp without time zone,
    failed_reactivation_attempts integer DEFAULT 0,
    reactivation_count integer DEFAULT 0,
    active_task_ids text[],
    reactivated_at timestamp without time zone,
    previous_status character varying(50),
    CONSTRAINT tasks_internal_status_chk CHECK (((internal_status)::text = ANY ((ARRAY['pending'::character varying, 'processing'::character varying, 'testing'::character varying, 'debugging'::character varying, 'quality_check'::character varying, 'completed'::character varying, 'failed'::character varying])::text[])))
);


ALTER TABLE public.tasks OWNER TO admin;

--
-- Name: TABLE tasks; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.tasks IS 'Tâches provenant de Monday.com pour le workflow AI';


--
-- Name: COLUMN tasks.tasks_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.tasks_id IS 'ID interne de la base de données (utilisé pour les foreign keys)';


--
-- Name: COLUMN tasks.monday_item_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.monday_item_id IS 'ID de l''item Monday.com (unique)';


--
-- Name: COLUMN tasks.is_locked; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.is_locked IS 'Indique si la tâche est verrouillée pour éviter les modifications concurrentes';


--
-- Name: COLUMN tasks.locked_at; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.locked_at IS 'Date du verrouillage';


--
-- Name: COLUMN tasks.locked_by; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.locked_by IS 'Identifiant du processus/tâche qui a verrouillé (ex: celery_task_id)';


--
-- Name: COLUMN tasks.cooldown_until; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.cooldown_until IS 'Date de fin du cooldown (pendant cette période, pas de réactivation)';


--
-- Name: COLUMN tasks.last_reactivation_attempt; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.last_reactivation_attempt IS 'Date de la dernière tentative de réactivation';


--
-- Name: COLUMN tasks.failed_reactivation_attempts; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.failed_reactivation_attempts IS 'Nombre de tentatives de réactivation échouées consécutives';


--
-- Name: COLUMN tasks.reactivation_count; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.reactivation_count IS 'Nombre de fois que la tâche a été réactivée';


--
-- Name: COLUMN tasks.reactivated_at; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.reactivated_at IS 'Date de la dernière réactivation de la tâche';


--
-- Name: COLUMN tasks.previous_status; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.tasks.previous_status IS 'Statut précédent avant réactivation';


--
-- Name: tasks_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.tasks ALTER COLUMN tasks_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.tasks_tasks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: taskset_id_sequence; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.taskset_id_sequence
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.taskset_id_sequence OWNER TO admin;

--
-- Name: test_results; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.test_results (
    test_results_id bigint NOT NULL,
    task_run_id bigint NOT NULL,
    passed boolean NOT NULL,
    status character varying(50) DEFAULT 'passed'::character varying NOT NULL,
    tests_total integer DEFAULT 0,
    tests_passed integer DEFAULT 0,
    tests_failed integer DEFAULT 0,
    tests_skipped integer DEFAULT 0,
    coverage_percentage numeric(5,2),
    pytest_report jsonb,
    security_scan_report jsonb,
    executed_at timestamp with time zone DEFAULT now() NOT NULL,
    duration_seconds integer
);


ALTER TABLE public.test_results OWNER TO admin;

--
-- Name: TABLE test_results; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.test_results IS 'Résultats des tests automatisés';


--
-- Name: test_results_test_results_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.test_results ALTER COLUMN test_results_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.test_results_test_results_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    email character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(50) DEFAULT 'Viewer'::character varying NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_login timestamp without time zone,
    CONSTRAINT users_role_check CHECK (((role)::text = ANY ((ARRAY['Admin'::character varying, 'Developer'::character varying, 'Viewer'::character varying, 'Auditor'::character varying])::text[])))
);


ALTER TABLE public.users OWNER TO admin;

--
-- Name: TABLE users; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.users IS 'Table des utilisateurs autorisés à accéder à l''interface admin';


--
-- Name: COLUMN users.role; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.users.role IS 'Rôle de l''utilisateur: Admin, Developer, Viewer, ou Auditor';


--
-- Name: COLUMN users.is_active; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.users.is_active IS 'Indique si l''utilisateur peut se connecter';


--
-- Name: COLUMN users.last_login; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.users.last_login IS 'Date et heure de la dernière connexion réussie';


--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_user_id_seq OWNER TO admin;

--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- Name: workflow_reactivations; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.workflow_reactivations (
    id integer NOT NULL,
    workflow_id integer NOT NULL,
    reactivated_at timestamp with time zone DEFAULT now() NOT NULL,
    trigger_type character varying(50) NOT NULL,
    update_data jsonb,
    task_id character varying(255),
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT workflow_reactivations_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'processing'::character varying, 'completed'::character varying, 'failed'::character varying])::text[]))),
    CONSTRAINT workflow_reactivations_trigger_type_check CHECK (((trigger_type)::text = ANY ((ARRAY['update'::character varying, 'manual'::character varying, 'automatic'::character varying])::text[])))
);


ALTER TABLE public.workflow_reactivations OWNER TO admin;

--
-- Name: TABLE workflow_reactivations; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.workflow_reactivations IS 'Table d''enregistrement des réactivations de workflow pour suivi et audit';


--
-- Name: COLUMN workflow_reactivations.id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_reactivations.id IS 'Identifiant unique de la réactivation';


--
-- Name: COLUMN workflow_reactivations.workflow_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_reactivations.workflow_id IS 'ID du workflow/tâche réactivé (référence à tasks.tasks_id)';


--
-- Name: COLUMN workflow_reactivations.reactivated_at; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_reactivations.reactivated_at IS 'Date et heure de la réactivation';


--
-- Name: COLUMN workflow_reactivations.trigger_type; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_reactivations.trigger_type IS 'Type de déclencheur de la réactivation (update, manual, automatic)';


--
-- Name: COLUMN workflow_reactivations.update_data; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_reactivations.update_data IS 'Données de l''update Monday.com ou contexte de la réactivation (JSON)';


--
-- Name: COLUMN workflow_reactivations.task_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_reactivations.task_id IS 'ID de la tâche Celery lancée pour cette réactivation';


--
-- Name: COLUMN workflow_reactivations.status; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_reactivations.status IS 'Statut de la réactivation (pending, processing, completed, failed)';


--
-- Name: COLUMN workflow_reactivations.error_message; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_reactivations.error_message IS 'Message d''erreur en cas d''échec de la réactivation';


--
-- Name: COLUMN workflow_reactivations.completed_at; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_reactivations.completed_at IS 'Date de complétion (succès ou échec) de la réactivation';


--
-- Name: v_recent_reactivations; Type: VIEW; Schema: public; Owner: admin
--

CREATE VIEW public.v_recent_reactivations AS
 SELECT wr.id,
    wr.workflow_id,
    t.title AS task_title,
    wr.trigger_type,
    wr.status,
    wr.reactivated_at,
    wr.completed_at,
    (EXTRACT(epoch FROM (COALESCE(wr.completed_at, now()) - wr.reactivated_at)))::integer AS duration_seconds,
    wr.error_message
   FROM (public.workflow_reactivations wr
     JOIN public.tasks t ON ((wr.workflow_id = t.tasks_id)))
  WHERE (wr.reactivated_at >= (now() - '24:00:00'::interval))
  ORDER BY wr.reactivated_at DESC;


ALTER TABLE public.v_recent_reactivations OWNER TO admin;

--
-- Name: VIEW v_recent_reactivations; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON VIEW public.v_recent_reactivations IS 'Liste des réactivations des dernières 24 heures avec durées et statuts';


--
-- Name: v_workflow_reactivation_stats; Type: VIEW; Schema: public; Owner: admin
--

CREATE VIEW public.v_workflow_reactivation_stats AS
 SELECT wr.workflow_id,
    t.title AS task_title,
    t.internal_status AS current_status,
    count(*) AS total_reactivations,
    count(*) FILTER (WHERE ((wr.status)::text = 'completed'::text)) AS successful_reactivations,
    count(*) FILTER (WHERE ((wr.status)::text = 'failed'::text)) AS failed_reactivations,
    count(*) FILTER (WHERE ((wr.status)::text = ANY ((ARRAY['pending'::character varying, 'processing'::character varying])::text[]))) AS ongoing_reactivations,
    max(wr.reactivated_at) AS last_reactivation_at,
    avg(EXTRACT(epoch FROM (wr.completed_at - wr.reactivated_at))) FILTER (WHERE (wr.completed_at IS NOT NULL)) AS avg_duration_seconds
   FROM (public.workflow_reactivations wr
     JOIN public.tasks t ON ((wr.workflow_id = t.tasks_id)))
  GROUP BY wr.workflow_id, t.title, t.internal_status;


ALTER TABLE public.v_workflow_reactivation_stats OWNER TO admin;

--
-- Name: VIEW v_workflow_reactivation_stats; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON VIEW public.v_workflow_reactivation_stats IS 'Statistiques de réactivation par workflow avec taux de succès et durées moyennes';


--
-- Name: validation_actions; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.validation_actions (
    validation_actions_id bigint NOT NULL,
    human_validation_id bigint NOT NULL,
    validation_id character varying(100) NOT NULL,
    action_type character varying(50) NOT NULL,
    action_status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    action_data jsonb,
    result_data jsonb,
    merge_commit_hash character varying(100),
    merge_commit_url character varying(500),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    error_message text,
    retry_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT validation_actions_status_chk CHECK (((action_status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying, 'completed'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT validation_actions_type_chk CHECK (((action_type)::text = ANY ((ARRAY['merge_pr'::character varying, 'reject_pr'::character varying, 'update_monday'::character varying, 'cleanup_branch'::character varying, 'notify_user'::character varying])::text[])))
);


ALTER TABLE public.validation_actions OWNER TO admin;

--
-- Name: TABLE validation_actions; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.validation_actions IS 'Actions effectuées suite à la validation (merge, etc.)';


--
-- Name: validation_actions_validation_actions_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.validation_actions ALTER COLUMN validation_actions_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.validation_actions_validation_actions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: validation_dashboard; Type: VIEW; Schema: public; Owner: admin
--

CREATE VIEW public.validation_dashboard AS
 SELECT hv.human_validations_id,
    hv.validation_id,
    hv.task_title,
    hv.status,
    hv.created_at,
    hv.expires_at,
        CASE
            WHEN ((hv.expires_at IS NOT NULL) AND (hv.expires_at < (now() + '01:00:00'::interval))) THEN true
            ELSE false
        END AS is_urgent,
        CASE
            WHEN ((hv.test_results IS NOT NULL) AND (((hv.test_results ->> 'success'::text))::boolean = false)) THEN true
            ELSE false
        END AS has_test_failures,
    array_length(hv.files_modified, 1) AS files_count,
    (hv.pr_info ->> 'url'::text) AS pr_url,
    t.priority,
    t.repository_url,
    hvr.validated_by,
    hvr.validated_at,
    hvr.comments AS validation_comments
   FROM ((public.human_validations hv
     JOIN public.tasks t ON ((hv.task_id = t.tasks_id)))
     LEFT JOIN public.human_validation_responses hvr ON ((hv.human_validations_id = hvr.human_validation_id)))
  ORDER BY
        CASE
            WHEN ((hv.status)::text = 'pending'::text) THEN 0
            ELSE 1
        END,
        CASE
            WHEN ((hv.expires_at IS NOT NULL) AND (hv.expires_at < (now() + '01:00:00'::interval))) THEN 0
            ELSE 1
        END, hv.created_at DESC;


ALTER TABLE public.validation_dashboard OWNER TO admin;

--
-- Name: VIEW validation_dashboard; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON VIEW public.validation_dashboard IS 'Vue optimisée pour l''interface d''administration des validations';


--
-- Name: validation_history; Type: VIEW; Schema: public; Owner: admin
--

CREATE VIEW public.validation_history AS
 SELECT hv.validation_id,
    hv.task_title,
    hv.status,
    hv.created_at,
    hv.expires_at,
    hvr.response_status,
    hvr.validated_by,
    hvr.validated_at,
    hvr.validation_duration_seconds,
    va.action_type,
    va.action_status,
    va.merge_commit_hash,
    t.repository_url,
    t.priority
   FROM (((public.human_validations hv
     JOIN public.tasks t ON ((hv.task_id = t.tasks_id)))
     LEFT JOIN public.human_validation_responses hvr ON ((hv.human_validations_id = hvr.human_validation_id)))
     LEFT JOIN public.validation_actions va ON ((hv.human_validations_id = va.human_validation_id)))
  WHERE ((hv.status)::text <> 'pending'::text)
  ORDER BY hv.created_at DESC;


ALTER TABLE public.validation_history OWNER TO admin;

--
-- Name: VIEW validation_history; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON VIEW public.validation_history IS 'Historique complet des validations avec actions associées';


--
-- Name: webhook_events; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.webhook_events (
    webhook_events_id bigint NOT NULL,
    source character varying(50) NOT NULL,
    event_type character varying(100),
    payload jsonb NOT NULL,
    headers jsonb,
    signature text,
    processed boolean DEFAULT false NOT NULL,
    processing_status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    related_task_id bigint,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone
)
PARTITION BY RANGE (received_at);


ALTER TABLE public.webhook_events OWNER TO admin;

--
-- Name: TABLE webhook_events; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.webhook_events IS 'Événements webhook reçus (Monday.com, GitHub, etc.)';


--
-- Name: webhook_events_2025_09; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.webhook_events_2025_09 (
    webhook_events_id bigint NOT NULL,
    source character varying(50) NOT NULL,
    event_type character varying(100),
    payload jsonb NOT NULL,
    headers jsonb,
    signature text,
    processed boolean DEFAULT false NOT NULL,
    processing_status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    related_task_id bigint,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone
);


ALTER TABLE public.webhook_events_2025_09 OWNER TO admin;

--
-- Name: webhook_events_p2025_10; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.webhook_events_p2025_10 (
    webhook_events_id bigint NOT NULL,
    source character varying(50) NOT NULL,
    event_type character varying(100),
    payload jsonb NOT NULL,
    headers jsonb,
    signature text,
    processed boolean DEFAULT false NOT NULL,
    processing_status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    related_task_id bigint,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone
);


ALTER TABLE public.webhook_events_p2025_10 OWNER TO admin;

--
-- Name: webhook_events_p2025_11; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.webhook_events_p2025_11 (
    webhook_events_id bigint NOT NULL,
    source character varying(50) NOT NULL,
    event_type character varying(100),
    payload jsonb NOT NULL,
    headers jsonb,
    signature text,
    processed boolean DEFAULT false NOT NULL,
    processing_status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    related_task_id bigint,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone
);


ALTER TABLE public.webhook_events_p2025_11 OWNER TO admin;

--
-- Name: webhook_events_p2025_12; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.webhook_events_p2025_12 (
    webhook_events_id bigint NOT NULL,
    source character varying(50) NOT NULL,
    event_type character varying(100),
    payload jsonb NOT NULL,
    headers jsonb,
    signature text,
    processed boolean DEFAULT false NOT NULL,
    processing_status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    related_task_id bigint,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone
);


ALTER TABLE public.webhook_events_p2025_12 OWNER TO admin;

--
-- Name: webhook_events_p2026_01; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.webhook_events_p2026_01 (
    webhook_events_id bigint NOT NULL,
    source character varying(50) NOT NULL,
    event_type character varying(100),
    payload jsonb NOT NULL,
    headers jsonb,
    signature text,
    processed boolean DEFAULT false NOT NULL,
    processing_status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    related_task_id bigint,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone
);


ALTER TABLE public.webhook_events_p2026_01 OWNER TO admin;

--
-- Name: webhook_events_webhook_events_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

ALTER TABLE public.webhook_events ALTER COLUMN webhook_events_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.webhook_events_webhook_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: workflow_cooldowns; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.workflow_cooldowns (
    cooldown_id integer NOT NULL,
    task_id integer NOT NULL,
    cooldown_type character varying(50) NOT NULL,
    cooldown_until timestamp without time zone NOT NULL,
    failed_reactivation_attempts integer DEFAULT 0,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.workflow_cooldowns OWNER TO admin;

--
-- Name: workflow_cooldowns_cooldown_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.workflow_cooldowns_cooldown_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.workflow_cooldowns_cooldown_id_seq OWNER TO admin;

--
-- Name: workflow_cooldowns_cooldown_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.workflow_cooldowns_cooldown_id_seq OWNED BY public.workflow_cooldowns.cooldown_id;


--
-- Name: workflow_locks; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.workflow_locks (
    lock_id integer NOT NULL,
    task_id integer NOT NULL,
    lock_key character varying(255) NOT NULL,
    is_locked boolean DEFAULT true,
    is_active boolean DEFAULT true,
    locked_at timestamp without time zone DEFAULT now(),
    released_at timestamp without time zone,
    lock_owner character varying(255),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.workflow_locks OWNER TO admin;

--
-- Name: workflow_locks_lock_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.workflow_locks_lock_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.workflow_locks_lock_id_seq OWNER TO admin;

--
-- Name: workflow_locks_lock_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.workflow_locks_lock_id_seq OWNED BY public.workflow_locks.lock_id;


--
-- Name: workflow_metrics_summary; Type: VIEW; Schema: public; Owner: admin
--

CREATE VIEW public.workflow_metrics_summary AS
 SELECT t.tasks_id,
    t.title,
    t.repository_url,
    t.internal_status,
    count(DISTINCT tr.tasks_runs_id) AS total_runs,
    count(DISTINCT tr.tasks_runs_id) FILTER (WHERE ((tr.status)::text = 'completed'::text)) AS successful_runs,
    count(DISTINCT tr.tasks_runs_id) FILTER (WHERE ((tr.status)::text = 'failed'::text)) AS failed_runs,
    avg(pm.total_duration_seconds) AS avg_duration_seconds,
    avg(pm.total_ai_cost) AS avg_cost_usd,
    max(tr.completed_at) AS last_run_at
   FROM ((public.tasks t
     LEFT JOIN public.task_runs tr ON ((t.tasks_id = tr.task_id)))
     LEFT JOIN public.performance_metrics pm ON ((tr.tasks_runs_id = pm.task_run_id)))
  GROUP BY t.tasks_id, t.title, t.repository_url, t.internal_status
  ORDER BY (max(tr.completed_at)) DESC NULLS LAST;


ALTER TABLE public.workflow_metrics_summary OWNER TO admin;

--
-- Name: VIEW workflow_metrics_summary; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON VIEW public.workflow_metrics_summary IS 'Résumé des métriques par tâche';


--
-- Name: workflow_queue; Type: TABLE; Schema: public; Owner: admin
--

CREATE TABLE public.workflow_queue (
    queue_id character varying(50) NOT NULL,
    monday_item_id bigint NOT NULL,
    task_id integer,
    status character varying(50) DEFAULT 'pending'::character varying NOT NULL,
    priority integer DEFAULT 5 NOT NULL,
    queued_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    celery_task_id character varying(255),
    error text,
    retry_count integer DEFAULT 0 NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.workflow_queue OWNER TO admin;

--
-- Name: TABLE workflow_queue; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON TABLE public.workflow_queue IS 'Queue de workflows pour éviter le traitement concurrent par Monday item';


--
-- Name: COLUMN workflow_queue.queue_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_queue.queue_id IS 'Identifiant unique de la queue entry';


--
-- Name: COLUMN workflow_queue.monday_item_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_queue.monday_item_id IS 'ID de l''item Monday.com';


--
-- Name: COLUMN workflow_queue.task_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_queue.task_id IS 'ID de la tâche en base (si créée)';


--
-- Name: COLUMN workflow_queue.status; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_queue.status IS 'Statut: pending, running, waiting_validation, completed, failed, cancelled, timeout';


--
-- Name: COLUMN workflow_queue.priority; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_queue.priority IS 'Priorité (1-10, plus haut = plus prioritaire)';


--
-- Name: COLUMN workflow_queue.celery_task_id; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_queue.celery_task_id IS 'ID de la tâche Celery associée';


--
-- Name: COLUMN workflow_queue.payload; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON COLUMN public.workflow_queue.payload IS 'Payload complet du webhook pour rejouer si nécessaire';


--
-- Name: workflow_reactivations_id_seq; Type: SEQUENCE; Schema: public; Owner: admin
--

CREATE SEQUENCE public.workflow_reactivations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.workflow_reactivations_id_seq OWNER TO admin;

--
-- Name: workflow_reactivations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: admin
--

ALTER SEQUENCE public.workflow_reactivations_id_seq OWNED BY public.workflow_reactivations.id;


--
-- Name: webhook_events_2025_09; Type: TABLE ATTACH; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events ATTACH PARTITION public.webhook_events_2025_09 FOR VALUES FROM ('2025-09-01 00:00:00+00') TO ('2025-10-01 00:00:00+00');


--
-- Name: webhook_events_p2025_10; Type: TABLE ATTACH; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events ATTACH PARTITION public.webhook_events_p2025_10 FOR VALUES FROM ('2025-10-01 00:00:00+00') TO ('2025-11-01 00:00:00+00');


--
-- Name: webhook_events_p2025_11; Type: TABLE ATTACH; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events ATTACH PARTITION public.webhook_events_p2025_11 FOR VALUES FROM ('2025-11-01 00:00:00+00') TO ('2025-12-01 00:00:00+00');


--
-- Name: webhook_events_p2025_12; Type: TABLE ATTACH; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events ATTACH PARTITION public.webhook_events_p2025_12 FOR VALUES FROM ('2025-12-01 00:00:00+00') TO ('2026-01-01 00:00:00+00');


--
-- Name: webhook_events_p2026_01; Type: TABLE ATTACH; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events ATTACH PARTITION public.webhook_events_p2026_01 FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-02-01 00:00:00+00');


--
-- Name: ai_prompt_templates template_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_prompt_templates ALTER COLUMN template_id SET DEFAULT nextval('public.ai_prompt_templates_template_id_seq'::regclass);


--
-- Name: ai_prompt_usage usage_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_prompt_usage ALTER COLUMN usage_id SET DEFAULT nextval('public.ai_prompt_usage_usage_id_seq'::regclass);


--
-- Name: ai_usage_logs id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_usage_logs ALTER COLUMN id SET DEFAULT nextval('public.ai_usage_logs_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: code_quality_feedback feedback_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.code_quality_feedback ALTER COLUMN feedback_id SET DEFAULT nextval('public.code_quality_feedback_feedback_id_seq'::regclass);


--
-- Name: message_embeddings id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.message_embeddings ALTER COLUMN id SET DEFAULT nextval('public.message_embeddings_id_seq'::regclass);


--
-- Name: monday_updates_history update_history_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.monday_updates_history ALTER COLUMN update_history_id SET DEFAULT nextval('public.monday_updates_history_update_history_id_seq'::regclass);


--
-- Name: project_context_embeddings id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_context_embeddings ALTER COLUMN id SET DEFAULT nextval('public.project_context_embeddings_id_seq'::regclass);


--
-- Name: rate_limits rate_limit_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rate_limits ALTER COLUMN rate_limit_id SET DEFAULT nextval('public.rate_limits_rate_limit_id_seq'::regclass);


--
-- Name: system_users user_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.system_users ALTER COLUMN user_id SET DEFAULT nextval('public.system_users_user_id_seq'::regclass);


--
-- Name: task_context_memory memory_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_context_memory ALTER COLUMN memory_id SET DEFAULT nextval('public.task_context_memory_memory_id_seq'::regclass);


--
-- Name: task_update_triggers trigger_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_update_triggers ALTER COLUMN trigger_id SET DEFAULT nextval('public.task_update_triggers_trigger_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- Name: workflow_cooldowns cooldown_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_cooldowns ALTER COLUMN cooldown_id SET DEFAULT nextval('public.workflow_cooldowns_cooldown_id_seq'::regclass);


--
-- Name: workflow_locks lock_id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_locks ALTER COLUMN lock_id SET DEFAULT nextval('public.workflow_locks_lock_id_seq'::regclass);


--
-- Name: workflow_reactivations id; Type: DEFAULT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_reactivations ALTER COLUMN id SET DEFAULT nextval('public.workflow_reactivations_id_seq'::regclass);


--
-- Name: ai_code_generations ai_code_generations_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_code_generations
    ADD CONSTRAINT ai_code_generations_pkey PRIMARY KEY (ai_code_generations_id);


--
-- Name: ai_cost_tracking ai_cost_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_cost_tracking
    ADD CONSTRAINT ai_cost_tracking_pkey PRIMARY KEY (ai_cost_tracking_id);


--
-- Name: ai_interactions ai_interactions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_interactions
    ADD CONSTRAINT ai_interactions_pkey PRIMARY KEY (ai_interactions_id);


--
-- Name: ai_prompt_templates ai_prompt_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_prompt_templates
    ADD CONSTRAINT ai_prompt_templates_pkey PRIMARY KEY (template_id);


--
-- Name: ai_prompt_templates ai_prompt_templates_template_name_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_prompt_templates
    ADD CONSTRAINT ai_prompt_templates_template_name_key UNIQUE (template_name);


--
-- Name: ai_prompt_usage ai_prompt_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_prompt_usage
    ADD CONSTRAINT ai_prompt_usage_pkey PRIMARY KEY (usage_id);


--
-- Name: ai_usage_logs ai_usage_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_usage_logs
    ADD CONSTRAINT ai_usage_logs_pkey PRIMARY KEY (id);


--
-- Name: application_logs application_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.application_logs
    ADD CONSTRAINT application_logs_pkey PRIMARY KEY (application_logs_id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: celery_taskmeta celery_taskmeta_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.celery_taskmeta
    ADD CONSTRAINT celery_taskmeta_pkey PRIMARY KEY (id);


--
-- Name: celery_taskmeta celery_taskmeta_task_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.celery_taskmeta
    ADD CONSTRAINT celery_taskmeta_task_id_key UNIQUE (task_id);


--
-- Name: celery_tasksetmeta celery_tasksetmeta_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.celery_tasksetmeta
    ADD CONSTRAINT celery_tasksetmeta_pkey PRIMARY KEY (id);


--
-- Name: celery_tasksetmeta celery_tasksetmeta_taskset_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.celery_tasksetmeta
    ADD CONSTRAINT celery_tasksetmeta_taskset_id_key UNIQUE (taskset_id);


--
-- Name: code_quality_feedback code_quality_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.code_quality_feedback
    ADD CONSTRAINT code_quality_feedback_pkey PRIMARY KEY (feedback_id);


--
-- Name: human_validation_responses human_validation_responses_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.human_validation_responses
    ADD CONSTRAINT human_validation_responses_pkey PRIMARY KEY (human_validation_responses_id);


--
-- Name: human_validations human_validations_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.human_validations
    ADD CONSTRAINT human_validations_pkey PRIMARY KEY (human_validations_id);


--
-- Name: human_validations human_validations_validation_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.human_validations
    ADD CONSTRAINT human_validations_validation_id_key UNIQUE (validation_id);


--
-- Name: message_embeddings message_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.message_embeddings
    ADD CONSTRAINT message_embeddings_pkey PRIMARY KEY (id);


--
-- Name: monday_updates_history monday_updates_history_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.monday_updates_history
    ADD CONSTRAINT monday_updates_history_pkey PRIMARY KEY (update_history_id);


--
-- Name: performance_metrics performance_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.performance_metrics
    ADD CONSTRAINT performance_metrics_pkey PRIMARY KEY (performance_metrics_id);


--
-- Name: project_context_embeddings project_context_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.project_context_embeddings
    ADD CONSTRAINT project_context_embeddings_pkey PRIMARY KEY (id);


--
-- Name: pull_requests pull_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.pull_requests
    ADD CONSTRAINT pull_requests_pkey PRIMARY KEY (pull_requests_id);


--
-- Name: rate_limits rate_limits_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rate_limits
    ADD CONSTRAINT rate_limits_pkey PRIMARY KEY (rate_limit_id);


--
-- Name: run_step_checkpoints run_step_checkpoints_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.run_step_checkpoints
    ADD CONSTRAINT run_step_checkpoints_pkey PRIMARY KEY (checkpoint_id);


--
-- Name: run_steps run_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.run_steps
    ADD CONSTRAINT run_steps_pkey PRIMARY KEY (run_steps_id);


--
-- Name: system_config system_config_key_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.system_config
    ADD CONSTRAINT system_config_key_key UNIQUE (key);


--
-- Name: system_config system_config_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.system_config
    ADD CONSTRAINT system_config_pkey PRIMARY KEY (system_config_id);


--
-- Name: system_users system_users_email_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.system_users
    ADD CONSTRAINT system_users_email_key UNIQUE (email);


--
-- Name: system_users system_users_monday_user_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.system_users
    ADD CONSTRAINT system_users_monday_user_id_key UNIQUE (monday_user_id);


--
-- Name: system_users system_users_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.system_users
    ADD CONSTRAINT system_users_pkey PRIMARY KEY (user_id);


--
-- Name: system_users system_users_username_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.system_users
    ADD CONSTRAINT system_users_username_key UNIQUE (username);


--
-- Name: task_context_memory task_context_memory_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_context_memory
    ADD CONSTRAINT task_context_memory_pkey PRIMARY KEY (memory_id);


--
-- Name: task_runs task_runs_celery_task_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_runs
    ADD CONSTRAINT task_runs_celery_task_id_key UNIQUE (celery_task_id);


--
-- Name: task_runs task_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_runs
    ADD CONSTRAINT task_runs_pkey PRIMARY KEY (tasks_runs_id);


--
-- Name: task_update_triggers task_update_triggers_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_update_triggers
    ADD CONSTRAINT task_update_triggers_pkey PRIMARY KEY (trigger_id);


--
-- Name: tasks tasks_monday_item_id_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_monday_item_id_key UNIQUE (monday_item_id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (tasks_id);


--
-- Name: test_results test_results_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.test_results
    ADD CONSTRAINT test_results_pkey PRIMARY KEY (test_results_id);


--
-- Name: message_embeddings unique_message_update; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.message_embeddings
    ADD CONSTRAINT unique_message_update UNIQUE (monday_update_id);


--
-- Name: human_validations unique_validation_per_run; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.human_validations
    ADD CONSTRAINT unique_validation_per_run UNIQUE (task_run_id, validation_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: validation_actions validation_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.validation_actions
    ADD CONSTRAINT validation_actions_pkey PRIMARY KEY (validation_actions_id);


--
-- Name: webhook_events webhook_events_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events
    ADD CONSTRAINT webhook_events_pkey PRIMARY KEY (webhook_events_id, received_at);


--
-- Name: webhook_events_2025_09 webhook_events_2025_09_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events_2025_09
    ADD CONSTRAINT webhook_events_2025_09_pkey PRIMARY KEY (webhook_events_id, received_at);


--
-- Name: webhook_events_p2025_10 webhook_events_p2025_10_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events_p2025_10
    ADD CONSTRAINT webhook_events_p2025_10_pkey PRIMARY KEY (webhook_events_id, received_at);


--
-- Name: webhook_events_p2025_11 webhook_events_p2025_11_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events_p2025_11
    ADD CONSTRAINT webhook_events_p2025_11_pkey PRIMARY KEY (webhook_events_id, received_at);


--
-- Name: webhook_events_p2025_12 webhook_events_p2025_12_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events_p2025_12
    ADD CONSTRAINT webhook_events_p2025_12_pkey PRIMARY KEY (webhook_events_id, received_at);


--
-- Name: webhook_events_p2026_01 webhook_events_p2026_01_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.webhook_events_p2026_01
    ADD CONSTRAINT webhook_events_p2026_01_pkey PRIMARY KEY (webhook_events_id, received_at);


--
-- Name: workflow_cooldowns workflow_cooldowns_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_cooldowns
    ADD CONSTRAINT workflow_cooldowns_pkey PRIMARY KEY (cooldown_id);


--
-- Name: workflow_locks workflow_locks_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_locks
    ADD CONSTRAINT workflow_locks_pkey PRIMARY KEY (lock_id);


--
-- Name: workflow_queue workflow_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_queue
    ADD CONSTRAINT workflow_queue_pkey PRIMARY KEY (queue_id);


--
-- Name: workflow_reactivations workflow_reactivations_pkey; Type: CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_reactivations
    ADD CONSTRAINT workflow_reactivations_pkey PRIMARY KEY (id);


--
-- Name: ai_usage_logs_date_provider_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ai_usage_logs_date_provider_idx ON public.ai_usage_logs USING btree ("timestamp", provider);


--
-- Name: ai_usage_logs_provider_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ai_usage_logs_provider_idx ON public.ai_usage_logs USING btree (provider);


--
-- Name: ai_usage_logs_task_id_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ai_usage_logs_task_id_idx ON public.ai_usage_logs USING btree (task_id);


--
-- Name: ai_usage_logs_timestamp_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ai_usage_logs_timestamp_idx ON public.ai_usage_logs USING btree ("timestamp");


--
-- Name: ai_usage_logs_workflow_id_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ai_usage_logs_workflow_id_idx ON public.ai_usage_logs USING btree (workflow_id);


--
-- Name: ai_usage_logs_workflow_timestamp_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX ai_usage_logs_workflow_timestamp_idx ON public.ai_usage_logs USING btree (workflow_id, "timestamp");


--
-- Name: idx_ai_code_gen_provider; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_code_gen_provider ON public.ai_code_generations USING btree (provider, generated_at DESC);


--
-- Name: idx_ai_code_gen_run; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_code_gen_run ON public.ai_code_generations USING btree (task_run_id);


--
-- Name: idx_ai_cost_provider_date; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_cost_provider_date ON public.ai_cost_tracking USING btree (provider, created_at DESC);


--
-- Name: idx_ai_cost_run; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_cost_run ON public.ai_cost_tracking USING btree (task_run_id);


--
-- Name: idx_ai_cost_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_cost_task ON public.ai_cost_tracking USING btree (task_id);


--
-- Name: idx_ai_interactions_provider; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_interactions_provider ON public.ai_interactions USING btree (ai_provider, created_at DESC);


--
-- Name: idx_ai_interactions_step; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_interactions_step ON public.ai_interactions USING btree (run_step_id);


--
-- Name: idx_ai_prompt_templates_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_prompt_templates_active ON public.ai_prompt_templates USING btree (is_active);


--
-- Name: idx_ai_prompt_templates_category; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_prompt_templates_category ON public.ai_prompt_templates USING btree (template_category);


--
-- Name: idx_ai_usage_logs_cost; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_usage_logs_cost ON public.ai_usage_logs USING btree (estimated_cost DESC);


--
-- Name: idx_ai_usage_logs_provider; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_usage_logs_provider ON public.ai_usage_logs USING btree (provider);


--
-- Name: idx_ai_usage_logs_run; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_usage_logs_run ON public.ai_usage_logs USING btree (task_id);


--
-- Name: idx_ai_usage_logs_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_usage_logs_task ON public.ai_usage_logs USING btree (workflow_id);


--
-- Name: idx_ai_usage_logs_timestamp; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_ai_usage_logs_timestamp ON public.ai_usage_logs USING btree ("timestamp");


--
-- Name: idx_application_logs_component; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_application_logs_component ON public.application_logs USING btree (source_component, ts DESC);


--
-- Name: idx_application_logs_level; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_application_logs_level ON public.application_logs USING btree (level, ts DESC);


--
-- Name: idx_application_logs_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_application_logs_task ON public.application_logs USING btree (task_id, ts DESC);


--
-- Name: idx_audit_logs_action; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_audit_logs_action ON public.audit_logs USING btree (action);


--
-- Name: idx_audit_logs_details; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_audit_logs_details ON public.audit_logs USING gin (details);


--
-- Name: idx_audit_logs_severity; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_audit_logs_severity ON public.audit_logs USING btree (severity);


--
-- Name: idx_audit_logs_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_audit_logs_status ON public.audit_logs USING btree (status);


--
-- Name: idx_audit_logs_timestamp; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_audit_logs_timestamp ON public.audit_logs USING btree ("timestamp" DESC);


--
-- Name: idx_audit_logs_user_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_audit_logs_user_id ON public.audit_logs USING btree (user_id);


--
-- Name: idx_checkpoints_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_checkpoints_created_at ON public.run_step_checkpoints USING btree (created_at DESC);


--
-- Name: idx_checkpoints_step_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_checkpoints_step_id ON public.run_step_checkpoints USING btree (step_id);


--
-- Name: idx_human_validation_responses_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validation_responses_status ON public.human_validation_responses USING btree (response_status);


--
-- Name: idx_human_validation_responses_validated_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validation_responses_validated_at ON public.human_validation_responses USING btree (validated_at DESC);


--
-- Name: idx_human_validation_responses_validated_by; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validation_responses_validated_by ON public.human_validation_responses USING btree (validated_by);


--
-- Name: idx_human_validation_responses_validation_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validation_responses_validation_id ON public.human_validation_responses USING btree (validation_id);


--
-- Name: idx_human_validations_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_created_at ON public.human_validations USING btree (created_at DESC);


--
-- Name: idx_human_validations_expires_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_expires_at ON public.human_validations USING btree (expires_at) WHERE (expires_at IS NOT NULL);


--
-- Name: idx_human_validations_is_retry; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_is_retry ON public.human_validations USING btree (is_retry) WHERE (is_retry = true);


--
-- Name: idx_human_validations_parent_validation; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_parent_validation ON public.human_validations USING btree (parent_validation_id) WHERE (parent_validation_id IS NOT NULL);


--
-- Name: idx_human_validations_rejection_count; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_rejection_count ON public.human_validations USING btree (rejection_count);


--
-- Name: idx_human_validations_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_status ON public.human_validations USING btree (status);


--
-- Name: idx_human_validations_status_expires; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_status_expires ON public.human_validations USING btree (status, expires_at);


--
-- Name: idx_human_validations_task_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_task_id ON public.human_validations USING btree (task_id);


--
-- Name: idx_human_validations_updated_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_updated_at ON public.human_validations USING btree (updated_at DESC);


--
-- Name: idx_human_validations_user_email; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_user_email ON public.human_validations USING btree (user_email);


--
-- Name: idx_human_validations_validation_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_human_validations_validation_id ON public.human_validations USING btree (validation_id);


--
-- Name: idx_perf_recorded; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_perf_recorded ON public.performance_metrics USING btree (recorded_at DESC);


--
-- Name: idx_perf_task_run; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_perf_task_run ON public.performance_metrics USING btree (task_id, task_run_id);


--
-- Name: idx_pr_created; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pr_created ON public.pull_requests USING btree (created_at DESC);


--
-- Name: idx_pr_number; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pr_number ON public.pull_requests USING btree (github_pr_number);


--
-- Name: idx_pr_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pr_status ON public.pull_requests USING btree (pr_status);


--
-- Name: idx_pr_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_pr_task ON public.pull_requests USING btree (task_id);


--
-- Name: idx_prompt_templates_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_templates_active ON public.ai_prompt_templates USING btree (is_active);


--
-- Name: idx_prompt_templates_category; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_templates_category ON public.ai_prompt_templates USING btree (template_category);


--
-- Name: idx_prompt_templates_created; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_templates_created ON public.ai_prompt_templates USING btree (created_at);


--
-- Name: idx_prompt_templates_default; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_templates_default ON public.ai_prompt_templates USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_prompt_templates_success; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_templates_success ON public.ai_prompt_templates USING btree (avg_cost_usd);


--
-- Name: idx_prompt_usage_cost; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_usage_cost ON public.ai_prompt_usage USING btree (cost_usd DESC);


--
-- Name: idx_prompt_usage_date; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_usage_date ON public.ai_prompt_usage USING btree (executed_at DESC);


--
-- Name: idx_prompt_usage_interaction; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_usage_interaction ON public.ai_prompt_usage USING btree (executed_at);


--
-- Name: idx_prompt_usage_run; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_usage_run ON public.ai_prompt_usage USING btree (task_run_id);


--
-- Name: idx_prompt_usage_success; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_usage_success ON public.ai_prompt_usage USING btree (success);


--
-- Name: idx_prompt_usage_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_usage_task ON public.ai_prompt_usage USING btree (task_id);


--
-- Name: idx_prompt_usage_template; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_usage_template ON public.ai_prompt_usage USING btree (template_id);


--
-- Name: idx_prompt_usage_user; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_prompt_usage_user ON public.ai_prompt_usage USING btree (template_id, executed_at);


--
-- Name: idx_run_steps_completed; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_run_steps_completed ON public.run_steps USING btree (task_run_id, completed_at) WHERE (completed_at IS NOT NULL);


--
-- Name: idx_run_steps_name_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_run_steps_name_status ON public.run_steps USING btree (node_name, status);


--
-- Name: idx_run_steps_run_order; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_run_steps_run_order ON public.run_steps USING btree (task_run_id, step_order);


--
-- Name: idx_run_steps_started_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_run_steps_started_at ON public.run_steps USING btree (started_at DESC);


--
-- Name: idx_run_steps_task_run; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_run_steps_task_run ON public.run_steps USING btree (task_run_id);


--
-- Name: idx_run_steps_task_run_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_run_steps_task_run_id ON public.run_steps USING btree (task_run_id);


--
-- Name: idx_system_config_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_system_config_type ON public.system_config USING btree (config_type);


--
-- Name: idx_system_users_email; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_system_users_email ON public.system_users USING btree (email);


--
-- Name: idx_system_users_is_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_system_users_is_active ON public.system_users USING btree (is_active);


--
-- Name: idx_task_runs_browser_qa_results; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_browser_qa_results ON public.task_runs USING gin (browser_qa_results);


--
-- Name: idx_task_runs_celery; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_celery ON public.task_runs USING btree (celery_task_id);


--
-- Name: idx_task_runs_completed_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_completed_at ON public.task_runs USING btree (completed_at DESC);


--
-- Name: idx_task_runs_completed_only; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_completed_only ON public.task_runs USING btree (task_id, completed_at DESC) WHERE (completed_at IS NOT NULL);


--
-- Name: idx_task_runs_duration_calc; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_duration_calc ON public.task_runs USING btree (started_at, completed_at) WHERE (completed_at IS NOT NULL);


--
-- Name: idx_task_runs_is_reactivation; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_is_reactivation ON public.task_runs USING btree (is_reactivation) WHERE (is_reactivation = true);


--
-- Name: idx_task_runs_parent_run_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_parent_run_id ON public.task_runs USING btree (parent_run_id) WHERE (parent_run_id IS NOT NULL);


--
-- Name: idx_task_runs_reactivation_chain; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_reactivation_chain ON public.task_runs USING btree (task_id, parent_run_id, is_reactivation) WHERE (is_reactivation = true);


--
-- Name: idx_task_runs_reactivation_count; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_reactivation_count ON public.task_runs USING btree (reactivation_count) WHERE (reactivation_count > 0);


--
-- Name: idx_task_runs_started_at_only; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_started_at_only ON public.task_runs USING btree (started_at DESC);


--
-- Name: idx_task_runs_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_status ON public.task_runs USING btree (status);


--
-- Name: idx_task_runs_task_id_only; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_task_id_only ON public.task_runs USING btree (task_id);


--
-- Name: idx_task_runs_task_started; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_task_runs_task_started ON public.task_runs USING btree (task_id, started_at DESC);


--
-- Name: idx_tasks_cooldown_until; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_cooldown_until ON public.tasks USING btree (cooldown_until) WHERE (cooldown_until IS NOT NULL);


--
-- Name: idx_tasks_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_created_at ON public.tasks USING btree (created_at DESC);


--
-- Name: idx_tasks_failed_attempts; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_failed_attempts ON public.tasks USING btree (failed_reactivation_attempts) WHERE (failed_reactivation_attempts > 0);


--
-- Name: idx_tasks_internal_status_full; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_internal_status_full ON public.tasks USING btree (internal_status);


--
-- Name: idx_tasks_internal_status_partial; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_internal_status_partial ON public.tasks USING btree (internal_status) WHERE ((internal_status)::text = ANY ((ARRAY['pending'::character varying, 'processing'::character varying])::text[]));


--
-- Name: idx_tasks_is_locked; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_is_locked ON public.tasks USING btree (is_locked) WHERE (is_locked = true);


--
-- Name: idx_tasks_monday_item_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_monday_item_id ON public.tasks USING btree (monday_item_id);


--
-- Name: idx_tasks_priority; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_priority ON public.tasks USING btree (priority);


--
-- Name: idx_tasks_priority_status_combo; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_priority_status_combo ON public.tasks USING btree (priority, internal_status);


--
-- Name: idx_tasks_reactivation; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_reactivation ON public.tasks USING btree (reactivation_count) WHERE (reactivation_count > 0);


--
-- Name: idx_tasks_repository; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_repository ON public.tasks USING btree (repository_url);


--
-- Name: idx_tasks_status_created_combo; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_tasks_status_created_combo ON public.tasks USING btree (internal_status, created_at DESC);


--
-- Name: idx_test_results_run; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_test_results_run ON public.test_results USING btree (task_run_id);


--
-- Name: idx_test_results_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_test_results_status ON public.test_results USING btree (status, executed_at DESC);


--
-- Name: idx_users_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_users_active ON public.users USING btree (is_active);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_role; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_users_role ON public.users USING btree (role);


--
-- Name: idx_validation_actions_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_validation_actions_created_at ON public.validation_actions USING btree (created_at DESC);


--
-- Name: idx_validation_actions_type_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_validation_actions_type_status ON public.validation_actions USING btree (action_type, action_status);


--
-- Name: idx_validation_actions_validation_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_validation_actions_validation_id ON public.validation_actions USING btree (validation_id);


--
-- Name: idx_webhook_events_event_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_event_type ON ONLY public.webhook_events USING btree (event_type);


--
-- Name: idx_webhook_events_p2025_10_processed; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2025_10_processed ON public.webhook_events_p2025_10 USING btree (processed, received_at);


--
-- Name: idx_webhook_events_p2025_10_source; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2025_10_source ON public.webhook_events_p2025_10 USING btree (source, event_type);


--
-- Name: idx_webhook_events_p2025_10_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2025_10_task ON public.webhook_events_p2025_10 USING btree (related_task_id);


--
-- Name: idx_webhook_events_p2025_11_processed; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2025_11_processed ON public.webhook_events_p2025_11 USING btree (processed, received_at);


--
-- Name: idx_webhook_events_p2025_11_source; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2025_11_source ON public.webhook_events_p2025_11 USING btree (source, event_type);


--
-- Name: idx_webhook_events_p2025_11_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2025_11_task ON public.webhook_events_p2025_11 USING btree (related_task_id);


--
-- Name: idx_webhook_events_p2025_12_processed; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2025_12_processed ON public.webhook_events_p2025_12 USING btree (processed, received_at);


--
-- Name: idx_webhook_events_p2025_12_source; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2025_12_source ON public.webhook_events_p2025_12 USING btree (source, event_type);


--
-- Name: idx_webhook_events_p2025_12_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2025_12_task ON public.webhook_events_p2025_12 USING btree (related_task_id);


--
-- Name: idx_webhook_events_p2026_01_processed; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2026_01_processed ON public.webhook_events_p2026_01 USING btree (processed, received_at);


--
-- Name: idx_webhook_events_p2026_01_source; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2026_01_source ON public.webhook_events_p2026_01 USING btree (source, event_type);


--
-- Name: idx_webhook_events_p2026_01_task; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_p2026_01_task ON public.webhook_events_p2026_01 USING btree (related_task_id);


--
-- Name: idx_webhook_events_processed; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_processed ON ONLY public.webhook_events USING btree (processed);


--
-- Name: idx_webhook_events_processed_2025_09; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_processed_2025_09 ON public.webhook_events_2025_09 USING btree (processed, received_at);


--
-- Name: idx_webhook_events_processed_part; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_processed_part ON public.webhook_events_2025_09 USING btree (processed, received_at);


--
-- Name: idx_webhook_events_received_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_received_at ON ONLY public.webhook_events USING btree (received_at DESC);


--
-- Name: idx_webhook_events_source_2025_09; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_source_2025_09 ON public.webhook_events_2025_09 USING btree (source, event_type);


--
-- Name: idx_webhook_events_source_part; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_webhook_events_source_part ON public.webhook_events_2025_09 USING btree (source, event_type);


--
-- Name: idx_workflow_cooldowns_task_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_cooldowns_task_id ON public.workflow_cooldowns USING btree (task_id);


--
-- Name: idx_workflow_cooldowns_until; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_cooldowns_until ON public.workflow_cooldowns USING btree (cooldown_until);


--
-- Name: idx_workflow_locks_is_active; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_locks_is_active ON public.workflow_locks USING btree (is_active);


--
-- Name: idx_workflow_locks_lock_key; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_locks_lock_key ON public.workflow_locks USING btree (lock_key);


--
-- Name: idx_workflow_locks_task_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_locks_task_id ON public.workflow_locks USING btree (task_id);


--
-- Name: idx_workflow_queue_completed; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_queue_completed ON public.workflow_queue USING btree (completed_at) WHERE (completed_at IS NOT NULL);


--
-- Name: idx_workflow_queue_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_queue_created_at ON public.workflow_queue USING btree (created_at DESC);


--
-- Name: idx_workflow_queue_monday_item; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_queue_monday_item ON public.workflow_queue USING btree (monday_item_id, queued_at);


--
-- Name: idx_workflow_queue_monday_item_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_queue_monday_item_id ON public.workflow_queue USING btree (monday_item_id);


--
-- Name: idx_workflow_queue_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_queue_status ON public.workflow_queue USING btree (status, queued_at);


--
-- Name: idx_workflow_reactivations_created_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_reactivations_created_at ON public.workflow_reactivations USING btree (created_at);


--
-- Name: idx_workflow_reactivations_reactivated_at; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_reactivations_reactivated_at ON public.workflow_reactivations USING btree (reactivated_at DESC);


--
-- Name: idx_workflow_reactivations_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_reactivations_status ON public.workflow_reactivations USING btree (status);


--
-- Name: idx_workflow_reactivations_task_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_reactivations_task_id ON public.workflow_reactivations USING btree (task_id);


--
-- Name: idx_workflow_reactivations_trigger_type; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_reactivations_trigger_type ON public.workflow_reactivations USING btree (trigger_type);


--
-- Name: idx_workflow_reactivations_update_data; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_reactivations_update_data ON public.workflow_reactivations USING gin (update_data);


--
-- Name: idx_workflow_reactivations_workflow_id; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_reactivations_workflow_id ON public.workflow_reactivations USING btree (workflow_id);


--
-- Name: idx_workflow_reactivations_workflow_status; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX idx_workflow_reactivations_workflow_status ON public.workflow_reactivations USING btree (workflow_id, status);


--
-- Name: message_embeddings_created_at_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX message_embeddings_created_at_idx ON public.message_embeddings USING btree (created_at DESC);


--
-- Name: message_embeddings_embedding_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX message_embeddings_embedding_idx ON public.message_embeddings USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: INDEX message_embeddings_embedding_idx; Type: COMMENT; Schema: public; Owner: admin
--

COMMENT ON INDEX public.message_embeddings_embedding_idx IS 'Index HNSW pour recherche rapide par similarité cosinus';


--
-- Name: message_embeddings_message_type_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX message_embeddings_message_type_idx ON public.message_embeddings USING btree (message_type);


--
-- Name: message_embeddings_metadata_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX message_embeddings_metadata_idx ON public.message_embeddings USING gin (metadata);


--
-- Name: message_embeddings_monday_item_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX message_embeddings_monday_item_idx ON public.message_embeddings USING btree (monday_item_id);


--
-- Name: message_embeddings_task_id_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX message_embeddings_task_id_idx ON public.message_embeddings USING btree (task_id);


--
-- Name: project_context_embeddings_embedding_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX project_context_embeddings_embedding_idx ON public.project_context_embeddings USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: project_context_embeddings_repo_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX project_context_embeddings_repo_idx ON public.project_context_embeddings USING btree (repository_url);


--
-- Name: project_context_embeddings_type_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX project_context_embeddings_type_idx ON public.project_context_embeddings USING btree (context_type);


--
-- Name: unique_task_reactivation_run; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX unique_task_reactivation_run ON public.task_runs USING btree (task_id, reactivation_count) WHERE ((is_reactivation = true) AND (task_id IS NOT NULL));


--
-- Name: uq_task_runs_task_run_number; Type: INDEX; Schema: public; Owner: admin
--

CREATE UNIQUE INDEX uq_task_runs_task_run_number ON public.task_runs USING btree (task_id, run_number);


--
-- Name: webhook_events_2025_09_event_type_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_2025_09_event_type_idx ON public.webhook_events_2025_09 USING btree (event_type);


--
-- Name: webhook_events_2025_09_processed_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_2025_09_processed_idx ON public.webhook_events_2025_09 USING btree (processed);


--
-- Name: webhook_events_2025_09_received_at_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_2025_09_received_at_idx ON public.webhook_events_2025_09 USING btree (received_at DESC);


--
-- Name: webhook_events_p2025_10_event_type_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2025_10_event_type_idx ON public.webhook_events_p2025_10 USING btree (event_type);


--
-- Name: webhook_events_p2025_10_processed_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2025_10_processed_idx ON public.webhook_events_p2025_10 USING btree (processed);


--
-- Name: webhook_events_p2025_10_received_at_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2025_10_received_at_idx ON public.webhook_events_p2025_10 USING btree (received_at DESC);


--
-- Name: webhook_events_p2025_11_event_type_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2025_11_event_type_idx ON public.webhook_events_p2025_11 USING btree (event_type);


--
-- Name: webhook_events_p2025_11_processed_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2025_11_processed_idx ON public.webhook_events_p2025_11 USING btree (processed);


--
-- Name: webhook_events_p2025_11_received_at_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2025_11_received_at_idx ON public.webhook_events_p2025_11 USING btree (received_at DESC);


--
-- Name: webhook_events_p2025_12_event_type_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2025_12_event_type_idx ON public.webhook_events_p2025_12 USING btree (event_type);


--
-- Name: webhook_events_p2025_12_processed_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2025_12_processed_idx ON public.webhook_events_p2025_12 USING btree (processed);


--
-- Name: webhook_events_p2025_12_received_at_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2025_12_received_at_idx ON public.webhook_events_p2025_12 USING btree (received_at DESC);


--
-- Name: webhook_events_p2026_01_event_type_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2026_01_event_type_idx ON public.webhook_events_p2026_01 USING btree (event_type);


--
-- Name: webhook_events_p2026_01_processed_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2026_01_processed_idx ON public.webhook_events_p2026_01 USING btree (processed);


--
-- Name: webhook_events_p2026_01_received_at_idx; Type: INDEX; Schema: public; Owner: admin
--

CREATE INDEX webhook_events_p2026_01_received_at_idx ON public.webhook_events_p2026_01 USING btree (received_at DESC);


--
-- Name: webhook_events_2025_09_event_type_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_event_type ATTACH PARTITION public.webhook_events_2025_09_event_type_idx;


--
-- Name: webhook_events_2025_09_pkey; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.webhook_events_pkey ATTACH PARTITION public.webhook_events_2025_09_pkey;


--
-- Name: webhook_events_2025_09_processed_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_processed ATTACH PARTITION public.webhook_events_2025_09_processed_idx;


--
-- Name: webhook_events_2025_09_received_at_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_received_at ATTACH PARTITION public.webhook_events_2025_09_received_at_idx;


--
-- Name: webhook_events_p2025_10_event_type_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_event_type ATTACH PARTITION public.webhook_events_p2025_10_event_type_idx;


--
-- Name: webhook_events_p2025_10_pkey; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.webhook_events_pkey ATTACH PARTITION public.webhook_events_p2025_10_pkey;


--
-- Name: webhook_events_p2025_10_processed_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_processed ATTACH PARTITION public.webhook_events_p2025_10_processed_idx;


--
-- Name: webhook_events_p2025_10_received_at_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_received_at ATTACH PARTITION public.webhook_events_p2025_10_received_at_idx;


--
-- Name: webhook_events_p2025_11_event_type_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_event_type ATTACH PARTITION public.webhook_events_p2025_11_event_type_idx;


--
-- Name: webhook_events_p2025_11_pkey; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.webhook_events_pkey ATTACH PARTITION public.webhook_events_p2025_11_pkey;


--
-- Name: webhook_events_p2025_11_processed_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_processed ATTACH PARTITION public.webhook_events_p2025_11_processed_idx;


--
-- Name: webhook_events_p2025_11_received_at_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_received_at ATTACH PARTITION public.webhook_events_p2025_11_received_at_idx;


--
-- Name: webhook_events_p2025_12_event_type_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_event_type ATTACH PARTITION public.webhook_events_p2025_12_event_type_idx;


--
-- Name: webhook_events_p2025_12_pkey; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.webhook_events_pkey ATTACH PARTITION public.webhook_events_p2025_12_pkey;


--
-- Name: webhook_events_p2025_12_processed_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_processed ATTACH PARTITION public.webhook_events_p2025_12_processed_idx;


--
-- Name: webhook_events_p2025_12_received_at_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_received_at ATTACH PARTITION public.webhook_events_p2025_12_received_at_idx;


--
-- Name: webhook_events_p2026_01_event_type_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_event_type ATTACH PARTITION public.webhook_events_p2026_01_event_type_idx;


--
-- Name: webhook_events_p2026_01_pkey; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.webhook_events_pkey ATTACH PARTITION public.webhook_events_p2026_01_pkey;


--
-- Name: webhook_events_p2026_01_processed_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_processed ATTACH PARTITION public.webhook_events_p2026_01_processed_idx;


--
-- Name: webhook_events_p2026_01_received_at_idx; Type: INDEX ATTACH; Schema: public; Owner: admin
--

ALTER INDEX public.idx_webhook_events_received_at ATTACH PARTITION public.webhook_events_p2026_01_received_at_idx;


--
-- Name: human_validation_responses check_rejection_limit_trigger; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER check_rejection_limit_trigger BEFORE INSERT OR UPDATE ON public.human_validation_responses FOR EACH ROW EXECUTE FUNCTION public.check_rejection_limit();


--
-- Name: message_embeddings message_embeddings_updated_at_trigger; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER message_embeddings_updated_at_trigger BEFORE UPDATE ON public.message_embeddings FOR EACH ROW EXECUTE FUNCTION public.update_message_embeddings_updated_at();


--
-- Name: human_validation_responses sync_validation_status_trigger; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER sync_validation_status_trigger AFTER INSERT ON public.human_validation_responses FOR EACH ROW EXECUTE FUNCTION public.sync_validation_status();


--
-- Name: system_config touch_system_config_updated_at; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER touch_system_config_updated_at BEFORE UPDATE ON public.system_config FOR EACH ROW EXECUTE FUNCTION public.trg_touch_updated_at();


--
-- Name: tasks touch_tasks_updated_at; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER touch_tasks_updated_at BEFORE UPDATE ON public.tasks FOR EACH ROW EXECUTE FUNCTION public.trg_touch_updated_at();


--
-- Name: ai_prompt_usage trg_update_prompt_stats; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER trg_update_prompt_stats AFTER INSERT ON public.ai_prompt_usage FOR EACH ROW EXECUTE FUNCTION public.update_prompt_template_stats();


--
-- Name: tasks trigger_reset_failed_attempts; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER trigger_reset_failed_attempts BEFORE UPDATE ON public.tasks FOR EACH ROW WHEN (((new.internal_status)::text = 'completed'::text)) EXECUTE FUNCTION public.reset_failed_attempts_on_success();


--
-- Name: workflow_queue trigger_update_workflow_queue_timestamp; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER trigger_update_workflow_queue_timestamp BEFORE UPDATE ON public.workflow_queue FOR EACH ROW EXECUTE FUNCTION public.update_workflow_queue_timestamp();


--
-- Name: workflow_reactivations trigger_workflow_reactivations_updated_at; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER trigger_workflow_reactivations_updated_at BEFORE UPDATE ON public.workflow_reactivations FOR EACH ROW EXECUTE FUNCTION public.update_workflow_reactivations_updated_at();


--
-- Name: users users_updated_at_trigger; Type: TRIGGER; Schema: public; Owner: admin
--

CREATE TRIGGER users_updated_at_trigger BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_users_updated_at();


--
-- Name: ai_prompt_usage ai_prompt_usage_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.ai_prompt_usage
    ADD CONSTRAINT ai_prompt_usage_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.ai_prompt_templates(template_id) ON DELETE SET NULL;


--
-- Name: application_logs application_logs_run_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.application_logs
    ADD CONSTRAINT application_logs_run_step_id_fkey FOREIGN KEY (run_step_id) REFERENCES public.run_steps(run_steps_id) ON DELETE SET NULL;


--
-- Name: application_logs application_logs_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.application_logs
    ADD CONSTRAINT application_logs_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id) ON DELETE SET NULL;


--
-- Name: application_logs application_logs_task_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.application_logs
    ADD CONSTRAINT application_logs_task_run_id_fkey FOREIGN KEY (task_run_id) REFERENCES public.task_runs(tasks_runs_id) ON DELETE SET NULL;


--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE SET NULL;


--
-- Name: code_quality_feedback code_quality_feedback_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.code_quality_feedback
    ADD CONSTRAINT code_quality_feedback_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id);


--
-- Name: code_quality_feedback code_quality_feedback_task_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.code_quality_feedback
    ADD CONSTRAINT code_quality_feedback_task_run_id_fkey FOREIGN KEY (task_run_id) REFERENCES public.task_runs(tasks_runs_id);


--
-- Name: workflow_reactivations fk_workflow_reactivations_workflow; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_reactivations
    ADD CONSTRAINT fk_workflow_reactivations_workflow FOREIGN KEY (workflow_id) REFERENCES public.tasks(tasks_id) ON DELETE CASCADE;


--
-- Name: human_validation_responses human_validation_responses_human_validation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.human_validation_responses
    ADD CONSTRAINT human_validation_responses_human_validation_id_fkey FOREIGN KEY (human_validation_id) REFERENCES public.human_validations(human_validations_id) ON DELETE CASCADE;


--
-- Name: human_validations human_validations_run_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.human_validations
    ADD CONSTRAINT human_validations_run_step_id_fkey FOREIGN KEY (run_step_id) REFERENCES public.run_steps(run_steps_id) ON DELETE CASCADE;


--
-- Name: human_validations human_validations_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.human_validations
    ADD CONSTRAINT human_validations_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id) ON DELETE CASCADE;


--
-- Name: human_validations human_validations_task_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.human_validations
    ADD CONSTRAINT human_validations_task_run_id_fkey FOREIGN KEY (task_run_id) REFERENCES public.task_runs(tasks_runs_id) ON DELETE CASCADE;


--
-- Name: monday_updates_history monday_updates_history_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.monday_updates_history
    ADD CONSTRAINT monday_updates_history_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id);


--
-- Name: performance_metrics performance_metrics_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.performance_metrics
    ADD CONSTRAINT performance_metrics_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id) ON DELETE CASCADE;


--
-- Name: performance_metrics performance_metrics_task_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.performance_metrics
    ADD CONSTRAINT performance_metrics_task_run_id_fkey FOREIGN KEY (task_run_id) REFERENCES public.task_runs(tasks_runs_id) ON DELETE CASCADE;


--
-- Name: pull_requests pull_requests_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.pull_requests
    ADD CONSTRAINT pull_requests_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id) ON DELETE CASCADE;


--
-- Name: pull_requests pull_requests_task_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.pull_requests
    ADD CONSTRAINT pull_requests_task_run_id_fkey FOREIGN KEY (task_run_id) REFERENCES public.task_runs(tasks_runs_id) ON DELETE SET NULL;


--
-- Name: rate_limits rate_limits_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.rate_limits
    ADD CONSTRAINT rate_limits_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.system_users(user_id);


--
-- Name: run_step_checkpoints run_step_checkpoints_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.run_step_checkpoints
    ADD CONSTRAINT run_step_checkpoints_step_id_fkey FOREIGN KEY (step_id) REFERENCES public.run_steps(run_steps_id) ON DELETE CASCADE;


--
-- Name: run_steps run_steps_task_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.run_steps
    ADD CONSTRAINT run_steps_task_run_id_fkey FOREIGN KEY (task_run_id) REFERENCES public.task_runs(tasks_runs_id) ON DELETE CASCADE;


--
-- Name: task_context_memory task_context_memory_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_context_memory
    ADD CONSTRAINT task_context_memory_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id);


--
-- Name: task_runs task_runs_parent_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_runs
    ADD CONSTRAINT task_runs_parent_run_id_fkey FOREIGN KEY (parent_run_id) REFERENCES public.task_runs(tasks_runs_id) ON DELETE SET NULL;


--
-- Name: task_runs task_runs_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_runs
    ADD CONSTRAINT task_runs_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id) ON DELETE SET NULL;


--
-- Name: task_update_triggers task_update_triggers_new_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_update_triggers
    ADD CONSTRAINT task_update_triggers_new_run_id_fkey FOREIGN KEY (new_run_id) REFERENCES public.task_runs(tasks_runs_id);


--
-- Name: task_update_triggers task_update_triggers_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.task_update_triggers
    ADD CONSTRAINT task_update_triggers_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id);


--
-- Name: test_results test_results_task_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.test_results
    ADD CONSTRAINT test_results_task_run_id_fkey FOREIGN KEY (task_run_id) REFERENCES public.task_runs(tasks_runs_id) ON DELETE CASCADE;


--
-- Name: validation_actions validation_actions_human_validation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.validation_actions
    ADD CONSTRAINT validation_actions_human_validation_id_fkey FOREIGN KEY (human_validation_id) REFERENCES public.human_validations(human_validations_id) ON DELETE CASCADE;


--
-- Name: workflow_cooldowns workflow_cooldowns_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_cooldowns
    ADD CONSTRAINT workflow_cooldowns_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id) ON DELETE CASCADE;


--
-- Name: workflow_locks workflow_locks_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_locks
    ADD CONSTRAINT workflow_locks_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id) ON DELETE CASCADE;


--
-- Name: workflow_queue workflow_queue_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: admin
--

ALTER TABLE ONLY public.workflow_queue
    ADD CONSTRAINT workflow_queue_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.tasks(tasks_id) ON DELETE SET NULL;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO ai_agent_app;


--
-- Name: FUNCTION auto_cleanup(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.auto_cleanup() TO ai_agent_app;


--
-- Name: FUNCTION calculate_duration(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.calculate_duration() TO ai_agent_app;


--
-- Name: FUNCTION clean_expired_locks(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.clean_expired_locks() TO ai_agent_app;


--
-- Name: FUNCTION cleanup_expired_contexts(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.cleanup_expired_contexts() TO ai_agent_app;


--
-- Name: FUNCTION cleanup_old_data(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.cleanup_old_data() TO ai_agent_app;


--
-- Name: FUNCTION cleanup_old_logs(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.cleanup_old_logs() TO ai_agent_app;


--
-- Name: FUNCTION cleanup_old_reactivations(retention_days integer); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.cleanup_old_reactivations(retention_days integer) TO ai_agent_app;


--
-- Name: FUNCTION cleanup_old_update_triggers(days_to_keep integer); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.cleanup_old_update_triggers(days_to_keep integer) TO ai_agent_app;


--
-- Name: FUNCTION get_current_month_ai_stats(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.get_current_month_ai_stats() TO ai_agent_app;


--
-- Name: FUNCTION get_expensive_workflows(cost_threshold numeric); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.get_expensive_workflows(cost_threshold numeric) TO ai_agent_app;


--
-- Name: FUNCTION get_task_reactivation_stats(p_task_id bigint); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.get_task_reactivation_stats(p_task_id bigint) TO ai_agent_app;


--
-- Name: FUNCTION get_validation_stats(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.get_validation_stats() TO ai_agent_app;


--
-- Name: FUNCTION health_check(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.health_check() TO ai_agent_app;


--
-- Name: FUNCTION log_critical_changes(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.log_critical_changes() TO ai_agent_app;


--
-- Name: FUNCTION mark_expired_validations(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.mark_expired_validations() TO ai_agent_app;


--
-- Name: FUNCTION optimize_database(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.optimize_database() TO ai_agent_app;


--
-- Name: FUNCTION reset_failed_attempts_on_success(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.reset_failed_attempts_on_success() TO ai_agent_app;


--
-- Name: FUNCTION reset_monthly_user_quotas(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.reset_monthly_user_quotas() TO ai_agent_app;


--
-- Name: FUNCTION sync_task_last_run(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.sync_task_last_run() TO ai_agent_app;


--
-- Name: FUNCTION sync_task_status(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.sync_task_status() TO ai_agent_app;


--
-- Name: FUNCTION sync_validation_status(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.sync_validation_status() TO ai_agent_app;


--
-- Name: FUNCTION trg_touch_updated_at(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.trg_touch_updated_at() TO ai_agent_app;


--
-- Name: FUNCTION update_prompt_template_stats(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.update_prompt_template_stats() TO ai_agent_app;


--
-- Name: FUNCTION update_reactivation_duration(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.update_reactivation_duration() TO ai_agent_app;


--
-- Name: FUNCTION update_updated_at_column(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.update_updated_at_column() TO ai_agent_app;


--
-- Name: FUNCTION update_workflow_reactivations_updated_at(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.update_workflow_reactivations_updated_at() TO ai_agent_app;


--
-- Name: FUNCTION validate_status_transition(); Type: ACL; Schema: public; Owner: admin
--

GRANT ALL ON FUNCTION public.validate_status_transition() TO ai_agent_app;


--
-- Name: TABLE ai_code_generations; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_code_generations TO ai_agent_app;


--
-- Name: SEQUENCE ai_code_generations_ai_code_generations_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.ai_code_generations_ai_code_generations_id_seq TO ai_agent_app;


--
-- Name: TABLE ai_usage_logs; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_usage_logs TO ai_agent_app;


--
-- Name: TABLE ai_cost_by_workflow; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_cost_by_workflow TO ai_agent_app;


--
-- Name: TABLE ai_cost_daily_summary; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_cost_daily_summary TO ai_agent_app;


--
-- Name: TABLE ai_cost_tracking; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_cost_tracking TO ai_agent_app;


--
-- Name: SEQUENCE ai_cost_tracking_ai_cost_tracking_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.ai_cost_tracking_ai_cost_tracking_id_seq TO ai_agent_app;


--
-- Name: TABLE ai_interactions; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_interactions TO ai_agent_app;


--
-- Name: SEQUENCE ai_interactions_ai_interactions_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.ai_interactions_ai_interactions_id_seq TO ai_agent_app;


--
-- Name: TABLE ai_prompt_templates; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_prompt_templates TO ai_agent_app;


--
-- Name: SEQUENCE ai_prompt_templates_template_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.ai_prompt_templates_template_id_seq TO ai_agent_app;


--
-- Name: TABLE ai_prompt_usage; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_prompt_usage TO ai_agent_app;


--
-- Name: SEQUENCE ai_prompt_usage_usage_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.ai_prompt_usage_usage_id_seq TO ai_agent_app;


--
-- Name: TABLE ai_usage_logs_backup; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_usage_logs_backup TO ai_agent_app;


--
-- Name: SEQUENCE ai_usage_logs_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.ai_usage_logs_id_seq TO ai_agent_app;


--
-- Name: TABLE application_logs; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.application_logs TO ai_agent_app;


--
-- Name: SEQUENCE application_logs_application_logs_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.application_logs_application_logs_id_seq TO ai_agent_app;


--
-- Name: TABLE audit_logs; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.audit_logs TO ai_agent_app;


--
-- Name: SEQUENCE audit_logs_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.audit_logs_id_seq TO ai_agent_app;


--
-- Name: TABLE celery_taskmeta; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.celery_taskmeta TO ai_agent_app;


--
-- Name: TABLE celery_tasksetmeta; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.celery_tasksetmeta TO ai_agent_app;


--
-- Name: TABLE code_quality_feedback; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.code_quality_feedback TO ai_agent_app;


--
-- Name: SEQUENCE code_quality_feedback_feedback_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.code_quality_feedback_feedback_id_seq TO ai_agent_app;


--
-- Name: TABLE human_validation_responses; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.human_validation_responses TO ai_agent_app;


--
-- Name: SEQUENCE human_validation_responses_human_validation_responses_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.human_validation_responses_human_validation_responses_id_seq TO ai_agent_app;


--
-- Name: TABLE human_validations; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.human_validations TO ai_agent_app;


--
-- Name: SEQUENCE human_validations_human_validations_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.human_validations_human_validations_id_seq TO ai_agent_app;


--
-- Name: TABLE message_embeddings; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.message_embeddings TO ai_agent_app;


--
-- Name: SEQUENCE message_embeddings_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.message_embeddings_id_seq TO ai_agent_app;


--
-- Name: TABLE monday_updates_history; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.monday_updates_history TO ai_agent_app;


--
-- Name: SEQUENCE monday_updates_history_update_history_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.monday_updates_history_update_history_id_seq TO ai_agent_app;


--
-- Name: TABLE performance_metrics; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.performance_metrics TO ai_agent_app;


--
-- Name: SEQUENCE performance_metrics_performance_metrics_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.performance_metrics_performance_metrics_id_seq TO ai_agent_app;


--
-- Name: TABLE project_context_embeddings; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.project_context_embeddings TO ai_agent_app;


--
-- Name: SEQUENCE project_context_embeddings_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.project_context_embeddings_id_seq TO ai_agent_app;


--
-- Name: TABLE pull_requests; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.pull_requests TO ai_agent_app;


--
-- Name: SEQUENCE pull_requests_pull_requests_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.pull_requests_pull_requests_id_seq TO ai_agent_app;


--
-- Name: TABLE rate_limits; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.rate_limits TO ai_agent_app;


--
-- Name: SEQUENCE rate_limits_rate_limit_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.rate_limits_rate_limit_id_seq TO ai_agent_app;


--
-- Name: TABLE run_step_checkpoints; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.run_step_checkpoints TO ai_agent_app;


--
-- Name: SEQUENCE run_step_checkpoints_checkpoint_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.run_step_checkpoints_checkpoint_id_seq TO ai_agent_app;


--
-- Name: TABLE run_steps; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.run_steps TO ai_agent_app;


--
-- Name: SEQUENCE run_steps_run_steps_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.run_steps_run_steps_id_seq TO ai_agent_app;


--
-- Name: TABLE system_config; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.system_config TO ai_agent_app;


--
-- Name: SEQUENCE system_config_system_config_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.system_config_system_config_id_seq TO ai_agent_app;


--
-- Name: TABLE system_users; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.system_users TO ai_agent_app;


--
-- Name: SEQUENCE system_users_user_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.system_users_user_id_seq TO ai_agent_app;


--
-- Name: TABLE task_context_memory; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.task_context_memory TO ai_agent_app;


--
-- Name: SEQUENCE task_context_memory_memory_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.task_context_memory_memory_id_seq TO ai_agent_app;


--
-- Name: SEQUENCE task_id_sequence; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.task_id_sequence TO ai_agent_app;


--
-- Name: TABLE task_runs; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.task_runs TO ai_agent_app;


--
-- Name: SEQUENCE task_runs_tasks_runs_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.task_runs_tasks_runs_id_seq TO ai_agent_app;


--
-- Name: TABLE task_update_triggers; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.task_update_triggers TO ai_agent_app;


--
-- Name: SEQUENCE task_update_triggers_trigger_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.task_update_triggers_trigger_id_seq TO ai_agent_app;


--
-- Name: TABLE tasks; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.tasks TO ai_agent_app;


--
-- Name: SEQUENCE tasks_tasks_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.tasks_tasks_id_seq TO ai_agent_app;


--
-- Name: SEQUENCE taskset_id_sequence; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.taskset_id_sequence TO ai_agent_app;


--
-- Name: TABLE test_results; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.test_results TO ai_agent_app;


--
-- Name: SEQUENCE test_results_test_results_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.test_results_test_results_id_seq TO ai_agent_app;


--
-- Name: TABLE users; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.users TO ai_agent_app;


--
-- Name: SEQUENCE users_user_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.users_user_id_seq TO ai_agent_app;


--
-- Name: TABLE workflow_reactivations; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.workflow_reactivations TO ai_agent_app;


--
-- Name: TABLE v_recent_reactivations; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.v_recent_reactivations TO ai_agent_app;


--
-- Name: TABLE v_workflow_reactivation_stats; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.v_workflow_reactivation_stats TO ai_agent_app;


--
-- Name: TABLE validation_actions; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.validation_actions TO ai_agent_app;


--
-- Name: SEQUENCE validation_actions_validation_actions_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.validation_actions_validation_actions_id_seq TO ai_agent_app;


--
-- Name: TABLE validation_dashboard; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.validation_dashboard TO ai_agent_app;


--
-- Name: TABLE validation_history; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.validation_history TO ai_agent_app;


--
-- Name: TABLE webhook_events; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.webhook_events TO ai_agent_app;


--
-- Name: TABLE webhook_events_2025_09; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.webhook_events_2025_09 TO ai_agent_app;


--
-- Name: TABLE webhook_events_p2025_10; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.webhook_events_p2025_10 TO ai_agent_app;


--
-- Name: TABLE webhook_events_p2025_11; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.webhook_events_p2025_11 TO ai_agent_app;


--
-- Name: TABLE webhook_events_p2025_12; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.webhook_events_p2025_12 TO ai_agent_app;


--
-- Name: TABLE webhook_events_p2026_01; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.webhook_events_p2026_01 TO ai_agent_app;


--
-- Name: SEQUENCE webhook_events_webhook_events_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.webhook_events_webhook_events_id_seq TO ai_agent_app;


--
-- Name: TABLE workflow_cooldowns; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.workflow_cooldowns TO ai_agent_app;


--
-- Name: SEQUENCE workflow_cooldowns_cooldown_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.workflow_cooldowns_cooldown_id_seq TO ai_agent_app;


--
-- Name: TABLE workflow_locks; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.workflow_locks TO ai_agent_app;


--
-- Name: SEQUENCE workflow_locks_lock_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.workflow_locks_lock_id_seq TO ai_agent_app;


--
-- Name: TABLE workflow_metrics_summary; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.workflow_metrics_summary TO ai_agent_app;


--
-- Name: TABLE workflow_queue; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.workflow_queue TO ai_agent_app;


--
-- Name: SEQUENCE workflow_reactivations_id_seq; Type: ACL; Schema: public; Owner: admin
--

GRANT SELECT,USAGE ON SEQUENCE public.workflow_reactivations_id_seq TO ai_agent_app;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public GRANT SELECT,USAGE ON SEQUENCES  TO ai_agent_app;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES  TO ai_agent_app;


--
-- PostgreSQL database dump complete
--

\unrestrict Tvdn84Qbff0sUswZoBBFlfgVsfr6OgDwyQSjcwAVcvVwdRwlVUPbmNEw2aInXT8

