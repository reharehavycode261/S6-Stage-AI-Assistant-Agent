"""
Service de recherche sémantique RAG (Retrieval-Augmented Generation).

Ce service:
- Combine embeddings et vector store pour la recherche sémantique
- Fournit un contexte pertinent multilingue pour le LLM
- Évite les hallucinations en basant les réponses sur les données réelles
- Gère l'historique des conversations
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re

from openai import AsyncOpenAI
from config.settings import get_settings
from utils.logger import get_logger
from services.embedding_service import embedding_service
from services.vector_store_service import (
    vector_store_service,
    SimilaritySearchResult,
    ContextSearchResult
)

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class EnrichedContext:
    """Contexte enrichi pour le LLM avec sources."""
    query: str
    similar_messages: List[SimilaritySearchResult] = field(default_factory=list)
    project_context: Optional[List[ContextSearchResult]] = None
    formatted_context: str = ""
    total_sources: int = 0
    relevance_score: float = 0.0


@dataclass
class SemanticSearchConfig:
    """Configuration pour la recherche sémantique."""
    message_match_threshold: float = 0.7
    message_match_count: int = 5
    context_match_threshold: float = 0.6
    context_match_count: int = 3
    min_relevance_score: float = 0.5
    include_project_context: bool = True
    include_similar_messages: bool = True


class SemanticSearchService:
    """
    Service de recherche sémantique RAG pour enrichir les requêtes LLM.
    
    Fonctionnalités principales:
    - Recherche multilingue par similarité
    - Enrichissement du contexte avec sources
    - Historique des conversations
    - Anti-hallucination via RAG
    """
    
    def __init__(self):
        """Initialise le service de recherche sémantique."""
        self.default_config = SemanticSearchConfig()
        self._openai_client: Optional[AsyncOpenAI] = None
    
    def _get_openai_client(self) -> AsyncOpenAI:
        """Récupère ou crée le client OpenAI."""
        if self._openai_client is None:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY non configurée")
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client
    
    async def initialize(self):
        """Initialise les services dépendants."""
        await vector_store_service.initialize()
        logger.info("✅ Service de recherche sémantique initialisé")
    
    async def _detect_language(self, text: str) -> str:
        """
        Détecte la langue du texte en utilisant le LLM OpenAI.
        
        Support de toutes les langues automatiquement (pas limité à FR/EN/ES).
        Analyse TOUT le texte pour détecter la langue MAJORITAIRE (pas juste le début).
        
        Args:
            text: Texte à analyser
            
        Returns:
            Code langue ISO 639-1 ('fr', 'en', 'es', 'de', 'it', 'pt', 'ar', 'zh', 'ja', 'ru', etc.)
        """
        try:
            client = self._get_openai_client()
            
            # Analyser plus de texte pour avoir une vue globale (jusqu'à 1000 caractères)
            text_sample = text[:1000] if len(text) > 500 else text
            
            logger.info(f"🌍 Détection langue pour texte ({len(text)} caractères):")
            logger.info(f"   Échantillon (100 car.): '{text_sample[:100]}...'")
            
            system_prompt = """Tu es un expert en détection de langues. 
Détecte la langue PRINCIPALE du texte et retourne UNIQUEMENT le code ISO 639-1 (2 lettres).

RÈGLES CRITIQUES:
1. Analyse TOUT le texte fourni (pas seulement le début)
2. Si le texte contient plusieurs langues, détecte la langue MAJORITAIRE
3. Ignore les noms propres, mentions (@), URLs et mots techniques anglais
4. Focus sur les mots de fonction (articles, verbes, connecteurs) pour déterminer la langue

Exemples:
- "@vydata Füge bitte... mais ajoute aussi une fonctionnalité" → 'de' (allemand majoritaire au début)
- "Ajoute cette feature avec README" → 'fr' (français majoritaire, ignore les anglicismes)
- "Please add this fonctionnalité" → 'en' (anglais majoritaire)

Codes ISO 639-1:
- fr (français)
- en (anglais / english)
- es (espagnol / español)
- de (allemand / deutsch)
- it (italien / italiano)
- pt (portugais / português)
- ar (arabe / arabic)
- zh (chinois / chinese)
- ja (japonais / japanese)
- ru (russe / russian)
- nl (néerlandais / dutch)
- pl (polonais / polish)
- tr (turc / turkish)
- ko (coréen / korean)
- hi (hindi)
- sv (suédois / swedish)
- no (norvégien / norwegian)
- da (danois / danish)
- fi (finnois / finnish)

