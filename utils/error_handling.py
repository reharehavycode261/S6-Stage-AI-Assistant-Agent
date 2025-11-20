"""
Utilitaires de gestion d'erreurs robuste pour le workflow AI-Agent.
"""

import functools
import traceback
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


def workflow_error_handler(node_name: str, critical: bool = False):
    """
    Décorateur pour gérer les erreurs de nœuds de workflow de manière robuste.
    
    Args:
        node_name: Nom du nœud pour le logging
        critical: Si True, les erreurs sont considérées comme critiques
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            try:
                ensure_state_integrity(state)
                
                result = await func(state, *args, **kwargs)
                
                if not isinstance(result, dict):
                    logger.error(f"❌ {node_name}: Résultat invalide (type {type(result)})")
                    state["results"]["error_logs"].append(f"Résultat invalide du nœud {node_name}")
                    state["results"]["current_status"] = "failed"
                    return state
                
                return result
                
            except Exception as e:
                error_msg = f"Exception dans {node_name}: {str(e)}"
                stack_trace = traceback.format_exc()
                
                logger.error(f"❌ {error_msg}")
                logger.debug(f"Stack trace: {stack_trace}")
                
                state["results"]["error_logs"].append(error_msg)
                state["results"]["ai_messages"].append(f"❌ Erreur: {error_msg}")
                
                if critical:
                    state["results"]["current_status"] = "failed_critical"
                    state["error"] = error_msg
                else:
                    state["results"]["current_status"] = "failed"
                    state["results"]["last_error"] = error_msg
                
                state["results"]["error_timestamp"] = datetime.now().isoformat()
                state["results"]["node_with_error"] = node_name
                
                return state
        
        return wrapper
    return decorator


def safe_get_from_state(state: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Récupère une valeur de l'état de manière sécurisée.
    
    Args:
        state: État du workflow
        key: Clé à rechercher
        default: Valeur par défaut
        
    Returns:
        Valeur trouvée ou valeur par défaut
    """
    try:
        if not isinstance(state, dict):
            logger.warning(f"⚠️ État invalide pour safe_get_from_state: {type(state)}")
            return default
        
        if "results" not in state:
            return default
        
        results = state["results"]
        if not isinstance(results, dict):
            logger.warning(f"⚠️ Results invalide pour safe_get_from_state: {type(results)}")
            return default
        
        return results.get(key, default)
        
    except Exception as e:
        logger.warning(f"⚠️ Erreur dans safe_get_from_state pour {key}: {e}")
        return default


def validate_state_structure(state: Dict[str, Any], required_keys: Optional[list] = None) -> bool:
    """
    Valide la structure de l'état du workflow.
    
    Args:
        state: État à valider
        required_keys: Clés requises dans results (optionnel)
        
    Returns:
        True si valide, False sinon
    """
    try:
        if not isinstance(state, dict):
            logger.error(f"❌ État invalide: type {type(state)}")
            return False
        
        if "task" not in state:
            logger.error("❌ État invalide: clé 'task' manquante")
            return False
        
        if "results" not in state:
            logger.warning("⚠️ État sans 'results' - initialisation automatique")
            state["results"] = {}
        
        if not isinstance(state["results"], dict):
            logger.error(f"❌ Results invalide: type {type(state['results'])}")
            return False
        
        if required_keys:
            results = state["results"]
            missing_keys = [key for key in required_keys if key not in results]
            if missing_keys:
                logger.warning(f"⚠️ Clés manquantes dans results: {missing_keys}")
                for key in missing_keys:
                    if key.endswith("_logs"):
                        results[key] = []
                    elif key.endswith("_messages"):
                        results[key] = []
                    else:
                        results[key] = None
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur validation état: {e}")
        return False


def ensure_state_integrity(state: Dict[str, Any]) -> None:
    """
    S'assure que l'état du workflow a tous les champs requis initialisés.
    
    Args:
        state: État du workflow à vérifier et corriger
    """
    if "results" not in state or not isinstance(state["results"], dict):
        state["results"] = {}
    
    results = state["results"]
    
    required_fields = {
        "ai_messages": [],
        "error_logs": [],
        "test_results": [],
        "modified_files": [],
        "current_status": "pending"
    }
    
    for field, default_value in required_fields.items():
        if field not in results:
            results[field] = default_value.copy() if isinstance(default_value, list) else default_value


def create_error_state(task: Any, error_message: str, node_name: str = "unknown") -> Dict[str, Any]:
    """
    Crée un état d'erreur sécurisé.
    
    Args:
        task: Tâche originale
        error_message: Message d'erreur
        node_name: Nom du nœud qui a échoué
        
    Returns:
        État d'erreur sécurisé
    """
    return {
        "task": task,
        "results": {
            "current_status": "failed_critical",
            "error_logs": [error_message],
            "ai_messages": [f"❌ Erreur critique: {error_message}"],
            "node_with_error": node_name,
            "error_timestamp": datetime.now().isoformat()
        },
        "error": error_message
    }


class WorkflowException(Exception):
    """Exception personnalisée pour les erreurs de workflow."""
    
    def __init__(self, message: str, node_name: str = "unknown", critical: bool = False):
        super().__init__(message)
        self.node_name = node_name
        self.critical = critical
        self.timestamp = datetime.now()


class ValidationException(WorkflowException):
    """Exception pour les erreurs de validation."""
    
    def __init__(self, message: str, node_name: str = "unknown"):
        super().__init__(message, node_name, critical=True) 