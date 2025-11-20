"""
Utilitaires de tracing LangSmith pour les métriques métier.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from models.state import GraphState
from utils.logger import get_logger

logger = get_logger(__name__)


def _get_langsmith_config():
    """Import paresseux pour éviter les cycles d'imports."""
    from config.langsmith_config import langsmith_config
    return langsmith_config


class WorkflowTracer:
    """Traceur spécialisé pour les workflows AI-Agent."""
    
    @staticmethod
    def trace_workflow_start(state: GraphState) -> None:
        """Tracer le début d'un workflow."""
        config = _get_langsmith_config()
        if not config.client:
            return
            
        try:
            task = state.get("task")
            config.client.create_run(
                name=f"workflow_start_{state.get('workflow_id', 'unknown')}",
                run_type="chain",
                inputs={
                    "workflow_id": state.get("workflow_id"),
                    "task_title": task.title if task else "Unknown",
                    "task_type": str(task.task_type) if task else "Unknown",
                    "repository_url": task.repository_url if task else None
                },
                session_name=state.get("langsmith_session"),
                extra={
                    "event_type": "workflow_start",
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur tracing workflow start: {e}")
    
    @staticmethod 
    def trace_node_execution(state: GraphState, node_name: str, 
                           node_inputs: Dict[str, Any], 
                           node_outputs: Dict[str, Any],
                           success: bool = True,
                           error: Optional[str] = None) -> None:
        """Tracer l'exécution d'un nœud de workflow."""
        config = _get_langsmith_config()
        if not config.client:
            return
            
        try:
            config.client.create_run(
                name=f"node_{node_name}",
                run_type="chain",
                inputs=node_inputs,
                outputs=node_outputs,
                session_name=state.get("langsmith_session"),
                extra={
                    "node_name": node_name,
                    "workflow_id": state.get("workflow_id"),
                    "success": success,
                    "error": error,
                    "timestamp": datetime.now().isoformat(),
                    "completed_nodes": state.get("completed_nodes", [])
                }
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur tracing node {node_name}: {e}")
    
    @staticmethod
    def trace_test_execution(state: GraphState, test_results: Dict[str, Any]) -> None:
        """Tracer l'exécution des tests."""
        config = _get_langsmith_config()
        if not config.client:
            return
            
        try:
            config.client.create_run(
                name="test_execution",
                run_type="tool",
                inputs={
                    "test_type": test_results.get("test_type", "unknown"),
                    "workflow_id": state.get("workflow_id")
                },
                outputs={
                    "success": test_results.get("success", False),
                    "tests_run": test_results.get("tests_run", 0),
                    "tests_passed": test_results.get("tests_passed", 0),
                    "tests_failed": test_results.get("tests_failed", 0),
                    "coverage": test_results.get("coverage_percentage"),
                    "execution_time": test_results.get("execution_time")
                },
                session_name=state.get("langsmith_session"),
                extra={
                    "event_type": "test_execution",
                    "failed_tests": test_results.get("failed_tests", [])
                }
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur tracing tests: {e}")
    
    @staticmethod
    def trace_code_generation(state: GraphState, generation_data: Dict[str, Any]) -> None:
        """Tracer la génération de code."""
        config = _get_langsmith_config()
        if not config.client:
            return
            
        try:
            config.client.create_run(
                name="code_generation",
                run_type="llm",
                inputs={
                    "files_to_modify": generation_data.get("files_to_modify", []),
                    "generation_type": generation_data.get("generation_type", "implementation"),
                    "workflow_id": state.get("workflow_id")
                },
                outputs={
                    "files_modified": generation_data.get("files_modified", []),
                    "lines_generated": generation_data.get("lines_generated", 0),
                    "compilation_successful": generation_data.get("compilation_successful"),
                    "syntax_valid": generation_data.get("syntax_valid")
                },
                session_name=state.get("langsmith_session"),
                extra={
                    "event_type": "code_generation",
                    "ai_provider": generation_data.get("ai_provider", "unknown")
                }
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur tracing code generation: {e}")
    
    @staticmethod
    def trace_business_event(state: GraphState, event_name: str, event_data: Dict[str, Any]) -> None:
        """Tracer un événement métier personnalisé."""
        config = _get_langsmith_config()
        if not config.client:
            return
            
        try:
            config.client.create_run(
                name=f"business_event_{event_name}",
                run_type="tool",
                inputs={
                    "event_name": event_name,
                    "workflow_id": state.get("workflow_id"),
                    **event_data
                },
                outputs={
                    "timestamp": datetime.now().isoformat(),
                    "success": event_data.get("success", True)
                },
                session_name=state.get("langsmith_session"),
                extra={
                    "event_type": "business_event",
                    "custom_event": event_name
                }
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur tracing business event {event_name}: {e}")
    
    @staticmethod
    def trace_workflow_completion(state: GraphState, final_result: Dict[str, Any]) -> None:
        """Tracer la fin d'un workflow."""
        config = _get_langsmith_config()
        if not config.client:
            return
            
        try:
            task = state.get("task")
            duration = None
            if state.get("started_at") and state.get("completed_at"):
                duration = (state["completed_at"] - state["started_at"]).total_seconds()
            
            config.client.create_run(
                name=f"workflow_completion_{state.get('workflow_id', 'unknown')}",
                run_type="chain",
                inputs={
                    "workflow_id": state.get("workflow_id"),
                    "task_title": task.title if task else "Unknown"
                },
                outputs={
                    "success": final_result.get("success", False),
                    "status": str(state.get("status", "unknown")),
                    "duration_seconds": duration,
                    "completed_nodes": state.get("completed_nodes", []),
                    "total_nodes": len(state.get("completed_nodes", [])),
                    "has_error": bool(state.get("error")),
                    "pull_request_url": final_result.get("pull_request_url"),
                    "files_modified": len(final_result.get("files_modified", []))
                },
                session_name=state.get("langsmith_session"),
                extra={
                    "event_type": "workflow_completion",
                    "final_error": state.get("error")
                }
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur tracing workflow completion: {e}")


# Instance globale pour faciliter l'utilisation
workflow_tracer = WorkflowTracer() 