"""
Service de gestion du vector store PostgreSQL avec pgvector.

Ce service:
- Stocke les embeddings dans PostgreSQL
- Effectue des recherches par similarité cosinus
- Gère le contexte de projet et les messages utilisateurs
- Support multilingue automatique
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

import asyncpg
from pgvector.asyncpg import register_vector
from config.settings import get_settings
from utils.logger import get_logger
from services.embedding_service import embedding_service, EmbeddingResult

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class MessageEmbeddingRecord:
    """Enregistrement d'un message avec son embedding."""
    id: Optional[int]
    monday_item_id: Optional[str]
    monday_update_id: Optional[str]
    task_id: Optional[int]
    message_text: str
    message_language: Optional[str]
    cleaned_text: Optional[str]
    embedding: List[float]
    message_type: str
    intent_type: Optional[str]
    user_id: Optional[str]
    metadata: Dict[str, Any]
    created_at: Optional[datetime]


@dataclass
class SimilaritySearchResult:
    """Résultat d'une recherche par similarité."""
    record: MessageEmbeddingRecord
    similarity: float


@dataclass
class ContextSearchResult:
    """Résultat d'une recherche de contexte de projet."""
    id: int
    context_text: str
    context_type: str
    file_path: Optional[str]
    similarity: float
    repository_url: str


