from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from services.llm_security_service import llm_security_guard
from services.content_moderation_service import content_moderator
from utils.logger import get_logger

logger = get_logger(__name__)


class LLMGuardrailsService:

    def __init__(self):
        """Initialise le service de guardrails."""
        self.security_guard = llm_security_guard
        self.content_moderator = content_moderator
        
        self.strict_mode = False
        self.auto_sanitize = True
        
        logger.info("✅ LLM Guardrails Service initialisé")
    
    async def validate_input(
        self,
        text: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        strict_mode: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Valide un input utilisateur avant traitement LLM.
        
        Pipeline de validation :
        1. Vérification sécurité (prompt injection, jailbreaking)
        2. Modération de contenu (violence, haine, etc.)
        3. Décision finale et sanitization si nécessaire
        
        Args:
            text: Texte à valider
            user_id: ID de l'utilisateur
            context: Contexte additionnel
            strict_mode: Si None, utilise self.strict_mode
            
        Returns:
            Dict avec: is_valid, is_safe, is_appropriate, sanitized_text, blocking_reasons
        """
        strict = strict_mode if strict_mode is not None else self.strict_mode
        
        logger.info(
            f"🛡️ Validation input | User: {user_id or 'anonymous'} | "
            f"Length: {len(text)} | Strict: {strict}"
        )
        
        security_check = self.security_guard.check_input_safety(text, user_id)
        
        moderation_result = await self.content_moderator.moderate_content(
            text,
            context={"user_id": user_id, **(context or {})},
            strict_mode=strict
        )
        
        is_safe = security_check["is_safe"]
        is_appropriate = moderation_result["is_appropriate"]
        is_valid = is_safe and is_appropriate
        
        blocking_reasons = []
        
        if not is_safe:
            blocking_reasons.append({
                "category": "security",
                "details": security_check["reasoning"],
                "risk_level": security_check["risk_level"],
                "threats": security_check["threats_detected"]
            })
        
        if not is_appropriate:
            blocking_reasons.append({
                "category": "content_moderation",
                "details": moderation_result["reasoning"],
                "flagged_categories": moderation_result["flagged_categories"]
            })
        
        sanitized_text = None
        if self.auto_sanitize and not is_valid:
            sanitized_text = security_check["sanitized_text"]
            
            if sanitized_text and sanitized_text != text:
                retry_security = self.security_guard.check_input_safety(sanitized_text, user_id)
                retry_moderation = await self.content_moderator.moderate_content(sanitized_text)
                
                if retry_security["is_safe"] and retry_moderation["is_appropriate"]:
                    logger.info(f"✅ Input sanitizé avec succès et maintenant valide")
                    is_valid = True
                    blocking_reasons.append({
                        "category": "info",
                        "details": "Input original non valide mais sanitization réussie"
                    })
        
        if is_valid:
            logger.info(f"✅ Input VALIDÉ | Safe: {is_safe} | Appropriate: {is_appropriate}")
        else:
            logger.warning(
                f"🚫 Input REJETÉ | Safe: {is_safe} | Appropriate: {is_appropriate} | "
                f"Raisons: {len(blocking_reasons)}"
            )
        
        return {
            "is_valid": is_valid,
            "is_safe": is_safe,
            "is_appropriate": is_appropriate,
            "sanitized_text": sanitized_text,
            "original_text": text,
            "blocking_reasons": blocking_reasons,
            "security_check": security_check,
            "moderation_result": moderation_result,
            "user_id": user_id,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
    
    def validate_output(
        self,
        output: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Valide un output LLM avant de le retourner à l'utilisateur.
        
        Vérifie :
        - Pas de fuite de prompt système
        - Pas d'exposition de clés API
        - Pas d'informations sensibles
        
        Args:
            output: Texte généré par le LLM
            context: Contexte de génération
            
        Returns:
            Dict avec: is_valid, issues_detected, sanitized_output
        """
        logger.info(f"🛡️ Validation output | Length: {len(output)}")
        
        security_check = self.security_guard.check_output_safety(output, context)
        
        is_valid = security_check["is_safe"]
        issues_detected = security_check["issues_detected"]
        sanitized_output = security_check["sanitized_output"]
        
        if is_valid:
            logger.info("✅ Output VALIDÉ - Aucun problème détecté")
        else:
            logger.error(
                f"🚨 Output NON SÉCURISÉ | Issues: {len(issues_detected)} | "
                f"Types: {[i['type'] for i in issues_detected]}"
            )
        
        return {
            "is_valid": is_valid,
            "issues_detected": issues_detected,
            "sanitized_output": sanitized_output if not is_valid else output,
            "original_output": output,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
    
    async def validate_conversation(
        self,
        user_message: str,
        llm_response: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Valide une conversation complète (input + output).
        
        Args:
            user_message: Message de l'utilisateur
            llm_response: Réponse du LLM
            user_id: ID de l'utilisateur
            context: Contexte
            
        Returns:
            Dict avec validation complète
        """
        logger.info(f"🛡️ Validation conversation | User: {user_id or 'anonymous'}")
        
        input_validation = await self.validate_input(user_message, user_id, context)
        
        output_validation = None
        if input_validation["is_valid"]:
            output_validation = self.validate_output(llm_response, context)
        
        is_valid = (
            input_validation["is_valid"] and
            (output_validation is None or output_validation["is_valid"])
        )
        
        return {
            "is_valid": is_valid,
            "input_validation": input_validation,
            "output_validation": output_validation,
            "user_id": user_id,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques combinées des guardrails."""
        return {
            "security_stats": self.security_guard.get_statistics(),
            "moderation_stats": self.content_moderator.get_statistics(),
            "configuration": {
                "strict_mode": self.strict_mode,
                "auto_sanitize": self.auto_sanitize
            }
        }
    
    def enable_strict_mode(self):
        """Active le mode strict (seuils plus bas)."""
        self.strict_mode = True
        logger.info("⚠️ Mode strict ACTIVÉ - Seuils de sécurité renforcés")
    
    def disable_strict_mode(self):
        """Désactive le mode strict."""
        self.strict_mode = False
        logger.info("ℹ️ Mode strict DÉSACTIVÉ - Seuils de sécurité normaux")

llm_guardrails = LLMGuardrailsService()
