"""
Service de classification d'intention pour @vydata.

Ce service analyse les commentaires Monday.com pour déterminer:
- Type 1 (Question informative): "Pourquoi", "Comment", "Explique", etc.
- Type 2 (Commande d'action): "Ajoute", "Crée", "Modifie", "Supprime", etc.

UTILISE LA CHAIN LANGCHAIN COMME LES AUTRES NODES DU PROJET.
"""

import re
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
from utils.logger import get_logger

logger = get_logger(__name__)


class IntentType(Enum):
    """Types d'intention détectés."""
    QUESTION = "question"  
    COMMAND = "command"    
    UNKNOWN = "unknown"    


@dataclass
class IntentAnalysis:
    """Résultat de l'analyse d'intention."""
    intent_type: IntentType
    confidence: float
    reasoning: str
    extracted_action: Optional[str] = None
    requires_workflow: bool = False
    requires_response_only: bool = False
    keywords_detected: list = None


class IntentClassifierService:
    """
    Service pour classifier l'intention des commentaires @vydata.
    
    Architecture:
    1. Utilise la chain LangChain vydata_intent_classification_chain
    2. Fallback sur mots-clés si la chain échoue
    3. Confiance combinée
    """
    
    QUESTION_KEYWORDS = [
        "pourquoi", "comment", "qu'est-ce que", "qu'est ce que",
        "explique", "expliques", "explique-moi", "expliquer",
        "c'est quoi", "cest quoi", "quelle est", "quel est",
        "est-ce que", "est ce que", "peux-tu expliquer",
        "dis-moi", "dis moi", "montre-moi", "montre moi",
        "décris", "décrit", "détaille", "détailler"
    ]
    
    COMMAND_KEYWORDS = [
        "ajoute", "ajouter", "crée", "créer", "créé",
        "modifie", "modifier", "change", "changer",
        "supprime", "supprimer", "efface", "effacer",
        "implémente", "implémenter", "développe", "développer",
        "corrige", "corriger", "fixe", "fixer", "répare", "réparer",
        "mets à jour", "met à jour", "update", "mettre à jour",
        "refactorise", "refactoriser", "optimise", "optimiser",
        "installe", "installer", "configure", "configurer",
        "génère", "générer", "produis", "produire"
    ]
    
    def __init__(self):
        """Initialise le service de classification."""
        pass
    
    async def classify_intent(
        self,
        text: str,
        task_context: Optional[Dict[str, Any]] = None
    ) -> IntentAnalysis:
        """
        Classifie l'intention d'un commentaire @vydata.
        
        Args:
            text: Texte du commentaire (déjà nettoyé du @vydata)
            task_context: Contexte de la tâche (optionnel)
            
        Returns:
            IntentAnalysis avec le type d'intention détecté
        """
        logger.info(f"🔍 Classification d'intention pour: '{text[:100]}...'")
        
        try:
            from ai.chains.vydata_intent_classification_chain import (
                classify_vydata_intent,
                extract_classification_metrics
            )
            
            logger.info("🔗 Utilisation chain LangChain pour classification...")
            
            classification = await classify_vydata_intent(
                message_text=text,
                task_context=task_context,
                provider="anthropic",
                fallback_to_openai=True
            )
            
            metrics = extract_classification_metrics(classification)
            logger.info(
                f"✅ Classification LangChain: {classification.intent_type} "
                f"(confiance: {classification.confidence:.2f})"
            )
            
            intent_type = IntentType.QUESTION if classification.intent_type == "QUESTION" else (
                IntentType.COMMAND if classification.intent_type == "COMMAND" else IntentType.UNKNOWN
            )
            
            return IntentAnalysis(
                intent_type=intent_type,
                confidence=classification.confidence,
                reasoning=classification.reasoning,
                requires_workflow=(intent_type == IntentType.COMMAND),
                requires_response_only=(intent_type == IntentType.QUESTION),
                keywords_detected=classification.keywords_detected if hasattr(classification, 'keywords_detected') else []
            )
            
        except Exception as e:
            logger.warning(f"⚠️ Chain LangChain échouée, fallback mots-clés: {e}")
            
            return self._classify_by_keywords(text)
    
    def _classify_by_keywords(self, text: str) -> IntentAnalysis:
        """
        
        Avantages:
        - Rapide (pas d'appel API)
        - Fiable pour les cas évidents
        """
        text_lower = text.lower()

        question_count = sum(1 for kw in self.QUESTION_KEYWORDS if kw in text_lower)
        
        command_count = sum(1 for kw in self.COMMAND_KEYWORDS if kw in text_lower)
        
        has_question_mark = "?" in text
        starts_with_interrogative = any(
            text_lower.startswith(word) 
            for word in ["pourquoi", "comment", "qu'est", "quelle", "quel", "est-ce"]
        )
        
        starts_with_imperative = any(
            text_lower.startswith(word)
            for word in ["ajoute", "crée", "modifie", "supprime", "implémente", "corrige"]
        )
        
        if question_count > command_count or has_question_mark or starts_with_interrogative:
            confidence = min(0.7, 0.4 + (question_count * 0.1) + (0.2 if has_question_mark else 0))
            return IntentAnalysis(
                intent_type=IntentType.QUESTION,
                confidence=confidence,
                reasoning=f"Fallback mots-clés: question ({question_count} indicateurs)",
                requires_workflow=False,
                requires_response_only=True,
                keywords_detected=[]
            )
        elif command_count > question_count or starts_with_imperative:
            confidence = min(0.7, 0.4 + (command_count * 0.1) + (0.2 if starts_with_imperative else 0))
            return IntentAnalysis(
                intent_type=IntentType.COMMAND,
                confidence=confidence,
                reasoning=f"Fallback mots-clés: commande ({command_count} indicateurs)",
                requires_workflow=True,
                requires_response_only=False,
                keywords_detected=[]
            )
        else:
            return IntentAnalysis(
                intent_type=IntentType.UNKNOWN,
                confidence=0.3,
                reasoning=f"Fallback mots-clés: incertain (Q:{question_count}, C:{command_count})",
                requires_workflow=False,
                requires_response_only=False,
                keywords_detected=[]
            )

intent_classifier_service = IntentClassifierService()
