"""Nœud de mise à jour Monday - met à jour le ticket avec les résultats."""

from datetime import datetime
from models.schemas import WorkflowStatus
from models.state import GraphState
from tools.monday_tool import MondayTool
from services.github_pr_service import github_pr_service
from utils.logger import get_logger
from services.workflow_queue_manager import workflow_queue_manager

logger = get_logger(__name__)


async def update_monday(state: GraphState) -> GraphState:
    """
    Nœud de mise à jour Monday.com : met à jour l'item avec les résultats finaux.

    Ce nœud :
    1. Collecte tous les résultats du workflow
    2. Génère un commentaire de completion
    3. Met à jour le statut de l'item Monday.com
    4. Attache les liens vers la PR et les artefacts
    5. Marque la tâche comme terminée

    Args:
        state: État actuel du graphe

    Returns:
        État mis à jour avec le statut final
    """
    logger.info(f"📝 🔔 DÉBUT UPDATE_MONDAY NODE - Mise à jour finale Monday.com pour: {state['task'].title}")

    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    if "results" not in state:
        state["results"] = {}

    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []

    state["results"]["ai_messages"].append("📋 Début de la mise à jour du ticket Monday.com...")

    try:
        monday_tool = MondayTool()

        if not hasattr(monday_tool, 'api_token') or not monday_tool.api_token:
            logger.warning("⚠️ Monday.com non configuré - mise à jour FINALE ignorée (mais workflow complété)")
            state["status"] = "completed"
            if "results" not in state:
                state["results"] = {}
            state["results"]["monday_update_skipped"] = "Configuration Monday.com manquante"
            state["results"]["ai_messages"].append("⚠️ Update Monday.com finale ignorée - API non configurée")
            return state

        task = state["task"]

        final_status, success_level = _determine_final_status(state)

        if state["results"].get("merge_successful", False) and final_status != "Done":
            logger.error(f"❌ INCOHÉRENCE: merge_successful=True mais final_status='{final_status}'")
            logger.warning("🔧 Correction automatique - Forçage à 'Done'")
            final_status = "Done"
            success_level = "success"
            state["results"]["status_corrected"] = True
    
        if state["results"].get("reimplementation_message_posted", False):
            logger.info("✅ Message de ré-implémentation déjà posté - skip du message de completion standard")
            completion_comment = None  
        else:
            completion_comment = await _generate_completion_comment(state, success_level)

        if completion_comment is not None and state["results"].get("merge_successful", False):
            merge_info = "\n\n✅ **Pull Request mergée avec succès**\n"
            if state["results"].get("merge_commit"):
                merge_info += f"- **Commit de merge**: `{state['results']['merge_commit']}`\n"
            if state["results"].get("merge_commit_url"):
                merge_info += f"- **Lien**: {state['results']['merge_commit_url']}\n"
            completion_comment += merge_info

        pr_url = None
        if state["results"] and "pr_info" in state["results"]:
            pr_info = state["results"]["pr_info"]
            pr_url = pr_info.get("pr_url") if isinstance(pr_info, dict) else getattr(pr_info, "pr_url", None)

        logger.info(f"📝 Mise à jour statut: {final_status}, PR: {pr_url or 'N/A'}")

        monday_item_id = str(task.monday_item_id) if task.monday_item_id else task.task_id

        status_result = await monday_tool._arun(
            action="update_item_status",
            item_id=monday_item_id,
            status=final_status
        )

        if completion_comment is not None:
            logger.info(f"🔔 POSTING DEUXIÈME UPDATE MONDAY - Commentaire final de complétion pour item {monday_item_id}")
            comment_result = await monday_tool._arun(
                action="add_comment",
                item_id=monday_item_id,
                comment=completion_comment
            )
            logger.info(f"✅ Résultat post commentaire final: {comment_result.get('success', False)}")
        else:
            logger.info(f"✅ Skip commentaire final - message personnalisé déjà posté pour item {monday_item_id}")
            comment_result = {"success": True, "skipped": True}

        if success_level == "success" and pr_url:
            try:
                from config.settings import get_settings
                settings = get_settings()
                
                if settings.monday_repository_url_column_id:
                    await monday_tool._arun(
                        action="update_column_value",
                        item_id=monday_item_id,
                        column_id=settings.monday_repository_url_column_id,
                        value=pr_url
                    )
                    logger.info(f"✅ Lien PR ajouté dans colonne {settings.monday_repository_url_column_id}: {pr_url}")
                else:
                    logger.warning("⚠️ Colonne Repository URL non configurée - lien PR non ajouté")
            except Exception as e:
                logger.debug(f"Impossible d'ajouter le lien PR (colonne peut-être absente): {e}")

        await _update_repository_url_column(state, monday_tool, monday_item_id)

        if not isinstance(status_result, dict):
            logger.error(f"❌ status_result n'est pas un dictionnaire: {type(status_result)} - {status_result}")
            if isinstance(status_result, list):
                status_result = {"success": False, "error": f"API retourné liste: {status_result}"}
            else:
                status_result = {"success": False, "error": f"Type invalide: {type(status_result)}"}

        if not isinstance(comment_result, dict):
            logger.error(f"❌ comment_result n'est pas un dictionnaire: {type(comment_result)} - {comment_result}")
            if isinstance(comment_result, list):
                comment_result = {"success": False, "error": f"API retourné liste: {comment_result}"}
            else:
                comment_result = {"success": False, "error": f"Type invalide: {type(comment_result)}"}

        update_result = {
            "success": status_result.get("success", False) and comment_result.get("success", False),
            "operations": [("status", status_result), ("comment", comment_result)]
        }

        if update_result.get("success", False):
            logger.info("✅ 🎉 DEUXIÈME UPDATE MONDAY POSTÉ AVEC SUCCÈS - Commentaire final visible dans Monday.com")

            if state["results"].get("merge_successful", False):
                if final_status != "Done":
                    logger.error(f"❌ ERREUR: Merge réussi mais statut='{final_status}'")
                    state["results"]["ai_messages"].append(
                        f"⚠️ Avertissement: Statut Monday='{final_status}' (attendu 'Done')"
                    )
                else:
                    logger.info("✅ Vérification: Statut 'Done' correctement appliqué")
                    state["results"]["ai_messages"].append(
                        "✅ Statut Monday.com mis à jour : Done"
                    )

            update_summary = f"✅ Mise à jour Monday.com réussie - Statut: {final_status}"
            if pr_url:
                update_summary += f" | PR: {pr_url}"

            state["results"]["ai_messages"].append(update_summary)
            state["results"]["ai_messages"].append("📋 Ticket Monday.com mis à jour avec les résultats du workflow")

            state["status"] = WorkflowStatus.COMPLETED
            state["completed_at"] = datetime.now()

            state["results"]["monday_update"] = {
                "success": True,
                "message": "Monday.com mis à jour avec succès",
                "final_status": final_status,
                "pr_url": pr_url,
                "comment_added": True
            }
        else:
            error_msg = update_result.get("error", "Erreur inconnue lors de la mise à jour Monday")
            logger.error(f"❌ 🔴 ÉCHEC DEUXIÈME UPDATE MONDAY - Le commentaire final n'a PAS été posté: {error_msg}")
            logger.error(f"🔍 Détails status_result: {status_result}")
            logger.error(f"🔍 Détails comment_result: {comment_result}")

            state["results"]["ai_messages"].append(f"❌ Échec mise à jour Monday.com: {error_msg}")
            state["results"]["ai_messages"].append("⚠️ Le workflow a été complété mais la mise à jour du ticket a échoué")

            state["status"] = WorkflowStatus.FAILED
            state["error"] = f"Échec mise à jour Monday: {error_msg}"

            state["results"]["monday_update"] = {
                "success": False,
                "error": error_msg,
                "final_status": "Échec mise à jour",
                "comment_added": False
            }

    except Exception as e:
        error_msg = f"Exception lors de la mise à jour Monday: {str(e)}"
        logger.error(error_msg, exc_info=True)

        state["results"]["ai_messages"].append(f"❌ Exception lors de la mise à jour Monday.com: {str(e)}")
        state["results"]["ai_messages"].append("⚠️ Erreur technique lors de la mise à jour du ticket")

        state["status"] = WorkflowStatus.FAILED
        state["error"] = error_msg

        state["results"]["monday_update"] = {
            "success": False,
            "error": error_msg,
            "final_status": "Erreur technique",
            "comment_added": False
        }
    
    try:
        monday_item_id = None
        if hasattr(task, 'monday_item_id') and task.monday_item_id:
            monday_item_id = task.monday_item_id
        
        queue_id = state["results"].get("queue_id") or state.get("queue_id")
        
        if monday_item_id and queue_id:
            is_success = state["results"].get("monday_update", {}).get("success", False)
            
            if is_success:
                await workflow_queue_manager.mark_as_completed(monday_item_id, queue_id)
                logger.info(f"✅ Queue libérée après succès du workflow pour item {monday_item_id}")
            else:
                error = state["results"].get("monday_update", {}).get("error", "Unknown error")
                await workflow_queue_manager.mark_as_failed(monday_item_id, queue_id, error)
                logger.info(f"❌ Queue libérée après échec du workflow pour item {monday_item_id}")
        else:
            logger.debug(f"ℹ️ Pas de libération de queue (monday_item_id={monday_item_id}, queue_id={queue_id})")
    
    except Exception as queue_error:    
        logger.error(f"❌ Erreur libération queue: {queue_error}")

    return state


