"""Nœud de merge - effectue le merge de la PR après validation humaine."""

from datetime import datetime
from models.state import GraphState
from models.schemas import HumanValidationStatus
from tools.github_tool import GitHubTool
from utils.logger import get_logger
from config.langsmith_config import langsmith_config

logger = get_logger(__name__)


async def merge_after_validation(state: GraphState) -> GraphState:
    """
    Nœud de merge: fusionne la Pull Request après validation humaine.
    
    Ce nœud :
    1. Vérifie que la validation humaine est positive
    2. Effectue le merge de la PR dans la branche principale
    3. Met à jour le statut dans Monday.com
    4. Nettoie les ressources temporaires
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec le résultat du merge
    """
    logger.info(f"🔀 Merge après validation pour: {state['task'].title}")
    
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []
    
    state["results"]["ai_messages"].append("🔀 Vérification validation avant merge...")
    
    try:
        should_merge = state["results"].get("should_merge", False)
        validation_status = state["results"].get("human_validation_status")
        human_decision = state["results"].get("human_decision")
        
        validation_errors = []
        
        if not should_merge:
            validation_errors.append("should_merge est False")
        
        if validation_status != HumanValidationStatus.APPROVED.value:
            validation_errors.append(f"Statut validation incorrect: {validation_status}")
        
        if human_decision not in ["approved"]:
            validation_errors.append(f"Décision humaine incorrecte: {human_decision}")
        
        if not state["results"].get("validation_response"):
            validation_errors.append("Aucune réponse de validation trouvée")
        
        if validation_errors:
            logger.warning(f"⏭️ Merge annulé - problèmes de validation: {'; '.join(validation_errors)}")
            state["results"]["ai_messages"].append(f"⏭️ Merge annulé: {'; '.join(validation_errors)}")
            state["results"]["merge_skipped"] = True
            state["results"]["skip_reason"] = "Validation incomplète ou incorrecte"
            state["results"]["validation_errors"] = validation_errors
            return state
        
        from services.pull_request_service import pr_service
        
        pr_result = await pr_service.ensure_pull_request_created(state)
        if not pr_result.success:
            error_msg = f"Échec création/récupération PR: {pr_result.error}"
            logger.error(f"❌ {error_msg}")
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            
            if pr_result.should_retry:
                state["results"]["should_retry_later"] = True
                state["results"]["retry_after"] = pr_result.retry_after or 60
                state["results"]["ai_messages"].append(f"⏳ Retry recommandé dans {pr_result.retry_after or 60}s")
            
            return state
        
        pr_info = pr_result.pr_info
        state["results"]["pr_info"] = pr_info
        state["results"]["ai_messages"].append(f"✅ PR prête: #{pr_info.number}")
        logger.info(f"✅ PR prête pour merge: #{pr_info.number}")
        
        task = state["task"]
        repo_url = state.get("results", {}).get("repository_url") or getattr(task, 'repository_url', None)
        
        if not repo_url and hasattr(task, 'description') and task.description:
            from utils.github_parser import extract_github_url_from_description
            
            logger.info("🔍 Tentative d'extraction URL GitHub depuis la description...")
            extracted_url = extract_github_url_from_description(task.description)
            
            if extracted_url:
                repo_url = extracted_url
                logger.info(f"✅ URL GitHub extraite de la description: {repo_url}")
        
        if repo_url and isinstance(repo_url, str):
            import re
            https_match = re.search(r'(https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?)', repo_url)
            if https_match:
                cleaned_url = https_match.group(1)
                if cleaned_url.endswith('.git'):
                    cleaned_url = cleaned_url[:-4]
                if cleaned_url != repo_url:
                    logger.info(f"🧹 URL repository nettoyée pour merge: '{repo_url[:50]}...' → '{cleaned_url}'")
                    repo_url = cleaned_url
        
        if not repo_url:
            error_msg = (
                "❌ URL du repository non trouvée pour le merge. "
                "Veuillez spécifier une URL GitHub dans la tâche Monday.com ou la description."
            )
            logger.error(f"❌ {error_msg}")
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["error_logs"].append(error_msg)
            return state
        
        if langsmith_config.client:
            try:
                langsmith_config.client.create_run(
                    name="merge_after_validation",
                    run_type="tool",
                    inputs={
                        "pr_number": pr_info.number if hasattr(pr_info, 'number') else getattr(pr_info, 'pr_number', 'unknown'),
                        "pr_url": pr_info.url if hasattr(pr_info, 'url') else getattr(pr_info, 'pr_url', ''),
                        "validation_status": validation_status,
                        "task_title": task.title
                    },
                    session_name=state.get("langsmith_session"),
                    extra={
                        "workflow_id": state.get("workflow_id"),
                        "human_approved": True
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        pr_number = pr_info.number if hasattr(pr_info, 'number') else getattr(pr_info, 'pr_number', None)
        
        if not pr_number:
            error_msg = "Numéro de PR non trouvé"
            logger.error(f"❌ {error_msg}")
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["error_logs"].append(error_msg)
            return state
        
        logger.info(f"🔀 Début du merge PR #{pr_number}...")
        state["results"]["ai_messages"].append(f"🔀 Merge de la PR #{pr_number}...")
        
        github_tool = GitHubTool()
        
        try:
            merge_result = await github_tool._arun(
                action="merge_pull_request",
                repo_url=repo_url,
                pr_number=pr_number,
                merge_method="squash",  
                commit_title=f"✅ Merge: {task.title}",
                commit_message=_generate_merge_commit_message(state)
            )
        except Exception as e:
            error_msg = f"Exception lors du merge GitHub: {str(e)}"
            logger.error(f"❌ {error_msg}")
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["error_logs"].append(error_msg)
            state["results"]["merge_successful"] = False
            return state
        
        if merge_result.get("success", False):
            merge_commit = merge_result.get("merge_commit")
            logger.info(f"✅ Merge réussi - Commit: {merge_commit}")
            
            state["results"]["merge_successful"] = True
            state["results"]["merge_commit"] = merge_commit
            state["results"]["ai_messages"].append(f"✅ Merge réussi: {merge_commit}")
            
            state["results"]["monday_final_status"] = "Done"
            state["results"]["workflow_success"] = True
            
            from models.schemas import WorkflowStatus
            state["status"] = WorkflowStatus.COMPLETED
            
            state["results"]["ai_messages"].append("🎉 Tâche prête à être marquée comme Done dans Monday.com")
            
            logger.info(f"📊 État après merge - merge_successful={state['results']['merge_successful']}, final_status={state['results']['monday_final_status']}")
            
            if merge_commit:
                commit_url = f"{repo_url.rstrip('/')}/commit/{merge_commit}"
                state["results"]["merge_commit_url"] = commit_url
                
        else:
            error_msg = merge_result.get("error", "Erreur inconnue lors du merge")
            logger.error(f"❌ Échec du merge: {error_msg}")
            state["results"]["ai_messages"].append(f"❌ Échec merge: {error_msg}")
            state["results"]["error_logs"].append(f"Merge failed: {error_msg}")
            state["results"]["merge_successful"] = False
            
        if state["results"].get("merge_successful", False):
            try:
                cleanup_result = await github_tool._arun(
                    action="delete_branch",
                    repo_url=repo_url,
                    branch=task.branch_name
                )
                
                if cleanup_result.get("success", False):
                    logger.info(f"🧹 Branche supprimée: {task.branch_name}")
                    state["results"]["ai_messages"].append("🧹 Branche de travail supprimée")
                else:
                    logger.warning(f"⚠️ Impossible de supprimer la branche: {task.branch_name}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors du nettoyage de branche: {e}")
        
        state["results"]["current_status"] = "merge_completed" if state["results"].get("merge_successful", False) else "merge_failed"
        
        logger.info(f"🔀 Processus de merge terminé: {'succès' if state['results'].get('merge_successful', False) else 'échec'}")
        
    except Exception as e:
        error_msg = f"Erreur lors du merge: {str(e)}"
        logger.error(f"❌ {error_msg}")
        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ {error_msg}")
        state["results"]["merge_successful"] = False
    
    return state


def _generate_merge_commit_message(state: GraphState) -> str:
    """Génère un message de commit pour le merge."""
    task = state["task"]
    validation_response = state["results"].get("validation_response")
    
    message = f"""
{task.title}

Description: {task.description[:200]}{'...' if len(task.description) > 200 else ''}

Type: {task.task_type.value}
Priorité: {task.priority.value}
"""
    
    if validation_response and hasattr(validation_response, 'approval_notes') and validation_response.approval_notes:
        message += f"\nNotes de validation: {validation_response.approval_notes}"
    
    test_results = state["results"].get("test_results")
    if test_results:
        if isinstance(test_results, dict) and test_results.get("success"):
            message += "\n✅ Tests: Passed"
        else:
            message += "\n⚠️ Tests: Some issues"
    
    message += f"\nValidé par: {validation_response.validated_by if validation_response and hasattr(validation_response, 'validated_by') else 'Human reviewer'}"
    message += f"\nWorkflow ID: {state.get('workflow_id', 'unknown')}"
    
    return message