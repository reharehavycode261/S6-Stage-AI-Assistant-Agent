"""Service pour analyser les updates Monday.com et détecter les nouvelles demandes."""

import json
from typing import Dict, Any, Optional
from models.schemas import UpdateIntent, UpdateType, UpdateAnalysisContext
from ai.llm.llm_factory import get_llm_with_fallback
from utils.logger import get_logger

logger = get_logger(__name__)


ANALYZE_UPDATE_PROMPT = """
Analyse ce commentaire Monday.com et détermine s'il s'agit d'une NOUVELLE DEMANDE nécessitant un workflow.

CONTEXTE:
- Tâche : {task_title}
- Statut actuel : {task_status}
- Statut Monday : {monday_status}
- Description originale : {original_description}

COMMENTAIRE À ANALYSER:
{update_text}

INSTRUCTIONS:
1. Détermine le TYPE de commentaire :
   - NEW_REQUEST : Nouvelle fonctionnalité/implémentation demandée
   - MODIFICATION : Modification d'une feature existante
   - BUG_REPORT : Signalement de bug nécessitant correction
   - QUESTION : Simple question sans action requise
   - AFFIRMATION : Commentaire/Remerciement/Confirmation
   - VALIDATION_RESPONSE : Réponse à une validation (oui/non/approuvé)

2. Si NEW_REQUEST, MODIFICATION ou BUG_REPORT, extrais :
   - Ce qui est demandé (description claire)
   - Type de tâche (feature/bugfix/refactor/etc)
   - Priorité estimée (low/medium/high/urgent)
   - Fichiers potentiellement concernés

RÉPONDS EN JSON (et UNIQUEMENT en JSON, sans texte avant ou après):
{{
  "type": "NEW_REQUEST|MODIFICATION|BUG_REPORT|QUESTION|AFFIRMATION|VALIDATION_RESPONSE",
  "confidence": 0.85,
  "requires_workflow": true,
  "reasoning": "Explication de la décision",
  "extracted_requirements": {{
    "title": "Titre court de la demande",
    "description": "Description détaillée",
    "task_type": "feature",
    "priority": "medium",
    "files_mentioned": ["file1.py", "file2.js"],
    "technical_keywords": ["React", "API", "Database"]
  }}
}}

IMPORTANT: Réponds UNIQUEMENT avec le JSON, sans introduction ni conclusion.
"""


class UpdateAnalyzerService:
    """Service pour analyser les updates Monday et détecter les nouvelles demandes."""
    
    def __init__(self):
        """Initialise le service d'analyse."""
        self.llm = None
        logger.info("✅ UpdateAnalyzerService initialisé")
    
    def _get_llm(self):
        """Récupère une instance LLM avec fallback."""
        if self.llm is None:
            self.llm = get_llm_with_fallback(
                temperature=0.2,  
                max_tokens=2000
            )
        return self.llm
    
    async def analyze_update_intent(
        self, 
        update_text: str, 
        context: Dict[str, Any]
    ) -> UpdateIntent:
        """
        Analyse l'intention d'un update Monday.com.
        
        Args:
            update_text: Texte du commentaire
            context: Contexte de la tâche (titre, statut, description, etc.)
            
        Returns:
            UpdateIntent avec le type détecté et les exigences extraites
        """
        try:
            logger.info(f"🔍 Analyse update: {update_text[:100]}...")
            
            if not update_text or not update_text.strip():
                logger.warning("⚠️ Update text vide - considéré comme AFFIRMATION")
                return UpdateIntent(
                    type=UpdateType.AFFIRMATION,
                    confidence=1.0,
                    requires_workflow=False,
                    reasoning="Commentaire vide",
                    extracted_requirements=None
                )
            
            prompt = ANALYZE_UPDATE_PROMPT.format(
                task_title=context.get("task_title", "Non spécifié"),
                task_status=context.get("task_status", "unknown"),
                monday_status=context.get("monday_status", "Non spécifié"),
                original_description=context.get("original_description", "Non spécifié")[:500],
                update_text=update_text
            )
            
            llm = self._get_llm()
            logger.debug(f"📤 Envoi prompt au LLM (longueur: {len(prompt)})")
            
            response = await llm.ainvoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            logger.debug(f"📥 Réponse LLM reçue: {response_text[:200]}...")
            
            result = self._parse_llm_response(response_text)
            
            if result:
                logger.info(f"✅ Analyse terminée: type={result.type}, "
                          f"confidence={result.confidence}, "
                          f"requires_workflow={result.requires_workflow}")
                return result
            else:
                logger.warning("⚠️ Échec parsing réponse LLM - fallback vers QUESTION")
                return UpdateIntent(
                    type=UpdateType.QUESTION,
                    confidence=0.5,
                    requires_workflow=False,
                    reasoning="Échec parsing réponse LLM",
                    extracted_requirements=None
                )
                
        except Exception as e:
            logger.error(f"❌ Erreur analyse update: {e}", exc_info=True)
            return UpdateIntent(
                type=UpdateType.QUESTION,
                confidence=0.0,
                requires_workflow=False,
                reasoning=f"Erreur d'analyse: {str(e)}",
                extracted_requirements=None
            )
    
    def _parse_llm_response(self, response_text: str) -> Optional[UpdateIntent]:
        """
        Parse la réponse JSON du LLM.
        
        Args:
            response_text: Texte de réponse du LLM
            
        Returns:
            UpdateIntent ou None si parsing échoue
        """
        try:
            cleaned = response_text.strip()
            
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            
            update_intent = UpdateIntent(
                type=UpdateType(data.get("type", "question").lower()),
                confidence=float(data.get("confidence", 0.5)),
                requires_workflow=bool(data.get("requires_workflow", False)),
                reasoning=str(data.get("reasoning", "")),
                extracted_requirements=data.get("extracted_requirements")
            )
            
            return update_intent
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur parsing JSON: {e}")
            logger.error(f"📄 Réponse reçue: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur création UpdateIntent: {e}", exc_info=True)
            return None
    
    async def is_new_request(self, update_text: str, context: Dict[str, Any]) -> bool:
        """
        Détermine rapidement si un update est une nouvelle demande.
        
        Args:
            update_text: Texte du commentaire
            context: Contexte de la tâche
            
        Returns:
            True si c'est une nouvelle demande nécessitant un workflow
        """
        intent = await self.analyze_update_intent(update_text, context)
        return intent.requires_workflow and intent.confidence > 0.7
    
    def classify_update_type(self, update_text: str) -> UpdateType:
        """
        Classification simple basée sur des mots-clés (fallback sans LLM).
        
        Args:
            update_text: Texte du commentaire
            
        Returns:
            Type d'update détecté
        """
        text_lower = update_text.lower()
        
        if any(word in text_lower for word in ["merci", "thank", "parfait", "ok", "d'accord", "👍"]):
            return UpdateType.AFFIRMATION
        
        if any(word in text_lower for word in ["?", "comment", "pourquoi", "how", "why"]):
            return UpdateType.QUESTION
        
        if any(word in text_lower for word in ["bug", "erreur", "ne fonctionne pas", "error", "broken"]):
            return UpdateType.BUG_REPORT
        
        if any(word in text_lower for word in ["ajouter", "créer", "implémenter", "add", "create", "implement"]):
            return UpdateType.NEW_REQUEST
        
        if any(word in text_lower for word in ["modifier", "changer", "update", "change", "modify"]):
            return UpdateType.MODIFICATION
        
        return UpdateType.QUESTION

    
update_analyzer_service = UpdateAnalyzerService()

