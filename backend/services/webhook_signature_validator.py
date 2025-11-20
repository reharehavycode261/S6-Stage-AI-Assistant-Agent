"""
Service de validation de signature HMAC pour les webhooks Monday.com.

Sécurité:
- Vérifie la signature X-Monday-Signature
- Rejette les webhooks non signés ou invalides
- Utilise HMAC SHA256
"""

import hmac
import hashlib
import json
from typing import Dict, Any, Optional
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class WebhookSignatureValidator:
    """
    Service de validation de signature HMAC pour webhooks Monday.com.
    
    Monday.com envoie une signature dans l'header X-Monday-Signature:
    - Format: "v1={signature_hex}"
    - Algorithme: HMAC-SHA256
    - Secret: MONDAY_SIGNING_SECRET
    """
    
    def __init__(self):
        """Initialise le validateur."""
        self.signing_secret = settings.monday_signing_secret
        self.is_enabled = bool(self.signing_secret)
        
        if not self.is_enabled:
            logger.warning(
                "⚠️ MONDAY_SIGNING_SECRET non configuré - "
                "validation HMAC désactivée (mode développement)"
            )
    
    def validate_signature(
        self,
        payload: Dict[str, Any],
        signature_header: Optional[str]
    ) -> tuple[bool, Optional[str]]:
        """
        Valide la signature HMAC d'un webhook Monday.com.
        
        Args:
            payload: Payload du webhook (dict Python)
            signature_header: Valeur de l'header X-Monday-Signature
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not self.is_enabled:
            logger.debug("⚠️ Validation HMAC désactivée (mode dev)")
            return True, None
        
        if not signature_header:
            error_msg = "Signature HMAC manquante (header X-Monday-Signature)"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        try:
            if not signature_header.startswith("v1="):
                error_msg = f"Format signature invalide: {signature_header[:20]}..."
                logger.error(f"❌ {error_msg}")
                return False, error_msg
            
            received_signature = signature_header[3:]  
            
            expected_signature = self._compute_signature(payload)
            
            is_valid = hmac.compare_digest(received_signature, expected_signature)
            
            if is_valid:
                logger.debug("✅ Signature HMAC valide")
                return True, None
            else:
                error_msg = "Signature HMAC invalide"
                logger.error(f"❌ {error_msg}")
                logger.debug(f"   Reçue: {received_signature[:20]}...")
                logger.debug(f"   Attendue: {expected_signature[:20]}...")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Erreur validation signature: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return False, error_msg
    
    def _compute_signature(self, payload: Dict[str, Any]) -> str:
        """
        Calcule la signature HMAC-SHA256 du payload.
        
        Args:
            payload: Payload du webhook
            
        Returns:
            Signature hex (lowercase)
        """
        payload_bytes = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
        
        signature = hmac.new(
            key=self.signing_secret.encode('utf-8'),
            msg=payload_bytes,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def validate_request(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> tuple[bool, Optional[str]]:
        """
        Valide une requête webhook complète.
        
        Args:
            payload: Payload du webhook
            headers: Headers HTTP de la requête
            
        Returns:
            Tuple (is_valid, error_message)
        """
        signature = (
            headers.get("X-Monday-Signature") or
            headers.get("x-monday-signature") or
            headers.get("X-MONDAY-SIGNATURE")
        )
        
        return self.validate_signature(payload, signature)

webhook_signature_validator = WebhookSignatureValidator()