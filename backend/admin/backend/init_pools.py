from admin.backend.db_pool import DatabasePool
from admin.backend.cache_service import CacheService
from utils.logger import get_logger

logger = get_logger(__name__)


async def initialize_services():
    logger.info("🚀 Initialisation des services...")
    
    try:
        await DatabasePool.initialize()
        logger.info("✅ Pool PostgreSQL initialisé")
    except Exception as e:
        logger.error(f"❌ Erreur initialisation pool PostgreSQL: {e}")
    
    try:
        await CacheService.initialize()
        logger.info("✅ Redis initialisé")
    except Exception as e:
        logger.warning(f"⚠️ Erreur initialisation Redis: {e}")
    
    logger.info("✅ Tous les services sont initialisés")


async def shutdown_services():
    logger.info("🛑 Arrêt des services...")
    
    try:
        await DatabasePool.close()
        logger.info("✅ Pool PostgreSQL fermé")
    except Exception as e:
        logger.error(f"❌ Erreur fermeture pool PostgreSQL: {e}")
    
    try:
        await CacheService.close()
        logger.info("✅ Redis fermé")
    except Exception as e:
        logger.warning(f"⚠️ Erreur fermeture Redis: {e}")
    
    logger.info("✅ Tous les services sont arrêtés")

