import asyncpg
from typing import Optional
from contextlib import asynccontextmanager
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class DatabasePool:

    
    _pool: Optional[asyncpg.Pool] = None
    
    @classmethod
    async def initialize(cls) -> None:
        if cls._pool is None:
            try:
                logger.info("🔄 Initialisation du pool de connexions PostgreSQL...")
                cls._pool = await asyncpg.create_pool(
                    settings.database_url,
                    min_size=5,              # Minimum 5 connexions
                    max_size=20,             # Maximum 20 connexions
                    command_timeout=60,       # Timeout de 60 secondes
                    max_queries=50000,        # Max 50k requêtes par connexion
                    max_inactive_connection_lifetime=300  # 5 minutes
                )
                logger.info("✅ Pool de connexions PostgreSQL initialisé avec succès")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'initialisation du pool: {e}")
                raise
    
    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            await cls.initialize()
        return cls._pool
    
    @classmethod
    async def close(cls) -> None:
        if cls._pool:
            try:
                logger.info("🔄 Fermeture du pool de connexions PostgreSQL...")
                await cls._pool.close()
                cls._pool = None
                logger.info("✅ Pool de connexions fermé avec succès")
            except Exception as e:
                logger.error(f"❌ Erreur lors de la fermeture du pool: {e}")
    
    @classmethod
    @asynccontextmanager
    async def get_connection(cls):
        pool = await cls.get_pool()
        async with pool.acquire() as connection:
            yield connection
    
    @classmethod
    async def execute(cls, query: str, *args):
        async with cls.get_connection() as conn:
            return await conn.execute(query, *args)
    
    @classmethod
    async def fetch(cls, query: str, *args):
        async with cls.get_connection() as conn:
            return await conn.fetch(query, *args)
    
    @classmethod
    async def fetchrow(cls, query: str, *args):
        async with cls.get_connection() as conn:
            return await conn.fetchrow(query, *args)
    
    @classmethod
    async def fetchval(cls, query: str, *args):
        async with cls.get_connection() as conn:
            return await conn.fetchval(query, *args)