def _determine_final_status(state: GraphState) -> tuple[str, str]:
    """
    Détermine le statut final de la tâche basé sur les résultats.

    Returns:
        Tuple (statut_monday, niveau_succès)
    """
    if state["results"] and state["results"].get("merge_successful", False):
        logger.info("🎉 Merge réussi détecté - Statut forcé à 'Done'")
        return "Done", "success"

    if state["results"] and "monday_final_status" in state["results"]:
        explicit_status = state["results"]["monday_final_status"]
        logger.info(f"📌 Utilisation du statut explicite: {explicit_status}")

        if explicit_status == "Done":
            return "Done", "success"
        elif explicit_status == "Working on it":
            return "Working on it", "partial"
        elif explicit_status == "Stuck":
            return "Stuck", "failed"
        else:
            return explicit_status, "partial"

    current_status = getattr(state, 'status', WorkflowStatus.PENDING)

    if current_status == WorkflowStatus.COMPLETED:
        if state["results"] and "pr_info" in state["results"]:
            return "Working on it", "partial"  
        else:
            return "Working on it", "partial"
    elif current_status == WorkflowStatus.FAILED:
        if state["error"] and any(keyword in state["error"].lower() for keyword in ["git", "clone", "repository"]):
            return "Stuck", "failed"
        elif state["error"] and any(keyword in state["error"].lower() for keyword in ["test", "tests"]):
            return "Stuck", "failed"
        else:
            return "Stuck", "failed"
    else:
        return "Working on it", "partial"


