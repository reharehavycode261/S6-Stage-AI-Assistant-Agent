"""
Gestionnaire centralisé des connexions PostgreSQL avec pool optimisé.

Ce module fournit une gestion robuste des connexions à la base de données
avec des mécanismes de retry, pooling et nettoyage automatique.
"""

import asyncpg
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, AsyncIterator
from datetime import datetime

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseConnectionManager:
    """
    Gestionnaire centralisé des connexions PostgreSQL.
    
    Fournit:
    - Pool de connexions optimisé
    - Context managers sécurisés
    - Retry automatique
    - Nettoyage des connexions orphelines
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.pool: Optional[asyncpg.Pool] = None
        self._initialization_lock = asyncio.Lock()
        self._is_initialized = False
    
    async def initialize(self) -> None:
        """Initialise le pool de connexions avec retry."""
        if self._is_initialized:
            logger.debug("Pool de connexions déjà initialisé")
            return
        
        async with self._initialization_lock:
            if self._is_initialized:  
                return
            
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"🔄 Tentative {attempt}/{max_retries} d'initialisation du pool de connexions")
                    
                    self.pool = await asyncpg.create_pool(
                        self.settings.database_url,
                        min_size=5,              
                        max_size=20,             
                        max_queries=50000,       
                        max_inactive_connection_lifetime=300,  
                        command_timeout=60,      
                        timeout=30,              
                        server_settings={
                            "application_name": "ai_agent_workflow",
                            "jit": "off"  
                        }
                    )
                    
                    async with self.pool.acquire() as conn:
                        await conn.execute("SELECT 1")
                    
                    self._is_initialized = True
                    logger.info(f"✅ Pool de connexions PostgreSQL initialisé (min=5, max=20)")
                    return
                    
                except Exception as e:
                    logger.error(f"❌ Échec tentative {attempt}/{max_retries}: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  
                    else:
                        logger.error("❌ Impossible d'initialiser le pool de connexions après tous les retries")
                        raise
    
    async def close(self) -> None:
        """Ferme proprement le pool de connexions avec protection contre event loop fermé."""
        if self.pool and self._is_initialized:
            try:
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_closed():
                        logger.debug("Event loop fermé - skip fermeture pool")
                        self._is_initialized = False
                        self.pool = None
                        return
                except RuntimeError:
                    logger.debug("Pas d'event loop actif - skip fermeture pool")
                    self._is_initialized = False
                    self.pool = None
                    return
                
                await self.pool.close()
                logger.info("🔒 Pool de connexions fermé proprement")
                self._is_initialized = False
                self.pool = None
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    logger.debug("Event loop fermé pendant fermeture pool - ignoré")
                else:
                    logger.error(f"⚠️ Erreur lors de la fermeture du pool: {e}")
                self._is_initialized = False
                self.pool = None
            except Exception as e:
                logger.error(f"⚠️ Erreur lors de la fermeture du pool: {e}")
                self._is_initialized = False
                self.pool = None
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[asyncpg.Connection]:
        """
        Context manager pour obtenir une connexion du pool.
        
        Usage:
            async with db_manager.get_connection() as conn:
                result = await conn.fetchrow("SELECT * FROM tasks WHERE tasks_id = $1", task_id)
        
        Yields:
            asyncpg.Connection: Connexion active
        """
        if not self._is_initialized:
            await self.initialize()
        
        if not self._is_initialized or not self.pool:
            raise RuntimeError("Pool de connexions non initialisé")
        
        conn = None
        try:
            conn = await asyncio.wait_for(
                self.pool.acquire(),
                timeout=10.0
            )
            
            yield conn
            
        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout lors de l'acquisition d'une connexion")
            if conn:
                try:
                    if self.pool and self._is_initialized:
                        await self.pool.release(conn)
                except Exception:
                    pass
            raise
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'utilisation de la connexion: {e}")
            if conn:
                try:
                    if self.pool and self._is_initialized:
                        await self.pool.release(conn)
                except Exception:
                    pass
            raise
        finally:
            if conn:
                try:
                    if self.pool and self._is_initialized:
                        try:
                            await asyncio.shield(self.pool.release(conn))
                        except RuntimeError as re:
                            if "Event loop is closed" not in str(re):
                                logger.debug(f"RuntimeError lors de la libération: {re}")
                except Exception as e:
                    error_msg = str(e)
                    if "Event loop is closed" not in error_msg and "another operation is in progress" not in error_msg and "has no attribute" not in error_msg:
                        logger.warning(f"⚠️ Erreur lors de la libération de la connexion: {e}")
    
    @asynccontextmanager
    async def get_transaction(self) -> AsyncIterator[asyncpg.Connection]:
        """
        Context manager pour obtenir une connexion avec transaction.
        
        La transaction est automatiquement commit en cas de succès,
        rollback en cas d'erreur.
        
        Usage:
            async with db_manager.get_transaction() as conn:
                await conn.execute("INSERT INTO tasks (...) VALUES (...)")
                await conn.execute("UPDATE workflow_runs SET ...")
        
        Yields:
            asyncpg.Connection: Connexion avec transaction active
        """
        async with self.get_connection() as conn:
            transaction = conn.transaction()
            try:
                await transaction.start()
                yield conn
                await transaction.commit()
            except Exception as e:
                await transaction.rollback()
                logger.error(f"❌ Transaction rollback suite à erreur: {e}")
                raise
    
    async def execute_with_retry(
        self, 
        query: str, 
        *args,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> str:
        """
        Exécute une requête avec retry automatique en cas d'erreur de connexion.
        
        Args:
            query: Requête SQL à exécuter
            *args: Arguments de la requête
            max_retries: Nombre maximum de tentatives
            retry_delay: Délai entre les tentatives (avec backoff exponentiel)
        
        Returns:
            Résultat de la requête
        """
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                async with self.get_connection() as conn:
                    result = await conn.execute(query, *args)
                    return result
            except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as e:
                last_error = e
                logger.warning(f"⚠️ Erreur connexion (tentative {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  
            except Exception as e:
                logger.error(f"❌ Erreur non-retriable: {e}")
                raise
        
        logger.error(f"❌ Échec de la requête après {max_retries} tentatives")
        raise last_error
    
    async def fetchrow_with_retry(
        self, 
        query: str, 
        *args,
        max_retries: int = 3
    ) -> Optional[asyncpg.Record]:
        """
        Exécute une requête fetchrow avec retry automatique.
        
        Args:
            query: Requête SQL
            *args: Arguments
            max_retries: Nombre de tentatives
        
        Returns:
            asyncpg.Record ou None
        """
        last_error = None
        retry_delay = 1.0
        
        for attempt in range(1, max_retries + 1):
            try:
                async with self.get_connection() as conn:
                    result = await conn.fetchrow(query, *args)
                    return result
            except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as e:
                last_error = e
                logger.warning(f"⚠️ Erreur connexion fetchrow (tentative {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
            except Exception as e:
                logger.error(f"❌ Erreur fetchrow non-retriable: {e}")
                raise
        
        raise last_error
    
    async def fetchval_with_retry(
        self, 
        query: str, 
        *args,
        max_retries: int = 3
    ) -> Optional[any]:
        """
        Exécute une requête fetchval avec retry automatique.
        
        Args:
            query: Requête SQL
            *args: Arguments
            max_retries: Nombre de tentatives
        
        Returns:
            Valeur ou None
        """
        last_error = None
        retry_delay = 1.0
        
        for attempt in range(1, max_retries + 1):
            try:
                async with self.get_connection() as conn:
                    result = await conn.fetchval(query, *args)
                    return result
            except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as e:
                last_error = e
                logger.warning(f"⚠️ Erreur connexion fetchval (tentative {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
            except Exception as e:
                logger.error(f"❌ Erreur fetchval non-retriable: {e}")
                raise
        
        raise last_error
    
    async def cleanup_idle_connections(self) -> None:
        """Nettoie les connexions inactives du pool."""
        if self.pool and not self.pool._closed:
            try:
                await self.pool.expire_connections()
                logger.debug("🧹 Nettoyage des connexions inactives effectué")
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors du nettoyage des connexions: {e}")
    
    async def get_pool_stats(self) -> dict:
        """
        Récupère les statistiques du pool de connexions.
        
        Returns:
            Dict avec les statistiques
        """
        if not self.pool:
            return {"status": "not_initialized"}
        
        return {
            "status": "active",
            "size": self.pool.get_size(),
            "min_size": self.pool.get_min_size(),
            "max_size": self.pool.get_max_size(),
            "free_size": self.pool.get_idle_size(),
            "is_closing": self.pool._closing if hasattr(self.pool, '_closing') else False
        }


db_manager = DatabaseConnectionManager()


async def get_db_connection() -> asyncpg.Connection:
    """
    Obtient une connexion du pool (pour compatibilité).
    
    ⚠️ DEPRECATED: Utiliser db_manager.get_connection() context manager à la place.
    """
    if not db_manager._is_initialized:
        await db_manager.initialize()
    
    if not db_manager._is_initialized or not db_manager.pool:
        raise RuntimeError("Pool de connexions non initialisé")
    
    return await db_manager.pool.acquire()


async def cleanup_connections() -> None:
    """
    Nettoie et ferme toutes les connexions.
    
    Utile pour shutdown propre de l'application.
    """
    await db_manager.close()

