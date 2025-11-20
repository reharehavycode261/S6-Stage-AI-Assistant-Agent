"""
Service de génération d'embeddings vectoriels pour la recherche sémantique.

Ce service:
- Génère des embeddings avec OpenAI (text-embedding-3-small)
- Support multilingue (FR, EN, ES, etc.)
- Cache les embeddings pour éviter les coûts
- Gère le batch processing pour optimiser les performances
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib
import json
from datetime import datetime, timedelta

from openai import AsyncOpenAI
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class EmbeddingResult:
    """Résultat d'un embedding vectoriel."""
    text: str
    embedding: List[float]
    model: str
    dimensions: int
    tokens_used: int
    from_cache: bool = False
    created_at: Optional[datetime] = None


@dataclass
class BatchEmbeddingResult:
    """Résultat d'un batch d'embeddings."""
    results: List[EmbeddingResult]
    total_tokens: int
    total_texts: int
    cache_hits: int
    model: str


class EmbeddingService:
    """
    Service pour générer des embeddings vectoriels avec OpenAI.
    
    Caractéristiques:
    - Modèle: text-embedding-3-small (1536 dimensions)
    - Support multilingue automatique
    - Cache en mémoire pour éviter les appels répétés
    - Batch processing pour efficacité
    """
    
    DEFAULT_MODEL = "text-embedding-3-small"
    DEFAULT_DIMENSIONS = 1536
    MAX_BATCH_SIZE = 100  
    CACHE_TTL_HOURS = 24
    
    def __init__(self):
        """Initialise le service d'embeddings."""
        self.client: Optional[AsyncOpenAI] = None
        self._cache: Dict[str, Tuple[List[float], datetime]] = {}
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialise le client OpenAI de manière asynchrone."""
        try:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY non configurée")
            
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            logger.info("✅ Client OpenAI initialisé pour embeddings")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation client OpenAI: {e}")
            raise
    
    def _get_cache_key(self, text: str, model: str = DEFAULT_MODEL) -> str:
        """
        Génère une clé de cache unique pour un texte.
        
        Args:
            text: Texte à encoder
            model: Modèle d'embedding
            
        Returns:
            Clé de cache (hash SHA256)
        """
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[float]]:
        """
        Récupère un embedding du cache s'il existe et est valide.
        
        Args:
            cache_key: Clé de cache
            
        Returns:
            Embedding ou None si absent/expiré
        """
        if cache_key not in self._cache:
            return None
        
        embedding, cached_at = self._cache[cache_key]
        
        if datetime.now() - cached_at > timedelta(hours=self.CACHE_TTL_HOURS):
            del self._cache[cache_key]
            return None
        
        return embedding
    
    def _add_to_cache(self, cache_key: str, embedding: List[float]):
        """
        Ajoute un embedding au cache.
        
        Args:
            cache_key: Clé de cache
            embedding: Vecteur d'embedding
        """
        self._cache[cache_key] = (embedding, datetime.now())
    
    async def generate_embedding(
        self,
        text: str,
        model: str = DEFAULT_MODEL,
        use_cache: bool = True
    ) -> EmbeddingResult:
        """
        Génère un embedding vectoriel pour un texte.
        
        Args:
            text: Texte à encoder (multilingue supporté)
            model: Modèle d'embedding OpenAI
            use_cache: Utiliser le cache si disponible
            
        Returns:
            EmbeddingResult avec le vecteur et les métadonnées
            
        Raises:
            ValueError: Si le texte est vide
            Exception: Si l'API OpenAI échoue
        """
        if not text or not text.strip():
            raise ValueError("Le texte ne peut pas être vide")
        
        text = text.strip()
        
        cache_key = self._get_cache_key(text, model)
        if use_cache:
            cached_embedding = self._get_from_cache(cache_key)
            if cached_embedding:
                logger.info(f"🎯 Embedding récupéré du cache ({len(text)} caractères)")
                return EmbeddingResult(
                    text=text,
                    embedding=cached_embedding,
                    model=model,
                    dimensions=len(cached_embedding),
                    tokens_used=0,  
                    from_cache=True
                )
        
        try:
            logger.info(f"🤖 Génération embedding OpenAI ({len(text)} caractères)")
            
            response = await self.client.embeddings.create(
                input=text,
                model=model,
                dimensions=self.DEFAULT_DIMENSIONS
            )
            
            embedding = response.data[0].embedding
            tokens_used = response.usage.total_tokens
            
            if use_cache:
                self._add_to_cache(cache_key, embedding)
            
            logger.info(f"✅ Embedding généré: {len(embedding)} dimensions, {tokens_used} tokens")
            
            return EmbeddingResult(
                text=text,
                embedding=embedding,
                model=model,
                dimensions=len(embedding),
                tokens_used=tokens_used,
                from_cache=False,
                created_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur génération embedding: {e}")
            raise
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: str = DEFAULT_MODEL,
        use_cache: bool = True
    ) -> BatchEmbeddingResult:
        """
        Génère des embeddings pour plusieurs textes en batch.
        
        Args:
            texts: Liste de textes à encoder
            model: Modèle d'embedding OpenAI
            use_cache: Utiliser le cache si disponible
            
        Returns:
            BatchEmbeddingResult avec tous les embeddings
            
        Raises:
            ValueError: Si la liste est vide ou trop grande
        """
        if not texts:
            raise ValueError("La liste de textes ne peut pas être vide")
        
        if len(texts) > self.MAX_BATCH_SIZE:
            logger.warning(f"⚠️ Batch trop grand ({len(texts)}), découpage automatique")
            return await self._generate_embeddings_chunked(texts, model, use_cache)
        
        results: List[EmbeddingResult] = []
        total_tokens = 0
        cache_hits = 0
        texts_to_generate: List[Tuple[int, str]] = []
        
        for idx, text in enumerate(texts):
            if not text or not text.strip():
                logger.warning(f"⚠️ Texte vide ignoré à l'index {idx}")
                continue
            
            text = text.strip()
            cache_key = self._get_cache_key(text, model)
            
            if use_cache:
                cached_embedding = self._get_from_cache(cache_key)
                if cached_embedding:
                    results.append(EmbeddingResult(
                        text=text,
                        embedding=cached_embedding,
                        model=model,
                        dimensions=len(cached_embedding),
                        tokens_used=0,
                        from_cache=True
                    ))
                    cache_hits += 1
                    continue
            
            texts_to_generate.append((idx, text))
        
        if texts_to_generate:
            try:
                logger.info(f"🤖 Génération batch: {len(texts_to_generate)} textes")
                
                response = await self.client.embeddings.create(
                    input=[t[1] for t in texts_to_generate],
                    model=model,
                    dimensions=self.DEFAULT_DIMENSIONS
                )
                
                total_tokens = response.usage.total_tokens
                
                for (idx, text), data in zip(texts_to_generate, response.data):
                    embedding = data.embedding
                    
                    if use_cache:
                        cache_key = self._get_cache_key(text, model)
                        self._add_to_cache(cache_key, embedding)
                    
                    results.append(EmbeddingResult(
                        text=text,
                        embedding=embedding,
                        model=model,
                        dimensions=len(embedding),
                        tokens_used=0,  
                        from_cache=False,
                        created_at=datetime.now()
                    ))
                
                logger.info(f"✅ Batch généré: {len(texts_to_generate)} embeddings, {total_tokens} tokens")
                
            except Exception as e:
                logger.error(f"❌ Erreur génération batch: {e}")
                raise
        
        return BatchEmbeddingResult(
            results=results,
            total_tokens=total_tokens,
            total_texts=len(texts),
            cache_hits=cache_hits,
            model=model
        )
    
    async def _generate_embeddings_chunked(
        self,
        texts: List[str],
        model: str,
        use_cache: bool
    ) -> BatchEmbeddingResult:
        """
        Génère des embeddings en découpant en chunks pour respecter les limites.
        
        Args:
            texts: Liste de textes
            model: Modèle d'embedding
            use_cache: Utiliser le cache
            
        Returns:
            BatchEmbeddingResult agrégé
        """
        all_results: List[EmbeddingResult] = []
        total_tokens = 0
        total_cache_hits = 0
        
        for i in range(0, len(texts), self.MAX_BATCH_SIZE):
            chunk = texts[i:i + self.MAX_BATCH_SIZE]
            logger.info(f"📦 Traitement chunk {i//self.MAX_BATCH_SIZE + 1}: {len(chunk)} textes")
            
            batch_result = await self.generate_embeddings_batch(chunk, model, use_cache)
            
            all_results.extend(batch_result.results)
            total_tokens += batch_result.total_tokens
            total_cache_hits += batch_result.cache_hits
        
        return BatchEmbeddingResult(
            results=all_results,
            total_tokens=total_tokens,
            total_texts=len(texts),
            cache_hits=total_cache_hits,
            model=model
        )
    
    def clear_cache(self):
        """Vide le cache des embeddings."""
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info(f"🧹 Cache vidé: {cache_size} embeddings supprimés")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du cache.
        
        Returns:
            Dict avec les stats du cache
        """
        now = datetime.now()
        valid_entries = sum(
            1 for _, (_, cached_at) in self._cache.items()
            if now - cached_at <= timedelta(hours=self.CACHE_TTL_HOURS)
        )
        
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self._cache) - valid_entries,
            "ttl_hours": self.CACHE_TTL_HOURS,
            "max_batch_size": self.MAX_BATCH_SIZE,
            "model": self.DEFAULT_MODEL,
            "dimensions": self.DEFAULT_DIMENSIONS
        }


embedding_service = EmbeddingService()

