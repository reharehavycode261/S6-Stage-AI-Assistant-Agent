"""
Gestionnaire de queue de workflows pour éviter les conflits de traitement concurrent.

Ce service gère une queue par Monday item pour s'assurer qu'un seul workflow
est en cours d'exécution à la fois pour un même item, tout en permettant
à d'autres items d'être traités en parallèle.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from utils.logger import get_logger
from services.database_persistence_service import db_persistence

logger = get_logger(__name__)


class WorkflowQueueStatus(str, Enum):
    """Statuts possibles d'un workflow dans la queue."""
    PENDING = "pending"  
    RUNNING = "running"  
    WAITING_VALIDATION = "waiting_validation"  
    COMPLETED = "completed"  
    FAILED = "failed"  
    CANCELLED = "cancelled"  
    TIMEOUT = "timeout"  


@dataclass
class QueuedWorkflow:
    """Représente un workflow dans la queue."""
    queue_id: str
    monday_item_id: int
    task_id: Optional[int]  
    payload: Dict[str, Any]
    status: WorkflowQueueStatus = WorkflowQueueStatus.PENDING
    priority: int = 5  
    queued_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    celery_task_id: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class WorkflowQueueManager:
    """
    Gestionnaire de queue de workflows par Monday item.
    
    Fonctionnalités :
    - Queue FIFO par Monday item (premier arrivé, premier servi)
    - Détection des workflows en cours
    - Gestion de l'état "en attente de validation humaine"
    - Libération automatique de la queue après completion
    - Persistence en base de données pour reprise après crash
    """
    
    def __init__(self):
        self._queues: Dict[int, List[QueuedWorkflow]] = {}
        
        self._locks: Dict[int, asyncio.Lock] = {}
        
        self._workflow_timeout = timedelta(minutes=30)
        
        self._validation_timeout = timedelta(minutes=15)
        
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def _get_lock(self, monday_item_id: int) -> asyncio.Lock:
        if monday_item_id not in self._locks:
            self._locks[monday_item_id] = asyncio.Lock()
        return self._locks[monday_item_id]
    
    async def enqueue_workflow(
        self,
        monday_item_id: int,
        payload: Dict[str, Any],
        task_db_id: Optional[int] = None,
        priority: int = 5
    ) -> str:
        """
        Ajoute un workflow à la queue pour un Monday item.
        
        Args:
            monday_item_id: ID de l'item Monday.com
            payload: Payload du webhook
            task_db_id: ID de la tâche en base (si déjà créée)
            priority: Priorité (1-10, plus haut = plus prioritaire)
            
        Returns:
            ID de queue unique du workflow
        """
        lock = self._get_lock(monday_item_id)
        
        async with lock:
            queue_id = f"queue_{uuid.uuid4().hex[:12]}"
            queued_workflow = QueuedWorkflow(
                queue_id=queue_id,
                monday_item_id=monday_item_id,
                task_id=task_db_id,  
                payload=payload,
                priority=priority
            )
            
            if monday_item_id not in self._queues:
                self._queues[monday_item_id] = []
            
                
            self._queues[monday_item_id].append(queued_workflow)
            
            self._queues[monday_item_id].sort(key=lambda w: w.priority, reverse=True)
            
            await self._persist_queue_entry(queued_workflow)
            
            queue_position = self._get_queue_position(monday_item_id, queue_id)
            
            logger.info(
                f"📋 Workflow ajouté à la queue pour item {monday_item_id}",
                queue_id=queue_id,
                position=queue_position,
                queue_size=len(self._queues[monday_item_id]),
                priority=priority
            )
            
            return queue_id
    
    async def should_execute_now(self, monday_item_id: int, queue_id: str) -> bool:
        """
        Vérifie si un workflow doit être exécuté immédiatement.
        
        Returns:
            True si le workflow est en tête de queue et aucun workflow n'est en cours
        """
        lock = self._get_lock(monday_item_id)
        
        async with lock:
            if monday_item_id not in self._queues:
                return False
            
            queue = self._queues[monday_item_id]
            
            if not queue:
                return False
            
            first_workflow = queue[0]
            if first_workflow.queue_id != queue_id:
                logger.info(
                    f"⏳ Workflow {queue_id} en attente (position {self._get_queue_position(monday_item_id, queue_id)})"
                )
                return False
            
            running_workflow = self._get_running_workflow(monday_item_id)
            if running_workflow:
                logger.info(
                    f"⏳ Workflow {queue_id} en attente - workflow {running_workflow.queue_id} en cours ({running_workflow.status})"
                )
                return False
            
            return True
    
    async def mark_as_running(self, monday_item_id: int, queue_id: str, celery_task_id: str):
        """Marque un workflow comme en cours d'exécution."""
        lock = self._get_lock(monday_item_id)
        
        async with lock:
            workflow = self._find_workflow(monday_item_id, queue_id)
            if workflow:
                workflow.status = WorkflowQueueStatus.RUNNING
                workflow.started_at = datetime.now()
                workflow.celery_task_id = celery_task_id
                
                await self._update_queue_entry(workflow)
                
                logger.info(
                    f"🚀 Workflow {queue_id} en cours d'exécution",
                    monday_item_id=monday_item_id,
                    celery_task_id=celery_task_id
                )
    
    async def mark_as_waiting_validation(self, monday_item_id: int, queue_id: str):
        """
        Marque un workflow comme en attente de validation humaine.
        
        ✅ IMPORTANT: Le workflow en attente NE bloque PAS la queue !
        Le prochain workflow peut démarrer pendant que celui-ci attend la validation.
        """
        lock = self._get_lock(monday_item_id)
        
        async with lock:
            workflow = self._find_workflow(monday_item_id, queue_id)
            if workflow:
                workflow.status = WorkflowQueueStatus.WAITING_VALIDATION
                
                await self._update_queue_entry(workflow)
                
                logger.info(
                    f"⏸️ Workflow {queue_id} en attente de validation humaine",
                    monday_item_id=monday_item_id,
                    timeout_minutes=self._validation_timeout.total_seconds() / 60
                )
                
                logger.info(f"🚀 Libération de la queue pour lancer le prochain workflow...")
                await self._trigger_next_workflow(monday_item_id)
    
    async def mark_as_completed(self, monday_item_id: int, queue_id: str):
        """Marque un workflow comme terminé et lance le suivant dans la queue."""
        lock = self._get_lock(monday_item_id)
        
        async with lock:
            workflow = self._find_workflow(monday_item_id, queue_id)
            if workflow:
                workflow.status = WorkflowQueueStatus.COMPLETED
                workflow.completed_at = datetime.now()
                
                await self._update_queue_entry(workflow)
                
                if monday_item_id in self._queues:
                    self._queues[monday_item_id] = [
                        w for w in self._queues[monday_item_id] 
                        if w.queue_id != queue_id
                    ]
                
                duration = (workflow.completed_at - workflow.started_at).total_seconds() if workflow.started_at else 0
                
                logger.info(
                    f"✅ Workflow {queue_id} terminé (durée: {duration:.1f}s)",
                    monday_item_id=monday_item_id,
                    remaining_in_queue=len(self._queues.get(monday_item_id, []))
                )
                
                await self._trigger_next_workflow(monday_item_id)
    
    async def mark_as_failed(self, monday_item_id: int, queue_id: str, error: str):
        """Marque un workflow comme échoué et lance le suivant."""
        lock = self._get_lock(monday_item_id)
        
        async with lock:
            workflow = self._find_workflow(monday_item_id, queue_id)
            if workflow:
                workflow.status = WorkflowQueueStatus.FAILED
                workflow.completed_at = datetime.now()
                workflow.error = error
                
                await self._update_queue_entry(workflow)
                
                if monday_item_id in self._queues:
                    self._queues[monday_item_id] = [
                        w for w in self._queues[monday_item_id] 
                        if w.queue_id != queue_id
                    ]
                
                logger.error(
                    f"❌ Workflow {queue_id} échoué: {error}",
                    monday_item_id=monday_item_id,
                    remaining_in_queue=len(self._queues.get(monday_item_id, []))
                )
                
                await self._trigger_next_workflow(monday_item_id)
    
    async def _trigger_next_workflow(self, monday_item_id: int):
        """Déclenche le prochain workflow en attente dans la queue."""
        if monday_item_id not in self._queues or not self._queues[monday_item_id]:
            logger.debug(f"📭 Queue vide pour item {monday_item_id}")
            return
        
        next_workflow = self._queues[monday_item_id][0]
        
        logger.info(
            f"➡️ Déclenchement du prochain workflow dans la queue",
            monday_item_id=monday_item_id,
            queue_id=next_workflow.queue_id,
            queued_since=(datetime.now() - next_workflow.queued_at).total_seconds()
        )
        
        from services.celery_app import submit_task
        
        try:
            task = submit_task(
                "ai_agent_background.process_monday_webhook",
                next_workflow.payload,
                priority=next_workflow.priority
            )
            
            next_workflow.celery_task_id = task.id
            next_workflow.status = WorkflowQueueStatus.RUNNING
            next_workflow.started_at = datetime.now()
            
            await self._update_queue_entry(next_workflow)
            
        except Exception as e:
            logger.error(f"❌ Erreur déclenchement workflow suivant: {e}")
            next_workflow.status = WorkflowQueueStatus.FAILED
            next_workflow.error = str(e)
            await self._update_queue_entry(next_workflow)
    
    def _find_workflow(self, monday_item_id: int, queue_id: str) -> Optional[QueuedWorkflow]:
        """Trouve un workflow dans la queue."""
        if monday_item_id not in self._queues:
            return None
        
        for workflow in self._queues[monday_item_id]:
            if workflow.queue_id == queue_id:
                return workflow
        
        return None
    
    def _get_running_workflow(self, monday_item_id: int) -> Optional[QueuedWorkflow]:
        """
        Retourne le workflow en cours pour un Monday item.
        
        ⚠️ IMPORTANT: Un workflow en WAITING_VALIDATION ne bloque PAS la queue !
        Cela permet à d'autres workflows de s'exécuter pendant que l'utilisateur répond.
        """
        if monday_item_id not in self._queues:
            return None
        
        for workflow in self._queues[monday_item_id]:
            if workflow.status == WorkflowQueueStatus.RUNNING:
                return workflow
        
        return None
    
    def _get_queue_position(self, monday_item_id: int, queue_id: str) -> int:
        """Retourne la position d'un workflow dans la queue (1-based)."""
        if monday_item_id not in self._queues:
            return -1
        
        for i, workflow in enumerate(self._queues[monday_item_id]):
            if workflow.queue_id == queue_id:
                return i + 1
        
        return -1
    
    async def get_queue_status(self, monday_item_id: int) -> Dict[str, Any]:
        """Retourne le statut de la queue pour un Monday item."""
        lock = self._get_lock(monday_item_id)
        
        async with lock:
            if monday_item_id not in self._queues:
                return {
                    "monday_item_id": monday_item_id,
                    "queue_size": 0,
                    "running_workflow": None,
                    "pending_workflows": []
                }
            
            queue = self._queues[monday_item_id]
            running = self._get_running_workflow(monday_item_id)
            
            return {
                "monday_item_id": monday_item_id,
                "queue_size": len(queue),
                "running_workflow": {
                    "queue_id": running.queue_id,
                    "status": running.status,
                    "started_at": running.started_at.isoformat() if running.started_at else None,
                    "duration_seconds": (datetime.now() - running.started_at).total_seconds() if running.started_at else 0
                } if running else None,
                "pending_workflows": [
                    {
                        "queue_id": w.queue_id,
                        "status": w.status,
                        "priority": w.priority,
                        "queued_at": w.queued_at.isoformat(),
                        "waiting_seconds": (datetime.now() - w.queued_at).total_seconds()
                    }
                    for w in queue if w.status == WorkflowQueueStatus.PENDING
                ]
            }
    
    async def _persist_queue_entry(self, workflow: QueuedWorkflow):
        """Persiste une entrée de queue en base de données."""
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO workflow_queue (
                        queue_id, monday_item_id, task_id, status, priority,
                        queued_at, started_at, completed_at, celery_task_id,
                        error, retry_count, payload
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (queue_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        started_at = EXCLUDED.started_at,
                        completed_at = EXCLUDED.completed_at,
                        celery_task_id = EXCLUDED.celery_task_id,
                        error = EXCLUDED.error,
                        retry_count = EXCLUDED.retry_count
                """,
                    workflow.queue_id,
                    workflow.monday_item_id,
                    workflow.task_id,  
                    workflow.status.value,
                    workflow.priority,
                    workflow.queued_at,
                    workflow.started_at,
                    workflow.completed_at,
                    workflow.celery_task_id,
                    workflow.error,
                    workflow.retry_count,
                    workflow.payload
                )
        except Exception as e:
            logger.error(f"❌ Erreur persistence queue entry: {e}")
    
    async def _update_queue_entry(self, workflow: QueuedWorkflow):
        """Met à jour une entrée de queue en base."""
        await self._persist_queue_entry(workflow)
    
    async def restore_queues_from_db(self):
        """Restaure les queues depuis la base de données après un crash."""
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT queue_id, monday_item_id, task_id, status, priority,
                           queued_at, started_at, completed_at, celery_task_id,
                           error, retry_count, payload
                    FROM workflow_queue
                    WHERE status IN ('pending', 'running', 'waiting_validation')
                    AND queued_at > NOW() - INTERVAL '24 hours'
                    ORDER BY monday_item_id, priority DESC, queued_at ASC
                """)
                
                restored_count = 0
                for row in rows:
                    workflow = QueuedWorkflow(
                        queue_id=row['queue_id'],
                        monday_item_id=row['monday_item_id'],
                        task_id=row['task_id'],  
                        payload=row['payload'],
                        status=WorkflowQueueStatus(row['status']),
                        priority=row['priority'],
                        queued_at=row['queued_at'],
                        started_at=row['started_at'],
                        completed_at=row['completed_at'],
                        celery_task_id=row['celery_task_id'],
                        error=row['error'],
                        retry_count=row['retry_count']
                    )
                    
                    monday_item_id = workflow.monday_item_id
                    if monday_item_id not in self._queues:
                        self._queues[monday_item_id] = []
                    
                    self._queues[monday_item_id].append(workflow)
                    restored_count += 1
                
                if restored_count > 0:
                    logger.info(f"✅ {restored_count} workflows restaurés depuis la DB")
        
        except Exception as e:
            logger.error(f"❌ Erreur restauration queues: {e}")
    
    async def start_cleanup_task(self):
        """Démarre la tâche de nettoyage périodique."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("🧹 Tâche de nettoyage des queues démarrée")
    
    async def _cleanup_loop(self):
        """Boucle de nettoyage périodique (toutes les 5 minutes)."""
        while True:
            try:
                await asyncio.sleep(300)  
                await self._cleanup_expired_workflows()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erreur dans cleanup loop: {e}")
    
    async def _cleanup_expired_workflows(self):
        """Nettoie les workflows expirés (timeout)."""
        now = datetime.now()
        expired_count = 0
        
        for monday_item_id, queue in list(self._queues.items()):
            lock = self._get_lock(monday_item_id)
            
            async with lock:
                for workflow in list(queue):
                    if workflow.status == WorkflowQueueStatus.RUNNING and workflow.started_at:
                        duration = now - workflow.started_at
                        if duration > self._workflow_timeout:
                            logger.warning(
                                f"⏰ Workflow {workflow.queue_id} en timeout après {duration.total_seconds():.0f}s"
                            )
                            workflow.status = WorkflowQueueStatus.TIMEOUT
                            workflow.completed_at = now
                            workflow.error = f"Timeout après {duration.total_seconds():.0f}s"
                            
                            await self._update_queue_entry(workflow)
                            
                            queue.remove(workflow)
                            expired_count += 1
                            
                            await self._trigger_next_workflow(monday_item_id)
                    
                    elif workflow.status == WorkflowQueueStatus.WAITING_VALIDATION and workflow.started_at:
                        duration = now - workflow.started_at
                        if duration > self._validation_timeout:
                            logger.warning(
                                f"⏰ Validation humaine en timeout pour workflow {workflow.queue_id}"
                            )
                            workflow.status = WorkflowQueueStatus.TIMEOUT
                            workflow.completed_at = now
                            workflow.error = "Timeout validation humaine"
                            
                            await self._update_queue_entry(workflow)
                            
                            queue.remove(workflow)
                            expired_count += 1
                            
                            await self._trigger_next_workflow(monday_item_id)
        
        if expired_count > 0:
            logger.info(f"🧹 {expired_count} workflows expirés nettoyés")

workflow_queue_manager = WorkflowQueueManager()

