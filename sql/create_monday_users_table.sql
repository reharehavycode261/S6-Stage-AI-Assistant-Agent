-- Table des utilisateurs Monday.com qui utilisent l'agent
-- Cette table stocke les informations des utilisateurs qui créent des tâches dans Monday
CREATE TABLE IF NOT EXISTS monday_users (
    monday_user_id BIGINT PRIMARY KEY,
    monday_item_id BIGINT UNIQUE,  -- L'item Monday qui représente cet utilisateur
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(100),
    team VARCHAR(100),
    access_status VARCHAR(20) DEFAULT 'authorized' CHECK (access_status IN ('authorized', 'suspended', 'restricted', 'pending')),
    satisfaction_score DECIMAL(2,1) CHECK (satisfaction_score >= 0 AND satisfaction_score <= 5),
    satisfaction_comment TEXT,
    last_activity TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Métadonnées Monday.com
    monday_metadata JSONB DEFAULT '{}',
    CONSTRAINT monday_users_satisfaction_check CHECK (satisfaction_score IS NULL OR (satisfaction_score >= 0 AND satisfaction_score <= 5))
);

-- Index pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_monday_users_email ON monday_users(email);
CREATE INDEX IF NOT EXISTS idx_monday_users_item_id ON monday_users(monday_item_id);
CREATE INDEX IF NOT EXISTS idx_monday_users_access_status ON monday_users(access_status);
CREATE INDEX IF NOT EXISTS idx_monday_users_last_activity ON monday_users(last_activity DESC);
CREATE INDEX IF NOT EXISTS idx_monday_users_active ON monday_users(is_active);

-- Index GIN pour recherche dans métadonnées
CREATE INDEX IF NOT EXISTS idx_monday_users_metadata ON monday_users USING GIN (monday_metadata);

-- Trigger pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_monday_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER monday_users_updated_at_trigger
    BEFORE UPDATE ON monday_users
    FOR EACH ROW
    EXECUTE FUNCTION update_monday_users_updated_at();

-- Fonction pour synchroniser last_activity depuis tasks
CREATE OR REPLACE FUNCTION sync_monday_user_activity()
RETURNS TRIGGER AS $$
BEGIN
    -- Mettre à jour last_activity de l'utilisateur quand une nouvelle tâche est créée
    UPDATE monday_users
    SET last_activity = NEW.created_at
    WHERE monday_item_id = NEW.monday_item_id
      AND (last_activity IS NULL OR last_activity < NEW.created_at);
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger sur tasks pour synchroniser automatiquement
CREATE TRIGGER sync_user_activity_on_task_create
    AFTER INSERT ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION sync_monday_user_activity();

-- Commentaires
COMMENT ON TABLE monday_users IS 'Utilisateurs Monday.com qui utilisent l''agent IA';
COMMENT ON COLUMN monday_users.monday_user_id IS 'ID unique de l''utilisateur dans Monday.com';
COMMENT ON COLUMN monday_users.monday_item_id IS 'ID de l''item Monday qui représente cet utilisateur';
COMMENT ON COLUMN monday_users.access_status IS 'Statut d''accès: authorized, suspended, restricted, pending';
COMMENT ON COLUMN monday_users.satisfaction_score IS 'Score de satisfaction de 0 à 5';
COMMENT ON COLUMN monday_users.last_activity IS 'Date et heure de la dernière action de l''utilisateur';
COMMENT ON COLUMN monday_users.monday_metadata IS 'Données supplémentaires depuis Monday.com au format JSON';