async def _generate_completion_comment(state: GraphState, success_level: str) -> str:
    """
    Génère un commentaire de completion COURT et multilingue pour Monday.com.
    """
    from services.project_language_detector import project_language_detector
    from utils.monday_comment_formatter import MondayCommentFormatter
    
    task = state["task"]
    
    user_language = state.get("user_language", "en")
    
    templates = await project_language_detector.get_monday_reply_template(
        user_language=user_language,
        project_language=user_language  
    )
    
    # SÉCURITÉ: Vérification pour garantir que templates n'est JAMAIS None
    if not templates or not isinstance(templates, dict):
        logger.error(f"❌ CRITIQUE: templates invalide dans update_node ! Type: {type(templates)}")
        templates = {
            'task_completed': 'Task Completed Successfully',
            'task_partial': 'Task Partially Completed',
            'task_failed': 'Task Failed',
            'task_label': 'Task',
            'pr_created': 'PR created',
            'pr_merged': 'PR merged'
        }
    
    creator_tag = ""
    if hasattr(task, 'creator_name') and task.creator_name:
        creator_tag = MondayCommentFormatter.format_creator_tag(task.creator_name)
        if creator_tag:
            creator_tag = f"{creator_tag} "
    
    if success_level == "success":
        header = f"{creator_tag}✅ **{templates.get('task_completed', 'Task Completed Successfully')}**\n\n"
    elif success_level == "partial":
        header = f"{creator_tag}⚠️ **{templates.get('task_partial', 'Task Partially Completed')}**\n\n"
    else:
        header = f"{creator_tag}❌ **{templates.get('task_failed', 'Task Failed')}**\n\n"
    
    message = header
    message += f"**{templates.get('task_label', 'Task')}**: {task.title}\n\n"
    
    if state["results"] and "pr_info" in state["results"]:
        pr_info = state["results"]["pr_info"]
        if isinstance(pr_info, dict) and pr_info.get('pr_url'):
            if state["results"].get("merge_successful", False):
                message += f"- **{templates.get('pr_merged', 'PR merged')}**: {pr_info.get('pr_url')}\n"
            else:
                message += f"- **{templates.get('pr_created', 'PR created')}**: {pr_info.get('pr_url')}\n"
    
    if state["results"] and "browser_qa" in state["results"]:
        browser_qa = state["results"]["browser_qa"]
        
        if browser_qa.get("executed", False):
            message += "\n**🌐 Browser QA Tests:**\n"
            
            tests_total = browser_qa.get("tests_executed", 0)
            tests_passed = browser_qa.get("tests_passed", 0)
            tests_failed = browser_qa.get("tests_failed", 0)
            
            if browser_qa.get("success", False):
                message += f"- ✅ {tests_passed}/{tests_total} tests passed\n"
            else:
                message += f"- ⚠️ {tests_failed}/{tests_total} tests failed\n"
            
            console_errors = browser_qa.get("console_errors", [])
            if console_errors:
                message += f"- 🐛 {len(console_errors)} console error(s) detected\n"
            
            screenshots = browser_qa.get("screenshots", [])
            if screenshots:
                message += f"- 📸 {len(screenshots)} screenshot(s) captured\n"
            
            perf = browser_qa.get("performance_metrics", {})
            if perf and not perf.get("error"):
                load_time = perf.get("load_time_ms", 0)
                if load_time > 0:
                    message += f"- ⚡ Load time: {load_time}ms\n"
    
    return message