Réponds UNIQUEMENT avec les 2 lettres du code langue, rien d'autre."""

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyse TOUT ce texte et détecte la langue MAJORITAIRE:\n\n{text_sample}"}
                ],
                temperature=0.0,
                max_tokens=5
            )
            
            detected_lang = response.choices[0].message.content.strip().lower()
            
            if len(detected_lang) == 2 and detected_lang.isalpha():
                logger.info(f"✅ Langue MAJORITAIRE détectée par LLM: {detected_lang}")
                logger.info(f"   Texte analysé ({len(text_sample)} car.): '{text_sample[:80]}...'")
                return detected_lang
            else:
                logger.warning(f"⚠️ Réponse LLM invalide: '{detected_lang}' - fallback sur 'en'")
                logger.warning(f"   Texte qui a causé l'erreur: '{text_sample[:80]}...'")
                return 'en'
                
        except Exception as e:
            logger.error(f"❌ Erreur détection langue par LLM: {e}")
            logger.error(f"   Texte qui a causé l'erreur: '{text[:80]}...'")
            return 'en'
    
    async def store_user_message(
        self,
        message_text: str,
        monday_item_id: Optional[str] = None,
        monday_update_id: Optional[str] = None,
        task_id: Optional[int] = None,
        intent_type: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Stocke un message utilisateur avec son embedding.
        
        Args:
            message_text: Texte du message
            monday_item_id: ID de l'item Monday.com
            monday_update_id: ID de l'update Monday.com
            task_id: ID de la tâche
            intent_type: Type d'intention ('question', 'command', etc.)
            user_id: ID de l'utilisateur
            metadata: Métadonnées additionnelles
            
        Returns:
            ID de l'enregistrement créé
        """
        language = await self._detect_language(message_text)
        
        cleaned_text = re.sub(r'<[^>]+>', '', message_text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        embedding_result = await embedding_service.generate_embedding(message_text)
        
        record_id = await vector_store_service.store_message_embedding(
            message_text=message_text,
            embedding=embedding_result.embedding,
            monday_item_id=monday_item_id,
            monday_update_id=monday_update_id,
            task_id=task_id,
            message_language=language,
            cleaned_text=cleaned_text,
            message_type="user_message",
            intent_type=intent_type,
            user_id=user_id,
            metadata=metadata or {}
        )
        
        logger.info(f"✅ Message utilisateur stocké: ID={record_id}, langue={language}")
        return record_id
    
    async def enrich_query_with_context(
        self,
        query: str,
        repository_url: Optional[str] = None,
        monday_item_id: Optional[str] = None,
        config: Optional[SemanticSearchConfig] = None
    ) -> EnrichedContext:
        """
        Enrichit une requête avec du contexte pertinent (RAG).
        
        Args:
            query: Question ou commande de l'utilisateur
            repository_url: URL du repository pour filtrer le contexte
            monday_item_id: ID de l'item Monday pour filtrer les messages
            config: Configuration personnalisée
            
        Returns:
            EnrichedContext avec le contexte formaté et les sources
        """
        config = config or self.default_config
        
        similar_messages: List[SimilaritySearchResult] = []
        project_context: List[ContextSearchResult] = []
        
        tasks = []
        
        if config.include_similar_messages:
            tasks.append(
                vector_store_service.search_similar_messages(
                    query_text=query,
                    match_threshold=config.message_match_threshold,
                    match_count=config.message_match_count,
                    filter_item_id=monday_item_id
                )
            )
        else:
            tasks.append(asyncio.sleep(0))
        
        if config.include_project_context and repository_url:
            tasks.append(
                vector_store_service.search_project_context(
                    query_text=query,
                    repository_url=repository_url,
                    match_threshold=config.context_match_threshold,
                    match_count=config.context_match_count
                )
            )
        else:
            tasks.append(asyncio.sleep(0))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        if config.include_similar_messages and not isinstance(results[0], Exception):
            similar_messages = results[0]
        
        if config.include_project_context and len(results) > 1 and not isinstance(results[1], Exception):
            project_context = results[1]
        
        formatted_context = self._format_context(
            query=query,
            similar_messages=similar_messages,
            project_context=project_context
        )
        
        relevance_score = self._calculate_relevance_score(similar_messages, project_context)
        
        total_sources = len(similar_messages) + (len(project_context) if project_context else 0)
        
        logger.info(f"🔍 Contexte enrichi: {total_sources} sources (score: {relevance_score:.2f})")
        logger.info(f"   • Messages similaires: {len(similar_messages)}")
        logger.info(f"   • Contexte projet: {len(project_context) if project_context else 0}")
        
        return EnrichedContext(
            query=query,
            similar_messages=similar_messages,
            project_context=project_context,
            formatted_context=formatted_context,
            total_sources=total_sources,
            relevance_score=relevance_score
        )
    
    def _format_context(
        self,
        query: str,
        similar_messages: List[SimilaritySearchResult],
        project_context: List[ContextSearchResult]
    ) -> str:
        """
        Formate le contexte pour le LLM.
        
        Args:
            query: Requête de l'utilisateur
            similar_messages: Messages similaires trouvés
            project_context: Contexte du projet trouvé
            
        Returns:
            Contexte formaté en markdown
        """
        context_parts = [
            "# CONTEXTE PERTINENT (RAG - Retrieval-Augmented Generation)",
            "",
            f"**Requête:** {query}",
            ""
        ]
        
        if similar_messages:
            context_parts.append("## 📝 Conversations Précédentes Similaires")
            context_parts.append("")
            
            for idx, result in enumerate(similar_messages[:3], 1):
                similarity_pct = result.similarity * 100
                context_parts.append(f"### Message {idx} (Similarité: {similarity_pct:.1f}%)")
                
                if result.record.message_language:
                    context_parts.append(f"**Langue:** {result.record.message_language}")
                if result.record.intent_type:
                    context_parts.append(f"**Type:** {result.record.intent_type}")
                if result.record.created_at:
                    context_parts.append(f"**Date:** {result.record.created_at.strftime('%Y-%m-%d %H:%M')}")

                text = result.record.cleaned_text or result.record.message_text
                context_parts.append(f"**Contenu:** {text[:500]}")
                context_parts.append("")
        
        if project_context:
            context_parts.append("## 📚 Contexte du Projet")
            context_parts.append("")
            
            for idx, result in enumerate(project_context, 1):
                similarity_pct = result.similarity * 100
                context_parts.append(f"### Source {idx}: {result.context_type} (Similarité: {similarity_pct:.1f}%)")
                
                if result.file_path:
                    context_parts.append(f"**Fichier:** `{result.file_path}`")
                
                context_parts.append(f"**Contenu:** {result.context_text[:800]}")
                context_parts.append("")
        
        context_parts.extend([
            "---",
            "",
            "**INSTRUCTIONS:**",
            "- Utilise UNIQUEMENT les informations ci-dessus pour répondre",
            "- Si les informations ne sont pas suffisantes, dis-le clairement",
            "- Ne fais PAS d'hallucinations ou d'inventions",
            "- Cite les sources quand tu utilises les informations",
            "- Adapte ta réponse à la langue de la requête",
            ""
        ])
        
        return "\n".join(context_parts)
    
    def _calculate_relevance_score(
        self,
        similar_messages: List[SimilaritySearchResult],
        project_context: List[ContextSearchResult]
    ) -> float:
        """
        Calcule un score de pertinence global du contexte.
        
        Args:
            similar_messages: Messages similaires
            project_context: Contexte projet
            
        Returns:
            Score de 0.0 à 1.0
        """
        if not similar_messages and not project_context:
            return 0.0
        
        total_score = 0.0
        total_weight = 0.0
        
        for result in similar_messages:
            total_score += result.similarity * 0.6
            total_weight += 0.6
        
        if project_context:
            for result in project_context:
                total_score += result.similarity * 0.4
                total_weight += 0.4
        
        if total_weight == 0:
            return 0.0
        
        return total_score / total_weight
    
    async def get_conversation_history(
        self,
        monday_item_id: str,
        limit: int = 10
    ) -> List[SimilaritySearchResult]:
        """
        Récupère l'historique des conversations pour un item Monday.
        
        Args:
            monday_item_id: ID de l'item Monday.com
            limit: Nombre maximum de messages
            
        Returns:
            Liste des messages de l'historique
        """
        results = await vector_store_service.search_similar_messages(
            query_text="historique conversation",
            match_threshold=0.0,
            match_count=limit,
            filter_item_id=monday_item_id
        )
        
        logger.info(f"📋 Historique récupéré: {len(results)} messages pour item {monday_item_id}")
        return results
    
    async def close(self):
        """Ferme les connexions."""
        await vector_store_service.close()
        logger.info("🔒 Service de recherche sémantique fermé")

semantic_search_service = SemanticSearchService()