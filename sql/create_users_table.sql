-- Table des utilisateurs pour l'authentification admin
-- Seuls les utilisateurs dans cette table peuvent accéder à l'interface admin

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'Viewer',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    CONSTRAINT users_role_check CHECK (role IN ('Admin', 'Developer', 'Viewer', 'Auditor'))
);

-- Index pour recherche rapide par email
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Index pour filtrage par rôle
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Index pour filtrage par statut actif
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

-- Trigger pour mettre à jour automatiquement updated_at
CREATE OR REPLACE FUNCTION update_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at_trigger
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_users_updated_at();

-- Table des logs d'audit
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action VARCHAR(100) NOT NULL,
    user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    user_email VARCHAR(255) NOT NULL,
    user_role VARCHAR(50) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    details JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(20) DEFAULT 'success',
    severity VARCHAR(20) DEFAULT 'low',
    CONSTRAINT audit_logs_status_check CHECK (status IN ('success', 'failed', 'warning')),
    CONSTRAINT audit_logs_severity_check CHECK (severity IN ('low', 'medium', 'high', 'critical'))
);

-- Index pour recherche rapide par timestamp
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);

-- Index pour recherche par utilisateur
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);

-- Index pour recherche par action
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);

-- Index pour recherche par sévérité
CREATE INDEX IF NOT EXISTS idx_audit_logs_severity ON audit_logs(severity);

-- Index pour recherche par statut
CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status);

-- Index GIN pour recherche dans les détails JSON
CREATE INDEX IF NOT EXISTS idx_audit_logs_details ON audit_logs USING GIN (details);

-- Commentaires sur les tables
COMMENT ON TABLE users IS 'Table des utilisateurs autorisés à accéder à l''interface admin';
COMMENT ON TABLE audit_logs IS 'Table des logs d''audit pour traçabilité complète (qui/quoi/quand)';

COMMENT ON COLUMN users.role IS 'Rôle de l''utilisateur: Admin, Developer, Viewer, ou Auditor';
COMMENT ON COLUMN users.is_active IS 'Indique si l''utilisateur peut se connecter';
COMMENT ON COLUMN users.last_login IS 'Date et heure de la dernière connexion réussie';

COMMENT ON COLUMN audit_logs.action IS 'Type d''action effectuée (ex: user_login, secret_viewed, config_updated)';
COMMENT ON COLUMN audit_logs.severity IS 'Niveau de gravité: low, medium, high, critical';
COMMENT ON COLUMN audit_logs.status IS 'Résultat de l''action: success, failed, warning';
COMMENT ON COLUMN audit_logs.details IS 'Détails supplémentaires au format JSON';

