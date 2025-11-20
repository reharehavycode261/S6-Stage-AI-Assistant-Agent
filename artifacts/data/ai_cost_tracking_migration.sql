-- Migration pour le tracking des coûts IA
-- Ajouter la table ai_usage_logs
CREATE TABLE IF NOT EXISTS ai_usage_logs (
    id SERIAL PRIMARY KEY,
    workflow_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    operation VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost DECIMAL(10, 6) NOT NULL DEFAULT 0.0,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    duration_seconds DECIMAL(8, 3) NULL,
    success BOOLEAN NOT NULL DEFAULT true,
    error_message TEXT NULL,
    
    -- Contraintes directement dans la table
    CONSTRAINT ai_usage_logs_cost_positive CHECK (estimated_cost >= 0),
    CONSTRAINT ai_usage_logs_tokens_positive CHECK (
        input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0
    ),
    CONSTRAINT ai_usage_logs_tokens_coherent CHECK (
        total_tokens = input_tokens + output_tokens
    )
);

-- Puis créer les indexes séparément
CREATE INDEX IF NOT EXISTS ai_usage_logs_workflow_id_idx ON ai_usage_logs (workflow_id);
CREATE INDEX IF NOT EXISTS ai_usage_logs_task_id_idx ON ai_usage_logs (task_id);
CREATE INDEX IF NOT EXISTS ai_usage_logs_provider_idx ON ai_usage_logs (provider);
CREATE INDEX IF NOT EXISTS ai_usage_logs_timestamp_idx ON ai_usage_logs (timestamp);
CREATE INDEX IF NOT EXISTS ai_usage_logs_timestamp_idx ON ai_usage_logs (timestamp);
-- Commentaires pour documentation
COMMENT ON TABLE ai_usage_logs IS 'Logs des usages IA avec tracking des tokens et coûts';
COMMENT ON COLUMN ai_usage_logs.workflow_id IS 'ID du workflow parent';
COMMENT ON COLUMN ai_usage_logs.task_id IS 'ID de la tâche Monday.com';
COMMENT ON COLUMN ai_usage_logs.provider IS 'Provider IA utilisé (claude, openai, etc.)';
COMMENT ON COLUMN ai_usage_logs.model IS 'Modèle spécifique utilisé';
COMMENT ON COLUMN ai_usage_logs.operation IS 'Type d''opération (analyze, implement, debug, etc.)';
COMMENT ON COLUMN ai_usage_logs.input_tokens IS 'Nombre de tokens en input (prompt)';
COMMENT ON COLUMN ai_usage_logs.output_tokens IS 'Nombre de tokens en output (réponse)';
COMMENT ON COLUMN ai_usage_logs.total_tokens IS 'Total des tokens (input + output)';
COMMENT ON COLUMN ai_usage_logs.estimated_cost IS 'Coût estimé en USD';
COMMENT ON COLUMN ai_usage_logs.duration_seconds IS 'Durée de l''appel IA en secondes';

-- Vue agrégée pour statistiques rapides
CREATE OR REPLACE VIEW ai_cost_daily_summary AS
SELECT 
    DATE(timestamp) as usage_date,
    provider,
    COUNT(*) as total_calls,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(total_tokens) as total_tokens,
    SUM(estimated_cost) as total_cost,
    AVG(estimated_cost) as avg_cost_per_call,
    COUNT(DISTINCT workflow_id) as unique_workflows,
    COUNT(DISTINCT task_id) as unique_tasks
FROM ai_usage_logs
WHERE success = true
GROUP BY DATE(timestamp), provider
ORDER BY usage_date DESC, total_cost DESC;

COMMENT ON VIEW ai_cost_daily_summary IS 'Résumé quotidien des coûts IA par provider';

-- Vue pour coûts par workflow
CREATE OR REPLACE VIEW ai_cost_by_workflow AS
SELECT 
    workflow_id,
    task_id,
    COUNT(*) as total_ai_calls,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(total_tokens) as total_tokens,
    SUM(estimated_cost) as total_workflow_cost,
    MIN(timestamp) as started_at,
    MAX(timestamp) as last_ai_call,
    EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) as duration_seconds,
    STRING_AGG(DISTINCT provider, ', ') as providers_used,
    STRING_AGG(DISTINCT operation, ', ') as operations_performed
FROM ai_usage_logs
WHERE success = true
GROUP BY workflow_id, task_id
ORDER BY total_workflow_cost DESC;

COMMENT ON VIEW ai_cost_by_workflow IS 'Coûts agrégés par workflow avec métriques de performance';

