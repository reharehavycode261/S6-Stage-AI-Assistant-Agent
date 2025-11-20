-- =========================================
-- 1) DASHBOARD SUMMARY
-- =========================================
CREATE OR REPLACE VIEW dashboard_summary AS
SELECT 
    t.tasks_id AS task_id,
    t.title,
    t.monday_status,
    t.internal_status,
    t.priority,
    t.created_at,
    tr.status AS last_run_status,
    tr.current_node,
    tr.progress_percentage,
    pr.github_pr_url,
    pr.pr_status
FROM tasks t
LEFT JOIN LATERAL (
    SELECT * FROM task_runs r
    WHERE r.task_id = t.tasks_id
    ORDER BY r.started_at DESC
    LIMIT 1
) tr ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM pull_requests p
    WHERE p.task_id = t.tasks_id
    ORDER BY p.created_at DESC
    LIMIT 1
) pr ON TRUE
ORDER BY t.created_at DESC;

-- PROBLÈME: Utilisation de LATERAL JOIN peut être coûteuse
-- SOLUTION: Vue matérialisée avec données pré-agrégées
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dashboard_summary AS
SELECT 
    t.tasks_id,
    t.title,
    t.monday_status,
    t.internal_status,
    t.priority,
    t.created_at,
    -- Utiliser l'index existant last_run_id au lieu de LATERAL
    tr.status AS last_run_status,
    tr.current_node,
    tr.progress_percentage,
    tr.ai_provider,
    pr.github_pr_url,
    pr.pr_status
FROM tasks t
LEFT JOIN task_runs tr ON tr.tasks_runs_id = t.last_run_id
LEFT JOIN pull_requests pr ON pr.task_id = t.tasks_id 
    AND pr.pull_requests_id = (
        SELECT pull_requests_id FROM pull_requests 
        WHERE task_id = t.tasks_id 
        ORDER BY created_at DESC LIMIT 1
    )
WHERE t.created_at >= NOW() - INTERVAL '30 days';

CREATE UNIQUE INDEX ON mv_dashboard_summary(tasks_id);
CREATE INDEX ON mv_dashboard_summary(internal_status, created_at DESC);

-- =========================================
-- 2) PERFORMANCE DASHBOARD
-- =========================================
CREATE OR REPLACE VIEW performance_dashboard AS
SELECT 
    DATE_TRUNC('day', t.created_at) AS date,
    COUNT(t.tasks_id) AS total_tasks,
    COUNT(*) FILTER (WHERE tr.status = 'completed') AS completed_tasks,
    COUNT(*) FILTER (WHERE tr.status = 'failed') AS failed_tasks,
    AVG(pm.total_duration_seconds) AS avg_duration,
    AVG(pm.total_ai_cost) AS avg_cost,
    AVG(pm.test_coverage_final) AS avg_coverage
FROM tasks t
LEFT JOIN LATERAL (
    SELECT * FROM task_runs r
    WHERE r.task_id = t.tasks_id
    ORDER BY r.started_at DESC
    LIMIT 1
) tr ON TRUE
LEFT JOIN performance_metrics pm ON pm.task_id = t.tasks_id
GROUP BY 1
ORDER BY 1 DESC;

-- =========================================
-- 3) VUES MATÉRIALISÉES SUPPLÉMENTAIRES
-- =========================================

-- A. Dashboard stats (dernier 7 jours)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dashboard_stats AS
SELECT 
    DATE_TRUNC('hour', created_at) AS hour_bucket,
    internal_status,
    COUNT(*) AS task_count,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) AS avg_duration_seconds
FROM tasks 
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2;

CREATE UNIQUE INDEX ON mv_dashboard_stats(hour_bucket, internal_status);

-- B. Monitoring temps réel
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_realtime_monitoring AS
SELECT 
    internal_status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (NOW() - started_at))/60) as avg_minutes_since_start
FROM tasks 
WHERE internal_status IN ('pending', 'processing', 'testing', 'debugging')
GROUP BY internal_status;

CREATE UNIQUE INDEX ON mv_realtime_monitoring(internal_status);

-- C. Analyse des coûts AI
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_cost_analysis AS
SELECT 
    DATE_TRUNC('day', recorded_at) as day,
    ai_provider,
    model_name,
    SUM(total_ai_cost) as daily_cost,
    COUNT(*) as runs_count,
    AVG(total_tokens_used) as avg_tokens
FROM performance_metrics pm
JOIN task_runs tr ON tr.tasks_runs_id = pm.task_run_id
WHERE recorded_at >= NOW() - INTERVAL '30 days'
GROUP BY 1, 2, 3;

CREATE UNIQUE INDEX ON mv_cost_analysis(day, ai_provider, model_name);

-- =========================================
-- 4) FONCTION D'AUDIT ET MONITORING
-- =========================================
CREATE OR REPLACE FUNCTION health_check() RETURNS TABLE(
    metric_name TEXT,
    metric_value NUMERIC,
    status TEXT
) AS $$
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
$$ LANGUAGE plpgsql;


