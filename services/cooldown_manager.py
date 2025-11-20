"""
Service de gestion des cooldowns pour éviter les cascades de réactivations.
Corrige la Faille #3 : Cascade de Réactivations.
"""

from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timedelta

from utils.logger import get_logger
from services.database_persistence_service import db_persistence

logger = get_logger(__name__)


class CooldownManager:
    """Gestionnaire de cooldowns pour limiter les réactivations rapides successives."""
    
    
    COOLDOWN_DURATIONS = {
        'normal': timedelta(seconds=0),        
        'aggressive': timedelta(seconds=0),    
        'emergency': timedelta(seconds=0)      
    }
    
    MAX_FAILED_ATTEMPTS = 3
    
    @staticmethod
    async def is_in_cooldown(task_id: int) -> Tuple[bool, Optional[datetime]]:
        """
        Vérifie si une tâche est en période de cooldown.
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Tuple (en_cooldown, fin_du_cooldown)
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                cooldown_until = await conn.fetchval("""
                    SELECT cooldown_until
                    FROM tasks
                    WHERE tasks_id = $1
                """, task_id)
                
                if not cooldown_until:
                    return False, None
                
                now = datetime.utcnow()
                
                if cooldown_until > now:
                    remaining = (cooldown_until - now).total_seconds()
                    logger.debug(f"⏱️ Tâche {task_id} en cooldown (reste {int(remaining)}s)")
                    return True, cooldown_until
                
                await CooldownManager.clear_cooldown(task_id)
                return False, None
                
        except Exception as e:
            logger.error(f"❌ Erreur vérification cooldown tâche {task_id}: {e}", exc_info=True)
            return False, None
    
    @staticmethod
    async def set_cooldown(task_id: int, cooldown_type: str = 'normal'):
        """
        Définit un cooldown pour une tâche.
        
        Args:
            task_id: ID de la tâche
            cooldown_type: Type de cooldown ('normal', 'aggressive', 'emergency')
        """
        try:
            duration = CooldownManager.COOLDOWN_DURATIONS.get(
                cooldown_type,
                CooldownManager.COOLDOWN_DURATIONS['normal']
            )
            
            cooldown_until = datetime.utcnow() + duration
            
            async with db_persistence.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE tasks
                    SET last_reactivation_attempt = NOW(),
                        cooldown_until = $1
                    WHERE tasks_id = $2
                """, cooldown_until, task_id)
                
                logger.info(f"⏱️ Cooldown {cooldown_type} défini pour tâche {task_id} jusqu'à {cooldown_until}")
                
        except Exception as e:
            logger.error(f"❌ Erreur définition cooldown tâche {task_id}: {e}", exc_info=True)
    
    @staticmethod
    async def clear_cooldown(task_id: int):
        """
        Efface le cooldown d'une tâche.
        
        Args:
            task_id: ID de la tâche
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE tasks
                    SET cooldown_until = NULL,
                        failed_reactivation_attempts = 0
                    WHERE tasks_id = $1
                """, task_id)
                
                logger.debug(f"✅ Cooldown effacé pour tâche {task_id}")
                
        except Exception as e:
            logger.error(f"❌ Erreur effacement cooldown tâche {task_id}: {e}", exc_info=True)
    
    @staticmethod
    async def increment_failed_attempt(task_id: int):
        """
        Incrémente le compteur d'échecs et ajuste le cooldown en conséquence.
        
        Args:
            task_id: ID de la tâche
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                failed_attempts = await conn.fetchval("""
                    UPDATE tasks
                    SET failed_reactivation_attempts = failed_reactivation_attempts + 1
                    WHERE tasks_id = $1
                    RETURNING failed_reactivation_attempts
                """, task_id)
                
                if not failed_attempts:
                    logger.error(f"❌ Tâche {task_id} introuvable lors de l'incrémentation des échecs")
                    return
                
                logger.warning(f"⚠️ Tentative de réactivation échouée pour tâche {task_id} (tentative #{failed_attempts})")
                
                if failed_attempts >= CooldownManager.MAX_FAILED_ATTEMPTS:
                    cooldown_type = 'emergency'
                    logger.error(f"🚨 Tâche {task_id} : Nombre max d'échecs atteint → Cooldown EMERGENCY")
                elif failed_attempts >= 2:
                    cooldown_type = 'aggressive'
                    logger.warning(f"⚠️ Tâche {task_id} : Échecs multiples → Cooldown AGGRESSIVE")
                else:
                    cooldown_type = 'normal'
                
                await CooldownManager.set_cooldown(task_id, cooldown_type)
                
        except Exception as e:
            logger.error(f"❌ Erreur incrémentation échecs tâche {task_id}: {e}", exc_info=True)
    
    @staticmethod
    async def reset_failed_attempts(task_id: int):
        """
        Réinitialise le compteur d'échecs (après succès).
        
        Args:
            task_id: ID de la tâche
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE tasks
                    SET failed_reactivation_attempts = 0
                    WHERE tasks_id = $1
                """, task_id)
                
                logger.debug(f"✅ Compteur d'échecs réinitialisé pour tâche {task_id}")
                
        except Exception as e:
            logger.error(f"❌ Erreur réinitialisation échecs tâche {task_id}: {e}", exc_info=True)
    
    @staticmethod
    async def get_cooldown_info(task_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations de cooldown d'une tâche.
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Dictionnaire avec les informations sur le cooldown
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                cooldown_data = await conn.fetchrow("""
                    SELECT 
                        last_reactivation_attempt,
                        cooldown_until,
                        failed_reactivation_attempts,
                        reactivation_count
                    FROM tasks
                    WHERE tasks_id = $1
                """, task_id)
                
                if not cooldown_data:
                    return None
                
                in_cooldown, cooldown_until = await CooldownManager.is_in_cooldown(task_id)
                
                remaining = None
                if in_cooldown and cooldown_until:
                    remaining = (cooldown_until - datetime.utcnow()).total_seconds()
                
                return {
                    'task_id': task_id,
                    'in_cooldown': in_cooldown,
                    'cooldown_until': cooldown_until.isoformat() if cooldown_until else None,
                    'remaining_seconds': int(remaining) if remaining else 0,
                    'failed_attempts': cooldown_data['failed_reactivation_attempts'],
                    'last_attempt': cooldown_data['last_reactivation_attempt'].isoformat() if cooldown_data['last_reactivation_attempt'] else None,
                    'total_reactivations': cooldown_data['reactivation_count']
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération info cooldown tâche {task_id}: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def get_tasks_in_cooldown() -> list:
        """
        Récupère toutes les tâches actuellement en cooldown.
        
        Returns:
            Liste des tâches en cooldown avec leurs informations
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                tasks = await conn.fetch("""
                    SELECT 
                        tasks_id,
                        title,
                        cooldown_until,
                        failed_reactivation_attempts,
                        reactivation_count,
                        EXTRACT(EPOCH FROM (cooldown_until - NOW())) AS remaining_seconds
                    FROM tasks
                    WHERE cooldown_until IS NOT NULL
                      AND cooldown_until > NOW()
                    ORDER BY cooldown_until ASC
                """)
                
                return [dict(task) for task in tasks]
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération tâches en cooldown: {e}", exc_info=True)
            return []
    
    @staticmethod
    async def cleanup_expired_cooldowns() -> int:
        """
        Nettoie les cooldowns expirés.
        
        Returns:
            Nombre de cooldowns nettoyés
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                result = await conn.execute("""
                    UPDATE tasks
                    SET cooldown_until = NULL
                    WHERE cooldown_until IS NOT NULL
                      AND cooldown_until <= NOW()
                """)
                
                cleaned_count = int(result.split()[-1]) if result else 0
                
                if cleaned_count > 0:
                    logger.info(f"🧹 {cleaned_count} cooldown(s) expiré(s) nettoyé(s)")
                
                return cleaned_count
                
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage cooldowns expirés: {e}", exc_info=True)
            return 0
    
    @staticmethod
    async def can_attempt_reactivation(task_id: int) -> Tuple[bool, str]:
        """
        Vérifie si une tentative de réactivation peut être effectuée.
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Tuple (peut_tenter, raison)
        """
        try:
            in_cooldown, cooldown_until = await CooldownManager.is_in_cooldown(task_id)
            
            if in_cooldown:
                remaining = (cooldown_until - datetime.utcnow()).total_seconds()
                return False, f"Tâche en cooldown (reste {int(remaining)}s)"
            
            cooldown_info = await CooldownManager.get_cooldown_info(task_id)
            
            if cooldown_info and cooldown_info['failed_attempts'] >= CooldownManager.MAX_FAILED_ATTEMPTS:
                return False, f"Trop de tentatives échouées ({cooldown_info['failed_attempts']})"
            
            return True, "OK"
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification tentative réactivation: {e}", exc_info=True)
            return False, f"Erreur: {e}"

cooldown_manager = CooldownManager()

