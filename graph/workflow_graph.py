"""Workflow principal utilisant LangGraph pour l'agent de développement."""

import asyncio
import tempfile
import os
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, AsyncIterator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from models.state import GraphState
from models.schemas import TaskRequest, WorkflowStatus
from utils.logger import get_logger

from nodes.prepare_node import prepare_environment
from nodes.analyze_node import analyze_requirements  
from nodes.implement_node import implement_task
from nodes.test_node import run_tests
from nodes.debug_node import debug_code
from nodes.openai_debug_node import openai_debug_after_human_request  
from nodes.qa_node import quality_assurance_automation
from nodes.browser_qa_node import browser_quality_assurance  
from nodes.finalize_node import finalize_pr
from nodes.monday_validation_node import monday_human_validation
from nodes.merge_node import merge_after_validation
from nodes.update_node import update_monday

from services.database_persistence_service import db_persistence
from config.workflow_limits import WorkflowLimits
from utils.langsmith_tracing import workflow_tracer
from config.langsmith_config import langsmith_config

logger = get_logger(__name__)

MAX_WORKFLOW_NODES = 12  
TOTAL_GRAPH_NODES = 12  
MAX_DEBUG_ATTEMPTS = 2  

WORKFLOW_TIMEOUT_SECONDS = WorkflowLimits.WORKFLOW_TIMEOUT  
NODE_TIMEOUT_SECONDS = 600      
MAX_NODE_RETRIES = 2            

def create_workflow_graph() -> StateGraph:
    """
    Crée et configure le graphe de workflow LangGraph pour RabbitMQ avec validation humaine.

    Le graphe suit ce flux optimisé conforme à la conception :
    START → prepare → analyze → implement → test → [debug ↔ test] → qa → finalize → human_validation → merge → update → END

    Returns:
        StateGraph configuré et prêt à être compilé
    """

    workflow = StateGraph(GraphState)

    workflow.add_node("prepare_environment", prepare_environment)
    workflow.add_node("analyze_requirements", analyze_requirements)
    workflow.add_node("implement_task", implement_task)
    workflow.add_node("run_tests", run_tests)
    workflow.add_node("debug_code", debug_code)
    workflow.add_node("quality_assurance_automation", quality_assurance_automation)
    workflow.add_node("browser_quality_assurance", browser_quality_assurance)  
    workflow.add_node("finalize_pr", finalize_pr)
    workflow.add_node("monday_validation", monday_human_validation)
    workflow.add_node("openai_debug", openai_debug_after_human_request)
    workflow.add_node("merge_after_validation", merge_after_validation)
    workflow.add_node("update_monday", update_monday)

    workflow.set_entry_point("prepare_environment")

    workflow.add_edge("prepare_environment", "analyze_requirements")
    workflow.add_edge("analyze_requirements", "implement_task")
    workflow.add_edge("implement_task", "run_tests")

    workflow.add_conditional_edges(
        "run_tests",
        _should_debug,
        {
            "debug": "debug_code",      
            "continue": "quality_assurance_automation",  
            "end": END                  
        }
    )
    
    workflow.add_edge("debug_code", "run_tests")

    workflow.add_edge("quality_assurance_automation", "browser_quality_assurance")
    
    workflow.add_edge("browser_quality_assurance", "finalize_pr")
    workflow.add_edge("finalize_pr", "monday_validation")

    workflow.add_conditional_edges(
        "monday_validation",
        _should_merge_or_debug_after_monday_validation,
        {
            "merge": "merge_after_validation",    
            "debug": "openai_debug",              
            "update_only": "update_monday",       
            "end": END                            
        }
    )

    workflow.add_conditional_edges(
        "openai_debug",
        _should_continue_after_openai_debug,
        {
            "implement": "implement_task",   
            "retest": "run_tests",           
            "update_only": "update_monday",  
            "end": END                       
        }
    )

    workflow.add_edge("merge_after_validation", "update_monday")
    workflow.add_edge("update_monday", END)

    logger.info("✅ Graphe de workflow créé et configuré pour RabbitMQ avec nouveaux nœuds")
    return workflow