-- =========================================
-- VUES OPTIMISÉES POUR AI-AGENT WORKFLOW
-- =========================================

-- 1) VUE TEMPS RÉEL DU WORKFLOW LANGGRAPH
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_workflow_status AS
SELECT 
    tr.tasks_runs_id,
    tr.task_id,
    t.title,
    tr.status AS run_status,
    tr.current_node,
    tr.progress_percentage,
    tr.ai_provider,
    tr.model_name,
    -- État détaillé des étapes LangGraph
    JSONB_AGG(
        JSONB_BUILD_OBJECT(
            'node_name', rs.node_name,
            'status', rs.status,
            'step_order', rs.step_order,
            'duration', rs.duration_seconds,
            'retry_count', rs.retry_count
        ) ORDER BY rs.step_order
    ) AS workflow_steps,
    -- Dernière étape échouée pour debugging
    (SELECT rs2.node_name FROM run_steps rs2 
     WHERE rs2.task_run_id = tr.tasks_runs_id 
       AND rs2.status = 'failed' 
     ORDER BY rs2.step_order DESC LIMIT 1) AS last_failed_step,
    -- Métriques de performance instantanées
    EXTRACT(EPOCH FROM (COALESCE(tr.completed_at, NOW()) - tr.started_at))/60 AS runtime_minutes,
    tr.started_at,
    tr.completed_at
FROM task_runs tr
JOIN tasks t ON t.tasks_id = tr.task_id
LEFT JOIN run_steps rs ON rs.task_run_id = tr.tasks_runs_id
WHERE tr.started_at >= NOW() - INTERVAL '7 days'
  AND tr.status IN ('started', 'running', 'failed')
GROUP BY tr.tasks_runs_id, tr.task_id, t.title, tr.status, tr.current_node, 
         tr.progress_percentage, tr.ai_provider, tr.model_name, 
         tr.started_at, tr.completed_at;

CREATE UNIQUE INDEX ON mv_workflow_status(tasks_runs_id);
CREATE INDEX ON mv_workflow_status(run_status, started_at DESC);
CREATE INDEX ON mv_workflow_status(current_node) WHERE run_status IN ('started', 'running');

-- 2) VUE AI PERFORMANCE & COÛTS EN TEMPS RÉEL
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ai_efficiency AS
SELECT 
    ai.ai_provider,
    ai.model_name,
    rs.node_name,
    DATE_TRUNC('hour', ai.created_at) AS hour_bucket,
    -- Métriques de performance IA
    COUNT(*) AS total_calls,
    AVG(ai.latency_ms) AS avg_latency_ms,
    SUM((ai.token_usage->>'prompt_tokens')::int) AS total_prompt_tokens,
    SUM((ai.token_usage->>'completion_tokens')::int) AS total_completion_tokens,
    -- Estimation des coûts (à adapter selon vos tarifs)
    SUM(
        CASE ai.ai_provider
            WHEN 'claude' THEN 
                ((ai.token_usage->>'prompt_tokens')::int * 0.000008) + 
                ((ai.token_usage->>'completion_tokens')::int * 0.000024)
            WHEN 'openai' THEN 
                ((ai.token_usage->>'prompt_tokens')::int * 0.000001) + 
                ((ai.token_usage->>'completion_tokens')::int * 0.000002)
            ELSE 0
        END
    ) AS estimated_cost_usd,
    -- Taux de succès par nœud
    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1 FROM run_steps rs2 
            WHERE rs2.run_steps_id = rs.run_steps_id 
              AND rs2.status = 'completed'
        )
    )::NUMERIC / COUNT(*) * 100 AS success_rate_percentage
FROM ai_interactions ai
JOIN run_steps rs ON rs.run_steps_id = ai.run_step_id
WHERE ai.created_at >= NOW() - INTERVAL '7 days'
GROUP BY ai.ai_provider, ai.model_name, rs.node_name, 
         DATE_TRUNC('hour', ai.created_at);

CREATE UNIQUE INDEX ON mv_ai_efficiency(ai_provider, model_name, node_name, hour_bucket);
CREATE INDEX ON mv_ai_efficiency(hour_bucket DESC, success_rate_percentage);

-- 3) VUE MONITORING QUALITÉ CODE
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_code_quality AS
SELECT 
    t.tasks_id,
    t.title,
    t.repository_name,
    tr.tasks_runs_id,
    -- Métriques de génération de code
    acg.provider AS code_provider,
    acg.model AS code_model,
    COUNT(acg.ai_code_generations_id) AS generation_attempts,
    AVG(acg.response_time_ms) AS avg_generation_time_ms,
    SUM(acg.tokens_used) AS total_tokens_used,
    -- Qualité du code généré
    COUNT(*) FILTER (WHERE acg.compilation_successful = true)::NUMERIC / COUNT(*) * 100 AS compilation_success_rate,
    COUNT(*) FILTER (WHERE acg.syntax_valid = true)::NUMERIC / COUNT(*) * 100 AS syntax_validity_rate,
    -- Résultats des tests
    tr_result.tests_total,
    tr_result.tests_passed,
    tr_result.coverage_percentage,
    CASE 
        WHEN tr_result.coverage_percentage >= 80 THEN 'excellent'
        WHEN tr_result.coverage_percentage >= 60 THEN 'good'
        WHEN tr_result.coverage_percentage >= 40 THEN 'fair'
        ELSE 'poor'
    END AS coverage_grade,
    -- Sécurité
    COALESCE((tr_result.security_scan_report->>'issues_count')::int, 0) AS security_issues,
    tr.completed_at
