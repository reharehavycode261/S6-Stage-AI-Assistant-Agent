"""Hub d'intelligence artificielle multi-provider pour éviter le vendor lock-in."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, ConfigDict
import asyncio

from anthropic import Client as AnthropicClient
from openai import OpenAI
from config.settings import get_settings
from utils.logger import get_logger
from config.langsmith_config import langsmith_config


class AIProvider(str, Enum):
    """Providers IA disponibles."""
    CLAUDE = "claude"
    OPENAI = "openai"


class TaskType(str, Enum):
    """Types de tâches pour optimiser le choix du provider."""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    DEBUGGING = "debugging"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    REFACTORING = "refactoring"
    ANALYSIS = "analysis"


class AIRequest(BaseModel):
    """Requête standardisée pour tous les providers."""
    prompt: str
    task_type: TaskType
    context: Optional[Dict[str, Any]] = None
    max_tokens: int = 4000
    temperature: float = 0.1


class AIResponse(BaseModel):
    """Réponse standardisée de tous les providers."""
    model_config = ConfigDict(protected_namespaces=())
    content: str
    provider: AIProvider
    model_used: str
    tokens_used: Optional[int] = None
    success: bool = True
    error: Optional[str] = None
    estimated_cost: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None


class AIProviderInterface(ABC):
    """Interface commune pour tous les providers IA."""
    
    @abstractmethod
    async def generate_code(self, request: AIRequest) -> AIResponse:
        """Génère du code selon la requête."""
        pass
    
    @abstractmethod
    async def analyze_requirements(self, task: Dict[str, Any]) -> AIResponse:
        """Analyse les exigences d'une tâche."""
        pass
    
    @abstractmethod
    async def review_code(self, code: str, context: str = "") -> AIResponse:
        """Effectue une revue de code."""
        pass
    
    @abstractmethod
    async def debug_code(self, code: str, error: str, context: str = "") -> AIResponse:
        """Aide au debugging de code."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Vérifie si le provider est disponible."""
        pass


class ClaudeProvider(AIProviderInterface):
    """Provider pour Claude/Anthropic."""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(self.__class__.__name__)
        self.client = AnthropicClient(api_key=self.settings.anthropic_api_key)
        self.model = "claude-3-5-sonnet-20241022"
    
    async def generate_code(self, request: AIRequest) -> AIResponse:
        """Génère du code avec Claude."""
        try:
            prompt = self._build_code_prompt(request)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            
            total_tokens = 0
            estimated_cost = 0.0
            token_usage = {}
            
            if hasattr(response, 'usage') and response.usage:
                input_tokens = response.usage.input_tokens or 0
                output_tokens = response.usage.output_tokens or 0
                total_tokens = input_tokens + output_tokens
                
                estimated_cost = (input_tokens * 0.000003) + (output_tokens * 0.000015)
                
                token_usage = {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": total_tokens
                }
                
                try:
                    from services.cost_monitoring_service import cost_monitor
                    await cost_monitor.log_ai_usage(
                        workflow_id=request.context.get("workflow_id", "unknown"),
                        task_id=request.context.get("task_id", "unknown"),
                        provider="claude",
                        model=self.model,
                        operation=str(request.task_type),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost=estimated_cost,
                        success=True
                    )
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur logging coûts IA: {e}")
            
            if langsmith_config.client:
                try:
                    langsmith_config.client.create_run(
                        name=f"claude_generate_code_{request.task_type}",
                        run_type="llm",
                        inputs={
                            "prompt": prompt[:500] + "..." if len(prompt) > 500 else prompt,
                            "task_type": str(request.task_type),
                            "max_tokens": request.max_tokens,
                            "temperature": request.temperature
                        },
                        outputs={
                            "content_length": len(response.content[0].text),
                            "tokens_used": total_tokens,
                            "estimated_cost": estimated_cost
                        },
                        extra={
                            "model": self.model,
                            "provider": "claude",
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens
                        }
                    )
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
            
            return AIResponse(
                content=response.content[0].text,
                provider=AIProvider.CLAUDE,
                model_used=self.model,
                tokens_used=total_tokens,
                estimated_cost=estimated_cost,
                token_usage=token_usage
            )
            
        except Exception as e:
            self.logger.error(f"Erreur Claude: {e}")
            return AIResponse(
                content="",
                provider=AIProvider.CLAUDE,
                model_used=self.model,
                success=False,
                error=str(e)
            )
    
    async def analyze_requirements(self, task: Dict[str, Any]) -> AIResponse:
        """Analyse les exigences avec Claude."""
        prompt = f"""
Analyse la tâche suivante et fournis une analyse détaillée :

Titre: {task.get('title', '')}
Description: {task.get('description', '')}
Contexte: {task.get('context', '')}

Fournis :
1. Résumé des exigences
2. Technologies recommandées
3. Plan d'implémentation étape par étape
4. Risques potentiels et mitigations
"""
        
        request = AIRequest(
            prompt=prompt,
            task_type=TaskType.CODE_GENERATION,
            context=task
        )
        
        return await self.generate_code(request)
    
    async def review_code(self, code: str, context: str = "") -> AIResponse:
        """Effectue une revue de code avec Claude."""
        prompt = f"""
Effectue une revue détaillée du code suivant :

Code :
```
{code}
```

Contexte : {context}

Analyse :
1. Qualité du code et bonnes pratiques
2. Sécurité et vulnérabilités potentielles
3. Performance et optimisations
4. Tests manquants
5. Documentation nécessaire
6. Suggestions d'amélioration
"""
        
        request = AIRequest(
            prompt=prompt,
            task_type=TaskType.CODE_REVIEW,
            context={"code": code, "context": context}
        )
        
        return await self.generate_code(request)
    
    async def debug_code(self, code: str, error: str, context: str = "") -> AIResponse:
        """Aide au debugging avec Claude."""
        prompt = f"""
Aide-moi à débugger ce code qui produit l'erreur suivante :

Erreur : {error}

Code problématique :
```
{code}
```

Contexte : {context}

Fournis :
1. Analyse de la cause de l'erreur
2. Solution corrigée
3. Explication de la correction
4. Suggestions pour éviter ce type d'erreur
"""
        
        request = AIRequest(
            prompt=prompt,
            task_type=TaskType.DEBUGGING,
            context={"code": code, "error": error, "context": context}
        )
        
        return await self.generate_code(request)
    
    def is_available(self) -> bool:
        """Vérifie si Claude est disponible."""
        return bool(self.settings.anthropic_api_key)
    
    def _build_code_prompt(self, request: AIRequest) -> str:
        """Construit un prompt optimisé pour Claude."""
        context_str = ""
        if request.context:
            context_str = f"\nContexte : {request.context}"
        
        return f"""Tu es un développeur expert. {request.prompt}{context_str}

Fournis uniquement le code demandé, bien structuré et commenté."""


