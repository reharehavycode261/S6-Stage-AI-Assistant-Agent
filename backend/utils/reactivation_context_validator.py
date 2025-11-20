"""
Utilitaire de validation du contexte de réactivation.
Centralise la source de vérité et valide la cohérence à l'entrée de chaque nœud.
"""

from typing import Dict, Any, Optional, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


class ReactivationContextValidator:
    """Validateur du contexte de réactivation pour assurer la cohérence."""
    
    @staticmethod
    def validate_reactivation_context(state: Dict[str, Any], node_name: str) -> Tuple[bool, Optional[str]]:
        """
        Valide la cohérence du contexte de réactivation à l'entrée d'un nœud.
        
        Args:
            state: État du graphe LangGraph
            node_name: Nom du nœud qui valide
            
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            is_reactivation = state.get('is_reactivation', False)
            reactivation_count = state.get('reactivation_count', 0)
            reactivation_context = state.get('reactivation_context')
            source_branch = state.get('source_branch', 'main')
            
            task = state.get('task')
            task_is_reactivation = getattr(task, 'is_reactivation', False) if task else False
            task_reactivation_count = getattr(task, 'reactivation_count', 0) if task else 0
            
            needs_sync = False
            
            if is_reactivation != task_is_reactivation:
                if task_is_reactivation and not is_reactivation:
                    logger.debug(f"🔄 [{node_name}] Synchronisation state.is_reactivation depuis task (LangGraph serialization)")
                elif not task_is_reactivation and is_reactivation:
                    logger.warning(f"⚠️ [{node_name}] INCOHÉRENCE: state indique réactivation mais task dit non - utilisation valeur task")
                is_reactivation = task_is_reactivation
                needs_sync = True
            
            if reactivation_count != task_reactivation_count:
                if abs(reactivation_count - task_reactivation_count) > 0:
                    if reactivation_count == 0 and task_reactivation_count > 0:
                        logger.debug(f"🔄 [{node_name}] Synchronisation reactivation_count depuis task (LangGraph serialization)")
                    else:
                        logger.warning(f"⚠️ [{node_name}] INCOHÉRENCE: reactivation_count diverge (state={reactivation_count}, task={task_reactivation_count})")
                reactivation_count = task_reactivation_count
                needs_sync = True
            
            if is_reactivation and reactivation_count < 0:
                error_msg = (
                    f"❌ [{node_name}] INCOHÉRENCE LOGIQUE: "
                    f"is_reactivation=True mais reactivation_count={reactivation_count} < 0"
                )
                logger.error(error_msg)
                return False, error_msg
            
            if not is_reactivation and reactivation_count > 0:
                error_msg = (
                    f"❌ [{node_name}] INCOHÉRENCE LOGIQUE: "
                    f"is_reactivation=False mais reactivation_count={reactivation_count} > 0"
                )
                logger.error(error_msg)
                return False, error_msg
            
            if is_reactivation and not reactivation_context:
                logger.warning(f"⚠️ [{node_name}] Réactivation sans contexte (peut être normal)")
            
            if reactivation_count < 0:
                error_msg = f"❌ [{node_name}] reactivation_count négatif: {reactivation_count}"
                logger.error(error_msg)
                return False, error_msg
            
            if reactivation_count > 100:  
                error_msg = f"❌ [{node_name}] reactivation_count trop élevé: {reactivation_count}"
                logger.error(error_msg)
                return False, error_msg
            
            if is_reactivation:
                logger.info(f"✅ [{node_name}] Contexte réactivation valide: #{reactivation_count}")
            else:
                logger.debug(f"✅ [{node_name}] Contexte workflow initial valide")
            
            return True, None
            
        except Exception as e:
            error_msg = f"❌ [{node_name}] Erreur validation contexte: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    @staticmethod
    def correct_reactivation_context(state: Dict[str, Any], node_name: str) -> Dict[str, Any]:
        """
        Corrige automatiquement les incohérences mineures du contexte de réactivation.
        
        Args:
            state: État du graphe LangGraph
            node_name: Nom du nœud qui corrige
            
        Returns:
            Dict[str, Any]: État corrigé
        """
        try:
            task = state.get('task')
            if not task:
                logger.warning(f"⚠️ [{node_name}] Pas de tâche dans l'état - impossible de corriger")
                return state
            
            task_is_reactivation = getattr(task, 'is_reactivation', False)
            task_reactivation_count = getattr(task, 'reactivation_count', 0)
            task_reactivation_context = getattr(task, 'reactivation_context', None)
            task_source_branch = getattr(task, 'source_branch', 'main')
            
            corrections_applied = []
            
            if state.get('is_reactivation') != task_is_reactivation:
                state['is_reactivation'] = task_is_reactivation
                corrections_applied.append(f"is_reactivation: {state.get('is_reactivation')} → {task_is_reactivation}")
            
            if state.get('reactivation_count') != task_reactivation_count:
                state['reactivation_count'] = task_reactivation_count
                corrections_applied.append(f"reactivation_count: {state.get('reactivation_count')} → {task_reactivation_count}")
            
            if state.get('reactivation_context') != task_reactivation_context:
                state['reactivation_context'] = task_reactivation_context
                corrections_applied.append(f"reactivation_context corrigé")
            
            if state.get('source_branch') != task_source_branch:
                state['source_branch'] = task_source_branch
                corrections_applied.append(f"source_branch: {state.get('source_branch')} → {task_source_branch}")
            
            if corrections_applied:
                logger.warning(f"🔧 [{node_name}] Corrections appliquées:")
                for correction in corrections_applied:
                    logger.warning(f"   • {correction}")
            
            return state
            
        except Exception as e:
            logger.error(f"❌ [{node_name}] Erreur correction contexte: {e}", exc_info=True)
            return state


# Instance globale
reactivation_validator = ReactivationContextValidator()