FROM tasks t
JOIN task_runs tr ON tr.task_id = t.tasks_id
LEFT JOIN ai_code_generations acg ON acg.task_run_id = tr.tasks_runs_id
LEFT JOIN test_results tr_result ON tr_result.task_run_id = tr.tasks_runs_id
WHERE tr.completed_at >= NOW() - INTERVAL '30 days'
GROUP BY t.tasks_id, t.title, t.repository_name, tr.tasks_runs_id,
         acg.provider, acg.model, tr_result.tests_total, tr_result.tests_passed,
         tr_result.coverage_percentage, tr_result.security_scan_report,
         tr.completed_at;

CREATE UNIQUE INDEX ON mv_code_quality(tasks_id, tasks_runs_id);
CREATE INDEX ON mv_code_quality(coverage_grade, completed_at DESC);
CREATE INDEX ON mv_code_quality(security_issues DESC) WHERE security_issues > 0;

-- 4) VUE MONITORING WEBHOOK & INTÉGRATIONS
CREATE MATERIALIZED VIEW mv_integration_health AS
SELECT 
    DATE_TRUNC('hour', we.received_at) AS hour_bucket,
    we.source,
    we.event_type,
    COUNT(*) AS total_events,
    COUNT(*) FILTER (WHERE we.processed = true) AS processed_events,
    COUNT(*) FILTER (WHERE we.processing_status = 'pending') AS pending_events,
    COUNT(*) FILTER (WHERE we.processing_status = 'error') AS failed_events,
    AVG(EXTRACT(EPOCH FROM (we.processed_at - we.received_at))) AS avg_processing_time_seconds,
    -- Santé des intégrations
    COUNT(*) FILTER (WHERE we.processed = true)::NUMERIC / COUNT(*) * 100 AS processing_success_rate
FROM webhook_events we
WHERE we.received_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', we.received_at), we.source, we.event_type;

CREATE UNIQUE INDEX ON mv_integration_health(hour_bucket, source, event_type);
CREATE INDEX ON mv_integration_health(processing_success_rate) WHERE processing_success_rate < 95;

-- 5) VUE EXECUTIVE DASHBOARD (HIGH-LEVEL METRICS)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_executive_dashboard AS
SELECT 
    DATE_TRUNC('day', t.created_at) AS date,
    -- Métriques de productivité
    COUNT(t.tasks_id) AS total_tasks_created,
    COUNT(*) FILTER (WHERE t.internal_status = 'completed') AS tasks_completed,
    COUNT(*) FILTER (WHERE t.internal_status = 'failed') AS tasks_failed,
    -- Temps de traitement
    AVG(EXTRACT(EPOCH FROM (t.completed_at - t.started_at))/3600) AS avg_completion_hours,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t.completed_at - t.started_at))/3600) AS median_completion_hours,
    -- Qualité
    AVG(pm.test_coverage_final) AS avg_test_coverage,
    AVG(pm.success_rate) AS avg_success_rate,
    -- Coûts
    SUM(pm.total_ai_cost) AS daily_ai_cost,
    AVG(pm.total_ai_cost) AS avg_cost_per_task,
    -- Pull Requests
    COUNT(pr.pull_requests_id) AS prs_created,
    COUNT(*) FILTER (WHERE pr.pr_status = 'merged') AS prs_merged
FROM tasks t
LEFT JOIN performance_metrics pm ON pm.task_id = t.tasks_id
LEFT JOIN pull_requests pr ON pr.task_id = t.tasks_id
WHERE t.created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', t.created_at);

CREATE UNIQUE INDEX ON mv_executive_dashboard(date);
CREATE INDEX ON mv_executive_dashboard(avg_success_rate DESC, date DESC);

-- =========================================
-- FONCTIONS UTILITAIRES POUR REFRESH AUTO
-- =========================================

CREATE OR REPLACE FUNCTION refresh_critical_views() RETURNS void AS $$
BEGIN
    -- Refresh des vues critiques pour le monitoring temps réel
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_workflow_status;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_integration_health;
    
    -- Log du refresh
    INSERT INTO application_logs (level, source_component, action, message)
    VALUES ('INFO', 'view_refresh', 'refresh_critical_views', 'Critical materialized views refreshed');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION refresh_analytics_views() RETURNS void AS $$
BEGIN
    -- Refresh des vues analytiques (moins fréquent)
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_ai_efficiency;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_code_quality;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_executive_dashboard;
    
    INSERT INTO application_logs (level, source_component, action, message)
    VALUES ('INFO', 'view_refresh', 'refresh_analytics_views', 'Analytics materialized views refreshed');
END;
$$ LANGUAGE plpgsql;