class OpenAIProvider(AIProviderInterface):
    """Provider pour OpenAI GPT."""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(self.__class__.__name__)
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = "gpt-4"
    
    async def generate_code(self, request: AIRequest) -> AIResponse:
        """Génère du code avec OpenAI."""
        try:
            prompt = self._build_code_prompt(request)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            total_tokens = 0
            estimated_cost = 0.0
            token_usage = {}
            
            if response.usage:
                total_tokens = response.usage.total_tokens or 0
                estimated_cost = (total_tokens / 1000) * 0.03
                
                token_usage = {
                    "prompt_tokens": response.usage.prompt_tokens or 0,
                    "completion_tokens": response.usage.completion_tokens or 0,
                    "total_tokens": total_tokens
                }
                
                try:
                    from services.cost_monitoring_service import cost_monitor
                    await cost_monitor.log_ai_usage(
                        workflow_id=request.context.get("workflow_id", "unknown"),
                        task_id=request.context.get("task_id", "unknown"),
                        provider="openai",
                        model=self.model,
                        operation=str(request.task_type),
                        input_tokens=response.usage.prompt_tokens or 0,
                        output_tokens=response.usage.completion_tokens or 0,
                        estimated_cost=estimated_cost,
                        success=True
                    )
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur logging coûts IA: {e}")
            
            return AIResponse(
                content=response.choices[0].message.content,
                provider=AIProvider.OPENAI,
                model_used=self.model,
                tokens_used=total_tokens,
                estimated_cost=estimated_cost,
                token_usage=token_usage
            )
            
        except Exception as e:
            self.logger.error(f"Erreur OpenAI: {e}")
            return AIResponse(
                content="",
                provider=AIProvider.OPENAI,
                model_used=self.model,
                success=False,
                error=str(e)
            )
    
    async def analyze_requirements(self, task: Dict[str, Any]) -> AIResponse:
        """Analyse les exigences avec GPT."""
        prompt = f"""
Analyse cette tâche de développement :

Titre: {task.get('title', '')}
Description: {task.get('description', '')}

Fournis une analyse structurée incluant :
- Compréhension des exigences
- Architecture recommandée  
- Plan d'implémentation
- Considérations techniques
"""
        
        request = AIRequest(
            prompt=prompt,
            task_type=TaskType.CODE_GENERATION,
            context=task
        )
        
        return await self.generate_code(request)
    
    async def review_code(self, code: str, context: str = "") -> AIResponse:
        """Revue de code avec GPT."""
        prompt = f"""
Revue de code détaillée :

```{code}```

Contexte: {context}

Analyse la qualité, sécurité, performance et fournis des améliorations.
"""
        
        request = AIRequest(
            prompt=prompt,
            task_type=TaskType.CODE_REVIEW
        )
        
        return await self.generate_code(request)
    
    async def debug_code(self, code: str, error: str, context: str = "") -> AIResponse:
        """Debugging avec GPT."""
        prompt = f"""
Debug ce code qui produit l'erreur: {error}

Code:
```{code}```

Contexte: {context}

Fournis la solution corrigée avec explication.
"""
        
        request = AIRequest(
            prompt=prompt,
            task_type=TaskType.DEBUGGING
        )
        
        return await self.generate_code(request)
    
    def is_available(self) -> bool:
        """Vérifie si OpenAI est disponible."""
        return bool(self.settings.openai_api_key)
    
    def _build_code_prompt(self, request: AIRequest) -> str:
        """Construit un prompt optimisé pour GPT."""
        return f"{request.prompt}\n\nFournis du code de qualité production avec commentaires."


