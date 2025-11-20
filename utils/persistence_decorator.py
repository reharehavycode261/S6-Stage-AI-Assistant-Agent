"""Décorateur pour intégrer la persistence dans les nœuds de workflow."""

import functools
import time
from typing import Dict, Any, Callable
from services.database_persistence_service import db_persistence
from utils.logger import get_logger

logger = get_logger(__name__)


def with_persistence(node_name: str):
    """
    Décorateur pour ajouter automatiquement la persistence aux nœuds.

    Args:
        node_name: Nom du nœud pour les logs
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            start_time = time.time()
            step_id = None

            # Récupérer les IDs de persistence de l'état
            task_run_id = state.get("db_run_id")
            task_id = state.get("db_task_id")

            try:
                # ✅ CORRECTION CRITIQUE: Vérifier que le pool DB est initialisé
                if task_run_id and db_persistence.db_manager._is_initialized:
                    step_order = len(state.get("completed_nodes", [])) + 1

                    # ✅ CORRECTION: Sérialisation JSON sécurisée
                    task_data = state.get("task", {})
                    if hasattr(task_data, 'dict'):
                        # TaskRequest Pydantic - utiliser .dict()
                        task_dict = task_data.dict()
                    elif hasattr(task_data, '__dict__'):
                        # Objet avec __dict__ - extraire les attributs
                        task_dict = task_data.__dict__
                    else:
                        # Déjà un dictionnaire ou autre
                        task_dict = task_data if isinstance(task_data, dict) else {}

                    # ✅ ROBUSTESSE: Gestion d'erreur pour create_run_step
                    try:
                        step_id = await db_persistence.create_run_step(
                            task_run_id, node_name, step_order,
                            input_data={"node_input": task_dict}
                        )

                        # ✅ CORRECTION: Utiliser db_step_id pour cohérence avec db_task_id et db_run_id
                        state["db_step_id"] = step_id
                        state["current_step_id"] = step_id  # Garder pour compatibilité
                    except Exception as step_error:
                        logger.warning(f"⚠️ Erreur création step pour {node_name}: {step_error}")
                        logger.warning(f"⚠️ Nœud {node_name} continuera sans persistence")
                        step_id = None

                elif task_run_id and not db_persistence.db_manager._is_initialized:
                    # Pool non initialisé - logger et continuer sans persistence
                    logger.warning(f"⚠️ Pool DB non initialisé - nœud {node_name} exécuté sans persistence")
                    # Continuer l'exécution normale

                # Exécuter le nœud original
                result_state = await func(state)

                # Marquer comme complété
                if step_id and db_persistence.db_manager._is_initialized:
                    duration = int(time.time() - start_time)
                    try:
                        await db_persistence.complete_run_step(
                            step_id, "completed",
                            output_data={
                                "success": result_state.get("results", {}).get("should_continue", True),
                                "outputs": result_state.get("results", {})
                            }
                        )

                        # Logger l'application event
                        await db_persistence.log_application_event(
                            task_id=task_id,
                            task_run_id=task_run_id,
                            run_step_id=step_id,
                            level="INFO",
                            source_component=node_name,
                            action="node_completed",
                            message=f"Nœud {node_name} terminé avec succès",
                            metadata={
                                "duration_seconds": duration,
                                "success": result_state.get("results", {}).get("should_continue", True)
                            }
                        )
                    except Exception as db_error:
                        logger.warning(f"⚠️ Erreur persistence completion pour {node_name}: {db_error}")
                elif step_id and not db_persistence.db_manager._is_initialized:
                    logger.warning(f"⚠️ Impossible de sauvegarder completion pour {node_name} - pool DB indisponible")

                return result_state

            except Exception as e:
                # Marquer comme échoué
                if step_id and db_persistence.db_manager._is_initialized:
                    duration = int(time.time() - start_time)
                    try:
                        await db_persistence.complete_run_step(
                            step_id, "failed",
                            error_details=str(e)
                        )

                        # Logger l'erreur
                        await db_persistence.log_application_event(
                            task_id=task_id,
                            task_run_id=task_run_id,
                            run_step_id=step_id,
                            level="ERROR",
                            source_component=node_name,
                            action="node_failed",
                            message=f"Erreur dans nœud {node_name}: {str(e)}",
                            metadata={
                                "duration_seconds": duration,
                                "exception_type": type(e).__name__
                            }
                        )
                    except Exception as db_error:
                        logger.warning(f"⚠️ Erreur persistence échec pour {node_name}: {db_error}")
                elif step_id and not db_persistence.db_manager._is_initialized:
                    logger.warning(f"⚠️ Impossible de sauvegarder échec pour {node_name} - pool DB indisponible")

                # Re-lancer l'exception originale
                raise

        return wrapper
    return decorator


def log_ai_interaction_decorator(provider: str, model: str):
    """
    Décorateur spécifique pour logger les interactions IA.

    Args:
        provider: Provider IA (claude, openai, etc.)
        model: Modèle utilisé
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            # Extraire les paramètres de l'interaction
            prompt = kwargs.get('prompt', '') or (args[0] if args else '')
            step_id = kwargs.get('step_id')  # Doit être passé par le nœud

            try:
                # Exécuter l'appel IA
                response = await func(*args, **kwargs)

                # Logger l'interaction
                if step_id:
                    latency_ms = int((time.time() - start_time) * 1000)

                    # Extraire les informations de tokens si disponibles
                    token_usage = {}
                    if hasattr(response, 'usage'):
                        token_usage = {
                            "prompt_tokens": getattr(response.usage, 'input_tokens', 0),
                            "completion_tokens": getattr(response.usage, 'output_tokens', 0)
                        }

                    await db_persistence.log_ai_interaction(
                        step_id, provider, model, prompt,
                        response=str(response) if response else None,
                        token_usage=token_usage,
                        latency_ms=latency_ms
                    )

                return response

            except Exception as e:
                # Logger l'erreur d'interaction IA
                if step_id:
                    latency_ms = int((time.time() - start_time) * 1000)
                    await db_persistence.log_ai_interaction(
                        step_id, provider, model, prompt,
                        response=f"ERROR: {str(e)}",
                        latency_ms=latency_ms
                    )
                raise

        return wrapper
    return decorator