class VectorStoreService:
    """
    Service pour gérer le stockage et la recherche vectorielle avec pgvector.
    
    Fonctionnalités:
    - Stockage des embeddings de messages
    - Recherche sémantique par similarité cosinus
    - Gestion du contexte de projet
    - Support multilingue automatique
    """
    
    def __init__(self):
        """Initialise le service de vector store."""
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """
        Initialise la connexion au pool PostgreSQL.
        
        Raises:
            Exception: Si la connexion échoue
        """
        if self.pool:
            logger.info("✅ Pool PostgreSQL déjà initialisé")
            return
        
        try:
            async def init_connection(conn):
                await register_vector(conn)
            
            self.pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
                init=init_connection
            )
            logger.info("✅ Pool PostgreSQL initialisé pour vector store")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation pool PostgreSQL: {e}")
            raise
    
    async def close(self):
        """Ferme le pool de connexions."""
        if self.pool:
            await self.pool.close()
            logger.info("🔒 Pool PostgreSQL fermé")
    
    async def store_message_embedding(
        self,
        message_text: str,
        embedding: List[float],
        monday_item_id: Optional[str] = None,
        monday_update_id: Optional[str] = None,
        task_id: Optional[int] = None,
        message_language: Optional[str] = None,
        cleaned_text: Optional[str] = None,
        message_type: str = "user_message",
        intent_type: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Stocke un embedding de message dans la base de données.
        
        Args:
            message_text: Texte du message original
            embedding: Vecteur d'embedding (1536 dimensions)
            monday_item_id: ID de l'item Monday.com
            monday_update_id: ID de l'update Monday.com
            task_id: ID de la tâche en base
            message_language: Langue du message ('fr', 'en', 'es', etc.)
            cleaned_text: Texte nettoyé sans HTML
            message_type: Type de message ('user_message', 'agent_response', 'context')
            intent_type: Type d'intention ('question', 'command', 'clarification')
            user_id: ID de l'utilisateur
            metadata: Métadonnées additionnelles
            
        Returns:
            ID de l'enregistrement créé
            
        Raises:
            Exception: Si l'insertion échoue
        """
        if not self.pool:
            await self.initialize()
        
        metadata = metadata or {}
        metadata_json = json.dumps(metadata)
        
        try:
            async with self.pool.acquire() as conn:
                if monday_update_id:
                    existing = await conn.fetchval(
                        "SELECT id FROM message_embeddings WHERE monday_update_id = $1",
                        monday_update_id
                    )
                    if existing:
                        logger.info(f"ℹ️  Message déjà stocké (update_id: {monday_update_id})")
                        return existing
                
                record_id = await conn.fetchval(
                    """
                    INSERT INTO message_embeddings (
                        monday_item_id, monday_update_id, task_id,
                        message_text, message_language, cleaned_text,
                        embedding, message_type, intent_type, user_id, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7::vector, $8, $9, $10, $11)
                    RETURNING id
                    """,
                    monday_item_id, monday_update_id, task_id,
                    message_text, message_language, cleaned_text,
                    embedding, message_type, intent_type, user_id, metadata_json
                )
                
                logger.info(f"✅ Embedding stocké: ID={record_id}, type={message_type}, lang={message_language}")
                return record_id
                
        except Exception as e:
            logger.error(f"❌ Erreur stockage embedding: {e}")
            raise
    
    async def search_similar_messages(
        self,
        query_text: str,
        match_threshold: float = 0.7,
        match_count: int = 5,
        filter_item_id: Optional[str] = None,
        filter_message_type: Optional[str] = None
    ) -> List[SimilaritySearchResult]:
        """
        Recherche les messages similaires par similarité cosinus.
        
        Args:
            query_text: Texte de la requête
            match_threshold: Seuil de similarité minimum (0.0 à 1.0)
            match_count: Nombre maximum de résultats
            filter_item_id: Filtrer par item Monday.com
            filter_message_type: Filtrer par type de message
            
        Returns:
            Liste de SimilaritySearchResult triés par similarité décroissante
            
        Raises:
            Exception: Si la recherche échoue
        """
        if not self.pool:
            await self.initialize()
        
        try:
            embedding_result = await embedding_service.generate_embedding(query_text)
            query_embedding = embedding_result.embedding
        except Exception as e:
            logger.error(f"❌ Erreur génération embedding requête: {e}")
            raise
        
        where_clauses = ["(1 - (embedding <=> $1::vector)) > $2"]
        params = [query_embedding, match_threshold]
        param_idx = 3
        
        if filter_item_id:
            where_clauses.append(f"monday_item_id = ${param_idx}")
            params.append(filter_item_id)
            param_idx += 1
        
        if filter_message_type:
            where_clauses.append(f"message_type = ${param_idx}")
            params.append(filter_message_type)
            param_idx += 1
        
        where_sql = " AND ".join(where_clauses)
        
        query_sql = f"""
        SELECT 
            id, monday_item_id, monday_update_id, task_id,
            message_text, message_language, cleaned_text,
            embedding, message_type, intent_type, user_id,
            metadata, created_at,
            (1 - (embedding <=> $1::vector)) AS similarity
        FROM message_embeddings
        WHERE {where_sql}
        ORDER BY embedding <=> $1::vector
        LIMIT ${param_idx}
        """
        params.append(match_count)
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query_sql, *params)
                
                results = []
                for row in rows:
                    record = MessageEmbeddingRecord(
                        id=row['id'],
                        monday_item_id=row['monday_item_id'],
                        monday_update_id=row['monday_update_id'],
                        task_id=row['task_id'],
                        message_text=row['message_text'],
                        message_language=row['message_language'],
                        cleaned_text=row['cleaned_text'],
                        embedding=row['embedding'],
                        message_type=row['message_type'],
                        intent_type=row['intent_type'],
                        user_id=row['user_id'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {},
                        created_at=row['created_at']
                    )
                    
                    results.append(SimilaritySearchResult(
                        record=record,
                        similarity=float(row['similarity'])
                    ))
                
                logger.info(f"🔍 Recherche terminée: {len(results)} résultats (seuil: {match_threshold})")
                return results
                
        except Exception as e:
            logger.error(f"❌ Erreur recherche similarité: {e}")
            raise
    
    async def store_and_search(
        self,
        message_text: str,
        **storage_kwargs
    ) -> Tuple[int, List[SimilaritySearchResult]]:
        """
        Stocke un message et recherche immédiatement des messages similaires.
        
        Args:
            message_text: Texte du message
            **storage_kwargs: Arguments pour store_message_embedding
            
        Returns:
            Tuple (record_id, similar_messages)
        """
        embedding_result = await embedding_service.generate_embedding(message_text)
        
        record_id = await self.store_message_embedding(
            message_text=message_text,
            embedding=embedding_result.embedding,
            **storage_kwargs
        )
        
        similar_messages = await self.search_similar_messages(
            query_text=message_text,
            match_threshold=0.7,
            match_count=5
        )
        
        return record_id, similar_messages
    
    async def store_project_context(
        self,
        repository_url: str,
        context_text: str,
        context_type: str,
        file_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None
    ) -> int:
        """
        Stocke le contexte d'un projet (README, code, etc.).
        
        Args:
            repository_url: URL du repository
            context_text: Texte du contexte
            context_type: Type de contexte ('readme', 'code_snippet', 'documentation', 'previous_task')
            file_path: Chemin du fichier source
            metadata: Métadonnées additionnelles
            language: Langue du contexte
            
        Returns:
            ID de l'enregistrement créé
        """
        if not self.pool:
            await self.initialize()
        
        embedding_result = await embedding_service.generate_embedding(context_text)
        
        metadata = metadata or {}
        metadata_json = json.dumps(metadata)

        repository_name = repository_url.split('/')[-1] if repository_url else None
        
        try:
            async with self.pool.acquire() as conn:
                record_id = await conn.fetchval(
                    """
                    INSERT INTO project_context_embeddings (
                        repository_url, repository_name, context_text,
                        context_type, file_path, embedding, metadata, language
                    ) VALUES ($1, $2, $3, $4, $5, $6::vector, $7, $8)
                    RETURNING id
                    """,
                    repository_url, repository_name, context_text,
                    context_type, file_path, embedding_result.embedding,
                    metadata_json, language
                )
                
                logger.info(f"✅ Contexte projet stocké: ID={record_id}, type={context_type}")
                return record_id
                
        except Exception as e:
            logger.error(f"❌ Erreur stockage contexte projet: {e}")
            raise
    
    async def search_project_context(
        self,
        query_text: str,
        repository_url: Optional[str] = None,
        match_threshold: float = 0.6,
        match_count: int = 3
    ) -> List[ContextSearchResult]:
        """
        Recherche le contexte de projet similaire.
        
        Args:
            query_text: Texte de la requête
            repository_url: Filtrer par repository (optionnel)
            match_threshold: Seuil de similarité minimum
            match_count: Nombre maximum de résultats
            
        Returns:
            Liste de ContextSearchResult
        """
        if not self.pool:
            await self.initialize()
        
        embedding_result = await embedding_service.generate_embedding(query_text)
        query_embedding = embedding_result.embedding
        
        if repository_url:
            query_sql = """
            SELECT 
                id, context_text, context_type, file_path, repository_url,
                (1 - (embedding <=> $1::vector)) AS similarity
            FROM project_context_embeddings
            WHERE repository_url = $2
                AND (1 - (embedding <=> $1::vector)) > $3
            ORDER BY embedding <=> $1::vector
            LIMIT $4
            """
            params = [query_embedding, repository_url, match_threshold, match_count]
        else:
            query_sql = """
            SELECT 
                id, context_text, context_type, file_path, repository_url,
                (1 - (embedding <=> $1::vector)) AS similarity
            FROM project_context_embeddings
            WHERE (1 - (embedding <=> $1::vector)) > $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """
            params = [query_embedding, match_threshold, match_count]
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query_sql, *params)
                
                results = []
                for row in rows:
                    results.append(ContextSearchResult(
                        id=row['id'],
                        context_text=row['context_text'],
                        context_type=row['context_type'],
                        file_path=row['file_path'],
                        similarity=float(row['similarity']),
                        repository_url=row['repository_url']
                    ))
                
                logger.info(f"🔍 Contexte trouvé: {len(results)} résultats")
                return results
                
        except Exception as e:
            logger.error(f"❌ Erreur recherche contexte: {e}")
            raise
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du vector store.
        
        Returns:
            Dict avec les statistiques
        """
        if not self.pool:
            await self.initialize()
        
        try:
            async with self.pool.acquire() as conn:
                stats = await conn.fetchrow("""
                SELECT 
                    (SELECT COUNT(*) FROM message_embeddings) as total_messages,
                    (SELECT COUNT(*) FROM project_context_embeddings) as total_contexts,
                    (SELECT COUNT(*) FROM message_embeddings WHERE created_at > NOW() - INTERVAL '24 hours') as messages_24h,
                    (SELECT COUNT(DISTINCT message_language) FROM message_embeddings) as languages_count,
                    (SELECT COUNT(DISTINCT monday_item_id) FROM message_embeddings) as unique_items
                """)
                
                return {
                    "total_messages": stats['total_messages'],
                    "total_contexts": stats['total_contexts'],
                    "messages_last_24h": stats['messages_24h'],
                    "languages_count": stats['languages_count'],
                    "unique_items": stats['unique_items']
                }
        except Exception as e:
            logger.error(f"❌ Erreur récupération statistiques: {e}")
            return {}

vector_store_service = VectorStoreService()