def _should_merge_or_debug_after_monday_validation(state: GraphState) -> str:
    """
    Détermine le chemin après validation Monday.com.

    LOGIQUE AMÉLIORÉE:
    - "oui" + pas de problèmes → merge
    - "oui" + problèmes détectés → debug automatique (ignore la réponse humaine)
    - "non/debug" → debug OpenAI
    - timeout/erreur → update seulement

    Args:
        state: État actuel du workflow

    Returns:
        "merge" si approuvé ET aucun problème, "debug" si problèmes détectés ou debug demandé, "update_only" si erreur/timeout
    """
    results = state.get("results", {})
    if not isinstance(results, dict):
        logger.warning("⚠️ Results n'est pas un dictionnaire dans _should_merge_or_debug_after_monday_validation")
        return "update_only"

    current_status = results.get("current_status", "")
    if current_status == "failed_validation":
        logger.error("❌ Erreur de validation critique détectée - arrêt du workflow")
        return "end"
    
    finalize_errors = results.get("error_logs", [])
    critical_finalize_errors = [
        "URL du repository non définie",
        "Branche Git non définie", 
        "Répertoire de travail non défini",
        "Working directory non défini"
    ]
    
    for error_log in finalize_errors:
        if any(critical_error in error_log for critical_error in critical_finalize_errors):
            logger.error(f"❌ Erreur critique de finalisation détectée: {error_log}")
            logger.error("❌ Impossible de continuer le workflow - données manquantes")
            return "end"
    
    if results.get("skip_github", False):
        logger.warning("⚠️ GitHub push ignoré - transition vers update Monday seulement")
        return "update_only"

    human_decision = results.get("human_decision", "error")
    should_merge = results.get("should_merge", False)
    validation_status = results.get("human_validation_status")
    error = results.get("error")

    if validation_status:
        validation_status_lower = str(validation_status).lower()
    else:
        validation_status_lower = None

    logger.info(f"🔍 Décision workflow: human_decision='{human_decision}', should_merge={should_merge}, validation_status='{validation_status}'")

    if human_decision == "approved" and not should_merge:
        logger.warning("⚠️ Incohérence détectée: approved sans should_merge - correction automatique")
        results["should_merge"] = True
        should_merge = True
    elif human_decision in ["rejected", "debug"] and should_merge:
        logger.warning(f"⚠️ Incohérence détectée: {human_decision} avec should_merge=True - correction automatique")
        results["should_merge"] = False
        should_merge = False
    elif validation_status_lower == "approved" and human_decision not in ["approved", "approve_auto"]:
        logger.info(f"🔄 Normalisation: validation_status='approved' → human_decision='approved' (était '{human_decision}')")
        results["human_decision"] = "approved"
        results["should_merge"] = True
        human_decision = "approved"
        should_merge = True
    elif validation_status_lower in ["rejected", "debug"] and human_decision not in ["rejected", "rejected_with_retry", "debug", "error", "timeout"]:
        logger.info(f"🔄 Normalisation: validation_status='{validation_status}' → human_decision='rejected'")
        results["human_decision"] = "rejected"
        results["should_merge"] = False
        human_decision = "rejected"
        should_merge = False

    if error and "timeout" in error.lower():
        logger.warning("⚠️ Timeout validation Monday.com - update seulement")
        return "update_only"

    if human_decision == "error":
        logger.warning("⚠️ Erreur validation Monday.com - update seulement")
        return "update_only"
    
    if human_decision == "timeout":
        logger.warning("⚠️ Timeout validation Monday.com - update seulement")
        return "update_only"
    
    if human_decision == "approve_auto":
        logger.info("✅ Validation automatique approuvée - traiter comme approved")
        human_decision = "approved"
        should_merge = True
        results["should_merge"] = True
        results["human_decision"] = "approved"

        if human_decision == "rejected_with_retry":
            rejection_count = results.get("rejection_count", 1)
            modification_instructions = results.get("modification_instructions", "")
            
            if rejection_count >= 3:
                logger.warning(f"⚠️ Limite de rejets atteinte ({rejection_count}/3) - arrêt du workflow")
                return "end"
            
            logger.info(f"🔄 Rejet avec modification demandée ({rejection_count}/3) - relance via ré-implémentation")
            logger.info(f"📝 Instructions de modification: {modification_instructions[:100]}...")
            
            state["results"]["reimplement_with_modifications"] = True
            state["results"]["modification_reason"] = "human_rejection_with_instructions"
            
            return "implement"
    
    if human_decision == "rejected":
        logger.info("❌ Code rejeté sans instructions de relance - mise à jour Monday.com seulement")
        return "update_only"

    def _has_unresolved_issues(results: dict) -> tuple[bool, list[str]]:
        """Vérifie s'il y a encore des problèmes non résolus dans le workflow."""
        issues = []

        test_results = results.get("test_results", {})
        if isinstance(test_results, dict):
            test_success = test_results.get("success", False)
            if not test_success:
                issues.append("tests échoués")
                failed_tests = test_results.get("failed_tests", [])
                if failed_tests:
                    issues.append(f"{len(failed_tests)} test(s) en échec")

        error_logs = results.get("error_logs", [])
        if error_logs:
            issues.append(f"{len(error_logs)} erreur(s) détectée(s)")

        implementation_errors = results.get("implementation_errors", [])
        if implementation_errors:
            issues.append(f"{len(implementation_errors)} erreur(s) d'implémentation")

        pr_url = results.get("pr_url")
        if not pr_url:
            issues.append("pull request non créée")

        quality_assurance = results.get("quality_assurance")
        if quality_assurance and isinstance(quality_assurance, dict):
            overall_score = quality_assurance.get("overall_score", 95) 
            if overall_score < 30:  
                issues.append(f"score qualité trop bas ({overall_score}/100)")
        elif "qa_results" in results:
            qa_results = results.get("qa_results", {})
            if isinstance(qa_results, dict) and qa_results:
                overall_score = qa_results.get("overall_score", 95)
                if overall_score < 30:
                    issues.append(f"score qualité trop bas ({overall_score}/100)")

        return len(issues) > 0, issues

    if human_decision == "debug":
        logger.info("🔧 Humain demande debug via Monday.com - lancer OpenAI debug")
        return "debug"

    if human_decision == "approved" and should_merge:
        has_issues, issue_list = _has_unresolved_issues(results)

        if has_issues:
            logger.warning("⚠️ Humain a dit 'oui' mais problèmes détectés - RESPECT DE LA DÉCISION HUMAINE")
            logger.warning(f"   Problèmes détectés: {', '.join(issue_list)}")
            logger.warning("   L'humain assume la responsabilité du merge malgré les problèmes")
            
            if "ai_messages" not in results:
                results["ai_messages"] = []
            results["ai_messages"].append(f"⚠️ Merge approuvé malgré: {', '.join(issue_list)}")
            results["human_override"] = True
            results["override_issues"] = issue_list
            
            return "merge"      
        else:
            logger.info("✅ Humain a dit 'oui' et aucun problème détecté - MERGE")
            return "merge"

    if human_decision == "abandoned":
        logger.warning("⛔ Workflow abandonné par l'humain - arrêt complet")
        return "end"
    
    logger.warning(f"⚠️ Décision non gérée: '{human_decision}' - mise à jour Monday.com seulement")
    logger.warning(f"   should_merge={should_merge}, validation_status='{validation_status}'")
    logger.warning("   Ceci ne devrait PAS se produire - vérifier la logique de validation")
    return "update_only"

