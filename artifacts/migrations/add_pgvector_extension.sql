-- ================================================================
-- Migration: Ajout de l'extension pgvector et table des embeddings
-- Date: 2025-11-11
-- Description: Système RAG pour recherche sémantique multilingue
-- ================================================================

-- Créer l'extension pgvector si elle n'existe pas
CREATE EXTENSION IF NOT EXISTS vector;

-- Table pour stocker les embeddings des messages utilisateurs
CREATE TABLE IF NOT EXISTS message_embeddings (
    id SERIAL PRIMARY KEY,
    
    -- Identifiants de référence
    monday_item_id VARCHAR(50),
    monday_update_id VARCHAR(100),
    task_id INTEGER,  -- Référence à tasks.id (pas de contrainte FK pour éviter les dépendances)
    
    -- Contenu du message
    message_text TEXT NOT NULL,
    message_language VARCHAR(10),  -- 'fr', 'en', 'es', etc.
    cleaned_text TEXT,  -- Texte nettoyé sans HTML
    
    -- Embedding vectoriel (1536 dimensions pour OpenAI text-embedding-3-small)
    embedding vector(1536) NOT NULL,
    
    -- Métadonnées
    message_type VARCHAR(50) DEFAULT 'user_message',  -- 'user_message', 'agent_response', 'context'
    intent_type VARCHAR(50),  -- 'question', 'command', 'clarification'
    user_id VARCHAR(100),
    
    -- Contexte additionnel (JSON)
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Index pour recherche rapide
    CONSTRAINT unique_message_update UNIQUE(monday_update_id)
);

-- Index pour la recherche par similarité cosinus (HNSW est le plus performant)
CREATE INDEX IF NOT EXISTS message_embeddings_embedding_idx 
ON message_embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Index supplémentaires pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS message_embeddings_monday_item_idx ON message_embeddings(monday_item_id);
CREATE INDEX IF NOT EXISTS message_embeddings_task_id_idx ON message_embeddings(task_id);
CREATE INDEX IF NOT EXISTS message_embeddings_created_at_idx ON message_embeddings(created_at DESC);
CREATE INDEX IF NOT EXISTS message_embeddings_message_type_idx ON message_embeddings(message_type);

-- Index GIN pour recherche dans les métadonnées JSON
CREATE INDEX IF NOT EXISTS message_embeddings_metadata_idx ON message_embeddings USING GIN (metadata);

-- Fonction pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_message_embeddings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour updated_at
DROP TRIGGER IF EXISTS message_embeddings_updated_at_trigger ON message_embeddings;
CREATE TRIGGER message_embeddings_updated_at_trigger
    BEFORE UPDATE ON message_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_message_embeddings_updated_at();

-- Table pour stocker les contextes de projet (pour enrichir les recherches)
CREATE TABLE IF NOT EXISTS project_context_embeddings (
    id SERIAL PRIMARY KEY,
    
    -- Référence au projet/repository
    repository_url TEXT NOT NULL,
    repository_name VARCHAR(255),
    
    -- Contenu du contexte
    context_text TEXT NOT NULL,
    context_type VARCHAR(50) NOT NULL,  -- 'readme', 'code_snippet', 'documentation', 'previous_task'
    file_path TEXT,
    
    -- Embedding vectoriel
    embedding vector(1536) NOT NULL,
    
    -- Métadonnées
    metadata JSONB DEFAULT '{}',
    language VARCHAR(10),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index pour la recherche de contexte
CREATE INDEX IF NOT EXISTS project_context_embeddings_embedding_idx 
ON project_context_embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS project_context_embeddings_repo_idx ON project_context_embeddings(repository_url);
CREATE INDEX IF NOT EXISTS project_context_embeddings_type_idx ON project_context_embeddings(context_type);

-- Vue pour faciliter les recherches de messages similaires
CREATE OR REPLACE VIEW recent_message_embeddings AS
SELECT 
    me.id,
    me.monday_item_id,
    me.message_text,
    me.cleaned_text,
    me.message_language,
    me.message_type,
    me.intent_type,
    me.embedding,
    me.created_at,
    t.title as task_title,
    t.repository_url
FROM message_embeddings me
LEFT JOIN tasks t ON me.task_id = t.id
WHERE me.created_at > NOW() - INTERVAL '30 days'
ORDER BY me.created_at DESC;

-- Fonction pour rechercher les messages similaires par similarité cosinus
CREATE OR REPLACE FUNCTION search_similar_messages(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5,
    filter_item_id VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    id INTEGER,
    monday_item_id VARCHAR,
    message_text TEXT,
    cleaned_text TEXT,
    message_type VARCHAR,
    intent_type VARCHAR,
    similarity FLOAT,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
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
$$ LANGUAGE plpgsql;

-- Fonction pour rechercher le contexte de projet similaire
CREATE OR REPLACE FUNCTION search_similar_context(
    query_embedding vector(1536),
    repo_url TEXT DEFAULT NULL,
    match_threshold FLOAT DEFAULT 0.6,
    match_count INT DEFAULT 3
)
RETURNS TABLE (
    id INTEGER,
    context_text TEXT,
    context_type VARCHAR,
    file_path TEXT,
    similarity FLOAT,
    repository_url TEXT
) AS $$
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
$$ LANGUAGE plpgsql;

-- Commentaires pour documentation
COMMENT ON TABLE message_embeddings IS 'Stockage des embeddings vectoriels des messages utilisateurs pour recherche sémantique multilingue';
COMMENT ON TABLE project_context_embeddings IS 'Stockage des embeddings du contexte de projet (README, code, docs) pour enrichir les réponses';
COMMENT ON COLUMN message_embeddings.embedding IS 'Vecteur d''embedding 1536 dimensions (OpenAI text-embedding-3-small)';
COMMENT ON INDEX message_embeddings_embedding_idx IS 'Index HNSW pour recherche rapide par similarité cosinus';

