"""
Service de modération de contenu - Filtrage de contenu inapproprié via OpenAI Moderation API.

Ce service utilise l'API de modération d'OpenAI pour détecter :
- Contenu violent
- Contenu sexuel
- Haine et harcèlement
- Auto-mutilation
- Contenu dangereux
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

import openai

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class ContentModerationService:
    """Service de modération de contenu utilisant OpenAI Moderation API."""
    
    CATEGORY_THRESHOLDS = {
        "hate": 0.7,             
        "hate/threatening": 0.5,  
        "harassment": 0.7,     
        "harassment/threatening": 0.5,  
        "self-harm": 0.3,      
        "self-harm/intent": 0.3,
        "self-harm/instructions": 0.3,
        "sexual": 0.8,         
        "sexual/minors": 0.0,  
        "violence": 0.7,       
        "violence/graphic": 0.5, 
    }
    
    def __init__(self):
        """Initialise le service de modération."""
        self.openai_client = None
        
        if settings.openai_api_key:
            self.openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            logger.info("✅ Content Moderation Service initialisé avec OpenAI")
        else:
            logger.warning("⚠️ OpenAI API key non configurée - Modération désactivée")
        
        self.stats = {
            "total_checks": 0,
            "flagged_content": 0,
            "clean_content": 0,
            "api_errors": 0,
            "by_category": {}
        }
    
    async def moderate_content(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        strict_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Modère un contenu textuel.
        
        Args:
            text: Texte à modérer
            context: Contexte optionnel (ex: user_id, task_id)
            strict_mode: Si True, applique des seuils plus stricts
            
        Returns:
            Dict avec: is_appropriate, flagged_categories, scores, reasoning
        """
        self.stats["total_checks"] += 1
        
        if not self.openai_client:
            return self._basic_moderation_fallback(text)
        
        try:
            response = await self.openai_client.moderations.create(input=text)
            result = response.results[0]
            
            flagged_categories = []
            category_scores = {}
            
            for category, score in result.category_scores.model_dump().items():
                category_scores[category] = round(score, 4)

                threshold = self.CATEGORY_THRESHOLDS.get(category, 0.7)
                if strict_mode:
                    threshold *= 0.7  
                
                if score >= threshold:
                    flagged_categories.append({
                        "category": category,
                        "score": round(score, 4),
                        "threshold": threshold,
                        "severity": self._get_severity(score, threshold)
                    })
                    
                    self.stats["by_category"][category] = self.stats["by_category"].get(category, 0) + 1
            
            is_appropriate = len(flagged_categories) == 0
            
            if not is_appropriate:
                self.stats["flagged_content"] += 1
                logger.warning(
                    f"🚨 Contenu INAPPROPRIÉ détecté | "
                    f"Catégories: {[c['category'] for c in flagged_categories]} | "
                    f"Context: {context}"
                )
            else:
                self.stats["clean_content"] += 1
            
            reasoning = self._build_reasoning(is_appropriate, flagged_categories, result.flagged)
            
            return {
                "is_appropriate": is_appropriate,
                "flagged_by_openai": result.flagged,
                "flagged_categories": flagged_categories,
                "category_scores": category_scores,
                "reasoning": reasoning,
                "context": context,
                "timestamp": datetime.now().isoformat(),
                "strict_mode": strict_mode
            }
            
        except Exception as e:
            self.stats["api_errors"] += 1
            logger.error(f"❌ Erreur lors de la modération OpenAI: {e}")
            
            return self._basic_moderation_fallback(text, error=str(e))
    
    def _basic_moderation_fallback(self, text: str, error: Optional[str] = None) -> Dict[str, Any]:
        """
        Modération basique sans API (fallback).
        
        Utilise des mots-clés simples pour détecter du contenu potentiellement inapproprié.
        """
        flagged_keywords = []
        
        hate_keywords = ["hate", "racist", "nazi", "supremacist"]
        violence_keywords = ["kill", "murder", "assault", "attack", "bomb"]
        sexual_keywords = ["porn", "xxx", "nsfw"]
        
        text_lower = text.lower()
        
        for keyword in hate_keywords:
            if keyword in text_lower:
                flagged_keywords.append({"category": "hate", "keyword": keyword})
        
        for keyword in violence_keywords:
            if keyword in text_lower:
                flagged_keywords.append({"category": "violence", "keyword": keyword})
        
        for keyword in sexual_keywords:
            if keyword in text_lower:
                flagged_keywords.append({"category": "sexual", "keyword": keyword})
        
        is_appropriate = len(flagged_keywords) == 0
        
        reasoning = "Modération basique par mots-clés (API non disponible)."
        if error:
            reasoning += f" Erreur API: {error}"
        
        if not is_appropriate:
            logger.warning(f"⚠️ Contenu suspect détecté (fallback) | Keywords: {flagged_keywords}")
        
        return {
            "is_appropriate": is_appropriate,
            "flagged_by_openai": None,
            "flagged_categories": flagged_keywords,
            "category_scores": {},
            "reasoning": reasoning,
            "fallback_mode": True,
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_severity(self, score: float, threshold: float) -> str:
        """Détermine la sévérité d'un flag."""
        if score >= threshold * 2:
            return "critical"
        elif score >= threshold * 1.5:
            return "high"
        elif score >= threshold * 1.2:
            return "medium"
        else:
            return "low"
    
    def _build_reasoning(
        self,
        is_appropriate: bool,
        flagged_categories: list,
        openai_flagged: bool
    ) -> str:
        """Construit un message expliquant la décision de modération."""
        if is_appropriate:
            return "✅ Contenu approprié. Aucune violation détectée."
        
        categories_str = ", ".join([
            f"{c['category']} (score: {c['score']}, sévérité: {c['severity']})"
            for c in flagged_categories
        ])
        
        return (
            f"🚨 Contenu inapproprié détecté. "
            f"Catégories violées: {categories_str}. "
            f"OpenAI a {'également ' if openai_flagged else 'aussi '}signalé ce contenu."
        )
    
    async def moderate_batch(
        self,
        texts: list[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Modère plusieurs contenus en batch.
        
        Args:
            texts: Liste de textes à modérer
            context: Contexte optionnel
            
        Returns:
            Dict avec résultats agrégés
        """
        results = await asyncio.gather(
            *[self.moderate_content(text, context) for text in texts],
            return_exceptions=True
        )
        
        # Agréger les résultats
        total = len(results)
        appropriate_count = sum(1 for r in results if isinstance(r, dict) and r.get("is_appropriate", False))
        flagged_count = total - appropriate_count
        
        return {
            "total_checked": total,
            "appropriate_count": appropriate_count,
            "flagged_count": flagged_count,
            "flagged_rate": round(flagged_count / total * 100, 2) if total > 0 else 0,
            "results": [r if isinstance(r, dict) else {"error": str(r)} for r in results]
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques de modération."""
        total = self.stats["total_checks"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "flagged_rate": round(self.stats["flagged_content"] / total * 100, 2),
            "clean_rate": round(self.stats["clean_content"] / total * 100, 2),
            "error_rate": round(self.stats["api_errors"] / total * 100, 2),
        }
    
    def reset_statistics(self):
        """Réinitialise les statistiques."""
        self.stats = {
            "total_checks": 0,
            "flagged_content": 0,
            "clean_content": 0,
            "api_errors": 0,
            "by_category": {}
        }


content_moderator = ContentModerationService()

