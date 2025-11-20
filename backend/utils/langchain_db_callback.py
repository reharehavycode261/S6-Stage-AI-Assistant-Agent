"""
Callback LangChain pour enregistrer automatiquement les interactions IA en base de données.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
import time
from datetime import datetime

from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from utils.logger import get_logger
from services.database_persistence_service import db_persistence

logger = get_logger(__name__)


class DatabaseLoggingCallback(AsyncCallbackHandler):
    """
    Callback pour enregistrer automatiquement les interactions IA dans la base de données.
    
    Ce callback intercepte tous les appels LLM et enregistre:
    - Le prompt (input)
    - La réponse (output)
    - Les tokens utilisés
    - La latence
    - Le provider et le modèle
    """
    
    def __init__(self, run_step_id: Optional[int] = None):
        """
        Initialise le callback.
        
        Args:
            run_step_id: ID du step en cours (si disponible)
        """
        super().__init__()
        self.run_step_id = run_step_id
        self.llm_start_times: Dict[UUID, float] = {}
        self.llm_prompts: Dict[UUID, str] = {}
        
    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Appelé quand un LLM démarre."""
        # Stocker le timestamp de début et le prompt
        self.llm_start_times[run_id] = time.time()
        self.llm_prompts[run_id] = "\n\n".join(prompts) if prompts else ""
        
        # Extraire le provider et le modèle depuis serialized ou kwargs
        provider = self._extract_provider(serialized, kwargs)
        model = self._extract_model(serialized, kwargs)
        
        logger.debug(f"🤖 LLM Start: provider={provider}, model={model}, run_id={run_id}")
    
    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Appelé quand un LLM termine."""
        try:
            # Calculer la latence
            start_time = self.llm_start_times.get(run_id)
            latency_ms = None
            if start_time:
                latency_ms = int((time.time() - start_time) * 1000)
                del self.llm_start_times[run_id]
            
            # Récupérer le prompt
            prompt = self.llm_prompts.get(run_id, "")
            if run_id in self.llm_prompts:
                del self.llm_prompts[run_id]
            
            # Extraire la réponse
            response_text = self._extract_response_text(response)
            
            # Extraire les tokens
            token_usage = self._extract_token_usage(response)
            
            # Extraire provider et modèle
            provider = self._extract_provider_from_response(response, kwargs)
            model = self._extract_model_from_response(response, kwargs)
            
            # Logger en base de données si run_step_id est disponible
            if self.run_step_id:
                try:
                    await db_persistence.log_ai_interaction(
                        run_step_id=self.run_step_id,
                        ai_provider=provider,
                        model=model,
                        prompt=prompt[:5000],  # Limiter la taille
                        response=response_text[:10000] if response_text else None,
                        token_usage=token_usage,
                        latency_ms=latency_ms
                    )
                    logger.debug(f"✅ Interaction IA enregistrée: step_id={self.run_step_id}, tokens={token_usage}")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur enregistrement interaction IA: {e}")
            else:
                logger.debug(f"⚠️ Interaction IA non enregistrée: pas de run_step_id")
                
        except Exception as e:
            logger.error(f"❌ Erreur dans on_llm_end callback: {e}")
    
    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Appelé quand un LLM rencontre une erreur."""
        try:
            # Nettoyer les données de tracking
            if run_id in self.llm_start_times:
                del self.llm_start_times[run_id]
            
            # Récupérer le prompt
            prompt = self.llm_prompts.get(run_id, "")
            if run_id in self.llm_prompts:
                del self.llm_prompts[run_id]
            
            # Logger l'erreur en base de données si run_step_id disponible
            if self.run_step_id and prompt:
                try:
                    await db_persistence.log_ai_interaction(
                        run_step_id=self.run_step_id,
                        ai_provider="unknown",
                        model="unknown",
                        prompt=prompt[:5000],
                        response=f"ERROR: {str(error)}"[:1000],
                        token_usage=None,
                        latency_ms=None
                    )
                    logger.debug(f"✅ Erreur IA enregistrée: step_id={self.run_step_id}")
                except Exception as log_error:
                    logger.warning(f"⚠️ Erreur enregistrement erreur IA: {log_error}")
                    
        except Exception as e:
            logger.error(f"❌ Erreur dans on_llm_error callback: {e}")
    
    def _extract_provider(self, serialized: Dict[str, Any], kwargs: Dict[str, Any]) -> str:
        """Extrait le provider depuis les données sérialisées."""
        # Essayer depuis le nom de la classe
        class_name = serialized.get("name", "").lower()
        if "anthropic" in class_name or "claude" in class_name:
            return "anthropic"
        elif "openai" in class_name or "gpt" in class_name:
            return "openai"
        
        # Essayer depuis kwargs
        if "model" in kwargs:
            model_name = str(kwargs["model"]).lower()
            if "claude" in model_name:
                return "anthropic"
            elif "gpt" in model_name:
                return "openai"
        
        return "unknown"
    
    def _extract_model(self, serialized: Dict[str, Any], kwargs: Dict[str, Any]) -> str:
        """Extrait le nom du modèle."""
        # Essayer depuis kwargs
        if "model" in kwargs:
            return str(kwargs["model"])
        
        # Essayer depuis serialized
        if "model_name" in serialized.get("kwargs", {}):
            return str(serialized["kwargs"]["model_name"])
        
        return "unknown"
    
    def _extract_provider_from_response(self, response: LLMResult, kwargs: Dict[str, Any]) -> str:
        """Extrait le provider depuis la réponse."""
        # Essayer depuis llm_output
        if response.llm_output:
            model_name = response.llm_output.get("model_name", "")
            if "claude" in model_name.lower():
                return "anthropic"
            elif "gpt" in model_name.lower():
                return "openai"
        
        # Essayer depuis generations
        if response.generations and len(response.generations) > 0:
            gen = response.generations[0]
            if len(gen) > 0 and hasattr(gen[0], "message"):
                msg = gen[0].message
                if hasattr(msg, "response_metadata"):
                    metadata = msg.response_metadata
                    if "model" in metadata:
                        model = str(metadata["model"]).lower()
                        if "claude" in model:
                            return "anthropic"
                        elif "gpt" in model:
                            return "openai"
        
        return "unknown"
    
    def _extract_model_from_response(self, response: LLMResult, kwargs: Dict[str, Any]) -> str:
        """Extrait le modèle depuis la réponse."""
        # Essayer depuis llm_output
        if response.llm_output:
            if "model_name" in response.llm_output:
                return str(response.llm_output["model_name"])
        
        # Essayer depuis generations metadata
        if response.generations and len(response.generations) > 0:
            gen = response.generations[0]
            if len(gen) > 0 and hasattr(gen[0], "message"):
                msg = gen[0].message
                if hasattr(msg, "response_metadata"):
                    metadata = msg.response_metadata
                    if "model" in metadata:
                        return str(metadata["model"])
        
        return "unknown"
    
    def _extract_response_text(self, response: LLMResult) -> str:
        """Extrait le texte de réponse."""
        if not response.generations:
            return ""
        
        # Combiner toutes les générations
        texts = []
        for generation_list in response.generations:
            for generation in generation_list:
                if hasattr(generation, "text"):
                    texts.append(generation.text)
                elif hasattr(generation, "message"):
                    if hasattr(generation.message, "content"):
                        texts.append(str(generation.message.content))
        
        return "\n\n".join(texts)
    
    def _extract_token_usage(self, response: LLMResult) -> Optional[Dict[str, int]]:
        """Extrait l'utilisation des tokens."""
        if not response.llm_output:
            return None
        
        token_usage = response.llm_output.get("token_usage")
        if token_usage:
            # Format OpenAI
            if isinstance(token_usage, dict):
                return {
                    "prompt_tokens": token_usage.get("prompt_tokens", 0),
                    "completion_tokens": token_usage.get("completion_tokens", 0),
                    "total_tokens": token_usage.get("total_tokens", 0)
                }
        
        # Format Anthropic (usage)
        usage = response.llm_output.get("usage")
        if usage and isinstance(usage, dict):
            return {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            }
        
        return None


def create_db_callback(run_step_id: Optional[int] = None) -> DatabaseLoggingCallback:
    """
    Crée un callback pour enregistrer les interactions IA.
    
    Args:
        run_step_id: ID du step en cours
        
    Returns:
        Instance du callback
    """
    return DatabaseLoggingCallback(run_step_id=run_step_id)
