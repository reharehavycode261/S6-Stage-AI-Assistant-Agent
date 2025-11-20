"""
Service de debouncing pour les updates Monday.com.
Corrige la Faille #3 : Cascade de Réactivations.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Callable, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PendingUpdate:
    """Représente un update en attente de traitement."""
    data: Dict[str, Any]
    timestamp: datetime
    monday_item_id: int
    update_text: str


@dataclass
class DebouncerState:
    """État du debouncer pour une tâche."""
    pending_updates: List[PendingUpdate] = field(default_factory=list)
    timer_task: Optional[asyncio.Task] = None
    is_processing: bool = False


class UpdateDebouncer:
    """
    Gère le debouncing des updates pour éviter les réactivations multiples.
    Groupe les updates qui arrivent dans un court laps de temps.
    """
    
    def __init__(self, delay_seconds: int = 10):
        """
        Args:
            delay_seconds: Délai en secondes pour grouper les updates
        """
        self.delay_seconds = delay_seconds
        self._states: Dict[int, DebouncerState] = defaultdict(DebouncerState)
        self._lock = asyncio.Lock()
    
    async def add_update(
        self, 
        task_id: int,
        monday_item_id: int,
        update_data: Dict[str, Any],
        update_text: str,
        callback: Callable
    ):
        """
        Ajoute un update avec debouncing.
        
        Args:
            task_id: ID de la tâche en base
            monday_item_id: ID de l'item Monday.com
            update_data: Données complètes de l'update
            update_text: Texte de l'update
            callback: Fonction asynchrone à appeler après le délai
        """
        async with self._lock:
            state = self._states[task_id]
            
            update = PendingUpdate(
                data=update_data,
                timestamp=datetime.utcnow(),
                monday_item_id=monday_item_id,
                update_text=update_text
            )
            state.pending_updates.append(update)
            
            logger.info(f"📥 Update ajouté pour tâche {task_id} (total: {len(state.pending_updates)} en attente)")
            
            if state.timer_task and not state.timer_task.done():
                state.timer_task.cancel()
                logger.debug(f"⏱️ Timer précédent annulé pour tâche {task_id}")
            
            state.timer_task = asyncio.create_task(
                self._delayed_process(task_id, callback)
            )
            
            logger.info(f"⏱️ Timer démarré pour tâche {task_id} ({self.delay_seconds}s)")
    
    async def _delayed_process(self, task_id: int, callback: Callable):
        """
        Attend le délai puis traite les updates groupés.
        
        Args:
            task_id: ID de la tâche
            callback: Fonction de traitement
        """
        try:
            await asyncio.sleep(self.delay_seconds)
            
            async with self._lock:
                state = self._states[task_id]
                
                if not state.pending_updates:
                    logger.debug(f"ℹ️ Aucun update à traiter pour tâche {task_id}")
                    return
                
                if state.is_processing:
                    logger.warning(f"⚠️ Traitement déjà en cours pour tâche {task_id}")
                    return
                
                state.is_processing = True
                updates = state.pending_updates.copy()
                state.pending_updates.clear()
            
            logger.info(f"🔄 Traitement de {len(updates)} update(s) groupé(s) pour tâche {task_id}")
            
            try:
                await callback(task_id, updates)
                
            except Exception as e:
                logger.error(f"❌ Erreur lors du traitement des updates pour tâche {task_id}: {e}", exc_info=True)
            
            finally:
                async with self._lock:
                    state = self._states[task_id]
                    state.is_processing = False
                    
                    if not state.pending_updates:
                        del self._states[task_id]
                        logger.debug(f"🧹 État nettoyé pour tâche {task_id}")
                
        except asyncio.CancelledError:
            logger.debug(f"⏱️ Timer annulé pour tâche {task_id}")
        
        except Exception as e:
            logger.error(f"❌ Erreur dans delayed_process pour tâche {task_id}: {e}", exc_info=True)
    
    def get_pending_count(self, task_id: int) -> int:
        """
        Retourne le nombre d'updates en attente pour une tâche.
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Nombre d'updates en attente
        """
        state = self._states.get(task_id)
        return len(state.pending_updates) if state else 0
    
    def is_processing(self, task_id: int) -> bool:
        """
        Vérifie si une tâche est en cours de traitement.
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            True si en cours de traitement
        """
        state = self._states.get(task_id)
        return state.is_processing if state else False
    
    async def get_debouncer_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques du debouncer.
        
        Returns:
            Dictionnaire avec les statistiques
        """
        async with self._lock:
            total_tasks = len(self._states)
            total_pending = sum(len(state.pending_updates) for state in self._states.values())
            processing = sum(1 for state in self._states.values() if state.is_processing)
            
            tasks_details = []
            for task_id, state in self._states.items():
                tasks_details.append({
                    'task_id': task_id,
                    'pending_count': len(state.pending_updates),
                    'is_processing': state.is_processing,
                    'has_timer': state.timer_task is not None and not state.timer_task.done()
                })
            
            return {
                'total_tasks_tracked': total_tasks,
                'total_pending_updates': total_pending,
                'tasks_processing': processing,
                'delay_seconds': self.delay_seconds,
                'tasks_details': tasks_details
            }
    
    async def cancel_pending(self, task_id: int):
        """
        Annule les updates en attente pour une tâche.
        
        Args:
            task_id: ID de la tâche
        """
        async with self._lock:
            state = self._states.get(task_id)
            
            if not state:
                logger.debug(f"ℹ️ Aucun update en attente pour tâche {task_id}")
                return
            
            if state.timer_task and not state.timer_task.done():
                state.timer_task.cancel()
            
            pending_count = len(state.pending_updates)
            state.pending_updates.clear()
            
            del self._states[task_id]
            
            logger.info(f"🚫 {pending_count} update(s) en attente annulé(s) pour tâche {task_id}")
    
    async def force_process_now(self, task_id: int, callback: Callable):
        """
        Force le traitement immédiat des updates en attente (sans attendre le délai).
        
        Args:
            task_id: ID de la tâche
            callback: Fonction de traitement
        """
        async with self._lock:
            state = self._states.get(task_id)
            
            if not state or not state.pending_updates:
                logger.debug(f"ℹ️ Aucun update à traiter immédiatement pour tâche {task_id}")
                return
            
            if state.timer_task and not state.timer_task.done():
                state.timer_task.cancel()
            
            state.is_processing = True
            updates = state.pending_updates.copy()
            state.pending_updates.clear()
        
        logger.info(f"⚡ Traitement IMMÉDIAT forcé de {len(updates)} update(s) pour tâche {task_id}")
        
        try:
            await callback(task_id, updates)
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement immédiat pour tâche {task_id}: {e}", exc_info=True)
        
        finally:
            async with self._lock:
                state = self._states.get(task_id)
                if state:
                    state.is_processing = False
                    if not state.pending_updates:
                        del self._states[task_id]
    
    async def cleanup(self):
        """Nettoie tous les timers et états en attente."""
        async with self._lock:
            for task_id, state in self._states.items():
                if state.timer_task and not state.timer_task.done():
                    state.timer_task.cancel()
                    logger.debug(f"🧹 Timer annulé pour tâche {task_id}")
            
            cleared_count = len(self._states)
            self._states.clear()
            
            if cleared_count > 0:
                logger.info(f"🧹 Debouncer nettoyé: {cleared_count} tâche(s)")


update_debouncer = UpdateDebouncer(delay_seconds=10)

