import redis.asyncio as redis
from typing import Any, Optional
import json
from datetime import timedelta
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class CacheService:
    
    _redis_client: Optional[redis.Redis] = None

    TTL_SHORT = 30        # 30 secondes - données très dynamiques
    TTL_MEDIUM = 300      # 5 minutes - données moyennement dynamiques
    TTL_LONG = 600        # 10 minutes - données peu dynamiques
    TTL_VERY_LONG = 3600  # 1 heure - données quasi-statiques
    
    @classmethod
    async def initialize(cls) -> None:
        if cls._redis_client is None:
            try:
                logger.info("🔄 Initialisation de la connexion Redis...")
                cls._redis_client = await redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30
                )
                await cls._redis_client.ping()
                logger.info("✅ Connexion Redis initialisée avec succès")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'initialisation de Redis: {e}")
                cls._redis_client = None
    
    @classmethod
    async def get_redis(cls) -> Optional[redis.Redis]:
        if cls._redis_client is None:
            await cls.initialize()
        return cls._redis_client
    
    @classmethod
    async def close(cls) -> None:
        if cls._redis_client:
            try:
                logger.info("🔄 Fermeture de la connexion Redis...")
                await cls._redis_client.close()
                cls._redis_client = None
                logger.info("✅ Connexion Redis fermée avec succès")
            except Exception as e:
                logger.error(f"❌ Erreur lors de la fermeture de Redis: {e}")
    
    @classmethod
    async def get(cls, key: str) -> Optional[Any]:
        try:
            client = await cls.get_redis()
            if not client:
                return None
                
            value = await client.get(key)
            if value:
                logger.debug(f"✅ Cache HIT pour la clé: {key}")
                return json.loads(value)
            else:
                logger.debug(f"❌ Cache MISS pour la clé: {key}")
                return None
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la lecture du cache pour {key}: {e}")
            return None
    
    @classmethod
    async def set(cls, key: str, value: Any, ttl: int = TTL_MEDIUM) -> bool:
        try:
            client = await cls.get_redis()
            if not client:
                return False
                
            serialized_value = json.dumps(value, default=str)  # default=str pour les dates
            await client.setex(key, ttl, serialized_value)
            logger.debug(f"✅ Valeur mise en cache pour {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de l'écriture du cache pour {key}: {e}")
            return False
    
    @classmethod
    async def delete(cls, key: str) -> bool:
        try:
            client = await cls.get_redis()
            if not client:
                return False
                
            await client.delete(key)
            logger.debug(f"✅ Clé supprimée du cache: {key}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la suppression du cache pour {key}: {e}")
            return False
    
    @classmethod
    async def invalidate_pattern(cls, pattern: str) -> int:
        try:
            client = await cls.get_redis()
            if not client:
                return 0
                
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await client.delete(*keys)
                logger.info(f"✅ {deleted} clés supprimées pour le pattern: {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de l'invalidation du pattern {pattern}: {e}")
            return 0
    
    @classmethod
    async def exists(cls, key: str) -> bool:
        try:
            client = await cls.get_redis()
            if not client:
                return False
                
            return await client.exists(key) > 0
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la vérification de l'existence de {key}: {e}")
            return False
    
    @classmethod
    async def get_ttl(cls, key: str) -> Optional[int]:
        try:
            client = await cls.get_redis()
            if not client:
                return None
                
            ttl = await client.ttl(key)
            return ttl if ttl > 0 else None
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la récupération du TTL pour {key}: {e}")
            return None
    
    @classmethod
    def cache_key_dashboard_metrics(cls) -> str:
        return "dashboard:metrics"
    
    @classmethod
    def cache_key_tasks(cls, status: Optional[str] = None, page: int = 1) -> str:
        return f"tasks:list:status={status}:page={page}"
    
    @classmethod
    def cache_key_task_detail(cls, task_id: int) -> str:
        return f"tasks:detail:{task_id}"
    
    @classmethod
    def cache_key_users(cls, page: int = 1) -> str:
        return f"users:list:page={page}"
    
    @classmethod
    def cache_key_language_stats(cls) -> str:
        return "languages:stats"
    
    @classmethod
    def cache_key_ai_usage(cls) -> str:
        return "ai:usage"
    
    @classmethod
    async def invalidate_task_caches(cls, task_id: Optional[int] = None) -> None:
        if task_id:
            await cls.delete(cls.cache_key_task_detail(task_id))

        await cls.invalidate_pattern("tasks:list:*")

        await cls.delete(cls.cache_key_dashboard_metrics())
        
        logger.info(f"✅ Caches des tâches invalidés (task_id: {task_id})")
    
    @classmethod
    async def invalidate_dashboard_caches(cls) -> None:
        """Invalider tous les caches du dashboard."""
        await cls.delete(cls.cache_key_dashboard_metrics())
        logger.info("✅ Caches du dashboard invalidés")