async def _update_repository_url_column(state: GraphState, monday_tool: MondayTool, monday_item_id: str) -> None:
    """
    Met à jour la colonne Repository URL avec l'URL de la dernière PR fusionnée.

    Cette fonction :
    1. Récupère l'URL du repository depuis l'état
    2. Récupère la dernière PR fusionnée sur ce repository
    3. Met à jour la colonne Repository URL dans Monday.com
    4. Sauvegarde l'URL en base de données

    Args:
        state: État du workflow
        monday_tool: Instance de l'outil Monday
        monday_item_id: ID de l'item Monday.com
    """
    try:
        from config.settings import get_settings
        settings = get_settings()

        if not settings.monday_repository_url_column_id:
            logger.debug("⏭️ Colonne Repository URL non configurée - mise à jour ignorée")
            return

        repo_url = None
        if hasattr(state["task"], 'repository_url') and state["task"].repository_url:
            repo_url = state["task"].repository_url
        elif state["results"] and "repository_url" in state["results"]:
            repo_url = state["results"]["repository_url"]

        if not repo_url:
            logger.debug("⏭️ Aucune URL de repository trouvée - mise à jour Repository URL ignorée")
            return
        
        if isinstance(repo_url, str):
            import re
            https_match = re.search(r'(https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?)', repo_url)
            if https_match:
                cleaned_url = https_match.group(1)
                if cleaned_url.endswith('.git'):
                    cleaned_url = cleaned_url[:-4]
                if cleaned_url != repo_url:
                    logger.info(f"🧹 URL repository nettoyée pour update: '{repo_url[:50]}...' → '{cleaned_url}'")
                    repo_url = cleaned_url

        logger.info(f"🔄 Mise à jour de la colonne Repository URL pour {repo_url}")

        last_pr_result = await github_pr_service.get_last_merged_pr(repo_url)

        if last_pr_result and last_pr_result.get("success"):
            pr_url = last_pr_result.get("pr_url")
            pr_number = last_pr_result.get("pr_number")
            pr_title = last_pr_result.get("pr_title", "")
            merged_at = last_pr_result.get("merged_at", "")

            repository_url_value = pr_url  

            logger.info(f"📌 Dernière PR fusionnée: #{pr_number} - {pr_title}")
            logger.info(f"🔗 URL à mettre à jour: {pr_url}")

            update_result = await monday_tool._arun(
                action="update_column_value",
                item_id=monday_item_id,
                column_id=settings.monday_repository_url_column_id,
                value=repository_url_value
            )

            if update_result and update_result.get("success"):
                logger.info("✅ Colonne Repository URL mise à jour avec succès")

                save_success = await _save_last_merged_pr_to_database(state, pr_url)
                if not save_success:
                    logger.warning("⚠️ Échec sauvegarde last_merged_pr_url en base (non-bloquant)")

                if "ai_messages" in state["results"]:
                    state["results"]["ai_messages"].append(
                        f"✅ Repository URL mis à jour: PR #{pr_number} fusionnée"
                    )

                state["results"]["repository_url_updated"] = {
                    "success": True,
                    "pr_url": pr_url,
                    "pr_number": pr_number,
                    "merged_at": merged_at
                }
            else:
                error_details = {}
                if update_result:
                    error_details = {
                        "error": update_result.get("error", "Erreur inconnue"),
                        "column_id": settings.monday_repository_url_column_id,
                        "item_id": monday_item_id,
                        "attempted_value": pr_url
                    }
                    error_msg = update_result.get("error", "Erreur inconnue")
                else:
                    error_msg = "Résultat vide de l'API Monday.com"
                    error_details = {"error": "API returned None result"}

                logger.warning(f"⚠️ Échec mise à jour Repository URL: {error_msg}")
                logger.debug(f"🔍 Détails erreur Repository URL: {error_details}")

                if "ai_messages" in state["results"]:
                    state["results"]["ai_messages"].append(
                        f"⚠️ Échec mise à jour Repository URL: {error_msg}"
                    )

                state["results"]["repository_url_error"] = {
                    "success": False,
                    "error": error_msg,
                    "details": error_details,
                    "attempted_url": pr_url
                }
        else:
            logger.info(f"📝 Aucune PR fusionnée trouvée, mise à jour avec l'URL du repository: {repo_url}")

            update_result = await monday_tool._arun(
                action="update_column_value",
                item_id=monday_item_id,
                column_id=settings.monday_repository_url_column_id,
                value=repo_url  
            )

            if update_result and update_result.get("success"):
                logger.info("✅ Colonne Repository URL mise à jour avec l'URL du repository")

                if "ai_messages" in state["results"]:
                    state["results"]["ai_messages"].append(
                        f"📝 Repository URL mis à jour: {repo_url}"
                    )

                state["results"]["repository_url_updated"] = {
                    "success": True,
                    "url": repo_url,
                    "type": "repository_base_url"
                }
            else:
                error_msg = update_result.get("error", "Erreur inconnue") if update_result else "Résultat vide"
                logger.warning(f"⚠️ Échec mise à jour Repository URL: {error_msg}")

    except Exception as e:
        logger.warning(f"⚠️ Erreur lors de la mise à jour de Repository URL: {e}")
        if "ai_messages" in state.get("results", {}):
            state["results"]["ai_messages"].append(
                f"⚠️ Erreur mise à jour Repository URL: {str(e)}"
            )


