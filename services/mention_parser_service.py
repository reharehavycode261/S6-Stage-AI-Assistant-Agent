"""
Service de parsing des mentions @vydata dans les commentaires Monday.com.

Ce service:
- Détecte la présence de @vydata au début du commentaire
- Extrait le texte de la commande/question
- Nettoie les balises HTML de Monday.com
- Valide le format
- ✅ NOUVEAU: Applique les guardrails de sécurité LLM
"""

import re
import html
import asyncio
from typing import Optional, Tuple
from dataclasses import dataclass, field
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MentionParseResult:
    """Résultat du parsing d'une mention @vydata."""
    has_mention: bool
    cleaned_text: str
    original_text: str
    mention_name: str = "@vydata"
    is_valid: bool = True
    error_message: Optional[str] = None
    # ✅ NOUVEAU: Informations de sécurité
    is_safe: bool = True
    is_appropriate: bool = True
    security_issues: list = field(default_factory=list)
    sanitized_text: Optional[str] = None


class MentionParserService:
    """
    Service pour parser et valider les mentions @vydata.
    
    Supporte différents formats:
    - @vydata Ajoute un fichier README
    - @vydata: Pourquoi ce projet utilise Java?
    - @vydata, crée une fonction update()
    - <p>@vydata Explique le workflow</p> (HTML Monday.com)
    """
    
    MENTION_PATTERNS = [
        r'^@vydata[:\s,]?\s*(.+)$',
        r'^<p>@vydata[:\s,]?\s*(.+)</p>$',
        r'^@vydata[:\s,]?\s*<p>(.+)</p>$',
    ]
    
    MIN_TEXT_LENGTH = 5
    
    MAX_TEXT_LENGTH = 2000
    
    def __init__(self):
        """Initialise le service de parsing."""
        self._guardrails = None
    
    async def parse_mention_with_security(
        self,
        text: str,
        user_id: Optional[str] = None,
        context: Optional[dict] = None
    ) -> MentionParseResult:
        """
        Parse un commentaire avec validation de sécurité LLM.
        
        Cette méthode DOIT être utilisée pour tous les inputs utilisateur.
        Elle applique les guardrails de sécurité avant le parsing standard.
        
        Args:
            text: Texte brut du commentaire Monday.com
            user_id: ID de l'utilisateur (pour rate limiting)
            context: Contexte optionnel
            
        Returns:
            MentionParseResult avec informations de sécurité
        """ 
        if self._guardrails is None:
            try:
                from services.llm_guardrails_service import llm_guardrails
                self._guardrails = llm_guardrails
            except ImportError:
                logger.warning("⚠️ Guardrails non disponibles - Mode dégradé")
                return self.parse_mention(text)
        
        parse_result = self.parse_mention(text)
        
        if not parse_result.has_mention or not parse_result.is_valid:
            return parse_result
        
        try:
            security_validation = await self._guardrails.validate_input(
                text=parse_result.cleaned_text,
                user_id=user_id,
                context=context
            )
            
            parse_result.is_safe = security_validation["is_safe"]
            parse_result.is_appropriate = security_validation["is_appropriate"]
            parse_result.is_valid = security_validation["is_valid"]
            parse_result.security_issues = security_validation["blocking_reasons"]
            parse_result.sanitized_text = security_validation.get("sanitized_text")
            
            if not security_validation["is_valid"] and parse_result.sanitized_text:
                logger.warning(
                    f"⚠️ Input non sécurisé mais sanitizé | User: {user_id} | "
                    f"Issues: {len(parse_result.security_issues)}"
                )
                parse_result.error_message = (
                    f"🚨 Contenu non sécurisé détecté. "
                    f"Raisons: {', '.join([i['category'] for i in parse_result.security_issues])}"
                )
            elif not security_validation["is_valid"]:
                logger.error(
                    f"🚨 Input BLOQUÉ par guardrails | User: {user_id} | "
                    f"Issues: {len(parse_result.security_issues)}"
                )
                parse_result.error_message = (
                    f"🚨 Votre message a été bloqué pour des raisons de sécurité. "
                    f"Veuillez reformuler votre demande."
                )
            
            return parse_result
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la validation de sécurité: {e}")
            return parse_result
    
    def parse_mention(self, text: str) -> MentionParseResult:
        """
        Parse un commentaire pour détecter et extraire la mention @vydata.
        
        Args:
            text: Texte brut du commentaire Monday.com
            
        Returns:
            MentionParseResult avec les informations extraites
        """
        if not text or not isinstance(text, str):
            return MentionParseResult(
                has_mention=False,
                cleaned_text="",
                original_text=text or "",
                is_valid=False,
                error_message="Texte vide ou invalide"
            )
        
        original_text = text

        cleaned_text = self._clean_html(text)
        
        cleaned_text = self._normalize_whitespace(cleaned_text)
        
        has_mention, extracted_text = self._detect_mention(cleaned_text)
        
        if not has_mention:
            return MentionParseResult(
                has_mention=False,
                cleaned_text=cleaned_text,
                original_text=original_text,
                is_valid=False,
                error_message="Mention @vydata non trouvée au début du commentaire"
            )
        
        is_valid, error_message = self._validate_extracted_text(extracted_text)
        
        if not is_valid:
            return MentionParseResult(
                has_mention=True,
                cleaned_text=extracted_text,
                original_text=original_text,
                is_valid=False,
                error_message=error_message
            )
        
        logger.info(f"✅ Mention @vydata détectée: '{extracted_text[:50]}...'")
        
        return MentionParseResult(
            has_mention=True,
            cleaned_text=extracted_text,
            original_text=original_text,
            is_valid=True
        )
    
    def _clean_html(self, text: str) -> str:
        """
        Nettoie les balises HTML de Monday.com.
        
        Monday.com envoie souvent des commentaires avec HTML:
        - <p>@vydata Ajoute un fichier README</p>
        - <strong>Texte en gras</strong>
        - &nbsp; pour les espaces
        """
        if not text:
            return ""
        
        text_no_tags = re.sub(r'<[^>]+>', '', text)
        
        text_decoded = html.unescape(text_no_tags)
        
        return text_decoded.strip()
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalise les espaces multiples et les retours à la ligne.
        """
        if not text:
            return ""
        
        text = re.sub(r'\s+', ' ', text)
        
        text = text.strip()
        
        return text
    
    def _detect_mention(self, text: str) -> Tuple[bool, str]:
        """
        Détecte la mention @vydata et extrait le texte qui suit.
        
        Returns:
            Tuple (has_mention, extracted_text)
        """
        if not text:
            return False, ""
        
        if '@vydata' not in text.lower():
            return False, ""
        
        for pattern in self.MENTION_PATTERNS:
            match = re.match(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted_text = match.group(1).strip()
                logger.debug(f"🔍 Mention détectée avec pattern: {pattern}")
                return True, extracted_text
        
        if text.lower().startswith('@vydata'):
            extracted_text = text[7:].strip()
            extracted_text = re.sub(r'^[:\s,]+', '', extracted_text)
            
            if extracted_text:
                logger.debug(f"🔍 Mention détectée avec pattern de secours")
                return True, extracted_text
        
        logger.debug(f"⚠️ @vydata trouvé mais pas au début du commentaire")
        return False, ""
    
    def _validate_extracted_text(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Valide le texte extrait après la mention @vydata.
        
        Returns:
            Tuple (is_valid, error_message)
        """
        if not text:
            return False, "Aucun texte après @vydata"
        
        if len(text) < self.MIN_TEXT_LENGTH:
            return False, f"Texte trop court après @vydata (minimum {self.MIN_TEXT_LENGTH} caractères)"
        
        if len(text) > self.MAX_TEXT_LENGTH:
            return False, f"Texte trop long après @vydata (maximum {self.MAX_TEXT_LENGTH} caractères)"
        
        if not re.search(r'[a-zA-Z0-9]', text):
            return False, "Le texte après @vydata ne contient pas de caractères alphanumériques"
        
        return True, None
    
    def is_agent_message(self, text: str) -> bool:
        """
        Détecte si un message vient de l'agent lui-même.
        
        Les messages de l'agent commencent généralement par:
        - 🤖
        - ✅ Validation
        - ✅ **Tâche Complétée
        - 🤖 **WORKFLOW TERMINÉ
        
        Args:
            text: Texte du commentaire
            
        Returns:
            True si c'est un message de l'agent
        """
        if not text:
            return False
        
        agent_patterns = [
            r'^🤖',
            r'^✅ Validation',
            r'^✅ \*\*Tâche Complétée',
            r'^🤖 \*\*WORKFLOW TERMINÉ',
            r'^🤖 \*\*RÉACTIVATION',
            r'^🤖 \*\*Réponse VyData\*\*',
            r'^\[AGENT\]',
            r'^\[BOT\]',
        ]
        
        cleaned_text = self._clean_html(text).strip()
        
        for pattern in agent_patterns:
            if re.match(pattern, cleaned_text, re.IGNORECASE):
                logger.debug(f"🤖 Message de l'agent détecté: {pattern}")
                return True
        
        return False

mention_parser_service = MentionParserService()
