"""Fonctions utilitaires diverses."""

import hashlib
import hmac
import re
from typing import Any, Dict, Optional, List
from datetime import datetime
import os
import tempfile
from utils.logger import get_logger

logger = get_logger(__name__)


def validate_webhook_signature(payload: Dict[str, Any], signature: str, secret: str) -> bool:
    """
    Valide la signature HMAC d'un webhook.
    
    Args:
        payload: Données du webhook
        signature: Signature reçue
        secret: Clé secrète
        
    Returns:
        True si la signature est valide
    """
    try:
        import json
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception:
        return False


def sanitize_branch_name(name: str) -> str:
    """
    Nettoie un nom pour créer une branche Git valide.
    
    Args:
        name: Nom à nettoyer
        
    Returns:
        Nom de branche valide
    """
    clean_name = name.lower()
    
    clean_name = re.sub(r'[^\w\s-]', '', clean_name)
    clean_name = re.sub(r'\s+', '-', clean_name)
    
    clean_name = re.sub(r'-+', '-', clean_name)
    
    clean_name = clean_name.strip('-')

    if len(clean_name) > 50:
        clean_name = clean_name[:50].rstrip('-')

    if not clean_name:
        clean_name = "unnamed-branch"
    
    return clean_name


def generate_unique_branch_name(base_name: str, prefix: str = "feature") -> str:
    """
    Génère un nom de branche unique avec timestamp.
    
    Args:
        base_name: Nom de base
        prefix: Préfixe (feature, bugfix, etc.)
        
    Returns:
        Nom de branche unique
    """
    clean_base = sanitize_branch_name(base_name)
    timestamp = datetime.now().strftime("%m%d-%H%M")
    
    return f"{prefix}/{clean_base}-{timestamp}"


def extract_error_details(error: Exception) -> Dict[str, Any]:
    """
    Extrait les détails d'une exception pour le logging.
    
    Args:
        error: Exception à analyser
        
    Returns:
        Dictionnaire avec les détails de l'erreur
    """
    import traceback
    
    return {
        "type": type(error).__name__,
        "message": str(error),
        "traceback": traceback.format_exc() if hasattr(error, '__traceback__') else None
    }