def _should_merge_after_validation(state: GraphState) -> str:
    """
    Détermine si le workflow doit procéder au merge après validation humaine.

    Args:
        state: État actuel du workflow

    Returns:
        "merge" si approuvé, "skip_merge" si rejeté, "end" si erreur critique
    """
    results = state.get("results", {})
    if not isinstance(results, dict):
        logger.warning("⚠️ Results n'est pas un dictionnaire dans _should_merge_after_validation")
        return "end"

    should_merge = results.get("should_merge", False)
    validation_status = results.get("human_validation_status")
    error = results.get("error")

    if error and "timeout" in error.lower():
        logger.warning("⚠️ Timeout validation humaine - arrêt du workflow")
        return "end"

    if should_merge and validation_status == "approved":
        logger.info("✅ Validation approuvée - procéder au merge")
        return "merge"

    logger.info(f"⏭️ Validation non approuvée ({validation_status}) - passer au update Monday")
    return "skip_merge"

def _should_debug(state: GraphState) -> str:
    """
    Détermine si le workflow doit passer en mode debug.

    Args:
        state: État actuel du workflow

    Returns:
        "debug" si debug nécessaire, "continue" si on peut passer à QA, "end" si erreur critique
    """
    from config.workflow_limits import WorkflowLimits

    results = state.get("results", {})
    if not isinstance(results, dict):
        logger.warning("⚠️ Results n'est pas un dictionnaire dans _should_debug")
        return "end"

    if not results or "test_results" not in results:
        logger.warning("⚠️ Aucun résultat de test trouvé - Structure de données incorrecte")
        results["current_status"] = "error_no_test_structure"
        results["error"] = "Structure de données de test manquante"
        results["should_continue"] = False
        return "end"  

    test_results_list = results["test_results"]

    if not test_results_list:
        logger.info("📝 Aucun test exécuté - Continuation vers assurance qualité")
        results["no_tests_found"] = True
        results["test_status"] = "no_tests"
        if "ai_messages" not in results:
            results["ai_messages"] = []
        results["ai_messages"].append("📝 Aucun test exécuté - Passage direct à l'assurance qualité")
        return "continue"  

    if isinstance(test_results_list, list):
        latest_test_result = test_results_list[-1]  
    else:
        latest_test_result = test_results_list  

    logger.info(f"🔍 Analyse du dernier résultat de test: {type(latest_test_result)}")

    tests_passed = False
    failed_count = 0
    total_tests = 0

    if isinstance(latest_test_result, dict):
        tests_passed = latest_test_result.get("success", False)
        total_tests = latest_test_result.get("total_tests", 0)
        failed_count = latest_test_result.get("failed_tests", 0)

        if latest_test_result.get("no_tests_found", False):
            logger.info("📝 Flag 'no_tests_found' détecté - Continuation vers assurance qualité")
            results["no_tests_found"] = True
            results["test_status"] = "no_tests"
            if "ai_messages" not in results:
                results["ai_messages"] = []
            results["ai_messages"].append("📝 Aucun test trouvé - Passage direct à l'assurance qualité")
            return "continue"  

        if isinstance(failed_count, int):
            pass  
        elif isinstance(failed_count, list):
            failed_count = len(failed_count)
        else:
            failed_count = 0

    elif hasattr(latest_test_result, 'success'):
        tests_passed = latest_test_result.success
        total_tests = getattr(latest_test_result, 'total_tests', 1)
        failed_count = getattr(latest_test_result, 'failed_tests', 0) if not tests_passed else 0
    else:
        tests_passed = bool(latest_test_result)
        total_tests = 1
        failed_count = 0 if tests_passed else 1

    if total_tests == 0:
        logger.info("📝 Aucun test trouvé (0/0) - Continuation vers assurance qualité")
        results["no_tests_found"] = True
        results["test_status"] = "no_tests"
        if "ai_messages" not in results:
            results["ai_messages"] = []
        results["ai_messages"].append("📝 Aucun test trouvé - Passage direct à l'assurance qualité")
        return "continue"  


    if "debug_attempts" not in results:
        results["debug_attempts"] = 0

    debug_attempts = results["debug_attempts"]
    MAX_DEBUG_ATTEMPTS = WorkflowLimits.MAX_DEBUG_ATTEMPTS

    logger.info(f"🔧 Debug attempts: {debug_attempts}/{MAX_DEBUG_ATTEMPTS}, Tests: {total_tests} total, {failed_count} échecs (dernier résultat uniquement)")

    if tests_passed:
        logger.info("✅ Tests réussis - passage à l'assurance qualité")
        return "continue"

    if debug_attempts >= MAX_DEBUG_ATTEMPTS:
        logger.warning(f"⚠️ Limite de debug atteinte ({debug_attempts}/{MAX_DEBUG_ATTEMPTS}) - passage forcé à QA")
        results["error"] = f"Tests échoués après {debug_attempts} tentatives de debug"
        return "continue"  

    results["debug_attempts"] += 1
    logger.info(f"🔧 Tests échoués ({failed_count} échecs) - lancement debug {results['debug_attempts']}/{MAX_DEBUG_ATTEMPTS}")
    return "debug"