class AIEngineHub:
    """Hub central pour gérer tous les providers IA."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.providers: Dict[AIProvider, AIProviderInterface] = {}
        self._initialize_providers()
        
        self.task_preferences = {
            TaskType.CODE_GENERATION: [AIProvider.OPENAI, AIProvider.CLAUDE],
            TaskType.CODE_REVIEW: [AIProvider.OPENAI, AIProvider.CLAUDE],
            TaskType.DEBUGGING: [AIProvider.OPENAI, AIProvider.CLAUDE],
            TaskType.DOCUMENTATION: [AIProvider.CLAUDE, AIProvider.OPENAI],  
            TaskType.TESTING: [AIProvider.OPENAI, AIProvider.CLAUDE],
            TaskType.REFACTORING: [AIProvider.OPENAI, AIProvider.CLAUDE],
            TaskType.ANALYSIS: [AIProvider.OPENAI, AIProvider.CLAUDE]
        }
    
    def _initialize_providers(self):
        """Initialise tous les providers disponibles."""
        claude = ClaudeProvider()
        if claude.is_available():
            self.providers[AIProvider.CLAUDE] = claude
            self.logger.info("✅ Claude provider initialisé")
        
        openai = OpenAIProvider()
        if openai.is_available():
            self.providers[AIProvider.OPENAI] = openai
            self.logger.info("✅ OpenAI provider initialisé")
        
        if not self.providers:
            self.logger.warning("⚠️ Aucun provider IA disponible")
    
    def get_best_provider(self, task_type: TaskType, preferred_provider: Optional[AIProvider] = None) -> Optional[AIProviderInterface]:
        """Sélectionne le meilleur provider pour un type de tâche."""
        if preferred_provider and preferred_provider in self.providers:
            return self.providers[preferred_provider]
        
        preferences = self.task_preferences.get(task_type, list(self.providers.keys()))
        
        for provider in preferences:
            if provider in self.providers:
                self.logger.info(f"🤖 Provider sélectionné: {provider.value} pour {task_type.value}")
                return self.providers[provider]
        
        self.logger.error(f"❌ Aucun provider disponible pour {task_type.value}")
        return None
    
    async def generate_code(self, request: AIRequest, preferred_provider: Optional[AIProvider] = None) -> AIResponse:
        """Génère du code en utilisant le meilleur provider disponible, avec retry/fallback."""
        provider = self.get_best_provider(request.task_type, preferred_provider)
        if not provider:
            return AIResponse(content="", provider=AIProvider.OPENAI, model_used="none", success=False, error="Aucun provider IA disponible")
        
        attempts = 0
        last_error = None
        max_retries = 3
        
        while attempts < max_retries:
            try:
                resp = await provider.generate_code(request)
                if getattr(resp, "success", True):
                    return resp
                if resp and isinstance(getattr(resp, "error", None), str) and ("529" in resp.error or "overloaded" in resp.error.lower()):
                    attempts += 1
                    wait_time = min(60, (2 ** attempts) * 5)  # 10s, 20s, 40s max
                    self.logger.warning(f"🔄 Claude surchargé (tentative {attempts}/{max_retries}), attente {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                return resp
            except Exception as e:
                msg = str(e)
                last_error = msg
                self.logger.error(f"❌ Erreur provider Claude: {e}")
                if "529" in msg or "overloaded" in msg.lower():
                    attempts += 1
                    wait_time = min(60, (2 ** attempts) * 5)
                    self.logger.warning(f"🔄 Claude surchargé (tentative {attempts}/{max_retries}), attente {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                break
        
        fallback = self.get_best_provider(request.task_type, AIProvider.CLAUDE)
        if fallback and (provider is not fallback):
            try:
                return await fallback.generate_code(request)
            except Exception as e:
                return AIResponse(content="", provider=AIProvider.CLAUDE, model_used="none", success=False, error=str(e))
        
        return AIResponse(content="", provider=AIProvider.OPENAI, model_used="none", success=False, error=last_error or "Erreur inconnue")

    async def analyze_requirements(self, request: AIRequest, preferred_provider: Optional[AIProvider] = None) -> AIResponse:
        """Analyse les exigences avec retry/backoff et fallback provider."""
        provider = self.get_best_provider(TaskType.ANALYSIS, preferred_provider)
        if not provider:
            return AIResponse(content="Analyse impossible - aucun provider disponible", provider=AIProvider.OPENAI, model_used="none", success=False, error="Aucun provider IA disponible")
        
        attempts = 0
        last_error = None
        max_retries = 3
        
        while attempts < max_retries:
            try:
                resp = await provider.analyze_requirements(request.context or {})
                if getattr(resp, "success", True):
                    return resp
                if resp and isinstance(getattr(resp, "error", None), str) and ("529" in resp.error or "overloaded" in resp.error.lower()):
                    attempts += 1
                    wait_time = min(60, (2 ** attempts) * 5)
                    self.logger.warning(f"🔄 Claude surchargé (analyse, tentative {attempts}/{max_retries}), attente {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                return resp
            except Exception as e:
                msg = str(e)
                last_error = msg
                self.logger.error(f"❌ Erreur provider Claude (analyse): {e}")
                if "529" in msg or "overloaded" in msg.lower():
                    attempts += 1
                    wait_time = min(60, (2 ** attempts) * 5)
                    self.logger.warning(f"🔄 Claude surchargé (analyse, tentative {attempts}/{max_retries}), attente {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                break
        
        fallback = self.get_best_provider(TaskType.ANALYSIS, AIProvider.CLAUDE)
        if fallback and (provider is not fallback):
            try:
                return await fallback.analyze_requirements(request.context or {})
            except Exception as e:
                return AIResponse(content="", provider=AIProvider.CLAUDE, model_used="none", success=False, error=str(e))
        
        return AIResponse(content="", provider=AIProvider.OPENAI, model_used="none", success=False, error=last_error or "Erreur inconnue")
    
    async def review_code(self, code: str, context: str = "", preferred_provider: Optional[AIProvider] = None) -> AIResponse:
        """Effectue une revue de code."""
        provider = self.get_best_provider(TaskType.CODE_REVIEW, preferred_provider)
        
        if not provider:
            return AIResponse(
                content="Revue impossible - aucun provider disponible",
                provider=AIProvider.OPENAI,
                model_used="none",
                success=False,
                error="Aucun provider IA disponible"
            )
        
        return await provider.review_code(code, context)
    
    async def debug_code(self, code: str, error: str, context: str = "", preferred_provider: Optional[AIProvider] = None) -> AIResponse:
        """Aide au debugging."""
        provider = self.get_best_provider(TaskType.DEBUGGING, preferred_provider)
        
        if not provider:
            return AIResponse(
                content="Debug impossible - aucun provider disponible",
                provider=AIProvider.OPENAI,
                model_used="none",
                success=False,
                error="Aucun provider IA disponible"
            )
        
        return await provider.debug_code(code, error, context)
    
    def get_available_providers(self) -> List[AIProvider]:
        """Retourne la liste des providers disponibles."""
        return list(self.providers.keys())
    
    def get_provider_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques des providers."""
        return {
            "available_providers": [p.value for p in self.providers.keys()],
            "total_providers": len(self.providers),
            "task_preferences": {t.value: [p.value for p in prefs] for t, prefs in self.task_preferences.items()}
        }


ai_hub = AIEngineHub() 