def format_duration(seconds: float) -> str:
    """
    Formate une durée en secondes en format lisible.
    
    Args:
        seconds: Durée en secondes
        
    Returns:
        Chaîne formatée (ex: "2m 30s")
    """
    if seconds < 1:
        return f"{seconds:.2f}s"
    elif seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Tronque un texte s'il dépasse la longueur maximale.
    
    Args:
        text: Texte à tronquer
        max_length: Longueur maximale
        suffix: Suffixe à ajouter si tronqué
        
    Returns:
        Texte éventuellement tronqué
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def safe_get_nested(data: Dict[str, Any], keys: str, default: Any = None) -> Any:
    """
    Récupère une valeur dans un dictionnaire imbriqué de manière sécurisée.
    
    Args:
        data: Dictionnaire source
        keys: Clés séparées par des points (ex: "user.profile.name")
        default: Valeur par défaut
        
    Returns:
        Valeur trouvée ou valeur par défaut
    """
    try:
        current = data
        for key in keys.split('.'):
            current = current[key]
        return current
    except (KeyError, TypeError, AttributeError):
        return default


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fusionne plusieurs dictionnaires.
    
    Args:
        *dicts: Dictionnaires à fusionner
        
    Returns:
        Dictionnaire fusionné
    """
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result


def is_valid_git_branch_name(name: str) -> bool:
    """
    Vérifie si un nom est valide pour une branche Git.
    
    Args:
        name: Nom à vérifier
        
    Returns:
        True si le nom est valide
    """
    if not name:
        return False

    invalid_patterns = [
        r'\.\.', r'\s', r'~', r'\^', r':', r'\?', r'\*', r'\[',
        r'\\', r'//', r'@\{', r'^\.', r'\.$', r'\.lock$'
    ]
    
    for pattern in invalid_patterns:
        if re.search(pattern, name):
            return False
    
    return True


def extract_repo_info_from_url(url: str) -> Optional[Dict[str, str]]:
    """
    Extrait les informations d'un repository depuis une URL Git.
    
    Args:
        url: URL du repository
        
    Returns:
        Dictionnaire avec owner, repo, etc. ou None
    """
    try:
        clean_url = url.strip()
        if clean_url.endswith('.git'):
            clean_url = clean_url[:-4]
        
        patterns = [
            r'github\.com[:/]([^/]+)/([^/]+)',
            r'gitlab\.com[:/]([^/]+)/([^/]+)',
            r'bitbucket\.org[:/]([^/]+)/([^/]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, clean_url)
            if match:
                return {
                    "owner": match.group(1),
                    "repo": match.group(2),
                    "full_name": f"{match.group(1)}/{match.group(2)}"
                }
        
        return None
        
    except Exception:
        return None

def sanitize_filename(filename: str) -> str:
    """
    Nettoie un nom de fichier pour qu'il soit valide sur tous les OS.
    
    Args:
        filename: Nom de fichier à nettoyer
        
    Returns:
        Nom de fichier nettoyé
    """
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    
    clean_name = re.sub(invalid_chars, '_', filename)
    
    clean_name = clean_name.strip('. ')
    
    if len(clean_name) > 200:
        name, ext = os.path.splitext(clean_name)
        clean_name = name[:200-len(ext)] + ext
    
    return clean_name or "unnamed_file"


def create_status_emoji(success: bool, partial: Optional[bool] = None) -> str:
    """
    Retourne un emoji basé sur le statut.
    
    Args:
        success: Succès complet
        partial: Succès partiel (optionnel)
        
    Returns:
        Emoji approprié
    """
    if success:
        return "✅"
    elif partial:
        return "⚠️"
    else:
        return "❌"


def parse_test_output(output: str) -> Dict[str, Any]:
    """
    Parse la sortie de tests pour extraire des informations utiles.
    
    Args:
        output: Sortie des tests
        
    Returns:
        Informations extraites
    """
    result = {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "errors": [],
        "framework": "unknown"
    }
    
    patterns = {
        "pytest": {
            "total": r'(\d+) passed',
            "failed": r'(\d+) failed',
            "framework": "pytest"
        },
        "jest": {
            "total": r'Tests:\s+(\d+) passed',
            "failed": r'(\d+) failed',
            "framework": "jest"
        },
        "unittest": {
            "total": r'Ran (\d+) tests',
            "failed": r'FAILED \(.*failures=(\d+)',
            "framework": "unittest"
        }
    }
    
    for framework, pattern_dict in patterns.items():
        if framework.lower() in output.lower():
            result["framework"] = framework
            
            for key, pattern in pattern_dict.items():
                if key in ["total", "failed"]:
                    match = re.search(pattern, output)
                    if match:
                        result[key if key != "total" else "total_tests"] = int(match.group(1))
            
            break
    
    result["passed"] = max(0, result["total_tests"] - result["failed"])
    
    error_patterns = [r'FAIL.*', r'ERROR.*', r'AssertionError.*', r'TypeError.*']
    
    for pattern in error_patterns:
        matches = re.findall(pattern, output, re.MULTILINE)
        result["errors"].extend(matches[:5])  
    
    return result


def _safe_extract_path(data_source: Any, path_keys: List[str]) -> Optional[str]:
    """
    Extrait de manière sécurisée un chemin depuis une source de données.
    
    Args:
        data_source: Source de données (dict, objet, etc.)
        path_keys: Liste des clés possibles à essayer
        
    Returns:
        Chemin trouvé ou None
    """
    if not data_source:
        return None
        
    for key in path_keys:
        try:
            if isinstance(data_source, dict) and key in data_source:
                path = data_source[key]
                if path and isinstance(path, str) and os.path.exists(path):
                    return path
            
            elif hasattr(data_source, key):
                path = getattr(data_source, key)
                if path and isinstance(path, str) and os.path.exists(path):
                    return path
                    
        except Exception:
            continue
            
    return None


def _safe_extract_path_from_task(task: Any) -> Optional[str]:
    """
    Extrait un chemin de travail depuis l'objet task si possible.
    
    Args:
        task: Objet task du workflow
        
    Returns:
        Chemin trouvé ou None
    """
    if not task:
        return None
        
    task_path_attributes = [
        'working_directory', 'workspace_path', 'local_path',
        'repository_path', 'clone_path', 'source_path'
    ]
    
    return _safe_extract_path(task, task_path_attributes)


def _extract_task_id(state: Dict[str, Any]) -> Optional[str]:
    """
    Extrait l'ID de tâche depuis l'état pour créer un répertoire persistant.
    
    Args:
        state: État du workflow
        
    Returns:
        ID de tâche ou None
    """
    try:
        task = state.get("task")
        if task:
            if hasattr(task, 'task_id'):
                return str(task.task_id)
            elif hasattr(task, 'id'):
                return str(task.id)
            elif isinstance(task, dict):
                return str(task.get('task_id') or task.get('id'))
        
        workflow_id = state.get("workflow_id")
        if workflow_id:
            return str(workflow_id)
            
        results = state.get("results", {})
        if isinstance(results, dict):
            return str(results.get('task_id') or results.get('workflow_id'))
            
    except Exception:
        pass
        
    return None


def _create_persistent_working_directory(task_id: str, prefix: str) -> Optional[str]:
    """
    Crée un répertoire de travail persistant basé sur l'ID de tâche.
    
    Args:
        task_id: ID de la tâche
        prefix: Préfixe pour le nom du répertoire
        
    Returns:
        Chemin du répertoire créé ou None en cas d'échec
    """
    try:
        base_dirs = [
            os.path.expanduser("~/.ai_agent_workspaces"),  
            "/var/tmp/ai_agent_workspaces",                
            "/tmp/ai_agent_workspaces"                     
        ]
        
        for base_dir in base_dirs:
            try:
                os.makedirs(base_dir, exist_ok=True)
                
                clean_task_id = "".join(c for c in str(task_id) if c.isalnum() or c in '-_')[:50]
                workspace_dir = os.path.join(base_dir, f"{prefix}{clean_task_id}")
                
                os.makedirs(workspace_dir, exist_ok=True)
                
                if os.access(workspace_dir, os.R_OK | os.W_OK):
                    metadata_file = os.path.join(workspace_dir, ".ai_agent_metadata")
                    with open(metadata_file, 'w') as f:
                        f.write(f"task_id={task_id}\ncreated_at={datetime.now().isoformat()}\n")
                    
                    return workspace_dir
                    
            except (OSError, PermissionError):
                continue
                
    except Exception as e:
        logger.debug(f"🔍 Échec création répertoire persistant: {e}")
        
    return None


def _create_robust_temp_directory(prefix: str) -> str:
    """
    Crée un répertoire temporaire robuste avec gestion d'erreurs.
    
    Args:
        prefix: Préfixe pour le nom du répertoire
        
    Returns:
        Chemin du répertoire temporaire créé
        
    Raises:
        RuntimeError: Si impossible de créer un répertoire temporaire
    """
    import time
    import uuid
    
    temp_locations = [
        tempfile.gettempdir(),  
        "/var/tmp",             
        "/tmp",                 
        os.path.expanduser("~") 
    ]
    
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8]
    
    for temp_base in temp_locations:
        try:
            if os.path.exists(temp_base) and os.access(temp_base, os.W_OK):
                temp_dir = os.path.join(temp_base, f"{prefix}{timestamp}_{unique_id}")
                os.makedirs(temp_dir, exist_ok=True)
                
                test_file = os.path.join(temp_dir, ".test_write")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                
                return temp_dir
                
        except (OSError, PermissionError):
            continue
    
    try:
        return tempfile.mkdtemp(prefix=f"{prefix}{timestamp}_")
    except Exception as e:
        raise RuntimeError(f"Impossible de créer un répertoire temporaire: {e}")


def _update_state_working_directory(state: Dict[str, Any], working_directory: str) -> None:
    """
    Met à jour l'état avec le répertoire de travail de manière cohérente.
    
    Args:
        state: État du workflow à mettre à jour
        working_directory: Chemin du répertoire de travail
    """
    normalized_path = os.path.abspath(working_directory)
    
    state["working_directory"] = normalized_path
    
    if "results" not in state:
        state["results"] = {}
    state["results"]["working_directory"] = normalized_path
    
    if "prepare_result" in state["results"]:
        if isinstance(state["results"]["prepare_result"], dict):
            state["results"]["prepare_result"]["working_directory"] = normalized_path


def ensure_state_structure(state: Any) -> None:
    """
    S'assure que l'état a la structure requise pour les nœuds du workflow.
    
    Args:
        state: État du workflow (Dict ou GraphState)
    """
    if hasattr(state, 'get'):
        if "results" not in state:
            state["results"] = {}
        
        results = state["results"]
    else:
        try:
            results = state.get("results", {})
            if not results:
                state["results"] = {}
                results = state["results"]
        except (AttributeError, KeyError):
            if not hasattr(state, 'results'):
                state.results = {}
            results = state.results
    
    required_lists = ["ai_messages", "error_logs", "modified_files"]
    for list_name in required_lists:
        if list_name not in results:
            results[list_name] = []
    
    default_values = {
        "debug_attempts": 0,
        "current_status": "pending",
        "should_continue": True,
        "environment_ready": False
    }
    
    for key, default_value in default_values.items():
        if key not in results:
            results[key] = default_value


def add_ai_message(state: Any, message: str) -> None:
    """
    Ajoute un message IA de manière sécurisée à l'état.
    
    Args:
        state: État du workflow
        message: Message à ajouter
    """
    ensure_state_structure(state)
    
    if hasattr(state, 'get'):
        results = state["results"]
    else:
        try:
            results = state.get("results")
        except (AttributeError, KeyError):
            results = state.results
    
    results["ai_messages"].append(message)


def add_error_log(state: Any, error: str) -> None:
    """
    Ajoute un log d'erreur de manière sécurisée à l'état.
    
    Args:
        state: État du workflow
        error: Message d'erreur à ajouter
    """
    ensure_state_structure(state)
    
    if hasattr(state, 'get'):
        results = state["results"]
    else:
        try:
            results = state.get("results")
        except (AttributeError, KeyError):
            results = state.results
    
    results["error_logs"].append(error)


"""Utilitaires helpers pour le workflow."""


def get_working_directory(state: Any) -> Optional[str]:
    """
    Récupère le répertoire de travail depuis l'état du workflow (dict ou objet).
    
    Args:
        state: État du workflow (Dict ou GraphState)
        
    Returns:
        Chemin du répertoire de travail ou None si non trouvé
    """
    if hasattr(state, 'get'):
        working_directory = state.get("working_directory")
        if working_directory:
            return str(working_directory)
        
        if "results" in state and isinstance(state["results"], dict):
            working_directory = state["results"].get("working_directory")
            if working_directory:
                return str(working_directory)
    else:
        try:
            if hasattr(state, 'working_directory') and state.working_directory:
                return str(state.working_directory)
            
            working_directory = state.get("working_directory")
            if working_directory:
                return str(working_directory)
            
            results = state.get("results")
            if results and isinstance(results, dict):
                working_directory = results.get("working_directory")
                if working_directory:
                    return str(working_directory)
        except (AttributeError, KeyError, TypeError):
            pass
    
    return None


def validate_working_directory(working_directory: Optional[str], node_name: str = "unknown") -> bool:
    """
    Valide qu'un répertoire de travail existe et est accessible.
    
    Args:
        working_directory: Chemin du répertoire à valider
        node_name: Nom du nœud pour les logs
        
    Returns:
        True si le répertoire est valide
    """
    if not working_directory:
        logger.warning(f"⚠️ {node_name}: Aucun répertoire de travail fourni")
        return False
    
    if not os.path.exists(working_directory):
        logger.warning(f"⚠️ {node_name}: Répertoire de travail inexistant: {working_directory}")
        return False
    
    if not os.path.isdir(working_directory):
        logger.warning(f"⚠️ {node_name}: Le chemin n'est pas un répertoire: {working_directory}")
        return False
    
    if not os.access(working_directory, os.R_OK | os.W_OK):
        logger.warning(f"⚠️ {node_name}: Permissions insuffisantes pour: {working_directory}")
        return False
    
    return True


def ensure_working_directory(state: Dict[str, Any], prefix: str = "ai_agent_") -> str:
    """
    S'assure qu'un répertoire de travail existe de manière robuste et persistante.
    
    Stratégie de récupération hiérarchique :
    1. Vérifier l'état actuel du workflow
    2. Rechercher dans tous les emplacements de sauvegarde
    3. Utiliser un répertoire persistant basé sur l'ID de tâche
    4. En dernier recours, créer un répertoire temporaire
    
    Args:
        state: État du workflow
        prefix: Préfixe pour le répertoire temporaire
        
    Returns:
        Chemin du répertoire de travail valide
    """
    # Étape 1: Récupération depuis l'état actuel
    working_directory = get_working_directory(state)
    if validate_working_directory(working_directory, "ensure_working_directory"):
        return working_directory
    
    # Étape 2: Stratégie de récupération étendue et robuste
    recovery_strategies = [
        # Stratégie préférée: depuis prepare_result
        ("prepare_result", lambda: _safe_extract_path(state.get("results", {}).get("prepare_result", {}), ["working_directory", "repository_path", "clone_path"])),
        
        # Stratégie depuis git_result 
        ("git_result", lambda: _safe_extract_path(state.get("results", {}).get("git_result", {}), ["working_directory", "repository_path", "clone_directory"])),
        
        # Stratégie depuis les résultats généraux
        ("results_general", lambda: _safe_extract_path(state.get("results", {}), ["working_directory", "environment_path", "workspace_path"])),
        
        # Stratégie depuis la tâche elle-même (si elle contient un chemin)
        ("task_context", lambda: _safe_extract_path_from_task(state.get("task"))),
    ]
    
    for strategy_name, extract_func in recovery_strategies:
        try:
            potential_path = extract_func()
            if potential_path and validate_working_directory(potential_path, f"recovery_{strategy_name}"):
                logger.info(f"✅ Répertoire récupéré via {strategy_name}: {potential_path}")
                _update_state_working_directory(state, potential_path)
                return str(potential_path)
        except Exception as e:
            logger.debug(f"🔍 Stratégie {strategy_name} échouée: {e}")
            continue
    
    # Étape 3: Création d'un répertoire persistant basé sur l'ID de tâche
    task_id = _extract_task_id(state)
    if task_id:
        persistent_dir = _create_persistent_working_directory(task_id, prefix)
        if persistent_dir:
            logger.info(f"📁 Répertoire persistant créé pour tâche {task_id}: {persistent_dir}")
            _update_state_working_directory(state, persistent_dir)
            return persistent_dir
    
    # Étape 4: Dernier recours - répertoire temporaire robuste
    temp_dir = _create_robust_temp_directory(prefix)
    logger.info(f"📁 Répertoire temporaire créé en dernier recours: {temp_dir}")
    
    # Mettre à jour l'état
    _update_state_working_directory(state, temp_dir)
    return temp_dir