def _should_continue_after_openai_debug(state: GraphState) -> str:
    """
    Détermine le chemin après debug OpenAI suite à validation humaine.
    
    LOGIQUE:
    - Si trigger_reimplementation → implement (ré-implémenter avec instructions)
    - Si limite de debug atteinte → update_only
    - Si debug réussi → retest 
    - Si erreur critique → end
    
    Args:
        state: État actuel du workflow
        
    Returns:
        "implement" pour ré-implémenter, "retest" pour retester, "update_only" si limite atteinte, "end" si erreur critique
    """
    results = state.get("results", {})
    if not isinstance(results, dict):
        logger.warning("⚠️ Results n'est pas un dictionnaire dans _should_continue_after_openai_debug")
        return "end"
    
    if results.get("trigger_reimplementation", False):
        logger.info("🔄 Ré-implémentation déclenchée avec instructions de modification humaine")
        return "implement"
    
    if results.get("debug_limit_reached", False):
        logger.warning("⚠️ Limite de debug après validation humaine atteinte - update Monday seulement")
        return "update_only"
    
    if results.get("openai_debug_failed", False):
        logger.error("❌ Debug OpenAI a échoué - update Monday seulement")
        return "update_only"
    
    if not results.get("should_continue", True):
        logger.warning("⚠️ Workflow marqué pour arrêt - update Monday seulement")
        return "update_only"
    

    if results.get("openai_debug_completed", False):
        logger.info("✅ Debug OpenAI terminé avec succès - relance des tests")
        return "retest"
    
    logger.info("🔄 Debug OpenAI terminé - relance des tests")
    return "retest"

