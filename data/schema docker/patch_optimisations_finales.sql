-- ============================================================================
-- PATCH D'OPTIMISATIONS FINALES
-- À appliquer après la création du schéma principal
-- ============================================================================

-- 1. Déplacer ai_prompt_templates vers le schéma config
-- ============================================================================

-- Créer la nouvelle table dans config
CREATE TABLE config.ai_prompt_templates (
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
    CONSTRAINT fk_config_ai_prompt_templates_model FOREIGN KEY (model_id)
        REFERENCES config.ai_models(model_id) ON DELETE SET NULL,
    CONSTRAINT fk_config_ai_prompt_templates_created_by FOREIGN KEY (created_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_config_ai_prompt_templates_updated_by FOREIGN KEY (updated_by)
        REFERENCES public.system_users(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE config.ai_prompt_templates IS 'Templates de prompts (déplacé dans config car ressource de configuration)';

-- Migrer les données si la table existe déjà dans public
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ai_prompt_templates') THEN
        INSERT INTO config.ai_prompt_templates SELECT * FROM public.ai_prompt_templates;
        DROP TABLE public.ai_prompt_templates CASCADE;
    END IF;
END $$;

-- Mettre à jour les FK dans ai_prompt_usage
ALTER TABLE public.ai_prompt_usage DROP CONSTRAINT IF EXISTS fk_ai_prompt_usage_template;
ALTER TABLE public.ai_prompt_usage
    ADD CONSTRAINT fk_ai_prompt_usage_template FOREIGN KEY (template_id)
        REFERENCES config.ai_prompt_templates(template_id) ON DELETE SET NULL;

-- Créer les index
CREATE INDEX idx_config_ai_prompt_templates_active ON config.ai_prompt_templates(is_active, template_category) WHERE deleted_at IS NULL;
CREATE INDEX idx_config_ai_prompt_templates_model ON config.ai_prompt_templates(model_id) WHERE deleted_at IS NULL;

-- Trigger updated_at
CREATE TRIGGER trg_config_ai_prompt_templates_updated_at BEFORE UPDATE ON config.ai_prompt_templates
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- 2. Améliorer la sécurité des credentials avec pgcrypto
-- ============================================================================

-- Fonction de hachage de mot de passe avec bcrypt
CREATE OR REPLACE FUNCTION public.hash_password(password TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Utilise bcrypt avec un coût de 10 (équilibre sécurité/performance)
    RETURN crypt(password, gen_salt('bf', 10));
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.hash_password IS 'Hache un mot de passe avec bcrypt (coût 10)';

-- Fonction de vérification de mot de passe
CREATE OR REPLACE FUNCTION public.verify_password(password TEXT, hash TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN hash = crypt(password, hash);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.verify_password IS 'Vérifie si un mot de passe correspond au hash bcrypt';

-- Modifier la table user_credentials pour utiliser un hash unifié
ALTER TABLE public.user_credentials
    ALTER COLUMN password_hash TYPE TEXT,
    ALTER COLUMN password_salt DROP NOT NULL;

COMMENT ON COLUMN public.user_credentials.password_hash IS 'Hash bcrypt du mot de passe (contient le sel et le coût)';
COMMENT ON COLUMN public.user_credentials.password_salt IS 'Obsolète - le sel est maintenant dans password_hash';

-- 3. Fonction utilitaire pour nettoyer les sessions expirées
-- ============================================================================

CREATE OR REPLACE FUNCTION public.cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    UPDATE public.user_sessions
    SET is_active = FALSE
    WHERE expires_at < NOW()
    AND is_active = TRUE;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Supprimer définitivement les sessions expirées depuis plus de 30 jours
    DELETE FROM public.user_sessions
    WHERE expires_at < NOW() - INTERVAL '30 days'
    AND is_active = FALSE;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.cleanup_expired_sessions IS 'Désactive les sessions expirées et supprime celles > 30 jours';

-- 4. Fonction pour calculer les statistiques de validation
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_validation_stats(days_back INTEGER DEFAULT 30)
RETURNS TABLE(
    total_validations BIGINT,
    pending_validations BIGINT,
    approved_validations BIGINT,
    rejected_validations BIGINT,
    expired_validations BIGINT,
    avg_approval_time_hours NUMERIC,
    urgent_validations BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_validations,
        COUNT(*) FILTER (WHERE st.status_code = 'validation_pending')::BIGINT as pending_validations,
        COUNT(*) FILTER (WHERE st.status_code = 'validation_approved')::BIGINT as approved_validations,
        COUNT(*) FILTER (WHERE st.status_code = 'validation_rejected')::BIGINT as rejected_validations,
        COUNT(*) FILTER (WHERE st.status_code = 'validation_expired')::BIGINT as expired_validations,
        ROUND(AVG(
            CASE 
                WHEN hvr.validated_at IS NOT NULL AND hv.created_at IS NOT NULL
                THEN EXTRACT(EPOCH FROM (hvr.validated_at - hv.created_at)) / 3600.0
                ELSE NULL
            END
        ), 2) as avg_approval_time_hours,
        COUNT(*) FILTER (
            WHERE st.status_code = 'validation_pending'
            AND hv.expires_at IS NOT NULL
            AND hv.expires_at < NOW() + INTERVAL '1 hour'
        )::BIGINT as urgent_validations
    FROM public.human_validations hv
    JOIN config.status_types st ON hv.current_status_id = st.status_id
    LEFT JOIN public.human_validation_responses hvr ON hv.validation_id = hvr.validation_id
    WHERE hv.created_at >= NOW() - INTERVAL '1 day' * days_back
    AND hv.deleted_at IS NULL;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.get_validation_stats IS 'Statistiques détaillées des validations sur N jours';

-- 5. Vue pour le monitoring des coûts en temps réel
-- ============================================================================

CREATE OR REPLACE VIEW public.v_ai_cost_realtime AS
SELECT 
    p.provider_name,
    m.model_name,
    o.operation_name,
    DATE(ai.created_at) as date,
    COUNT(*) as interactions_count,
    SUM(ai.input_tokens) as total_input_tokens,
    SUM(ai.output_tokens) as total_output_tokens,
    SUM(ai.total_tokens) as total_tokens,
    SUM(ai.cost_usd) as total_cost_usd,
    SUM(ai.calculated_cost_usd) as calculated_cost_usd,
    AVG(ai.latency_ms) as avg_latency_ms,
    COUNT(*) FILTER (WHERE ai.success = false) as failed_interactions
FROM public.ai_interactions ai
JOIN config.ai_providers p ON ai.provider_id = p.provider_id
JOIN config.ai_models m ON ai.model_id = m.model_id
JOIN config.ai_operations o ON ai.operation_id = o.operation_id
WHERE ai.deleted_at IS NULL
AND ai.created_at >= NOW() - INTERVAL '7 days'
GROUP BY p.provider_name, m.model_name, o.operation_name, DATE(ai.created_at)
ORDER BY date DESC, total_cost_usd DESC;

COMMENT ON VIEW public.v_ai_cost_realtime IS 'Monitoring des coûts IA en temps réel (7 derniers jours)';

-- 6. Trigger pour valider la cohérence des coûts IA
-- ============================================================================

CREATE OR REPLACE FUNCTION public.validate_ai_interaction_cost()
RETURNS TRIGGER AS $$
DECLARE
    model_input_cost NUMERIC(10,6);
    model_output_cost NUMERIC(10,6);
    expected_cost NUMERIC(12,6);
BEGIN
    -- Récupérer les coûts du modèle
    SELECT cost_per_1k_input_tokens, cost_per_1k_output_tokens
    INTO model_input_cost, model_output_cost
    FROM config.ai_models
    WHERE model_id = NEW.model_id;
    
    -- Calculer le coût attendu
    expected_cost := (COALESCE(NEW.input_tokens, 0)::NUMERIC / 1000.0) * model_input_cost +
                     (COALESCE(NEW.output_tokens, 0)::NUMERIC / 1000.0) * model_output_cost;
    
    -- Si cost_usd est fourni, vérifier qu'il correspond au calcul
    IF NEW.cost_usd IS NOT NULL THEN
        IF ABS(NEW.cost_usd - expected_cost) > 0.000001 THEN
            RAISE WARNING 'Cost mismatch: provided=%, expected=% for interaction on model_id=%',
                NEW.cost_usd, expected_cost, NEW.model_id;
        END IF;
    ELSE
        -- Si pas fourni, utiliser le coût calculé
        NEW.cost_usd := expected_cost;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ai_interactions_validate_cost
BEFORE INSERT OR UPDATE ON public.ai_interactions
FOR EACH ROW
EXECUTE FUNCTION public.validate_ai_interaction_cost();

COMMENT ON TRIGGER trg_ai_interactions_validate_cost ON public.ai_interactions IS 'Valide et auto-calcule les coûts IA';

-- 7. Index additionnels pour les performances
-- ============================================================================

-- Index composite pour les requêtes de dashboard
CREATE INDEX idx_tasks_status_priority ON public.tasks(current_status_id, priority DESC, created_at DESC) 
WHERE deleted_at IS NULL;

-- Index pour les recherches de runs récents
CREATE INDEX idx_task_runs_recent ON public.task_runs(task_id, started_at DESC) 
WHERE deleted_at IS NULL AND started_at >= NOW() - INTERVAL '30 days';

-- Index pour les validations urgentes
CREATE INDEX idx_human_validations_urgent ON public.human_validations(expires_at, current_status_id)
WHERE deleted_at IS NULL AND expires_at < NOW() + INTERVAL '24 hours';

-- Index partiel pour les interactions IA échouées
CREATE INDEX idx_ai_interactions_failed ON public.ai_interactions(created_at DESC, model_id, error_message)
WHERE success = false AND deleted_at IS NULL;

-- 8. Contrainte de vérification pour les transitions de statuts
-- ============================================================================

-- Fonction pour vérifier qu'une transition est valide avant insertion dans l'historique
CREATE OR REPLACE FUNCTION public.validate_status_history_transition()
RETURNS TRIGGER AS $$
DECLARE
    transition_exists BOOLEAN;
    category_val VARCHAR(50);
BEGIN
    -- Déterminer la catégorie basée sur la table d'historique
    IF TG_TABLE_NAME = 'task_status_history' THEN
        category_val := 'task';
    ELSIF TG_TABLE_NAME = 'task_run_status_history' THEN
        category_val := 'run';
    ELSIF TG_TABLE_NAME = 'human_validation_status_history' THEN
        category_val := 'validation';
    ELSE
        RETURN NEW;
    END IF;
    
    -- Vérifier si la transition est autorisée
    SELECT EXISTS(
        SELECT 1 FROM config.status_transitions
        WHERE (from_status_id = NEW.from_status_id OR NEW.from_status_id IS NULL)
        AND to_status_id = NEW.to_status_id
        AND category = category_val
    ) INTO transition_exists;
    
    IF NOT transition_exists AND NEW.from_status_id IS NOT NULL THEN
        RAISE EXCEPTION 'Invalid status transition logged in history: from % to % for category %',
            NEW.from_status_id, NEW.to_status_id, category_val;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Appliquer aux tables d'historique
CREATE TRIGGER trg_validate_task_status_history
BEFORE INSERT ON public.task_status_history
FOR EACH ROW
EXECUTE FUNCTION public.validate_status_history_transition();

CREATE TRIGGER trg_validate_task_run_status_history
BEFORE INSERT ON public.task_run_status_history
FOR EACH ROW
EXECUTE FUNCTION public.validate_status_history_transition();

CREATE TRIGGER trg_validate_hv_status_history
BEFORE INSERT ON public.human_validation_status_history
FOR EACH ROW
EXECUTE FUNCTION public.validate_status_history_transition();

-- 9. Vue pour l'analyse des performances des modèles IA
-- ============================================================================

CREATE OR REPLACE VIEW public.v_ai_model_performance AS
SELECT 
    m.model_id,
    p.provider_name,
    m.model_name,
    COUNT(*) as total_interactions,
    COUNT(*) FILTER (WHERE ai.success = true) as successful_interactions,
    COUNT(*) FILTER (WHERE ai.success = false) as failed_interactions,
    ROUND(100.0 * COUNT(*) FILTER (WHERE ai.success = true) / COUNT(*), 2) as success_rate_pct,
    AVG(ai.latency_ms) as avg_latency_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ai.latency_ms) as median_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ai.latency_ms) as p95_latency_ms,
    SUM(ai.cost_usd) as total_cost_usd,
    AVG(ai.cost_usd) as avg_cost_per_interaction,
    SUM(ai.total_tokens) as total_tokens,
    AVG(ai.total_tokens) as avg_tokens_per_interaction,
    MIN(ai.created_at) as first_use,
    MAX(ai.created_at) as last_use
FROM public.ai_interactions ai
JOIN config.ai_models m ON ai.model_id = m.model_id
JOIN config.ai_providers p ON m.provider_id = p.provider_id
WHERE ai.deleted_at IS NULL
GROUP BY m.model_id, p.provider_name, m.model_name
ORDER BY total_interactions DESC;

COMMENT ON VIEW public.v_ai_model_performance IS 'Analyse des performances et coûts par modèle IA';

-- ============================================================================
-- FIN DU PATCH
-- ============================================================================