def log_test_results_decorator(func: Callable) -> Callable:
    """Décorateur pour logger automatiquement les résultats de tests."""
    @functools.wraps(func)
    async def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
        result_state = await func(state)

        # Logger les résultats de tests
        task_run_id = state.get("db_run_id")
        if task_run_id and "test_results" in result_state.get("results", {}):
            test_results = result_state["results"]["test_results"]

            try:
                # ✅ CORRECTION: Gérer à la fois les listes et les dictionnaires
                results_to_log = []
                
                if isinstance(test_results, list):
                    # Si c'est une liste, prendre le dernier résultat (le plus récent)
                    if test_results:
                        results_to_log = [test_results[-1]]
                elif isinstance(test_results, dict):
                    # Si c'est un dictionnaire, le traiter directement
                    results_to_log = [test_results]
                
                # Logger chaque résultat
                for test_result in results_to_log:
                    if not isinstance(test_result, dict):
                        continue
                        
                    passed = test_result.get("success", False)
                    total_tests = test_result.get("total_tests", 0)
                    passed_tests = test_result.get("passed_tests", 0)
                    failed_tests = test_result.get("failed_tests", 0)
                    
                    # ✅ AMÉLIORATION: Ne logger que si il y a eu de vrais tests exécutés
                    # ou si c'est un échec explicite
                    if total_tests > 0 or not passed:
                        await db_persistence.log_test_results(
                            task_run_id, passed, "passed" if passed else "failed",
                            total_tests, passed_tests, failed_tests,
                            coverage_percentage=test_result.get("coverage", None),
                            pytest_report=test_result,
                            duration_seconds=test_result.get("duration_seconds", None)
                        )
                        logger.info(f"✅ Résultats tests loggés en DB: passed={passed}, total={total_tests}")
                    else:
                        logger.debug(f"⏭️ Pas de tests réels à logger (validation automatique)")
                        
            except Exception as e:
                logger.warning(f"⚠️ Erreur logging résultats tests: {e}", exc_info=True)

        return result_state

    return wrapper


def log_code_generation_decorator(provider: str, model: str, generation_type: str = "initial"):
    """Décorateur pour logger les générations de code."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            start_time = time.time()
            result_state = await func(state)

            # Logger la génération de code
            task_run_id = state.get("db_run_id")
            if task_run_id:
                try:
                    response_time_ms = int((time.time() - start_time) * 1000)

                    # Extraire les informations de génération
                    code_changes = result_state.get("results", {}).get("code_changes", {})
                    files_modified = list(code_changes.keys()) if code_changes else []

                    # ✅ CORRECTION: Protection contre 'list' object has no attribute 'get'
                    task_obj = state.get("task", {})
                    if isinstance(task_obj, dict):
                        prompt = task_obj.get("description", "")
                    elif hasattr(task_obj, 'description'):
                        prompt = getattr(task_obj, 'description', "")
                    else:
                        prompt = ""

                    await db_persistence.log_code_generation(
                        task_run_id, provider, model, generation_type,
                        prompt=prompt,
                        generated_code=str(code_changes) if code_changes else None,
                        response_time_ms=response_time_ms,
                        files_modified=files_modified
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Erreur logging génération code: {e}")

            return result_state

        return wrapper
    return decorator