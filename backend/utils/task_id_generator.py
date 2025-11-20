# -*- coding: utf-8 -*-
"""
Générateur d'IDs uniques pour les tâches Celery.
Corrige la Faille #2 : Duplication des Tâches Celery.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class TaskIdGenerator:
    """Générateur d'IDs uniques et traçables pour les tâches Celery."""
    
    @staticmethod
    def generate_unique_task_id(
        task_run_id: int,
        task_type: str = 'workflow',
        prefix: str = 'task'
    ) -> str:
        """
        Génère un task_id unique basé sur le run et le timestamp.
        
        Args:
            task_run_id: ID du run de tâche en base
            task_type: Type de tâche (workflow, reactivated, retry, etc.)
            prefix: Préfixe pour l'ID (par défaut 'task')
            
        Returns:
            Task ID unique au format: {prefix}_{task_run_id}_{type}_{hash}
            
        Exemple:
            task_12345_workflow_a3f8d9e2
        """
        try:
            # Timestamp haute précision
            timestamp = datetime.utcnow().isoformat()
            
            # Composants de l'ID
            raw_id = f"{task_run_id}_{task_type}_{timestamp}_{uuid.uuid4().hex[:8]}"
            
            # Créer un hash court pour raccourcir l'ID
            hash_obj = hashlib.md5(raw_id.encode())
            short_hash = hash_obj.hexdigest()[:8]
            
            # Format final
            task_id = f"{prefix}_{task_run_id}_{task_type}_{short_hash}"
            
            logger.debug(f"📝 Task ID généré: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Erreur génération task_id: {e}")
            # Fallback: utiliser UUID
            fallback_id = f"{prefix}_{task_run_id}_{uuid.uuid4().hex[:12]}"
            logger.warning(f"⚠️ Utilisation fallback task_id: {fallback_id}")
            return fallback_id
    
    @staticmethod
    def generate_reactivation_task_id(
        task_run_id: int,
        reactivation_count: int
    ) -> str:
        """
        Génère un task_id spécifique pour une réactivation.
        
        Args:
            task_run_id: ID du run de tâche
            reactivation_count: Numéro de réactivation
            
        Returns:
            Task ID pour la réactivation
            
        Exemple:
            task_12345_reactivation_3_b7e4c1f9
        """
        try:
            timestamp = datetime.utcnow().isoformat()
            raw_id = f"{task_run_id}_reactivation_{reactivation_count}_{timestamp}"
            
            hash_obj = hashlib.md5(raw_id.encode())
            short_hash = hash_obj.hexdigest()[:8]
            
            task_id = f"task_{task_run_id}_reactivation_{reactivation_count}_{short_hash}"
            
            logger.info(f"🔄 Task ID réactivation généré: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Erreur génération task_id réactivation: {e}")
            fallback_id = f"task_{task_run_id}_reactivation_{uuid.uuid4().hex[:12]}"
            return fallback_id
    
    @staticmethod
    def generate_retry_task_id(
        task_run_id: int,
        retry_count: int,
        node_name: Optional[str] = None
    ) -> str:
        """
        Génère un task_id pour une tentative de retry.
        
        Args:
            task_run_id: ID du run de tâche
            retry_count: Numéro de tentative
            node_name: Nom du nœud en retry (optionnel)
            
        Returns:
            Task ID pour le retry
            
        Exemple:
            task_12345_retry_2_prepare_env_d9a3f8e1
        """
        try:
            timestamp = datetime.utcnow().isoformat()
            node_suffix = f"_{node_name}" if node_name else ""
            raw_id = f"{task_run_id}_retry_{retry_count}{node_suffix}_{timestamp}"
            
            hash_obj = hashlib.md5(raw_id.encode())
            short_hash = hash_obj.hexdigest()[:8]
            
            task_id = f"task_{task_run_id}_retry_{retry_count}{node_suffix}_{short_hash}"
            
            logger.debug(f"🔁 Task ID retry généré: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Erreur génération task_id retry: {e}")
            fallback_id = f"task_{task_run_id}_retry_{uuid.uuid4().hex[:12]}"
            return fallback_id
    
    @staticmethod
    def generate_webhook_task_id(
        monday_item_id: int,
        webhook_id: Optional[int] = None
    ) -> str:
        """
        Génère un task_id pour un déclenchement webhook.
        
        Args:
            monday_item_id: ID de l'item Monday.com
            webhook_id: ID du webhook en base (optionnel)
            
        Returns:
            Task ID pour le webhook
            
        Exemple:
            webhook_7891234_task_c4e8f2a1
        """
        try:
            timestamp = datetime.utcnow().isoformat()
            webhook_suffix = f"_{webhook_id}" if webhook_id else ""
            raw_id = f"webhook_{monday_item_id}{webhook_suffix}_{timestamp}"
            
            hash_obj = hashlib.md5(raw_id.encode())
            short_hash = hash_obj.hexdigest()[:8]
            
            task_id = f"webhook_{monday_item_id}_task_{short_hash}"
            
            logger.debug(f"🔗 Task ID webhook généré: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Erreur génération task_id webhook: {e}")
            fallback_id = f"webhook_{monday_item_id}_{uuid.uuid4().hex[:12]}"
            return fallback_id
    
    @staticmethod
    def parse_task_id(task_id: str) -> dict:
        """
        Parse un task_id pour extraire ses composants.
        
        Args:
            task_id: Task ID à parser
            
        Returns:
            Dictionnaire avec les composants (prefix, task_run_id, type, hash)
            
        Exemple:
            Input: "task_12345_workflow_a3f8d9e2"
            Output: {
                "prefix": "task",
                "task_run_id": 12345,
                "type": "workflow",
                "hash": "a3f8d9e2"
            }
        """
        try:
            parts = task_id.split('_')
            
            if len(parts) >= 4:
                return {
                    'prefix': parts[0],
                    'task_run_id': int(parts[1]) if parts[1].isdigit() else None,
                    'type': parts[2],
                    'hash': parts[3] if len(parts) > 3 else None,
                    'full_id': task_id
                }
            else:
                return {
                    'prefix': parts[0] if parts else None,
                    'full_id': task_id,
                    'parse_error': 'Format non standard'
                }
                
        except Exception as e:
            logger.warning(f"⚠️ Erreur parsing task_id {task_id}: {e}")
            return {
                'full_id': task_id,
                'parse_error': str(e)
            }
    
    @staticmethod
    def is_reactivation_task(task_id: str) -> bool:
        """
        Vérifie si un task_id correspond à une réactivation.
        
        Args:
            task_id: Task ID à vérifier
            
        Returns:
            True si c'est une réactivation
        """
        return 'reactivation' in task_id.lower()
    
    @staticmethod
    def is_retry_task(task_id: str) -> bool:
        """
        Vérifie si un task_id correspond à un retry.
        
        Args:
            task_id: Task ID à vérifier
            
        Returns:
            True si c'est un retry
        """
        return 'retry' in task_id.lower()
    
    @staticmethod
    def is_webhook_task(task_id: str) -> bool:
        """
        Vérifie si un task_id correspond à un webhook.
        
        Args:
            task_id: Task ID à vérifier
            
        Returns:
            True si c'est un webhook
        """
        return task_id.startswith('webhook_')


# Instance globale
task_id_generator = TaskIdGenerator()