-- Fonction pour obtenir les stats du mois en cours
CREATE OR REPLACE FUNCTION get_current_month_ai_stats()
RETURNS TABLE (
    provider_name VARCHAR(50),
    total_cost DECIMAL(10, 6),
    total_tokens BIGINT,
    total_calls BIGINT,
    unique_workflows BIGINT,
    avg_cost_per_call DECIMAL(10, 6)
) AS $$
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
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_current_month_ai_stats() IS 'Statistiques IA du mois en cours par provider';

-- Fonction pour détecter les workflows coûteux
CREATE OR REPLACE FUNCTION get_expensive_workflows(cost_threshold DECIMAL DEFAULT 1.0)
RETURNS TABLE (
    workflow_id VARCHAR(255),
    task_id VARCHAR(255),
    total_cost DECIMAL(10, 6),
    total_tokens BIGINT,
    ai_calls_count BIGINT,
    started_at TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    providers_used TEXT
) AS $$
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
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_expensive_workflows(DECIMAL) IS 'Trouve les workflows qui dépassent un seuil de coût';

-- Index composites pour optimiser les requêtes fréquentes
CREATE INDEX IF NOT EXISTS ai_usage_logs_date_provider_idx 
    ON ai_usage_logs (DATE(timestamp), provider);

CREATE INDEX IF NOT EXISTS ai_usage_logs_workflow_timestamp_idx 
    ON ai_usage_logs (workflow_id, timestamp);

-- Contrainte pour éviter les coûts négatifs
ALTER TABLE ai_usage_logs 
ADD CONSTRAINT ai_usage_logs_cost_positive 
CHECK (estimated_cost >= 0);

-- Contrainte pour tokens positifs
ALTER TABLE ai_usage_logs 
ADD CONSTRAINT ai_usage_logs_tokens_positive 
CHECK (input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0);

-- Vérification de cohérence des tokens
ALTER TABLE ai_usage_logs 
ADD CONSTRAINT ai_usage_logs_tokens_coherent 
CHECK (total_tokens = input_tokens + output_tokens);

COMMENT ON CONSTRAINT ai_usage_logs_cost_positive ON ai_usage_logs IS 'Les coûts ne peuvent pas être négatifs';
COMMENT ON CONSTRAINT ai_usage_logs_tokens_positive ON ai_usage_logs IS 'Les tokens ne peuvent pas être négatifs';
COMMENT ON CONSTRAINT ai_usage_logs_tokens_coherent ON ai_usage_logs IS 'total_tokens doit égaler input_tokens + output_tokens'; 

-- Script de suppression des données de la table ai_usage_logs
-- ATTENTION : Cette opération est irréversible !

-- Option 1: Suppression de toutes les données (TRUNCATE - plus rapide)
-- TRUNCATE TABLE ai_usage_logs RESTART IDENTITY CASCADE;

-- Option 2: Suppression conditionnelle par date (plus sûr)
-- DELETE FROM ai_usage_logs WHERE timestamp < '2024-01-01';

-- Option 3: Suppression par workflow_id spécifique
-- DELETE FROM ai_usage_logs WHERE workflow_id = 'workflow_specific_id';

-- Option 4: Suppression avec sauvegarde préalable (recommandé)
-- CREATE TABLE ai_usage_logs_backup AS SELECT * FROM ai_usage_logs;
-- TRUNCATE TABLE ai_usage_logs;

-- Pour supprimer également les vues et fonctions associées (DANGEREUX - tout supprimer)
-- DROP VIEW IF EXISTS ai_cost_daily_summary CASCADE;
-- DROP VIEW IF EXISTS ai_cost_by_workflow CASCADE;
-- DROP FUNCTION IF EXISTS get_current_month_ai_stats() CASCADE;
-- DROP FUNCTION IF EXISTS get_expensive_workflows(DECIMAL) CASCADE;
-- DROP TABLE IF EXISTS ai_usage_logs CASCADE;

-- Script de suppression sécurisé avec vérifications
DO $$
BEGIN
    -- Vérifier si la table existe avant de supprimer
    IF EXISTS (SELECT FROM information_schema.tables 
              WHERE table_schema = 'public' 
              AND table_name = 'ai_usage_logs') THEN
        
        -- Sauvegarde recommandée avant suppression
        RAISE NOTICE '⚠️  AVERTISSEMENT: Suppression des données de ai_usage_logs';
        RAISE NOTICE '📊 Nombre d''enregistrements à supprimer: %', 
                     (SELECT COUNT(*) FROM ai_usage_logs);
        
        -- Supprimer les données (décommenter pour exécuter réellement)
        -- TRUNCATE TABLE ai_usage_logs;
        
        RAISE NOTICE '✅ Données supprimées avec succès';
    ELSE
        RAISE NOTICE 'ℹ️  Table ai_usage_logs non trouvée';
    END IF;
END $$; 