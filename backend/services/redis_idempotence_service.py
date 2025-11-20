"""
Service Redis pour l'idempotence et la déduplication des webhooks.

Ce service gère:
- Déduplication des webhooks Monday.com
- Cache des contextes courts
- TTL automatique (1h par défaut)
"""

import json
from typing import Optional, Dict, Any
from datetime import timedelta
import redis.asyncio as aioredis
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class RedisIdempotenceService:
    """
    Service Redis pour gérer l'idempotence des webhooks.
    
    Clés Redis utilisées:
    - update:{update_id} → Webhook update traité (TTL 1h)
    - webhook:{item_id}:{event_type} → Événement webhook (TTL 1h)
    - context:{task_id} → Contexte court de tâche (TTL 1h)
    """
    
    def __init__(self):
        """Initialise le service Redis."""
        self.redis_client: Optional[aioredis.Redis] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialise la connexion Redis."""
        if self._initialized:
            return
        
        try:
            self.redis_client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0
            )
            
            await self.redis_client.ping()
            logger.info(f"✅ Redis connecté: {settings.redis_url}")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"❌ Erreur connexion Redis: {e}")
            logger.warning("⚠️ Mode dégradé: idempotence en mémoire uniquement")
            self.redis_client = None
            self._initialized = False
    
    async def close(self):
        """Ferme la connexion Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self._initialized = False
            logger.info("✅ Connexion Redis fermée")
    
    async def is_webhook_processed(self, update_id: str) -> bool:
        """
        Vérifie si un webhook update a déjà été traité.
        
        Args:
            update_id: ID de l'update Monday.com
            
        Returns:
            True si déjà traité, False sinon
        """
        if not self.redis_client:
            return False
        
        try:
            key = f"update:{update_id}"
            exists = await self.redis_client.exists(key)
            
            if exists:
                logger.warning(f"🚫 Webhook déjà traité: {update_id} (Redis)")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification Redis: {e}")
            return False
    
    async def mark_webhook_processed(
        self,
        update_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 3600
    ) -> bool:
        """
        Marque un webhook comme traité dans Redis.
        
        Args:
            update_id: ID de l'update Monday.com
            metadata: Métadonnées optionnelles à stocker
            ttl_seconds: Durée de vie en secondes (défaut: 1h)
            
        Returns:
            True si succès, False si échec
        """
        if not self.redis_client:
            return False
        
        try:
            key = f"update:{update_id}"
            value = json.dumps(metadata or {})
            
            await self.redis_client.setex(
                name=key,
                time=ttl_seconds,
                value=value
            )
            
            logger.debug(f"✅ Webhook marqué traité: {update_id} (TTL: {ttl_seconds}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur marquage Redis: {e}")
            return False
    
    async def is_event_duplicate(
        self,
        item_id: str,
        event_type: str,
        event_hash: Optional[str] = None
    ) -> bool:
        """
        Vérifie si un événement webhook est un doublon.
        
        Args:
            item_id: ID de l'item Monday.com
            event_type: Type d'événement (create_update, update_column_value, etc.)
            event_hash: Hash optionnel du payload pour déduplication fine
            
        Returns:
            True si doublon, False sinon
        """
        if not self.redis_client:
            return False
        
        try:
            if event_hash:
                key = f"webhook:{item_id}:{event_type}:{event_hash}"
            else:
                key = f"webhook:{item_id}:{event_type}"
            
            exists = await self.redis_client.exists(key)
            
            if exists:
                logger.warning(f"🚫 Événement doublon: {item_id}/{event_type}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification doublon Redis: {e}")
            return False
    
    async def mark_event_processed(
        self,
        item_id: str,
        event_type: str,
        event_hash: Optional[str] = None,
        ttl_seconds: int = 3600
    ) -> bool:
        """
        Marque un événement comme traité.
        
        Args:
            item_id: ID de l'item Monday.com
            event_type: Type d'événement
            event_hash: Hash optionnel du payload
            ttl_seconds: Durée de vie en secondes (défaut: 1h)
            
        Returns:
            True si succès, False si échec
        """
        if not self.redis_client:
            return False
        
        try:
            if event_hash:
                key = f"webhook:{item_id}:{event_type}:{event_hash}"
            else:
                key = f"webhook:{item_id}:{event_type}"
            
            await self.redis_client.setex(
                name=key,
                time=ttl_seconds,
                value="1"
            )
            
            logger.debug(f"✅ Événement marqué: {item_id}/{event_type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur marquage événement Redis: {e}")
            return False
    
    async def store_context(
        self,
        task_id: int,
        context: Dict[str, Any],
        ttl_seconds: int = 3600
    ) -> bool:
        """
        Stocke un contexte court de tâche dans Redis.
        
        Args:
            task_id: ID de la tâche
            context: Contexte à stocker
            ttl_seconds: Durée de vie (défaut: 1h)
            
        Returns:
            True si succès, False si échec
        """
        if not self.redis_client:
            return False
        
        try:
            key = f"context:{task_id}"
            value = json.dumps(context)
            
            await self.redis_client.setex(
                name=key,
                time=ttl_seconds,
                value=value
            )
            
            logger.debug(f"✅ Contexte stocké: task_{task_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur stockage contexte Redis: {e}")
            return False
    
    async def get_context(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère un contexte de tâche depuis Redis.
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Contexte si trouvé, None sinon
        """
        if not self.redis_client:
            return None
        
        try:
            key = f"context:{task_id}"
            value = await self.redis_client.get(key)
            
            if value:
                return json.loads(value)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération contexte Redis: {e}")
            return None
    
    def create_payload_hash(self, payload: Dict[str, Any]) -> str:
        """
        Crée un hash du payload pour déduplication fine.
        
        Args:
            payload: Payload webhook
            
        Returns:
            Hash MD5 du payload
        """
        import hashlib
        
        key_fields = {
            "pulseId": payload.get("event", {}).get("pulseId"),
            "type": payload.get("event", {}).get("type"),
            "textBody": payload.get("event", {}).get("textBody", "")[:100],
            "columnId": payload.get("event", {}).get("columnId"),
            "value": str(payload.get("event", {}).get("value", ""))[:100]
        }
        
        payload_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.md5(payload_str.encode()).hexdigest()

redis_idempotence_service = RedisIdempotenceService()

