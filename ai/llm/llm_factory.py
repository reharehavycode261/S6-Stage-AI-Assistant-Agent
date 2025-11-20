from typing import List, Optional, Dict, Any, Union
from langchain_core.language_models import BaseLanguageModel
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LLMConfig:
    
    def __init__(
        self,
        provider: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4000,
        max_retries: int = 2
    ):
        self.provider = provider.lower()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
    
    def __repr__(self):
        return f"LLMConfig(provider={self.provider}, model={self.model}, temp={self.temperature})"


DEFAULT_MODELS = {
    "anthropic": "claude-3-5-sonnet-20241022",
    "openai": "gpt-4o"  
}


def get_llm(
    provider: str = "anthropic",
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 4000,
    max_retries: int = 2,
    **kwargs
) -> BaseLanguageModel:
    """
    Crée une instance de LLM pour un provider spécifique.
    
    Args:
        provider: Provider à utiliser ("anthropic" ou "openai")
        model: Nom du modèle (optionnel, utilise le défaut du provider)
        temperature: Température du modèle (0.0-1.0)
        max_tokens: Nombre maximum de tokens
        max_retries: Nombre de tentatives en cas d'échec
        **kwargs: Arguments additionnels passés au LLM
        
    Returns:
        Instance de LLM configurée
        
    Raises:
        ValueError: Si le provider n'est pas supporté
        Exception: Si les clés API sont manquantes
    """
    provider = provider.lower()
    
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise Exception("ANTHROPIC_API_KEY manquante dans la configuration")
        
        model_name = model or DEFAULT_MODELS["anthropic"]
        
        llm = ChatAnthropic(
            model=model_name,
            anthropic_api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
            **kwargs
        )
        
        logger.debug(f"✅ LLM Anthropic créé: {model_name}")
        return llm
        
    elif provider == "openai":
        if not settings.openai_api_key:
            raise Exception("OPENAI_API_KEY manquante dans la configuration")
        
        model_name = model or DEFAULT_MODELS["openai"]
        
        llm = ChatOpenAI(
            model=model_name,
            openai_api_key=settings.openai_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
            **kwargs
        )
        
        logger.debug(f"✅ LLM OpenAI créé: {model_name}")
        return llm
        
    else:
        raise ValueError(
            f"Provider non supporté: {provider}. "
            f"Utilisez 'anthropic' ou 'openai'"
        )


def get_llm_with_fallback(
    primary_provider: str = "anthropic",
    fallback_providers: Optional[List[str]] = None,
    primary_model: Optional[str] = None,
    fallback_models: Optional[Dict[str, str]] = None,
    temperature: float = 0.1,
    max_tokens: int = 4000,
    max_retries: int = 2,
    **kwargs
) -> BaseLanguageModel:
    """
    Crée un LLM avec fallback automatique vers d'autres providers.
    
    Args:
        primary_provider: Provider principal ("anthropic" ou "openai")
        fallback_providers: Liste de providers de fallback (par défaut: ["openai"] si primary="anthropic")
        primary_model: Modèle pour le provider principal
        fallback_models: Dict de modèles pour chaque provider de fallback
        temperature: Température du modèle
        max_tokens: Nombre maximum de tokens
        max_retries: Nombre de tentatives en cas d'échec
        **kwargs: Arguments additionnels
        
    Returns:
        Instance de LLM avec fallback configuré
        
    Example:
        >>> llm = get_llm_with_fallback(
        ...     primary_provider="anthropic",
        ...     fallback_providers=["openai"],
        ...     temperature=0.1
        ... )
        >>> # En cas d'erreur avec Anthropic, bascule automatiquement vers OpenAI
    """
    if fallback_providers is None:
        if primary_provider.lower() == "openai":
            fallback_providers = ["anthropic"]
        elif primary_provider.lower() == "anthropic":
            fallback_providers = ["openai"]
        else:
            fallback_providers = []
    
    if fallback_models is None:
        fallback_models = {}

    try:
        primary_llm = get_llm(
            provider=primary_provider,
            model=primary_model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
            **kwargs
        )
        
        logger.info(f"🔗 LLM principal créé: {primary_provider}")
        
    except Exception as e:
        logger.error(f"❌ Impossible de créer le LLM principal ({primary_provider}): {e}")
        raise

    if not fallback_providers:
        return primary_llm

    fallback_llms = []
    for fallback_provider in fallback_providers:
        try:
            fallback_model = fallback_models.get(fallback_provider)
            fallback_llm = get_llm(
                provider=fallback_provider,
                model=fallback_model,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=max_retries,
                **kwargs
            )
            fallback_llms.append(fallback_llm)
            logger.info(f"🔄 Fallback configuré: {fallback_provider}")
            
        except Exception as e:
            logger.warning(
                f"⚠️ Impossible de configurer fallback {fallback_provider}: {e}"
            )
    
    if not fallback_llms:
        logger.warning("⚠️ Aucun fallback disponible, utilisation du LLM principal uniquement")
        return primary_llm
    
    llm_with_fallback = primary_llm.with_fallbacks(fallback_llms)
    
    logger.info(
        f"✅ LLM avec fallback créé: {primary_provider} → "
        f"{', '.join(fallback_providers)}"
    )
    
    return llm_with_fallback


