"""Nœud de validation humaine - attend la validation humaine avant le merge."""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from models.state import GraphState
from models.schemas import (
    HumanValidationRequest, 
    HumanValidationResponse, 
    HumanValidationStatus
)
from services.human_validation_service import validation_service
from utils.logger import get_logger
from config.langsmith_config import langsmith_config

logger = get_logger(__name__)


async def human_validation_node(state: GraphState) -> GraphState:
    """
    Nœud de validation humaine : crée une demande de validation et attend la réponse.
    
    Ce nœud :
    1. Crée une demande de validation humaine
    2. Sauvegarde les informations de la PR (sans merger)
    3. Attend la validation de l'humain
    4. Détermine la suite du workflow selon la réponse
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec la réponse de validation
    """
    logger.info(f"🤝 Demande de validation humaine pour: {state['task'].title}")
    
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []
    
    state["results"]["ai_messages"].append("🤝 Création demande de validation humaine...")
    
    try:
        validation_id = f"validation_{state['task'].task_id}_{uuid.uuid4().hex[:8]}"
        
        generated_code = await _collect_generated_code(state)
        code_summary = await _generate_code_summary(state)
        files_modified = list(generated_code.keys()) if generated_code else []
        
        pr_info = state["results"].get("pr_info")
        if not pr_info:
            logger.warning("⚠️ Aucune information de PR trouvée pour la validation")
        
        display_task_id = str(state["task"].monday_item_id) if hasattr(state["task"], 'monday_item_id') and state["task"].monday_item_id else str(state["task"].task_id)
        
        validation_request = HumanValidationRequest(
            validation_id=validation_id,
            workflow_id=state.get("workflow_id", "unknown"),
            task_id=display_task_id,  
            task_title=state["task"].title,
            generated_code=generated_code,
            code_summary=code_summary,
            files_modified=files_modified,
            original_request=state["task"].description,
            implementation_notes=state["results"].get("implementation_notes"),
            test_results=state["results"].get("test_results"),
            pr_info=pr_info,
            expires_at=datetime.now() + timedelta(hours=24),  
            requested_by="ai_agent"
        )
        
        task_id = state.get("db_task_id")
        task_run_id = state.get("db_run_id")
        run_step_id = state.get("db_step_id")
        
        if not task_id:
            logger.error("❌ db_task_id manquant dans l'état")
            task_id = None
        else:
            task_id = int(task_id)
        
        if task_run_id:
            task_run_id = int(task_run_id)
        if run_step_id:
            run_step_id = int(run_step_id)
        
        success = await validation_service.create_validation_request(
            validation_request, 
            task_id, 
            task_run_id, 
            run_step_id
        )
        
        if not success:
            error_msg = f"Erreur lors de la sauvegarde de la validation {validation_id}"
            logger.error(f"❌ {error_msg}")
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            return state
        
        logger.info(f"📝 Demande de validation créée: {validation_id}")
        state["results"]["validation_id"] = validation_id
        state["results"]["ai_messages"].append(f"✅ Validation {validation_id} créée")
        
        if langsmith_config.client:
            try:
                langsmith_config.client.create_run(
                    name="human_validation_request",
                    run_type="tool",
                    inputs={
                        "validation_id": validation_id,
                        "task_title": state["task"].title,
                        "files_count": len(files_modified),
                        "pr_url": pr_info.url if pr_info else None
                    },
                    outputs={
                        "status": "pending_validation",
                        "expires_at": validation_request.expires_at.isoformat()
                    },
                    session_name=state.get("langsmith_session"),
                    extra={
                        "workflow_id": state.get("workflow_id"),
                        "human_validation": True
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        logger.info(f"⏳ Attente de validation humaine pour {validation_id}...")
        state["results"]["ai_messages"].append("⏳ En attente de validation humaine...")
        
        validation_response = await validation_service.wait_for_validation_response(validation_id)
        
        if validation_response:
            state["results"]["validation_response"] = validation_response
            state["results"]["human_validation_status"] = validation_response.status.value
            
            if validation_response.status == HumanValidationStatus.APPROVED:
                logger.info(f"✅ Code approuvé par l'humain: {validation_id}")
                state["results"]["ai_messages"].append("✅ Code approuvé - Préparation du merge...")
                state["results"]["should_merge"] = True
                state["results"]["human_decision"] = "approved"
                
            elif validation_response.status == HumanValidationStatus.REJECTED:
                logger.info(f"❌ Code rejeté par l'humain: {validation_id}")
                state["results"]["ai_messages"].append(f"❌ Code rejeté: {validation_response.comments}")
                state["results"]["should_merge"] = False
                state["results"]["rejection_reason"] = validation_response.comments
                state["results"]["human_decision"] = "rejected"
                
            else:
                logger.warning(f"⚠️ Validation expirée ou annulée: {validation_id}")
                state["results"]["ai_messages"].append("⚠️ Validation expirée - Arrêt du workflow")
                state["results"]["should_merge"] = False
                state["results"]["human_decision"] = "timeout"
                
        else:
            logger.error(f"❌ Échec de validation humaine: {validation_id}")
            state["results"]["ai_messages"].append("❌ Échec validation humaine")
            state["results"]["should_merge"] = False
            state["results"]["error"] = "Timeout validation humaine"
            state["results"]["human_decision"] = "error"
        
        logger.info(f"🤝 Validation humaine terminée: {validation_response.status if validation_response else 'timeout'}")
        
    except Exception as e:
        error_msg = f"Erreur validation humaine: {str(e)}"
        logger.error(f"❌ {error_msg}")
        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ {error_msg}")
        state["results"]["should_merge"] = False
        state["results"]["human_decision"] = "error"
    
    return state


async def _collect_generated_code(state: GraphState) -> Dict[str, str]:
    """Collecte le code généré depuis l'état du workflow."""
    generated_code = {}
    
    implementation_results = state["results"].get("implementation_results", {})
    if isinstance(implementation_results, dict):
        files = implementation_results.get("modified_files", [])
        for file_info in files:
            if isinstance(file_info, dict) and "path" in file_info and "content" in file_info:
                generated_code[file_info["path"]] = file_info["content"]
    
    working_dir = state["results"].get("working_directory")
    if working_dir and not generated_code:
        logger.info(f"📁 Code collecté depuis working directory: {working_dir}")
        generated_code["simulation"] = f"Code from {working_dir}"
    
    return generated_code


async def _generate_code_summary(state: GraphState) -> str:
    """Génère un résumé des modifications de code."""
    task = state["task"]
    files_count = len(state["results"].get("implementation_results", {}).get("modified_files", []))
    
    summary = f"""
Résumé des modifications pour: {task.title}

Description originale: {task.description[:200]}...
Fichiers modifiés: {files_count}
Type de tâche: {task.task_type.value}
Priorité: {task.priority.value}

Modifications principales:
"""
    
    test_results = state["results"].get("test_results")
    if test_results:
        if isinstance(test_results, dict) and test_results.get("success"):
            summary += "\n✅ Tests: Tous les tests passent"
        else:
            summary += "\n⚠️ Tests: Certains tests échouent ou aucun test"
    
    return summary.strip()





async def get_pending_validation(validation_id: str) -> Optional[HumanValidationRequest]:
    """Récupère une demande de validation en attente."""
    return await validation_service.get_validation_by_id(validation_id)


async def list_pending_validations() -> List[HumanValidationRequest]:
    """Liste toutes les validations en attente."""
    summaries = await validation_service.list_pending_validations()
    validations = []
    for summary in summaries:
        validation = await validation_service.get_validation_by_id(summary.validation_id)
        if validation:
            validations.append(validation)
    return validations


async def submit_validation_response(validation_id: str, response: HumanValidationResponse) -> bool:
    """Soumet une réponse de validation humaine."""
    return await validation_service.submit_validation_response(validation_id, response) 