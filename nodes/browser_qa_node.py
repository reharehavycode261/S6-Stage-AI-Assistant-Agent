"""Nœud d'assurance qualité browser - exécute les tests browser automatiques."""

import os
from typing import Dict, Any
from models.state import GraphState
from utils.logger import get_logger
from utils.helpers import get_working_directory
from services.browser_qa_service import BrowserQAService

logger = get_logger(__name__)


async def browser_quality_assurance(state: GraphState) -> GraphState:
    """
    Nœud d'assurance qualité browser : exécute les tests browser automatiques sur TOUT le code.
    
    ✅ NOUVEAU: Ne se limite plus au frontend - teste tout le code généré par l'agent !
    
    Ce nœud :
    1. Détecte si des changements testables ont été effectués (frontend, backend, API, config, docs)
    2. Génère des tests intelligents adaptés au type de code
    3. Démarre un serveur de développement local si nécessaire
    4. Lance Chrome via MCP en mode headless
    5. Exécute des scénarios de test (API, UI, E2E, documentation)
    6. Utilise tous les outils Chrome MCP (network, performance, debugging)
    7. Capture des screenshots et analyse les erreurs console
    8. Analyse les performances et le réseau
    9. Génère un rapport détaillé pour affichage dans l'interface admin
    
    Args:
        state: État actuel du workflow
        
    Returns:
        État mis à jour avec les résultats complets des tests browser
    """
    logger.info(f"🌐 Tests browser automatiques (TOUT le code) pour: {state['task'].title}")
    
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)
    
    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []
    
    if not state["task"]:
        logger.error("❌ Aucune tâche pour les tests browser")
        state["error"] = "Aucune tâche fournie pour les tests browser"
        return state
    
    state["current_node"] = "browser_quality_assurance"
    if "browser_quality_assurance" not in state["completed_nodes"]:
        state["completed_nodes"].append("browser_quality_assurance")
    
    try:
        working_directory = get_working_directory(state)
        
        if working_directory is not None:
            working_directory = str(working_directory)
        
        if not working_directory or not os.path.exists(working_directory):
            logger.warning("⚠️ Répertoire de travail non trouvé - tests browser ignorés")
            state["results"]["browser_qa_skipped"] = True
            state["results"]["ai_messages"].append("ℹ️ Tests browser ignorés (pas de répertoire de travail)")
            return state
        
        logger.info(f"📁 Répertoire de travail: {working_directory}")
        
        modified_files = []
        if state["results"] and "code_changes" in state["results"]:
            code_changes = state["results"]["code_changes"]
            if isinstance(code_changes, dict):
                modified_files = list(code_changes.keys())
            elif isinstance(code_changes, list):
                modified_files = code_changes
        
        if not modified_files:
            modified_files = state["results"].get("modified_files", [])
        
        logger.info(f"📄 Fichiers modifiés: {len(modified_files)}")
        
        browser_qa_service = BrowserQAService()
        
        should_run = await browser_qa_service.should_run_browser_tests(modified_files)
        
        if not should_run:
            logger.info("ℹ️ Tests browser non nécessaires - aucun code testable détecté")
            state["results"]["browser_qa"] = {
                "executed": False,
                "success": True,  
                "skipped": True,
                "reason": "Aucun fichier testable détecté (backend uniquement ou docs)",
                "tests_executed": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "screenshots": [],
                "console_errors": [],
                "performance_metrics": {},
                "test_scenarios": []
            }
            state["results"]["ai_messages"].append("ℹ️ Tests browser ignorés (aucun code testable)")
            return state
        
        logger.info("🚀 Lancement des tests browser automatiques...")
        
        task_description = ""
        if hasattr(state["task"], "description"):
            task_description = getattr(state["task"], "description", "") or ""
        
        browser_results = await browser_qa_service.run_browser_tests(
            working_directory=working_directory,
            modified_files=modified_files,
            task_description=task_description
        )
        
        state["results"]["browser_qa"] = {
            "executed": True,
            "success": browser_results["success"],
            "tests_executed": browser_results["tests_executed"],
            "tests_passed": browser_results["tests_passed"],
            "tests_failed": browser_results["tests_failed"],
            "screenshots": browser_results["screenshots"],
            "console_errors": browser_results["console_errors"],
            "performance_metrics": browser_results["performance_metrics"],
            "error": browser_results.get("error")
        }
        
        if browser_results["success"]:
            success_msg = f"✅ Tests browser réussis: {browser_results['tests_passed']}/{browser_results['tests_executed']}"
            logger.info(success_msg)
            state["results"]["ai_messages"].append(success_msg)
            
            perf = browser_results["performance_metrics"]
            if perf and not perf.get("error"):
                perf_msg = f"📊 Performance: Load {perf.get('load_time_ms', 0)}ms"
                state["results"]["ai_messages"].append(perf_msg)
        else:
            fail_msg = f"⚠️ Tests browser: {browser_results['tests_failed']} échec(s)"
            logger.warning(fail_msg)
            state["results"]["ai_messages"].append(fail_msg)
            
            if browser_results["console_errors"]:
                error_count = len(browser_results["console_errors"])
                state["results"]["ai_messages"].append(f"🐛 {error_count} erreur(s) console détectée(s)")
                
                for error in browser_results["console_errors"][:3]:
                    logger.warning(f"   Console error: {error}")
            
            if browser_results.get("error"):
                state["results"]["ai_messages"].append(f"❌ {browser_results['error']}")
        
        logger.info("🏁 Tests browser terminés (non-bloquants)")
        
        return state
        
    except Exception as e:
        error_msg = f"Exception lors des tests browser: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        
        state["results"]["browser_qa"] = {
            "executed": False,
            "success": False,
            "error": error_msg,
            "tests_executed": 0,
            "tests_passed": 0,
            "tests_failed": 0
        }
        state["results"]["ai_messages"].append(f"⚠️ Tests browser échoués: {error_msg}")
        
        return state