def get_llm_chain(
    model_priority: List[str],
    temperature: float = 0.1,
    max_tokens: int = 4000,
    models: Optional[Dict[str, str]] = None,
    **kwargs
) -> BaseLanguageModel:
    """
    Crée un LLM avec fallback basé sur une liste de priorités.
    
    Args:
        model_priority: Liste ordonnée de providers (ex: ["anthropic", "openai"])
        temperature: Température du modèle
        max_tokens: Nombre maximum de tokens
        models: Dict optionnel de modèles spécifiques par provider
        **kwargs: Arguments additionnels
        
    Returns:
        Instance de LLM avec fallback configuré
        
    Example:
        >>> llm = get_llm_chain(
        ...     model_priority=["openai", "anthropic"],
        ...     temperature=0.0
        ... )
    """
    if not model_priority:
        raise ValueError("model_priority ne peut pas être vide")
    
    if models is None:
        models = {}
    
    primary_provider = model_priority[0]
    fallback_providers = model_priority[1:] if len(model_priority) > 1 else []
    
    return get_llm_with_fallback(
        primary_provider=primary_provider,
        fallback_providers=fallback_providers,
        primary_model=models.get(primary_provider),
        fallback_models={p: models.get(p) for p in fallback_providers if p in models},
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )


def get_default_llm_with_fallback(
    temperature: float = 0.1,
    max_tokens: int = 4000,
    **kwargs
) -> BaseLanguageModel:
    """
    Crée un LLM avec la configuration par défaut du projet.
    
    Utilise les settings pour déterminer le provider primaire et configure
    automatiquement le fallback.
    
    Args:
        temperature: Température du modèle
        max_tokens: Nombre maximum de tokens
        **kwargs: Arguments additionnels
        
    Returns:
        Instance de LLM avec fallback configuré
    """
    primary_provider = settings.default_ai_provider
    
    if primary_provider.lower() == "openai":
        fallback = ["anthropic"]
    elif primary_provider.lower() == "anthropic":
        fallback = ["openai"]
    else:
        primary_provider = "anthropic"
        fallback = ["openai"]
    
    return get_llm_with_fallback(
        primary_provider=primary_provider,
        fallback_providers=fallback,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )


# ====================================================================
# Métriques et Monitoring
# ====================================================================

class LLMFallbackTracker:
    """Tracker pour monitorer les fallbacks LLM."""
    
    def __init__(self):
        self.fallback_count = 0
        self.primary_success_count = 0
        self.fallback_success_count = 0
        self.total_failures = 0
        self.provider_stats = {}
    
    def record_primary_success(self, provider: str):
        """Enregistre un succès du provider principal."""
        self.primary_success_count += 1
        self._update_provider_stats(provider, success=True, is_fallback=False)
    
    def record_fallback_success(self, fallback_provider: str):
        """Enregistre un succès du fallback."""
        self.fallback_count += 1
        self.fallback_success_count += 1
        self._update_provider_stats(fallback_provider, success=True, is_fallback=True)
    
    def record_failure(self, provider: str):
        """Enregistre un échec."""
        self.total_failures += 1
        self._update_provider_stats(provider, success=False, is_fallback=False)
    
    def _update_provider_stats(self, provider: str, success: bool, is_fallback: bool):
        """Met à jour les statistiques par provider."""
        if provider not in self.provider_stats:
            self.provider_stats[provider] = {
                "success": 0,
                "failures": 0,
                "fallback_uses": 0
            }
        
        if success:
            self.provider_stats[provider]["success"] += 1
        else:
            self.provider_stats[provider]["failures"] += 1
        
        if is_fallback:
            self.provider_stats[provider]["fallback_uses"] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de fallback."""
        total_calls = self.primary_success_count + self.fallback_success_count + self.total_failures
        
        return {
            "total_calls": total_calls,
            "primary_success_count": self.primary_success_count,
            "fallback_count": self.fallback_count,
            "fallback_success_count": self.fallback_success_count,
            "total_failures": self.total_failures,
            "fallback_rate": (
                (self.fallback_count / total_calls * 100)
                if total_calls > 0 else 0
            ),
            "success_rate": (
                ((self.primary_success_count + self.fallback_success_count) / total_calls * 100)
                if total_calls > 0 else 0
            ),
            "provider_stats": self.provider_stats
        }
    
    def reset(self):
        """Réinitialise les compteurs."""
        self.fallback_count = 0
        self.primary_success_count = 0
        self.fallback_success_count = 0
        self.total_failures = 0
        self.provider_stats = {}


fallback_tracker = LLMFallbackTracker()

