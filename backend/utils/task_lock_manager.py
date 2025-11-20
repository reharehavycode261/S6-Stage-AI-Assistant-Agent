"""
Gestionnaire de verrous pour éviter le traitement concurrent des tâches.

Ce module fournit un système de verrouillage basé sur asyncio.Lock pour garantir
qu'une même tâche Monday.com ne soit pas traitée simultanément par plusieurs workers.
"""

import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import time

from utils.logger import get_logger

logger = get_logger(__name__)


class TaskLockManager:
    """
    Gestionnaire de verrous pour éviter le traitement concurrent des tâches.
    
    Utilise des verrous asyncio.Lock pour garantir qu'une tâche ne soit pas
    traitée plusieurs fois simultanément.
    """
    
    def __init__(self):
        # Dictionnaire des verrous par task_id
        self._locks: Dict[int, asyncio.Lock] = {}
        
        # Dictionnaire pour tracker les derniers traitements
        self._last_processing: Dict[int, float] = {}
        
        # Timeout pour considérer qu'un verrou est bloqué (10 minutes)
        self._lock_timeout = 600  # secondes
        
        # Cooldown minimal entre deux traitements de la même tâche (30 secondes)
        self._processing_cooldown = 30  # secondes
    
    def get_lock(self, task_id: int) -> asyncio.Lock:
        """
        Obtient ou crée un verrou pour une tâche.
        
        Args:
            task_id: ID de la tâche
        
        Returns:
            asyncio.Lock: Verrou pour cette tâche
        """
        if task_id not in self._locks:
            self._locks[task_id] = asyncio.Lock()
            logger.debug(f"🔐 Nouveau verrou créé pour tâche {task_id}")
        
        return self._locks[task_id]
    
    async def try_acquire(self, task_id: int, timeout: float = 5.0) -> bool:
        """
        Tente d'acquérir le verrou pour une tâche avec timeout.
        
        Args:
            task_id: ID de la tâche
            timeout: Timeout en secondes (défaut: 5s)
        
        Returns:
            bool: True si le verrou a été acquis, False sinon
        """
        lock = self.get_lock(task_id)
        
        # Vérifier si déjà verrouillé
        if lock.locked():
            logger.warning(
                f"🔒 Tâche {task_id} déjà en cours de traitement",
                task_id=task_id,
                lock_status="locked"
            )
            
            # Attendre avec timeout
            try:
                await asyncio.wait_for(lock.acquire(), timeout=timeout)
                logger.info(f"🔓 Verrou acquis après attente pour tâche {task_id}")
                return True
            except asyncio.TimeoutError:
                logger.warning(
                    f"⏱️ Timeout lors de l'acquisition du verrou pour tâche {task_id}",
                    task_id=task_id,
                    timeout=timeout
                )
                return False
        else:
            # Verrou disponible, l'acquérir immédiatement
            await lock.acquire()
            logger.info(f"🔓 Verrou acquis immédiatement pour tâche {task_id}")
            return True
    
    def release(self, task_id: int) -> None:
        """
        Libère le verrou pour une tâche.
        
        Args:
            task_id: ID de la tâche
        """
        if task_id in self._locks:
            try:
                self._locks[task_id].release()
                
                # Enregistrer le timestamp du dernier traitement
                self._last_processing[task_id] = time.time()
                
                logger.info(
                    f"🔐 Verrou libéré pour tâche {task_id}",
                    task_id=task_id
                )
            except RuntimeError:
                # Le verrou n'était pas acquis
                logger.warning(
                    f"⚠️ Tentative de libération d'un verrou non acquis pour tâche {task_id}",
                    task_id=task_id
                )
    
    def is_locked(self, task_id: int) -> bool:
        """
        Vérifie si une tâche est actuellement verrouillée.
        
        Args:
            task_id: ID de la tâche
        
        Returns:
            bool: True si la tâche est verrouillée
        """
        if task_id not in self._locks:
            return False
        
        return self._locks[task_id].locked()
    
    def check_cooldown(self, task_id: int) -> bool:
        """
        Vérifie si la période de cooldown est respectée.
        
        Args:
            task_id: ID de la tâche
        
        Returns:
            bool: True si le cooldown est OK (assez de temps écoulé), False sinon
        """
        if task_id not in self._last_processing:
            return True
        
        last_processing_time = self._last_processing[task_id]
        time_since_last = time.time() - last_processing_time
        
        if time_since_last < self._processing_cooldown:
            logger.warning(
                f"⏱️ Cooldown actif pour tâche {task_id}: {time_since_last:.1f}s écoulées sur {self._processing_cooldown}s",
                task_id=task_id,
                cooldown_remaining=self._processing_cooldown - time_since_last
            )
            return False
        
        return True
    
    async def acquire_with_cooldown(self, task_id: int, timeout: float = 5.0) -> bool:
        """
        Tente d'acquérir le verrou en vérifiant aussi le cooldown.
        
        Args:
            task_id: ID de la tâche
            timeout: Timeout en secondes
        
        Returns:
            bool: True si le verrou a été acquis et le cooldown respecté
        """
        # Vérifier le cooldown
        if not self.check_cooldown(task_id):
            logger.info(
                f"🚫 Traitement bloqué pour tâche {task_id} - cooldown actif",
                task_id=task_id
            )
            return False
        
        # Tenter d'acquérir le verrou
        return await self.try_acquire(task_id, timeout)
    
    def cleanup_old_locks(self, max_age_seconds: int = 3600) -> int:
        """
        Nettoie les verrous et timestamps obsolètes.
        
        Args:
            max_age_seconds: Âge maximum en secondes (défaut: 1 heure)
        
        Returns:
            int: Nombre de verrous nettoyés
        """
        current_time = time.time()
        cleaned_count = 0
        
        # Nettoyer les timestamps obsolètes
        tasks_to_remove = []
        for task_id, timestamp in list(self._last_processing.items()):
            if current_time - timestamp > max_age_seconds:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self._last_processing[task_id]
            
            # Nettoyer aussi le verrou s'il n'est pas acquis
            if task_id in self._locks and not self._locks[task_id].locked():
                del self._locks[task_id]
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"🧹 Nettoyage effectué: {cleaned_count} verrous obsolètes supprimés")
        
        return cleaned_count
    
    def get_stats(self) -> Dict[str, any]:
        """
        Récupère les statistiques des verrous.
        
        Returns:
            dict: Statistiques avec nombre de verrous, verrous actifs, etc.
        """
        locked_count = sum(1 for lock in self._locks.values() if lock.locked())
        
        return {
            "total_locks": len(self._locks),
            "active_locks": locked_count,
            "tracking_tasks": len(self._last_processing),
            "cooldown_seconds": self._processing_cooldown,
            "lock_timeout_seconds": self._lock_timeout
        }
    
    async def force_release_all(self) -> int:
        """
        Force la libération de tous les verrous (à utiliser en cas d'urgence).
        
        ⚠️ ATTENTION: Cette méthode doit être utilisée avec précaution,
        uniquement lors du shutdown ou en cas de blocage détecté.
        
        Returns:
            int: Nombre de verrous forcés à être libérés
        """
        released_count = 0
        
        for task_id, lock in list(self._locks.items()):
            if lock.locked():
                try:
                    lock.release()
                    released_count += 1
                    logger.warning(
                        f"⚠️ Verrou forcé à être libéré pour tâche {task_id}",
                        task_id=task_id
                    )
                except RuntimeError:
                    pass
        
        logger.warning(f"⚠️ Force release: {released_count} verrous libérés")
        return released_count


# Instance globale du gestionnaire de verrous
task_lock_manager = TaskLockManager()


# Fonction utilitaire pour cleanup périodique
async def periodic_lock_cleanup(interval_seconds: int = 300):
    """
    Effectue un cleanup périodique des verrous obsolètes.
    
    Args:
        interval_seconds: Intervalle entre les nettoyages (défaut: 5 minutes)
    """
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            task_lock_manager.cleanup_old_locks()
        except asyncio.CancelledError:
            logger.info("🛑 Arrêt du cleanup périodique des verrous")
            break
        except Exception as e:
            logger.error(f"❌ Erreur lors du cleanup périodique: {e}")

