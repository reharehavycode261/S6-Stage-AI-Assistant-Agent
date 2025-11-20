"""
Service de gestion du verrouillage des workflows.
Corrige la Faille #1 : Gestion Incohérente des États du Workflow.
"""

from typing import Tuple, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncio

from utils.logger import get_logger
from services.database_persistence_service import db_persistence

logger = get_logger(__name__)


class WorkflowLockManager:
    """Gestionnaire de verrouillage des workflows pour éviter les modifications concurrentes."""
    
    LOCK_TIMEOUT_MINUTES = 30  
    
    @staticmethod
    async def acquire_workflow_lock(task_id: int, locked_by: str) -> bool:
        """
        Acquiert un verrou sur une tâche pour éviter les modifications concurrentes.
        
        Args:
            task_id: ID de la tâche à verrouiller
            locked_by: Identifiant du processus/tâche qui verrouille
            
        Returns:
            True si le verrou a été acquis, False sinon
        """
        try:
            await WorkflowLockManager._clean_expired_locks()
            
            async with db_persistence.db_manager.get_connection() as conn:
                async with conn.transaction():
                    task_info = await conn.fetchrow("""
                        SELECT is_locked, locked_by, locked_at
                        FROM tasks
                        WHERE tasks_id = $1
                        FOR UPDATE
                    """, task_id)
                    
                    if not task_info:
                        logger.error(f"❌ Tâche {task_id} introuvable")
                        return False
                    
                    if task_info['is_locked']:
                        if task_info['locked_by'] == locked_by:
                            logger.debug(f"ℹ️ Verrou déjà détenu par {locked_by} pour tâche {task_id}")
                            return True
                        
                        logger.warning(f"⚠️ Tâche {task_id} déjà verrouillée par {task_info['locked_by']}")
                        return False
                    
                    await conn.execute("""
                        UPDATE tasks
                        SET is_locked = TRUE,
                            locked_at = NOW(),
                            locked_by = $1
                        WHERE tasks_id = $2
                    """, locked_by, task_id)
                    
                    logger.info(f"🔒 Verrou acquis sur tâche {task_id} par {locked_by}")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Erreur acquisition verrou tâche {task_id}: {e}", exc_info=True)
            return False
    
    @staticmethod
    async def release_workflow_lock(task_id: int, locked_by: str):
        """
        Libère le verrou sur une tâche.
        
        Args:
            task_id: ID de la tâche
            locked_by: Identifiant du processus qui détient le verrou
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                async with conn.transaction():
                    task_info = await conn.fetchrow("""
                        SELECT is_locked, locked_by
                        FROM tasks
                        WHERE tasks_id = $1
                        FOR UPDATE
                    """, task_id)
                    
                    if not task_info:
                        logger.error(f"❌ Tâche {task_id} introuvable")
                        return
                    
                    if task_info['is_locked'] and task_info['locked_by'] == locked_by:
                        await conn.execute("""
                            UPDATE tasks
                            SET is_locked = FALSE,
                                locked_at = NULL,
                                locked_by = NULL
                            WHERE tasks_id = $1
                        """, task_id)
                        
                        logger.info(f"🔓 Verrou libéré sur tâche {task_id} par {locked_by}")
                    elif not task_info['is_locked']:
                        logger.debug(f"ℹ️ Tâche {task_id} déjà déverrouillée")
                    else:
                        logger.warning(f"⚠️ Tentative de libération verrou par {locked_by} mais détenu par {task_info['locked_by']}")
                        
        except Exception as e:
            logger.error(f"❌ Erreur libération verrou tâche {task_id}: {e}", exc_info=True)
    
    @staticmethod
    async def _clean_expired_locks():
        """Nettoie les verrous expirés (> LOCK_TIMEOUT_MINUTES)."""
        try:
            timeout_threshold = datetime.utcnow() - timedelta(minutes=WorkflowLockManager.LOCK_TIMEOUT_MINUTES)
            
            async with db_persistence.db_manager.get_connection() as conn:
                result = await conn.execute("""
                    UPDATE tasks
                    SET is_locked = FALSE,
                        locked_at = NULL,
                        locked_by = NULL
                    WHERE is_locked = TRUE
                      AND locked_at < $1
                """, timeout_threshold)
                
                cleaned_count = int(result.split()[-1]) if result else 0
                
                if cleaned_count > 0:
                    logger.warning(f"🧹 {cleaned_count} verrou(x) expiré(s) nettoyé(s)")
                    
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage verrous expirés: {e}", exc_info=True)
    
    @staticmethod
    async def can_reactivate_workflow(task_id: int) -> Tuple[bool, str]:
        """
        Vérifie si une tâche peut être réactivée.
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Tuple (peut_réactiver, raison)
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                task_info = await conn.fetchrow("""
                    SELECT 
                        internal_status,
                        is_locked,
                        locked_by,
                        reactivation_count,
                        cooldown_until
                    FROM tasks
                    WHERE tasks_id = $1
                """, task_id)
                
                if not task_info:
                    return False, "Tâche introuvable"
                
                if task_info['is_locked']:
                    return False, f"Tâche verrouillée par {task_info['locked_by']}"
                
                if task_info['cooldown_until'] and task_info['cooldown_until'] > datetime.utcnow():
                    remaining = (task_info['cooldown_until'] - datetime.utcnow()).total_seconds()
                    return False, f"Tâche en cooldown (reste {int(remaining)}s)"
                
                logger.info(f"✅ Tâche {task_id} peut être réactivée (statut: {task_info['internal_status']})")
                return True, "OK"
                
        except Exception as e:
            logger.error(f"❌ Erreur vérification réactivation tâche {task_id}: {e}", exc_info=True)
            return False, f"Erreur de vérification: {e}"
    
    @staticmethod
    async def mark_task_reactivated(task_id: int):
        """
        Marque une tâche comme réactivée (incrémente le compteur).
        
        Args:
            task_id: ID de la tâche
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE tasks
                    SET reactivation_count = reactivation_count + 1,
                        reactivated_at = NOW(),
                        previous_status = internal_status,
                        internal_status = 'processing'
                    WHERE tasks_id = $1
                """, task_id)
                
                logger.info(f"🔄 Tâche {task_id} marquée comme réactivée")
                
        except Exception as e:
            logger.error(f"❌ Erreur marquage réactivation tâche {task_id}: {e}", exc_info=True)
    
    @staticmethod
    async def get_lock_info(task_id: int) -> Optional[dict]:
        """
        Récupère les informations de verrouillage d'une tâche.
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Dictionnaire avec les informations de verrouillage
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                lock_info = await conn.fetchrow("""
                    SELECT 
                        is_locked,
                        locked_by,
                        locked_at,
                        reactivation_count,
                        cooldown_until
                    FROM tasks
                    WHERE tasks_id = $1
                """, task_id)
                
                if not lock_info:
                    return None
                
                return dict(lock_info)
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération info verrou tâche {task_id}: {e}")
            return None
    
    @staticmethod
    async def force_release_all_locks():
        """
        Force la libération de tous les verrous (à utiliser en cas d'urgence).
        
        Returns:
            Nombre de verrous libérés
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                result = await conn.execute("""
                    UPDATE tasks
                    SET is_locked = FALSE,
                        locked_at = NULL,
                        locked_by = NULL
                    WHERE is_locked = TRUE
                """)
                
                cleaned_count = int(result.split()[-1]) if result else 0
                
                if cleaned_count > 0:
                    logger.warning(f"⚠️ FORCE RELEASE : {cleaned_count} verrou(x) libéré(s)")
                
                return cleaned_count
                
        except Exception as e:
            logger.error(f"❌ Erreur force release locks: {e}", exc_info=True)
            return 0
    
    @staticmethod
    @asynccontextmanager
    async def acquire_update_lock(workflow_id: int, timeout: int = 5):
        """
        Verrou distribué pour éviter les race conditions lors des updates Monday.com.
        
        Utilise une approche simple basée sur la base de données PostgreSQL.
        Pour une solution Redis, voir les commentaires ci-dessous.
        
        Args:
            workflow_id: ID du workflow/tâche à verrouiller
            timeout: Timeout en secondes pour le verrou
            
        Yields:
            True si le verrou a été acquis, False sinon
            
        Example:
            async with WorkflowLockManager.acquire_update_lock(workflow_id, timeout=5) as lock_acquired:
                if lock_acquired:
                    # Traiter l'update
                    pass
        """
        lock_key = f"update_lock_{workflow_id}"
        lock_acquired = False
        lock_id = f"{lock_key}_{datetime.utcnow().timestamp()}"
        
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                for attempt in range(timeout):
                    result = await conn.fetchval("""
                        WITH lock_check AS (
                            SELECT 
                                is_locked,
                                locked_at,
                                locked_by
                            FROM tasks
                            WHERE tasks_id = $1
                        ),
                        lock_update AS (
                            UPDATE tasks
                            SET is_locked = TRUE,
                                locked_at = NOW(),
                                locked_by = $2
                            WHERE tasks_id = $1
                              AND (
                                  is_locked = FALSE
                                  OR locked_at < NOW() - INTERVAL '10 seconds'
                              )
                            RETURNING tasks_id
                        )
                        SELECT CASE 
                            WHEN EXISTS (SELECT 1 FROM lock_update) THEN TRUE
                            ELSE FALSE
                        END
                    """, workflow_id, lock_id)
                    
                    if result:
                        lock_acquired = True
                        logger.debug(f"🔒 Verrou update acquis pour workflow {workflow_id} (lock_id: {lock_id})")
                        break
                    
                    if attempt < timeout - 1:
                        await asyncio.sleep(1)
                
                if not lock_acquired:
                    logger.warning(f"⚠️ Impossible d'acquérir le verrou update pour workflow {workflow_id} après {timeout}s")
            
            yield lock_acquired
            
        finally:
            if lock_acquired:
                try:
                    async with db_persistence.db_manager.get_connection() as conn:
                        await conn.execute("""
                            UPDATE tasks
                            SET is_locked = FALSE,
                                locked_at = NULL,
                                locked_by = NULL
                            WHERE tasks_id = $1
                              AND locked_by = $2
                        """, workflow_id, lock_id)
                        
                        logger.debug(f"🔓 Verrou update libéré pour workflow {workflow_id}")
                except Exception as e:
                    logger.error(f"❌ Erreur lors de la libération du verrou update: {e}", exc_info=True)

workflow_lock_manager = WorkflowLockManager()