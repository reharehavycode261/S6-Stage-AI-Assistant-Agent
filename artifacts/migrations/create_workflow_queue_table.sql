-- Migration: Création de la table workflow_queue pour gérer la concurrence des workflows
-- Date: 2025-10-29
-- Description: Table pour gérer les queues de workflows par Monday item (premier arrivé, premier servi)

CREATE TABLE IF NOT EXISTS workflow_queue (
    queue_id VARCHAR(50) PRIMARY KEY,
    monday_item_id BIGINT NOT NULL,
    task_id INTEGER REFERENCES tasks(tasks_id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 5,
    queued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    celery_task_id VARCHAR(255),
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index pour recherches rapides par monday_item_id
CREATE INDEX IF NOT EXISTS idx_workflow_queue_monday_item 
ON workflow_queue(monday_item_id, queued_at);

-- Index pour recherches par status
CREATE INDEX IF NOT EXISTS idx_workflow_queue_status 
ON workflow_queue(status, queued_at);

-- Index pour nettoyage des anciens workflows
CREATE INDEX IF NOT EXISTS idx_workflow_queue_completed 
ON workflow_queue(completed_at) 
WHERE completed_at IS NOT NULL;

-- Trigger pour mise à jour automatique du updated_at
CREATE OR REPLACE FUNCTION update_workflow_queue_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_workflow_queue_timestamp
BEFORE UPDATE ON workflow_queue
FOR EACH ROW
EXECUTE FUNCTION update_workflow_queue_timestamp();

-- Commentaires pour documentation
COMMENT ON TABLE workflow_queue IS 'Queue de workflows pour éviter le traitement concurrent par Monday item';
COMMENT ON COLUMN workflow_queue.queue_id IS 'Identifiant unique de la queue entry';
COMMENT ON COLUMN workflow_queue.monday_item_id IS 'ID de l''item Monday.com';
COMMENT ON COLUMN workflow_queue.task_id IS 'ID de la tâche en base (si créée)';
COMMENT ON COLUMN workflow_queue.status IS 'Statut: pending, running, waiting_validation, completed, failed, cancelled, timeout';
COMMENT ON COLUMN workflow_queue.priority IS 'Priorité (1-10, plus haut = plus prioritaire)';
COMMENT ON COLUMN workflow_queue.celery_task_id IS 'ID de la tâche Celery associée';
COMMENT ON COLUMN workflow_queue.payload IS 'Payload complet du webhook pour rejouer si nécessaire';

-- Nettoyage automatique des anciens workflows (> 7 jours)
CREATE OR REPLACE FUNCTION cleanup_old_workflow_queue_entries()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM workflow_queue
    WHERE completed_at < NOW() - INTERVAL '7 days'
    AND status IN ('completed', 'failed', 'cancelled', 'timeout');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_workflow_queue_entries() IS 'Nettoie les entrées de queue terminées depuis plus de 7 jours';