async def _save_last_merged_pr_to_database(state: GraphState, last_merged_pr_url: str) -> bool:
    """
    Sauvegarde l'URL de la dernière PR fusionnée en base de données.

    Args:
        state: État du workflow contenant le db_run_id
        last_merged_pr_url: URL de la dernière PR fusionnée

    Returns:
        True si sauvegarde réussie, False sinon
    """
    try:
        db_run_id = state.get("db_run_id") or state.get("run_id")

        if not db_run_id:
            logger.warning("⚠️ Aucun db_run_id trouvé - impossible de sauvegarder last_merged_pr_url en base")
            return False

        from services.database_persistence_service import db_persistence

        if not db_persistence.db_manager._is_initialized:
            logger.warning("⚠️ Pool de connexion non initialisé - impossible de sauvegarder last_merged_pr_url")
            return False

        success = await db_persistence.update_last_merged_pr_url(db_run_id, last_merged_pr_url)

        if success:
            logger.info(f"💾 URL dernière PR fusionnée sauvegardée en base: {last_merged_pr_url}")

            if "ai_messages" in state.get("results", {}):
                state["results"]["ai_messages"].append(
                    "💾 Dernière PR fusionnée sauvegardée en base de données"
                )

            return True
        else:
            logger.warning("⚠️ Échec de la sauvegarde de last_merged_pr_url en base")
            return False

    except Exception as e:
        logger.error(f"❌ Erreur lors de la sauvegarde de last_merged_pr_url: {e}")
        return False