async def run_workflow(task_request: TaskRequest) -> Dict[str, Any]:
    """
    Execute un workflow complet pour une tâche donnée avec RabbitMQ.

    Args:
        task_request: Requête de tâche à traiter

    Returns:
        Résultat du workflow avec métriques
    """
    workflow_id = f"workflow_{task_request.task_id}_{int(datetime.now().timestamp())}"

    logger.info(f"🚀 Démarrage workflow {workflow_id} pour: {task_request.title}")
    
    if hasattr(task_request, 'is_reactivation') and task_request.is_reactivation:
        logger.info(f"🔄 WORKFLOW DE RÉACTIVATION détecté:")
        logger.info(f"   • Réactivation #{task_request.reactivation_count}")
        logger.info(f"   • Repository: {task_request.repository_url}")
        logger.info(f"   • Source branch: {task_request.source_branch}")
        logger.info(f"   • Task DB ID: {task_request.task_db_id}")
        logger.info(f"   • Run ID: {getattr(task_request, 'run_id', 'N/A')}")
    else:
        logger.info(f"🆕 PREMIER WORKFLOW (non-réactivation)")

    try:
        return await asyncio.wait_for(
            _run_workflow_with_recovery(workflow_id, task_request),
            timeout=WORKFLOW_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.error(f"❌ Timeout global du workflow {workflow_id} après {WORKFLOW_TIMEOUT_SECONDS}s")
        return _create_timeout_result(task_request, workflow_id, "global_timeout")
    except Exception as e:
        logger.error(f"❌ Erreur critique dans le workflow {workflow_id}: {e}", exc_info=True)
        return _create_error_result(task_request, str(e))

async def _run_workflow_with_recovery(workflow_id: str, task_request: TaskRequest) -> Dict[str, Any]:
    """Execute le workflow avec gestion de récupération d'état."""

    if not db_persistence.db_manager._is_initialized:
        await db_persistence.initialize()

    task_db_id = None
    actual_task_run_id = None  
    uuid_task_run_id = None    
    task_run_id = f"run_{uuid.uuid4().hex[:12]}_{int(time.time())}"

    try:
        
        if hasattr(task_request, 'task_db_id') and task_request.task_db_id:
            
            task_db_id = task_request.task_db_id
            logger.info(f"✅ Utilisation tâche existante: task_db_id={task_db_id}")
            
            try:
                logger.debug(f"🔄 Vérification pool avant chargement tâche: initialized={db_persistence.db_manager._is_initialized}")
                
                if db_persistence.db_manager.pool or db_persistence.db_manager._is_initialized:
                    try:
                        await db_persistence.db_manager.close()
                    except Exception:
                        pass
                    db_persistence.db_manager._is_initialized = False
                    db_persistence.db_manager.pool = None
                
                await db_persistence.initialize()
                logger.debug("✅ Pool initialisé dans le nouvel event loop pour chargement tâche")
                
                async with db_persistence.db_manager.get_connection() as conn:
                    task_details = await conn.fetchrow("""
                        SELECT 
                            tasks_id,
                            monday_item_id,
                            title,
                            description,
                            repository_url,
                            repository_name,
                            priority,
                            internal_status
                        FROM tasks 
                        WHERE tasks_id = $1
                    """, task_db_id)
                    
                    if task_details:
                        if task_details['repository_url'] and not task_request.repository_url:
                            task_request.repository_url = task_details['repository_url']
                            logger.info(f"✅ Repository URL chargée depuis BDD: {task_request.repository_url}")
                        
                        if task_details['description'] and not task_request.description:
                            task_request.description = task_details['description']
                            logger.info(f"✅ Description chargée depuis BDD: {task_request.description[:50]}...")
                        
                        if task_details['title'] and not task_request.title:
                            task_request.title = task_details['title']
                        
                        if task_details['priority']:
                            task_request.priority = task_details['priority']
                        
                        if task_details['monday_item_id'] and not hasattr(task_request, 'monday_item_id'):
                            task_request.monday_item_id = task_details['monday_item_id']
                        
                        logger.info(f"✅ Données tâche chargées depuis DB: {task_request.title}")
                        logger.info(f"📄 Description: {task_request.description[:100] if task_request.description else 'VIDE'}...")
                        logger.info(f"🔗 Repository URL: {task_request.repository_url or 'NON DÉFINIE'}")
                    else:
                        logger.warning(f"⚠️ Impossible de charger les détails pour task_db_id={task_db_id}")
                    
            except Exception as e:
                logger.error(f"❌ Erreur chargement détails tâche depuis BDD: {e}", exc_info=True)
        elif hasattr(task_request, 'monday_item_id') and task_request.monday_item_id:
            monday_payload = {
                "pulseId": task_request.monday_item_id,
                "pulseName": task_request.title,
                "boardId": getattr(task_request, 'board_id', None),
                "columnValues": {}
            }
            task_db_id = await db_persistence.create_task_from_monday(monday_payload)
            logger.info(f"✅ Tâche créée en base depuis Monday: task_db_id={task_db_id}")

        logger.info(f"🔄 Tentative création task_run avec task_db_id={task_db_id}, task_run_id={task_run_id}")
        
        precreated_run_id = getattr(task_request, 'run_id', None)
        logger.info(f"🔍 DEBUG: task_request.run_id = {precreated_run_id}")
        logger.info(f"🔍 DEBUG: task_request.is_reactivation = {getattr(task_request, 'is_reactivation', False)}")
        actual_task_run_id = await db_persistence.start_task_run(
            task_db_id,     
            workflow_id,
            task_run_id,
            precreated_run_id=precreated_run_id  
        )

        if actual_task_run_id:
            uuid_task_run_id = task_run_id
            logger.info(f"✅ Task run créé: actual_id={actual_task_run_id}, uuid={uuid_task_run_id}")
        else:
            logger.warning("⚠️ Aucun task_run_id généré - workflow sans persistence")

        initial_state = _create_initial_state_with_recovery(task_request, workflow_id, task_db_id, actual_task_run_id, uuid_task_run_id)

        logger.info(f"✅ État initial créé:")
        logger.info(f"   • workflow_id: {initial_state['workflow_id']}")
        logger.info(f"   • db_task_id: {initial_state.get('db_task_id')}")
        logger.info(f"   • db_run_id: {initial_state.get('db_run_id')}")
        logger.info(f"   • is_reactivation: {initial_state.get('is_reactivation', False)}")
        logger.info(f"   • reactivation_count: {initial_state.get('reactivation_count', 0)}")
        logger.info(f"   • source_branch: {initial_state.get('source_branch', 'main')}")

        workflow_graph = create_workflow_graph()
        
        checkpointer = MemorySaver()
        compiled_graph = workflow_graph.compile(checkpointer=checkpointer)
        
        workflow_start_time = time.time()
        final_state = None
        status = "unknown"
        success = False
        workflow_error = None

        logger.info(f"🔄 Début de l'exécution du graphe LangGraph...")
        
        async for event in _execute_workflow_with_recovery(compiled_graph, initial_state, workflow_id):
            event_type = event.get("type")

            if event_type == "step":
                node_name = event.get("node")
                node_output = event.get("output")
                logger.info(f"🔄 Exécution du nœud: {node_name}")

                if node_name == "prepare_environment":
                    repo_url = node_output.get("task", {})
                    if hasattr(repo_url, 'repository_url'):
                        logger.info(f"   📍 Repository URL dans prepare: {repo_url.repository_url}")
                    logger.info(f"   📍 Is reactivation: {node_output.get('is_reactivation', False)}")

                await _save_node_checkpoint(actual_task_run_id, node_name, node_output)

                final_state = node_output
                
                if node_name == "update_monday":
                    status = final_state.get("results", {}).get("current_status", "completed")
                    success = final_state.get("results", {}).get("success", True)
                    workflow_error = final_state.get("results", {}).get("error", None)
                    logger.info(f"🏁 Dernier nœud exécuté (update_monday). Statut: {status}, Succès: {success}")

            elif event_type == "error":
                logger.error(f"❌ Erreur dans le workflow: {event.get('error')}")
                workflow_error = event.get('error')
                final_state = event.get("state", initial_state)
                status = "failed"
                success = False
                break

            elif event_type == "end":
                final_state = event["output"]
                status = final_state.get("results", {}).get("current_status", "completed")
                success = final_state.get("results", {}).get("success", True)
                workflow_error = final_state.get("results", {}).get("error", None)
                if workflow_error:
                    success = False 
                logger.info(f"🏁 Workflow terminé via END. Statut: {status}, Succès: {success}")
                break
            
        if final_state is None:
            final_state = initial_state  
            workflow_error = "Workflow terminé sans état final clair"
            success = False
            status = "failed"
            logger.error(f"❌ {workflow_error}")
        else:
            if not isinstance(final_state, dict):
                logger.warning(f"⚠️ État final inattendu (type: {type(final_state)}), conversion en dict")
                final_state = {"results": {}, "error": "État final invalide"}
                success = False
                status = "failed"
            
            if 'success' not in locals() or success is None:
                success = final_state.get("results", {}).get("success", True)
            if 'status' not in locals() or status == "unknown":
                status = final_state.get("results", {}).get("current_status", "completed")
            if 'workflow_error' not in locals():
                workflow_error = final_state.get("results", {}).get("error", None)
            
            logger.info(f"✅ État final traité: status={status}, success={success}, error={workflow_error}")

        duration = time.time() - workflow_start_time

        await _finalize_workflow_run(actual_task_run_id, success, workflow_error, final_state)

        return _create_workflow_result(task_request, final_state, duration, success, workflow_error)

    except Exception as e:
        logger.error(f"❌ Erreur critique workflow {workflow_id}: {e}", exc_info=True)
        return _create_error_result(task_request, str(e))

async def _execute_workflow_with_recovery(compiled_graph, initial_state: Dict[str, Any], workflow_id: str) -> AsyncIterator[Dict[str, Any]]:
    """Execute le workflow nœud par nœud avec récupération d'erreur."""

    node_count = 0
    max_nodes = WorkflowLimits.MAX_NODES_SAFETY_LIMIT

    try:
        async for event in compiled_graph.astream(initial_state, config={"configurable": {"thread_id": workflow_id}}):
            node_count += 1

            if node_count > max_nodes:
                logger.error(f"⚠️ Limite de nœuds atteinte ({node_count}/{max_nodes}) - arrêt du workflow")
                yield {
                    "type": "error",
                    "error": f"Arrêt forcé - limite de {max_nodes} nœuds atteinte",
                    "state": initial_state
                }
                return

            try:
                yield await asyncio.wait_for(_process_node_event(event), timeout=NODE_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Timeout du nœud après {NODE_TIMEOUT_SECONDS}s - tentative de récupération")

                yield {
                    "type": "error",
                    "error": f"Timeout du nœud après {NODE_TIMEOUT_SECONDS}s",
                    "state": event.get("output", initial_state)
                }
                return

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'exécution du workflow: {e}", exc_info=True)
        yield {
            "type": "error",
            "error": str(e),
            "state": initial_state
        }

async def _process_node_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Traite un événement de nœud avec logging."""
    if "__end__" in event:
        return {
            "type": "end",
            "output": event.get("__end__", event)
        }
    
    for node_name, node_output in event.items():
        if node_name != "__end__":
            return {
                "type": "step",
                "node": node_name,
                "output": node_output
            }

    return {
        "type": "end",
        "output": event
    }

def _create_initial_state_with_recovery(task_request: TaskRequest, workflow_id: str, task_db_id: Optional[int], actual_task_run_id: Optional[int], uuid_task_run_id: Optional[str]) -> Dict[str, Any]:
    """Crée l'état initial avec support de récupération."""

    is_reactivation = getattr(task_request, 'is_reactivation', False)
    reactivation_context = getattr(task_request, 'reactivation_context', None)
    reactivation_count = getattr(task_request, 'reactivation_count', 0)
    source_branch = getattr(task_request, 'source_branch', 'main')
    
    logger.info(f"🔍 DEBUG TaskRequest values:")
    logger.info(f"   • is_reactivation: {is_reactivation}")
    logger.info(f"   • reactivation_context: {reactivation_context}")
    logger.info(f"   • reactivation_count: {reactivation_count}")
    logger.info(f"   • source_branch: {source_branch}")
    
    queue_id = getattr(task_request, 'queue_id', None)
    
    user_language = 'en'  
    project_language = 'en'  

    if hasattr(task_request, 'task_context') and task_request.task_context:
        if isinstance(task_request.task_context, dict):
            user_language = task_request.task_context.get('user_language', 'en')
            project_language = task_request.task_context.get('project_language', 'en')
        elif hasattr(task_request.task_context, '__dict__'):
            user_language = getattr(task_request.task_context, 'user_language', 'en')
            project_language = getattr(task_request.task_context, 'project_language', 'en')
    
    logger.info(f"🌍 État initial avec langues: user={user_language}, project={project_language}")

    is_reactivation = getattr(task_request, 'is_reactivation', False)
    reactivation_count = getattr(task_request, 'reactivation_count', 0)
    source_branch = getattr(task_request, 'source_branch', 'main')
    reactivation_context = getattr(task_request, 'reactivation_context', None)
    
    
    initial_state = {
        "task": task_request,
        "workflow_id": workflow_id,
        "db_task_id": task_db_id,  
        "db_run_id": actual_task_run_id,  
        "run_id": actual_task_run_id,  
        "uuid_run_id": uuid_task_run_id,
        "queue_id": queue_id,  
        "user_language": user_language,  
        "project_language": project_language,  
        "is_reactivation": is_reactivation,  
        "reactivation_count": reactivation_count,  
        "source_branch": source_branch,  
        "reactivation_context": reactivation_context,  
        "results": {
            "ai_messages": [],
            "error_logs": [],
            "modified_files": [],
            "test_results": [],
            "debug_attempts": 0,
            "queue_id": queue_id  
        },
        "error": None,
        "current_node": None,
        "completed_nodes": [],
        "node_retry_count": {},  
        "recovery_mode": False,  
        "checkpoint_data": {},   
        "started_at": datetime.now(),
        "completed_at": None,
        "status": WorkflowStatus.PENDING,
        "langsmith_session": None
    }
    
    
    if is_reactivation:
        logger.info(f"🔄 État initial créé pour RÉACTIVATION #{reactivation_count}")
        logger.info(f"📋 Contexte: {reactivation_context[:100] if reactivation_context else 'Aucun'}")
        logger.info(f"🌿 Clone depuis: {source_branch}")
    else:
        logger.info(f"🆕 État initial créé pour PREMIER WORKFLOW")

    return initial_state

async def _save_node_checkpoint(task_run_id: Optional[int], node_name: str, node_output: Dict[str, Any]):
    """Sauvegarde un checkpoint après chaque nœud."""
    if not task_run_id:
        return

    try:
        checkpoint_data = {
            "node_name": node_name,
            "completed_at": datetime.now().isoformat(),
            "output_summary": {
                "has_results": bool(node_output.get("results")),
                "has_error": bool(node_output.get("error")),
                "current_status": node_output.get("results", {}).get("current_status", "unknown")
            }
        }

        await db_persistence.save_node_checkpoint(task_run_id, node_name, checkpoint_data)
        logger.debug(f"💾 Checkpoint sauvé pour {node_name}")

    except Exception as e:
        logger.warning(f"⚠️ Erreur sauvegarde checkpoint {node_name}: {e}")

async def _finalize_workflow_run(task_run_id: Optional[int], success: bool, error: Optional[str], final_state: Dict[str, Any]):
    """Finalise le workflow run avec l'état final."""
    if not task_run_id:
        return

    try:
        metrics = {
            "success": success,
            "error": error,
            "completed_nodes": final_state.get("completed_nodes", []),
            "final_status": final_state.get("results", {}).get("current_status", "unknown")
        }
        
        if final_state.get("results", {}).get("browser_qa"):
            metrics["browser_qa"] = final_state["results"]["browser_qa"]
            logger.info(f"📊 Résultats Browser QA inclus dans metrics (tests: {metrics['browser_qa'].get('tests_executed', 0)})")

        status = "completed" if success else "failed"
        await db_persistence.complete_task_run(task_run_id, status, metrics, error)
        logger.info(f"✅ Workflow run {task_run_id} finalisé")
        
        try:
            if not db_persistence.db_manager._is_initialized:
                logger.warning("⚠️ Gestionnaire DB non disponible - impossible de mettre à jour le statut")
                return
                
            async with db_persistence.db_manager.get_connection() as conn:
                task_id = await conn.fetchval('''
                    SELECT task_id FROM task_runs WHERE tasks_runs_id = $1
                ''', task_run_id)
                
                if task_id and success:
                    await conn.execute('''
                        UPDATE tasks 
                        SET internal_status = 'completed',
                            monday_status = 'Done',
                            updated_at = NOW()
                        WHERE tasks_id = $1
                    ''', task_id)
                    logger.info(f"✅ Statut tâche {task_id} mis à 'completed' - Réactivation possible")
                elif task_id and not success:
                    human_decision = final_state.get("results", {}).get("human_decision")
                    
                    if human_decision == "abandoned":
                        current_status = await conn.fetchval('''
                            SELECT internal_status FROM tasks WHERE tasks_id = $1
                        ''', task_id)
                        logger.info(f"⛔ Workflow abandonné - Statut de la tâche conservé: '{current_status}'")
                        await conn.execute('''
                            UPDATE tasks 
                            SET updated_at = NOW()
                            WHERE tasks_id = $1
                        ''', task_id)
                    else:
                        await conn.execute('''
                            UPDATE tasks 
                            SET internal_status = 'failed',
                                updated_at = NOW()
                            WHERE tasks_id = $1
                        ''', task_id)
                        logger.info(f"⚠️ Statut tâche {task_id} mis à 'failed'")
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour statut tâche: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"❌ Erreur finalisation workflow run {task_run_id}: {e}")

def _create_timeout_result(task_request: TaskRequest, workflow_id: str, timeout_type: str) -> Dict[str, Any]:
    """Crée un résultat pour un timeout de workflow."""
    return {
        "success": False,
        "status": "timeout",
        "error": f"Timeout {timeout_type} du workflow",
        "workflow_id": workflow_id,
        "task_id": task_request.task_id,
        "task_title": task_request.title,
        "duration": WORKFLOW_TIMEOUT_SECONDS if timeout_type == "global_timeout" else NODE_TIMEOUT_SECONDS,
        "results": {
            "current_status": "timeout",
            "error": f"Workflow interrompu par timeout {timeout_type}",
            "success": False
        }
    }


def _process_final_result(final_state: GraphState, task_request: TaskRequest) -> Dict[str, Any]:
    """
    Traite l'état final du workflow et génère le résultat.

    Args:
        final_state: État final du workflow
        task_request: Requête de tâche originale

    Returns:
        Dictionnaire avec le résultat du workflow
    """

    current_status = final_state.get('status', WorkflowStatus.PENDING)
    results = final_state.get("results") or {}
    completed_nodes = final_state.get("completed_nodes") or []
    error_message = final_state.get("error")

    success = False

    if current_status == WorkflowStatus.COMPLETED:
        success = True
    elif len(completed_nodes) >= 3:  
        important_nodes = ["requirements_analysis", "code_generation", "quality_assurance"]
        completed_important = sum(1 for node in important_nodes if node in completed_nodes)

        if completed_important >= 2:  
            success = True
            logger.info(f"🟡 Succès partiel - {completed_important}/3 étapes importantes complétées")

    if not success and len(completed_nodes) >= 5:
        if any(key in results for key in ["code_changes", "pr_info", "quality_assurance"]):
            success = True
            logger.info(f"🟡 Succès avec erreurs mineures - {len(completed_nodes)} nœuds complétés")

    duration = 0
    started_at = final_state.get("started_at")
    if started_at:
        end_time = final_state.get("completed_at")
        if not end_time:
            from datetime import timezone
            end_time = datetime.now(timezone.utc)
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
        duration = (end_time - started_at).total_seconds()

    pr_url = None
    if "pr_info" in results:
        pr_info = results["pr_info"]
        if isinstance(pr_info, dict):
            pr_url = pr_info.get("pr_url")
        else:
            pr_url = getattr(pr_info, "pr_url", None)

    files_modified = 0
    tests_executed = 0
    qa_score = 0
    analysis_score = 0

    if "code_changes" in results:
        files_modified = len(results["code_changes"]) if isinstance(results["code_changes"], dict) else 0

    if "test_results" in results:
        test_results = results["test_results"]
        if isinstance(test_results, dict):
            tests_executed = test_results.get("total_tests", 0)
        elif isinstance(test_results, list):
            tests_executed = len(test_results)
        elif hasattr(test_results, 'total_tests'):
            tests_executed = getattr(test_results, 'total_tests', 0)

    if "quality_assurance" in results:
        qa_data = results["quality_assurance"]
        qa_score = qa_data.get("qa_summary", {}).get("overall_score", 0)

    if "requirements_analysis" in results:
        analysis_data = results["requirements_analysis"]
        analysis_score = analysis_data.get("complexity_score", 5)

    result = {
        "success": success,
        "status": current_status.value if current_status else "unknown",
        "workflow_id": final_state.get("workflow_id"),
        "task_id": task_request.task_id,
        "duration": duration,
        "completed_nodes": completed_nodes,
        "pr_url": pr_url,
        "error": error_message,
        "metrics": {
            "files_modified": files_modified,
            "tests_executed": tests_executed,
            "nodes_completed": len(completed_nodes),
            "duration_seconds": duration,
            "qa_score": qa_score,
            "analysis_complexity": analysis_score,
            "workflow_completeness": len(completed_nodes) / MAX_WORKFLOW_NODES * 100  
        },
        "results": results
    }

    logger.info(f"📊 Workflow terminé - Succès: {success}, Durée: {duration:.1f}s, Nœuds: {len(completed_nodes)}, QA: {qa_score}")

    return result

def _create_error_result(task_request: TaskRequest, error_msg: str) -> Dict[str, Any]:
    """Crée un résultat d'erreur standardisé."""

    return {
        "success": False,
        "status": "failed",
        "workflow_id": f"error_{task_request.task_id}",
        "task_id": task_request.task_id,
        "duration": 0,
        "completed_nodes": [],
        "pr_url": None,
        "error": error_msg,
        "metrics": {
            "files_modified": 0,
            "tests_executed": 0,
            "nodes_completed": 0,
            "duration_seconds": 0,
            "qa_score": 0,
            "analysis_complexity": 0,
            "workflow_completeness": 0
        },
        "results": {}
    }

def _ensure_final_state(state: GraphState) -> GraphState:
    """
    Garantit que l'état final est bien défini avec tous les champs requis.

    Args:
        state: État du workflow (potentiellement incomplet)

    Returns:
        État complété avec tous les champs requis pour un résultat final
    """
    if not isinstance(state, dict):
        state = {}

    if "workflow_id" not in state:
        state["workflow_id"] = f"unknown_{int(time.time())}"

    if "status" not in state:
        state["status"] = WorkflowStatus.FAILED

    if "results" not in state:
        state["results"] = {}

    results = state["results"]
    required_result_fields = [
        "ai_messages", "error_logs", "modified_files",
        "test_results", "debug_attempts", "current_status",
        "success"
    ]

    for field in required_result_fields:
        if field not in results:
            if field == "success":
                results[field] = False
            elif field == "current_status":
                results[field] = "failed"
            elif field in ["ai_messages", "error_logs", "modified_files", "test_results"]:
                results[field] = []
            elif field == "debug_attempts":
                results[field] = 0

    if "error" not in state and not results.get("success", False):
        state["error"] = "Workflow terminé sans état final clair"
        results["error"] = state["error"]

    if "started_at" not in state:
        state["started_at"] = datetime.now()

    if "completed_at" not in state:
        state["completed_at"] = datetime.now()

    if "completed_nodes" not in state:
        state["completed_nodes"] = []

    logger.info(f"✅ État final normalisé: succès={results.get('success')}, status={results.get('current_status')}")

    return state

def _create_workflow_result(task_request: TaskRequest, final_state: Dict[str, Any], duration: float, success: bool, error: Optional[str]) -> Dict[str, Any]:
    """Crée le résultat final du workflow."""

    if isinstance(final_state, dict):
        final_results = final_state.get("results", {})
        completed_nodes = final_state.get("completed_nodes", [])
    else:
        final_results = getattr(final_state, "results", {})
        completed_nodes = getattr(final_state, "completed_nodes", [])

    pr_url = None
    if "pr_info" in final_results:
        pr_info = final_results["pr_info"]
        if isinstance(pr_info, dict):
            pr_url = pr_info.get("pr_url")
        else:
            pr_url = getattr(pr_info, "pr_url", None)

    files_modified = 0
    tests_executed = 0

    if "code_changes" in final_results:
        files_modified = len(final_results["code_changes"]) if isinstance(final_results["code_changes"], dict) else 0

    if "test_results" in final_results:
        test_results = final_results["test_results"]
        if isinstance(test_results, dict):
            tests_executed = test_results.get("total_tests", 0)
        elif isinstance(test_results, list):
            tests_executed = len(test_results)

    return {
        "success": success,
        "status": "completed" if success else "failed",
        "error": error,
        "workflow_id": final_state.get("workflow_id", "unknown"),
        "task_id": task_request.task_id,
        "task_title": task_request.title,
        "duration": duration,
        "completed_nodes": completed_nodes,
        "files_modified": files_modified,
        "tests_executed": tests_executed,
        "pr_url": pr_url,
        "results": final_results
    }
