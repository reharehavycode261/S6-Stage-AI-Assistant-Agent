"""
Service de gestion des tâches Celery pour éviter les doublons.
Corrige la Faille #2 : Duplication des Tâches Celery.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from celery.result import AsyncResult

from utils.logger import get_logger
from services.database_persistence_service import db_persistence

logger = get_logger(__name__)

_celery_app = None

def get_celery_app():
    """Récupère l'instance Celery de manière paresseuse."""
    global _celery_app
    if _celery_app is None:
        from services.celery_app import celery_app
        _celery_app = celery_app
    return _celery_app


class CeleryTaskManager:
    """Gestionnaire des tâches Celery pour éviter les doublons et gérer le cycle de vie."""
    
    @staticmethod
    async def revoke_workflow_tasks(task_run_id: int, terminate: bool = True) -> List[str]:
        """
        Annule toutes les tâches Celery actives pour un workflow run.
        
        Args:
            task_run_id: ID du run de tâche
            terminate: Si True, termine les tâches en cours d'exécution (SIGKILL)
            
        Returns:
            Liste des task_ids révoqués
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                run_info = await conn.fetchrow("""
                    SELECT active_task_ids, celery_task_id, task_id
                    FROM task_runs
                    WHERE tasks_runs_id = $1
                """, task_run_id)
                
                if not run_info:
                    logger.warning(f"⚠️ Run {task_run_id} introuvable")
                    return []
                
                active_task_ids = run_info['active_task_ids'] or []
                
                if not active_task_ids and run_info['celery_task_id']:
                    active_task_ids = [run_info['celery_task_id']]
                
                if not active_task_ids:
                    logger.info(f"ℹ️ Aucune tâche active pour run {task_run_id}")
                    return []
                
                logger.info(f"🔄 Révocation de {len(active_task_ids)} tâche(s) pour run {task_run_id}")
                
                revoked_tasks = []
                
                for task_id in active_task_ids:
                    try:
                        get_celery_app().control.revoke(
                            task_id,
                            terminate=terminate,
                            signal='SIGKILL' if terminate else 'SIGTERM'
                        )
                        revoked_tasks.append(task_id)
                        logger.info(f"✅ Tâche révoquée: {task_id}")
                        
                    except Exception as e:
                        logger.error(f"❌ Erreur révocation tâche {task_id}: {e}")
                
                await conn.execute("""
                    UPDATE task_runs
                    SET active_task_ids = '[]'::jsonb,
                        last_task_id = NULL
                    WHERE tasks_runs_id = $1
                """, task_run_id)
                
                logger.info(f"✅ {len(revoked_tasks)} tâche(s) révoquée(s) pour run {task_run_id}")
                return revoked_tasks
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la révocation des tâches: {e}", exc_info=True)
            return []
    
    @staticmethod
    async def register_task(task_run_id: int, celery_task_id: str):
        """
        Enregistre une nouvelle tâche Celery pour un workflow run.
        
        Args:
            task_run_id: ID du run de tâche
            celery_task_id: ID de la tâche Celery
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                current_tasks = await conn.fetchval("""
                    SELECT active_task_ids
                    FROM task_runs
                    WHERE tasks_runs_id = $1
                """, task_run_id) or []
                
                if celery_task_id not in current_tasks:
                    current_tasks.append(celery_task_id)
                    
                    await conn.execute("""
                        UPDATE task_runs
                        SET active_task_ids = $1::jsonb,
                            last_task_id = $2,
                            task_started_at = NOW()
                        WHERE tasks_runs_id = $3
                    """, json.dumps(current_tasks), celery_task_id, task_run_id)
                    
                    logger.info(f"📝 Tâche Celery enregistrée: {celery_task_id} pour run {task_run_id}")
                else:
                    logger.debug(f"ℹ️ Tâche {celery_task_id} déjà enregistrée pour run {task_run_id}")
                    
        except Exception as e:
            logger.error(f"❌ Erreur enregistrement tâche {celery_task_id}: {e}", exc_info=True)
    
    @staticmethod
    async def unregister_task(task_run_id: int, celery_task_id: str):
        """
        Retire une tâche de la liste des tâches actives.
        
        Args:
            task_run_id: ID du run de tâche
            celery_task_id: ID de la tâche à retirer
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                current_tasks = await conn.fetchval("""
                    SELECT active_task_ids
                    FROM task_runs
                    WHERE tasks_runs_id = $1
                """, task_run_id) or []
                
                if celery_task_id in current_tasks:
                    current_tasks.remove(celery_task_id)
                    await conn.execute("""
                        UPDATE task_runs
                        SET active_task_ids = $1::jsonb
                        WHERE tasks_runs_id = $2
                    """, json.dumps(current_tasks), task_run_id)
                    
                    logger.info(f"✅ Tâche Celery désenregistrée: {celery_task_id} pour run {task_run_id}")
                    
        except Exception as e:
            logger.error(f"❌ Erreur désenregistrement tâche {celery_task_id}: {e}", exc_info=True)
    
    @staticmethod
    def get_task_status(celery_task_id: str) -> Dict[str, Any]:
        """
        Récupère le statut d'une tâche Celery.
        
        Args:
            celery_task_id: ID de la tâche
            
        Returns:
            Dictionnaire avec les informations de la tâche
        """
        try:
            result = AsyncResult(celery_task_id, app=get_celery_app())
            
            return {
                'task_id': celery_task_id,
                'status': result.status,
                'ready': result.ready(),
                'successful': result.successful() if result.ready() else None,
                'failed': result.failed() if result.ready() else None,
                'result': result.result if result.ready() else None
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération statut tâche {celery_task_id}: {e}")
            return {
                'task_id': celery_task_id,
                'status': 'UNKNOWN',
                'error': str(e)
            }
    
    @staticmethod
    async def cleanup_finished_tasks(task_run_id: int) -> int:
        """
        Nettoie les tâches terminées de la liste active.
        
        Args:
            task_run_id: ID du run de tâche
            
        Returns:
            Nombre de tâches nettoyées
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                active_tasks = await conn.fetchval("""
                    SELECT active_task_ids
                    FROM task_runs
                    WHERE tasks_runs_id = $1
                """, task_run_id) or []
                
                if not active_tasks:
                    return 0
                
                still_active = []
                cleaned = 0
                
                for task_id in active_tasks:
                    status = CeleryTaskManager.get_task_status(task_id)
                    
                    if status['status'] in ['PENDING', 'STARTED', 'RETRY']:
                        still_active.append(task_id)
                    else:
                        cleaned += 1
                        logger.debug(f"🧹 Tâche terminée nettoyée: {task_id} (status: {status['status']})")
                
                await conn.execute("""
                    UPDATE task_runs
                    SET active_task_ids = $1::jsonb
                    WHERE tasks_runs_id = $2
                """, json.dumps(still_active), task_run_id)
                
                if cleaned > 0:
                    logger.info(f"🧹 {cleaned} tâche(s) terminée(s) nettoyée(s) pour run {task_run_id}")
                
                return cleaned
                
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage tâches pour run {task_run_id}: {e}", exc_info=True)
            return 0
    
    @staticmethod
    async def get_active_tasks_count(task_run_id: int) -> int:
        """
        Compte le nombre de tâches actives pour un run.
        
        Args:
            task_run_id: ID du run de tâche
            
        Returns:
            Nombre de tâches actives
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                active_tasks = await conn.fetchval("""
                    SELECT active_task_ids
                    FROM task_runs
                    WHERE tasks_runs_id = $1
                """, task_run_id) or []
                
                return len(active_tasks)
                
        except Exception as e:
            logger.error(f"❌ Erreur comptage tâches actives: {e}")
            return 0
    
    @staticmethod
    async def has_active_tasks(task_run_id: int) -> bool:
        """
        Vérifie si un run a des tâches actives.
        
        Args:
            task_run_id: ID du run de tâche
            
        Returns:
            True si des tâches sont actives
        """
        count = await CeleryTaskManager.get_active_tasks_count(task_run_id)
        return count > 0


celery_task_manager = CeleryTaskManager()

