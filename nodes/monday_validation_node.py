"""Nœud de validation humaine via Monday.com updates."""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from models.state import GraphState
from models.schemas import HumanValidationRequest, PullRequestInfo, HumanValidationStatus
from services.monday_validation_service import monday_validation_service
from services.human_validation_service import validation_service as human_validation_service
from tools.monday_tool import MondayTool
from utils.logger import get_logger
from utils.helpers import get_working_directory
from config.langsmith_config import langsmith_config
from config.settings import get_settings
import json

from services.workflow_queue_manager import workflow_queue_manager
from services.slack_notification_service import slack_notification_service

logger = get_logger(__name__)
settings = get_settings()


async def _wait_for_validation_with_reminder(
    monday_validation_service,
    slack_notification_service,
    update_id: str,
    user_slack_id: Optional[str],
    user_email: Optional[str],
    task_title: str,
    task_id: str,
    monday_item_id: str,
    pr_url: Optional[str],
    slack_reminder_seconds: Optional[int],
    final_timeout_seconds: int,
    is_command: bool
):
    """
    Attend une validation humaine avec système de rappel Slack à 2 niveaux.
    
    1. Envoie immédiatement une notification Slack d'attente de validation
    2. Si slack_reminder_seconds est défini: Envoie un rappel timeout après ce délai
    3. Attend jusqu'à final_timeout_seconds pour la vraie réponse
    
    Args:
        monday_validation_service: Service de validation Monday.com
        slack_notification_service: Service d'envoi Slack
        update_id: ID de l'update Monday.com
        user_slack_id: ID Slack de l'utilisateur (optionnel)
        user_email: Email de l'utilisateur (fallback si pas de Slack ID)
        task_title: Titre de la tâche
        task_id: ID de la tâche
        monday_item_id: ID de l'item Monday.com
        pr_url: URL de la Pull Request (optionnel)
        slack_reminder_seconds: Délai avant envoi rappel timeout (None = pas de rappel)
        final_timeout_seconds: Timeout final pour la validation
        is_command: True si c'est une commande (pour le Slack)
        
    Returns:
        HumanValidationResponse ou None
    """
    import asyncio
    
    slack_reminder_sent = False
    start_time = asyncio.get_event_loop().time()
    
    final_timeout_minutes = final_timeout_seconds / 60
    
    if user_slack_id and is_command:
        try:
            logger.info("💬 Envoi notification Slack d'attente de validation...")
            waiting_result = await slack_notification_service.send_validation_waiting_notification(
                user_slack_id=user_slack_id,
                task_title=task_title,
                task_id=task_id,
                monday_item_id=monday_item_id,
                pr_url=pr_url
            )
            
            if waiting_result.get("success"):
                logger.info(f"✅ Notification d'attente envoyée à <@{user_slack_id}>")
            else:
                logger.warning(f"⚠️ Échec notification d'attente: {waiting_result.get('error')}")
        except Exception as e:
            logger.error(f"❌ Erreur envoi notification d'attente Slack: {e}", exc_info=True)
    
    async def send_reminder_slack():
        nonlocal slack_reminder_sent
        if slack_reminder_seconds and user_slack_id and is_command:
            await asyncio.sleep(slack_reminder_seconds)
            
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= slack_reminder_seconds and not slack_reminder_sent:
                logger.info(f"⏰ {slack_reminder_seconds}s écoulées - Envoi rappel timeout Slack...")
                slack_reminder_sent = True
                
                try:
                    slack_result = await slack_notification_service.send_validation_timeout_notification(
                        user_slack_id=user_slack_id,
                        task_title=task_title,
                        task_id=task_id,
                        monday_item_id=monday_item_id,
                        timeout_duration=slack_reminder_seconds
                    )
                    
                    if slack_result.get("success"):
                        logger.info(f"✅ Rappel timeout Slack envoyé à <@{user_slack_id}>")
                    else:
                        logger.warning(f"⚠️ Échec rappel timeout Slack: {slack_result.get('error')}")
                except Exception as e:
                    logger.error(f"❌ Erreur envoi rappel timeout Slack: {e}", exc_info=True)
    
    reminder_task = asyncio.create_task(send_reminder_slack())
    
    try:
        logger.info(f"⏳ Attente validation (timeout final: {final_timeout_minutes:.1f}min)...")
        validation_response = await monday_validation_service.check_for_human_replies(
            update_id=update_id,
            timeout_minutes=final_timeout_minutes
        )
        
        return validation_response
        
    finally:
        if not reminder_task.done():
            reminder_task.cancel()
            try:
                await reminder_task
            except asyncio.CancelledError:
                pass


async def _get_user_email_from_monday(
    monday_item_id: str,
    monday_tool: MondayTool
) -> Optional[str]:
    """
    Récupère l'email de l'utilisateur qui a posté le dernier commentaire @vydata.
    
    Cette fonction cherche l'update la plus récente contenant '@vydata' et 
    récupère l'email de son créateur. C'est cet utilisateur qui recevra 
    l'email de notification en cas de timeout de validation.
    
    Args:
        monday_item_id: ID de l'item Monday.com
        monday_tool: Instance de MondayTool
        
    Returns:
        Email de l'utilisateur qui a posté @vydata, ou None si non trouvé
    """
    try:
        logger.info(f"🔍 Récupération email utilisateur pour item {monday_item_id}...")
        
        query = """
        query ($itemId: [ID!]) {
            items(ids: $itemId) {
                creator {
                    email
                    name
                }
                updates {
                    id
                    body
                    created_at
                    creator {
                        id
                        email
                        name
                    }
                }
            }
        }
        """
        
        variables = {"itemId": [int(monday_item_id)]}
        
        result = await monday_tool._make_request(query, variables)
        
        if result and isinstance(result, dict) and result.get("data", {}).get("items"):
            items = result["data"]["items"]
            if items and len(items) > 0:
                item = items[0]
                updates = item.get("updates", [])
                
                logger.info(f"🔍 Recherche de @vydata parmi {len(updates)} updates...")
                
                for update in reversed(updates):  
                    body = update.get("body", "")
                    if "@vydata" in body.lower():
                        creator = update.get("creator", {})
                        email = creator.get("email")
                        name = creator.get("name", "Unknown")
                        
                        if email:
                            logger.info(f"✅ Email trouvé du créateur de l'update @vydata: {email} ({name})")
                            return email
                        else:
                            logger.warning(f"⚠️ Update @vydata trouvée mais sans email pour {name}")
                
                item_creator = item.get("creator", {})
                if item_creator.get("email"):
                    email = item_creator["email"]
                    logger.info(f"ℹ️  Fallback 1: Email du créateur de l'item: {email}")
                    return email
                
                logger.info(f"🔍 Fallback 2: Récupération des subscribers de l'item")
                subscribers = item.get("subscribers", [])
                if subscribers:
                    logger.info(f"📋 {len(subscribers)} subscriber(s) trouvé(s)")
                    for subscriber in subscribers:
                        sub_email = subscriber.get("email")
                        if sub_email:
                            logger.info(f"✅ Email subscriber trouvé: {sub_email}")
                            return sub_email
                
                logger.warning(f"⚠️ Aucune update @vydata, créateur ni subscriber avec email")
        else:
            logger.warning(f"⚠️ Pas d'items retournés - tentative query enrichie")
            
            try:
                enriched_query = """
                query ($itemId: [ID!]) {
                    items(ids: $itemId) {
                        creator {
                            email
                            name
                        }
                        subscribers {
                            email
                            name
                        }
                    }
                }
                """
                
                enriched_result = await monday_tool._make_request(enriched_query, variables)
                
                if enriched_result and isinstance(enriched_result, dict) and enriched_result.get("data", {}).get("items"):
                    item = enriched_result["data"]["items"][0]
                    
                    creator = item.get("creator", {})
                    if creator.get("email"):
                        logger.info(f"✅ Email créateur via query enrichie: {creator['email']}")
                        return creator["email"]
                    
                    subscribers = item.get("subscribers", [])
                    for sub in subscribers:
                        if sub.get("email"):
                            logger.info(f"✅ Email subscriber via query enrichie: {sub['email']}")
                            return sub["email"]
                            
            except Exception as fallback_err:
                logger.warning(f"⚠️ Erreur fallback query enrichie: {fallback_err}")
        
        logger.warning(f"⚠️ Aucun email trouvé pour l'item {monday_item_id}")
        return None
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération email utilisateur: {e}", exc_info=True)
        return None


async def _get_user_slack_id_from_monday(
    monday_item_id: str,
    monday_tool: MondayTool,
    slack_notification_service
) -> tuple[Optional[str], Optional[str]]:
    """
    Récupère l'ID Slack et l'email de l'utilisateur qui a posté le dernier commentaire @vydata.
    
    Stratégie:
    1. Récupère l'email depuis Monday.com
    2. Utilise l'API Slack pour trouver l'utilisateur par email
    3. Retourne (slack_id, email)
    
    Args:
        monday_item_id: ID de l'item Monday.com
        monday_tool: Instance de MondayTool
        slack_notification_service: Service Slack pour lookup
        
    Returns:
        Tuple (slack_user_id, email) ou (None, None) si non trouvé
    """
    try:
        user_email = await _get_user_email_from_monday(monday_item_id, monday_tool)
        
        if not user_email:
            logger.warning(f"⚠️ Aucun email trouvé pour item {monday_item_id}")
            return None, None
        
        logger.info(f"🔍 Recherche ID Slack pour email: {user_email}")
        slack_user_id = await slack_notification_service.get_user_id_by_email(user_email)
        
        if slack_user_id:
            logger.info(f"✅ ID Slack trouvé: {slack_user_id} pour {user_email}")
            return slack_user_id, user_email
        else:
            logger.warning(f"⚠️ Aucun utilisateur Slack trouvé pour {user_email}")
            return None, user_email
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération ID Slack: {e}", exc_info=True)
        return None, None


def _convert_test_results_to_dict(test_results) -> Optional[Dict[str, Any]]:
    """
    Convertit test_results en dictionnaire compatible avec HumanValidationRequest.
    
    Args:
        test_results: Peut être une liste ou un dictionnaire
        
    Returns:
        Dictionnaire structuré ou None
    """
    if not test_results:
        return None
    
    if isinstance(test_results, dict):
        return test_results
    
    if isinstance(test_results, list):
        return {
            "tests": test_results,
            "count": len(test_results),
            "summary": f"{len(test_results)} test(s) exécuté(s)",
            "success": all(
                test.get("success", False) if isinstance(test, dict) else False 
                for test in test_results
            )
        }
    
    return {"raw": str(test_results), "type": str(type(test_results))}


async def monday_human_validation(state: GraphState) -> GraphState:
    """
    Nœud de validation humaine via Monday.com.
    
    Ce nœud :
    1. Poste une update dans Monday.com avec les résultats
    2. Attend une reply humaine ("oui"/"non") 
    3. Analyse la réponse avec IA intelligente
    4. Détermine la suite du workflow (merge ou debug)
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec la décision humaine
    """
    logger.info(f"🤝 Validation humaine Monday.com pour: {state['task'].title}")
    
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []
    
    state["results"]["ai_messages"].append("🤝 Posting update de validation dans Monday.com...")
    
    try:
        if not hasattr(monday_validation_service.monday_tool, 'api_token') or not monday_validation_service.monday_tool.api_token:
            logger.info("💡 Monday.com non configuré - validation humaine automatiquement approuvée")
            state["results"]["human_decision"] = "approved"
            state["results"]["human_reply"] = "Auto-approuvé (Monday.com non configuré)"
            state["results"]["validation_skipped"] = "Configuration Monday.com manquante"
            return state
        
        # _prepare_workflow_results garantit de toujours retourner un dict valide (jamais None)
        workflow_results = _prepare_workflow_results(state)
        
        if "validation_id" in state.get("results", {}):
            workflow_results["validation_id"] = state["results"]["validation_id"]
        
        try:
            validation_id = f"val_{state['task'].task_id}_{int(datetime.now().timestamp())}"
            
            pr_info_obj = None
            pr_info_dict = workflow_results.get("pr_info") or state.get("results", {}).get("pr_info")
            if pr_info_dict:
                pr_info_obj = PullRequestInfo(
                    number=pr_info_dict.get("number", 0) if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "number", 0),
                    title=pr_info_dict.get("title", "") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "title", ""),
                    url=pr_info_dict.get("url", "") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "url", ""),
                    branch=pr_info_dict.get("branch", "") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "branch", ""),
                    base_branch=pr_info_dict.get("base_branch", "main") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "base_branch", "main"),
                    status=pr_info_dict.get("status", "open") if isinstance(pr_info_dict, dict) else getattr(pr_info_dict, "status", "open"),
                    created_at=datetime.now()
                )
            
            modified_files_raw = workflow_results.get("modified_files", [])
            generated_code = {}
            code_changes = state.get("results", {}).get("code_changes", {})
            if code_changes:
                generated_code = code_changes
            
            if isinstance(modified_files_raw, dict):
                modified_files = list(modified_files_raw.keys())
                logger.info(f"✅ Conversion dict -> list pour files_modified: {len(modified_files)} fichiers")
            elif isinstance(modified_files_raw, list):
                modified_files = modified_files_raw
            else:
                modified_files = []
                logger.warning(f"⚠️ Type inattendu pour modified_files: {type(modified_files_raw)}")
            
            generated_code_dict = generated_code if generated_code else {"summary": "Code généré - voir fichiers modifiés"}
            generated_code_str = json.dumps(
                generated_code_dict,
                ensure_ascii=False,
                indent=2
            )
            logger.info(f"✅ Conversion generated_code dict -> JSON string ({len(generated_code_str)} caractères)")            
            test_results_dict = _convert_test_results_to_dict(workflow_results.get("test_results"))
            test_results_str = json.dumps(
                test_results_dict if test_results_dict else {},
                ensure_ascii=False,
                indent=2
            )
            logger.info(f"✅ Conversion test_results dict -> JSON string ({len(test_results_str)} caractères)")
            
            if pr_info_obj:
                pr_info_str = json.dumps(
                    pr_info_obj.model_dump() if hasattr(pr_info_obj, 'model_dump') else pr_info_obj.dict(),
                    ensure_ascii=False,
                    indent=2,
                    default=str  
                )
                logger.info(f"✅ Conversion pr_info object -> JSON string ({len(pr_info_str)} caractères)")
            else:
                pr_info_str = None
            
            display_task_id = str(state["task"].monday_item_id) if hasattr(state["task"], 'monday_item_id') and state["task"].monday_item_id else str(state["task"].task_id)
            
            validation_request = HumanValidationRequest(
                validation_id=validation_id,
                workflow_id=state.get("workflow_id", ""),
                task_id=display_task_id,  
                task_title=state["task"].title,  
                generated_code=generated_code_str,  
                code_summary=f"Implémentation de: {state['task'].title}",
                files_modified=modified_files,
                original_request=state["task"].description or state["task"].title,
                implementation_notes="\n".join(workflow_results.get("ai_messages", [])[-5:]),  
                test_results=test_results_str,  
                pr_info=pr_info_str,  
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=10),  
                requested_by="ai_agent"
            )
            
            if not human_validation_service.db_pool:
                await human_validation_service.init_db_pool()
            
            task_id_int = state.get("db_task_id")
            
            if not task_id_int:
                logger.warning(f"⚠️ db_task_id manquant dans state - tentative récupération depuis DB")
                monday_item_id = state["task"].monday_item_id if hasattr(state["task"], 'monday_item_id') else state["task"].task_id
                
                if human_validation_service.db_pool:
                    try:
                        async with human_validation_service.db_pool.acquire() as conn:
                            task_id_int = await conn.fetchval("""
                                SELECT tasks_id FROM tasks WHERE monday_item_id = $1
                            """, int(monday_item_id))
                            
                            if task_id_int:
                                logger.info(f"✅ task_id récupéré depuis DB: {task_id_int} (monday_item_id={monday_item_id})")
                                state["db_task_id"] = task_id_int
                            else:
                                logger.error(f"❌ Aucune tâche trouvée pour monday_item_id={monday_item_id}")
                    except Exception as e:
                        logger.error(f"❌ Erreur récupération task_id depuis DB: {e}")
                        
            if not task_id_int:
                logger.error(f"❌ Impossible de déterminer task_id - skip sauvegarde validation en DB")
                task_id_int = None  
            
            task_run_id_int = state.get("db_run_id")
            run_step_id = state.get("current_step_id") or state.get("db_step_id")
            
            if task_id_int:
                success = await human_validation_service.create_validation_request(
                    validation_request=validation_request,
                    task_id=task_id_int,
                    task_run_id=task_run_id_int,
                    run_step_id=run_step_id
                )
                
                if success:
                    logger.info(f"✅ Validation {validation_id} créée en base de données")
                    state["results"]["validation_id"] = validation_id
                    workflow_results["validation_id"] = validation_id  
                    state["results"]["ai_messages"].append(f"✅ Validation {validation_id} sauvegardée en DB")
                else:
                    logger.warning(f"⚠️ Échec sauvegarde validation {validation_id} en DB - continuation du workflow")
            else:
                logger.warning(f"⚠️ task_id manquant - skip sauvegarde validation en DB, workflow continue")
                
        except Exception as db_error:
            logger.error(f"❌ Erreur lors de la création de validation en DB: {db_error}")
            state["results"]["ai_messages"].append(f"⚠️ Erreur DB validation: {str(db_error)}")
        
        monday_item_id = str(state["task"].monday_item_id) if state["task"].monday_item_id else state["task"].task_id
        logger.info(f"📝 Posting update de validation pour item Monday.com {monday_item_id}")
        
        creator_name = None
        task = state["task"]
        if hasattr(task, 'creator_name') and task.creator_name:
            creator_name = task.creator_name
            logger.info(f"👤 Creator_name trouvé dans task: {creator_name}")
        else:
            logger.info(f"🔍 Creator_name absent du task, récupération depuis Monday.com...")
            try:
                monday_tool = MondayTool()
                item_info = await monday_tool._arun(action="get_item_info", item_id=monday_item_id)
                if item_info and isinstance(item_info, dict) and item_info.get("success") and item_info.get("creator_name"):
                    creator_name = item_info.get("creator_name")
                    logger.info(f"✅ Creator_name récupéré depuis Monday.com: {creator_name}")
                else:
                    logger.debug("ℹ️  Creator_name non disponible dans Monday.com")
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors de la récupération du creator_name: {e}")
        
        user_language = state.get("user_language")
        
        if not user_language:
            task = state.get("task")
            if task:
                if hasattr(task, 'user_language'):
                    user_language = task.user_language
                elif hasattr(task, '__dict__') and 'user_language' in task.__dict__:
                    user_language = task.__dict__['user_language']
        
        if not user_language:
            task_context = state.get("task_context", {})
            # SÉCURITÉ: task_context peut être None si explicitement défini à None dans state
            if task_context and isinstance(task_context, dict):
                user_language = task_context.get("user_language")
            else:
                logger.warning(f"⚠️ task_context invalide: {type(task_context)}")
                user_language = None
        
        if not user_language:
            logger.warning("⚠️ Aucune langue utilisateur trouvée, fallback vers 'en'")
            user_language = 'en'  # Default final
        
        logger.info(f"🌍 Langue utilisateur pour validation Monday.com: {user_language}")
        
        try:
            logger.info(f"🔍 DEBUG: Appel post_validation_update avec workflow_results type={type(workflow_results)}")
            logger.info(f"🔍 DEBUG: workflow_results is None? {workflow_results is None}")
            logger.info(f"🔍 DEBUG: creator_name={creator_name}, user_language={user_language}")
            
            update_id = await monday_validation_service.post_validation_update(
                item_id=monday_item_id,
                workflow_results=workflow_results,
                creator_name=creator_name,
                user_language=user_language
            )
            
            logger.info(f"🔍 DEBUG: post_validation_update retourné update_id={update_id} (type={type(update_id)})")
            
            if not isinstance(update_id, str):
                logger.error(f"❌ Update ID invalide (type {type(update_id)}): {update_id}")
                raise Exception(f"Update ID invalide: attendu str, reçu {type(update_id)}")
                
        except Exception as post_error:
            logger.error(f"❌ Erreur lors du post validation update: {str(post_error)}", exc_info=True)
            logger.error(f"❌ Type de l'exception: {type(post_error).__name__}")
            logger.error(f"❌ Traceback complet de l'erreur ci-dessus")
            update_id = f"failed_update_{monday_item_id}"
            state["results"]["validation_error"] = str(post_error)
            state["results"]["ai_messages"].append(f"❌ Erreur validation Monday.com: {str(post_error)}")
        
        state["results"]["validation_update_id"] = update_id
        state["results"]["ai_messages"].append(f"✅ Update de validation postée: {update_id}")
        
        if langsmith_config.client:
            try:
                display_item_id = str(state["task"].monday_item_id) if hasattr(state["task"], 'monday_item_id') and state["task"].monday_item_id else str(state["task"].task_id)
                
                langsmith_config.client.create_run(
                    name="monday_validation_update_posted",
                    run_type="tool",
                    inputs={
                        "item_id": display_item_id,  
                        "task_title": state["task"].title,
                        "update_id": update_id,
                        "workflow_results": workflow_results
                    },
                    outputs={
                        "status": "waiting_for_human_reply",
                        "update_posted": True
                    },
                    session_name=state.get("langsmith_session"),
                    extra={
                        "workflow_id": state.get("workflow_id"),
                        "monday_validation": True
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        logger.info(f"⏳ Attente de reply humaine sur update {update_id}...")
        state["results"]["ai_messages"].append("⏳ En attente de reply humaine dans Monday.com...")
        
        try:
            monday_item_id = state["task"].monday_item_id if hasattr(state["task"], 'monday_item_id') else None
            queue_id = state["results"].get("queue_id") or state.get("queue_id")
            
            if monday_item_id and queue_id:
                await workflow_queue_manager.mark_as_waiting_validation(monday_item_id, queue_id)
                logger.info(f"⏸️ Queue notifiée de l'attente de validation pour item {monday_item_id}")
        except Exception as queue_error:
            logger.error(f"❌ Erreur notification queue: {queue_error}")
        
        is_command = state.get("results", {}).get("is_command", True)  
        is_reactivation = state["task"].is_reactivation if hasattr(state["task"], 'is_reactivation') else False
        
        slack_reminder_seconds = settings.validation_timeout_command  
        final_timeout_seconds = settings.validation_timeout_question  
        
        if is_command or is_reactivation:
            timeout_type = "COMMANDE"
            logger.info(f"⏰ Type: {timeout_type}")
            logger.info(f"   💬 Notification Slack immédiate + rappel timeout après: {slack_reminder_seconds}s")
            logger.info(f"   ⏱️  Timeout final: {final_timeout_seconds}s ({final_timeout_seconds/60:.0f}min)")
        else:
            timeout_type = "QUESTION"
            slack_reminder_seconds = None
            logger.info(f"⏰ Type: {timeout_type} → Timeout: {final_timeout_seconds}s ({final_timeout_seconds/60:.0f}min)")
        
        user_slack_id = None
        user_email = None
        if is_command or is_reactivation:
            try:
                user_slack_id, user_email = await _get_user_slack_id_from_monday(
                    monday_item_id=str(monday_item_id),
                    monday_tool=monday_validation_service.monday_tool,
                    slack_notification_service=slack_notification_service
                )
                if user_slack_id:
                    logger.info(f"💬 ID Slack utilisateur récupéré: {user_slack_id} ({user_email})")
                elif user_email:
                    logger.warning(f"⚠️ Email trouvé ({user_email}) mais pas de compte Slack - pas de notification")
                else:
                    logger.warning("⚠️ Aucun utilisateur trouvé - pas de notification Slack")
            except Exception as slack_error:
                logger.error(f"❌ Erreur récupération ID Slack: {slack_error}")
        
        pr_url = None
        pr_info = state.get("results", {}).get("pr_info")
        if pr_info:
            if isinstance(pr_info, dict):
                pr_url = pr_info.get("pr_url") or pr_info.get("url")
            else:
                pr_url = getattr(pr_info, "url", None) or getattr(pr_info, "pr_url", None)
        
        validation_response = await _wait_for_validation_with_reminder(
            monday_validation_service=monday_validation_service,
            slack_notification_service=slack_notification_service,
            update_id=update_id,
            user_slack_id=user_slack_id,
            user_email=user_email,
            task_title=state["task"].title,
            task_id=str(state.get("db_task_id", "N/A")),
            monday_item_id=str(monday_item_id),
            pr_url=pr_url,
            slack_reminder_seconds=slack_reminder_seconds,
            final_timeout_seconds=final_timeout_seconds,
            is_command=(is_command or is_reactivation)
        )
        
        is_timeout = (
            validation_response is None or 
            (hasattr(validation_response, 'status') and 
             validation_response.status == HumanValidationStatus.EXPIRED)
        )
        
        if is_timeout:
            logger.warning("⏰ Timeout final atteint - Application mode automatique")
            logger.info(f"ℹ️  Rappel timeout Slack déjà envoyé après {slack_reminder_seconds}s" if slack_reminder_seconds else "ℹ️  Aucun rappel timeout (Question)")
            
            results = state.get("results", {})
            
            test_results = results.get("test_results", [])
            if isinstance(test_results, list) and test_results:
                last_test = test_results[-1]
                if isinstance(last_test, dict):
                    has_tests_success = last_test.get("success", True)
                elif hasattr(last_test, 'success'):
                    has_tests_success = last_test.success
                else:
                    has_tests_success = True
            else:
                has_tests_success = True  
            
            has_critical_error = len(results.get("error_logs", [])) > 0
            has_modified_files = len(results.get("modified_files", [])) > 0
            
            auto_approve = (
                has_tests_success and 
                not has_critical_error and 
                has_modified_files
            )
            
            if auto_approve:
                logger.info("✅ Validation automatique approuvée (critères remplis)")
                state["results"]["monday_validation"] = {
                    "human_decision": "approve_auto",
                    "timeout": True,
                    "auto_approved": True,
                    "reason": "Tests passent, pas d'erreur critique, fichiers modifiés"
                }
                state["results"]["ai_messages"].append("✅ Validation automatique: Critères de qualité remplis")
            else:
                logger.warning("⚠️ Validation automatique rejetée (critères non remplis)")
                state["results"]["monday_validation"] = {
                    "human_decision": "timeout", 
                    "timeout": True,
                    "auto_approved": False,
                    "reason": f"Tests: {has_tests_success}, Erreurs: {has_critical_error}, Fichiers: {has_modified_files}"
                }
                state["results"]["ai_messages"].append("⚠️ Validation expirée - update Monday.com seulement")
        else:
            state["results"]["validation_response"] = validation_response
            
            status_value = validation_response.status.value if hasattr(validation_response.status, 'value') else str(validation_response.status)
            state["results"]["human_validation_status"] = status_value
            
            logger.info(f"📊 Statut de validation reçu: '{status_value}' (type: {type(validation_response.status)})")
            
            if status_value in ["approve", "approved", "APPROVED"]:
                logger.info("✅ Code approuvé par l'humain via Monday.com")
                state["results"]["ai_messages"].append("✅ Code approuvé - Préparation du merge...")
                state["results"]["should_merge"] = True
                state["results"]["human_decision"] = "approved"
                
                if user_slack_id:
                    try:
                        logger.info("💬 Envoi notification Slack de succès...")
                        success_result = await slack_notification_service.send_task_success_notification(
                            user_slack_id=user_slack_id,
                            task_title=state["task"].title,
                            monday_item_id=str(monday_item_id),
                            pr_url=pr_url,
                            merged=True  
                        )
                        
                        if success_result.get("success"):
                            logger.info(f"✅ Notification de succès envoyée à <@{user_slack_id}>")
                        else:
                            logger.warning(f"⚠️ Échec notification de succès: {success_result.get('error')}")
                    except Exception as e:
                        logger.error(f"❌ Erreur envoi notification de succès Slack: {e}", exc_info=True)
                
            elif status_value in ["reject", "rejected", "REJECTED", "debug"]:
                rejection_count = validation_response.rejection_count
                should_retry = getattr(validation_response, 'should_retry_workflow', False)
                modification_instructions = getattr(validation_response, 'modification_instructions', None)
                
                if should_retry:
                    logger.info(f"🔄 Rejet avec relance demandé ({rejection_count}/3) via Monday.com")
                    state["results"]["ai_messages"].append(f"🔄 Rejet {rejection_count}/3 - Relance du workflow avec instructions")
                    state["results"]["should_merge"] = False
                    state["results"]["human_decision"] = "rejected_with_retry"
                    state["results"]["rejection_count"] = rejection_count
                    state["results"]["modification_instructions"] = modification_instructions
                    state["results"]["should_retry_workflow"] = True
                    
                    if modification_instructions:
                        state["results"]["ai_messages"].append(f"📝 Instructions: {modification_instructions[:200]}")
                        
                        try:
                            import re
                            clean_instructions = re.sub(r'<[^>]+>', '', modification_instructions)
                            
                            # Message personnalisé et court
                            retry_message = f"""🔄 **Rejet avec instructions pris en compte**

Oh, nous avons bien pris en compte votre rejet et vos instructions de modification ! 

📝 **Vos instructions**: {clean_instructions}

🤖 Notre agent est en train de **ré-implémenter** la solution en tenant compte de vos remarques.

⏳ **Veuillez patienter** quelques instants pendant que nous appliquons vos modifications...

Une nouvelle Pull Request sera créée et soumise à votre validation."""
                            
                            monday_tool = MondayTool()
                            
                            logger.info(f"📝 Posting message de ré-implémentation pour item {monday_item_id}")
                            await monday_tool._arun(
                                action="add_update",
                                item_id=monday_item_id,
                                update_text=retry_message
                            )
                            logger.info("✅ Message de ré-implémentation posté dans Monday.com")
                            
                            state["results"]["reimplementation_message_posted"] = True
                            logger.info("✅ Flag reimplementation_message_posted défini - le message générique sera skippé")
                        except Exception as post_error:
                            logger.warning(f"⚠️ Erreur posting message de ré-implémentation: {post_error}")
                else:
                    logger.info("🔧 Debug demandé par l'humain via Monday.com (sans relance)")
                    state["results"]["ai_messages"].append(f"🔧 Debug demandé: {validation_response.comments}")
                    state["results"]["should_merge"] = False
                    state["results"]["human_decision"] = "rejected"
                    state["results"]["debug_request"] = validation_response.comments
                    
            elif status_value in ["abandoned", "ABANDONED"]:
                logger.warning("⛔ Workflow abandonné par l'humain via Monday.com")
                state["results"]["ai_messages"].append("⛔ Workflow abandonné - Arrêt complet")
                state["results"]["should_merge"] = False
                state["results"]["human_decision"] = "abandoned"
                state["results"]["workflow_terminated"] = True
                
            elif status_value in ["expired", "EXPIRED", "timeout"]:
                logger.warning("⏰ Validation expirée - timeout atteint")
                state["results"]["ai_messages"].append("⏰ Validation expirée - update Monday.com seulement")
                state["results"]["should_merge"] = False
                state["results"]["human_decision"] = "timeout"
                
            else:
                logger.warning(f"⚠️ Statut de validation inconnu: {status_value}")
                state["results"]["ai_messages"].append(f"⚠️ Statut inconnu: {status_value} - Workflow arrêté")
                state["results"]["should_merge"] = False
                state["results"]["human_decision"] = "error"
            
            try:
                db_validation_id = state.get("results", {}).get("validation_id")
                
                if not db_validation_id:
                    logger.info("ℹ️ Pas de validation_id en DB - la validation n'a pas été sauvegardée initialement, skip sauvegarde réponse")
                elif validation_response:
                    if not human_validation_service.db_pool:
                        await human_validation_service.init_db_pool()
                    
                    validation_response.validation_id = db_validation_id
                    
                    response_saved = await human_validation_service.submit_validation_response(
                        validation_id=db_validation_id,
                        response=validation_response
                    )
                    
                    if response_saved:
                        logger.info(f"✅ Réponse validation {db_validation_id} sauvegardée en DB")
                        state["results"]["ai_messages"].append("✅ Réponse validation sauvegardée en DB")
                    else:
                        logger.warning(f"⚠️ Échec sauvegarde réponse validation en DB")
                else:
                    logger.warning("⚠️ Aucune réponse de validation à sauvegarder")
                        
            except Exception as db_error:
                logger.error(f"❌ Erreur sauvegarde réponse validation en DB: {db_error}")
                state["results"]["ai_messages"].append(f"⚠️ Erreur DB réponse: {str(db_error)}")
                
        if langsmith_config.client and validation_response:
            try:
                langsmith_config.client.create_run(
                    name="monday_validation_response_received",
                    run_type="tool",
                    inputs={
                        "update_id": update_id,
                        "response_status": validation_response.status.value,
                        "human_comments": validation_response.comments
                    },
                    outputs={
                        "should_merge": state["results"].get("should_merge", False),
                        "human_decision": state["results"].get("human_decision", "error")
                    },
                    session_name=state.get("langsmith_session"),
                    extra={
                        "workflow_id": state.get("workflow_id"),
                        "monday_validation": True,
                        "validated_by": validation_response.validated_by
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
        
        logger.info(f"🤝 Validation Monday.com terminée: {state['results'].get('human_decision', 'error')}")
        
    except Exception as e:
        error_msg = f"Erreur validation Monday.com: {str(e)}"
        logger.error(f"❌ {error_msg}")
        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ {error_msg}")
        state["results"]["should_merge"] = False
        state["results"]["human_decision"] = "error"
    
    return state


def _prepare_workflow_results(state: GraphState) -> Dict[str, Any]:
    """Prépare les résultats du workflow pour l'update de validation.
    
    Cette fonction ne retourne JAMAIS None - elle retourne toujours un dict valide.
    """
    
    try:
        task = state["task"]
        results = state.get("results", {})
        
        success_level = "unknown"
        if results.get("test_results"):
            test_results = results["test_results"]
            if isinstance(test_results, list) and test_results:
                last_test = test_results[-1]
                if isinstance(last_test, dict):
                    success_level = "success" if last_test.get("success") else "partial"
                elif hasattr(last_test, 'success'):
                    success_level = "success" if last_test.success else "partial"
                else:
                    success_level = "partial"
            elif isinstance(test_results, dict):
                success_level = "success" if test_results.get("success") else "partial"
            elif hasattr(test_results, 'success'):
                success_level = "success" if test_results.success else "partial"
            else:
                success_level = "partial"
        elif results.get("error_logs") and len(results["error_logs"]) > 0:
            success_level = "failed"
        else:
            success_level = "partial"
        
        pr_url = None
        if results.get("pr_info"):
            pr_info = results["pr_info"]
            if isinstance(pr_info, dict):
                pr_url = pr_info.get("pr_url") or pr_info.get("url")
            else:
                pr_url = getattr(pr_info, "url", None) or getattr(pr_info, "pr_url", None)
        
        workflow_analysis = _analyze_workflow_completion(state, task, results, pr_url)
        
        workflow_results = {
            "task_title": state["task"].title,  
            "task_id": task.task_id,
            "success_level": success_level,
            "workflow_id": state.get("workflow_id"),
            
            "environment_path": workflow_analysis["environment"]["path"],
            "environment_valid": workflow_analysis["environment"]["is_valid"],
            "modified_files": workflow_analysis["implementation"]["modified_files"],
            "implementation_success": workflow_analysis["implementation"]["success"],
            "implementation_details": workflow_analysis["implementation"]["details"],
            
            "test_executed": workflow_analysis["testing"]["executed"],
            "test_success": workflow_analysis["testing"]["success"],
            "test_results": workflow_analysis["testing"]["results"],
            "test_summary": workflow_analysis["testing"]["summary"],
            
            "pr_created": workflow_analysis["pr"]["created"],
            "pr_url": workflow_analysis["pr"]["url"],
            "pr_status": workflow_analysis["pr"]["status"],
            
            "workflow_metrics": workflow_analysis["metrics"],
            "error_logs": results.get("error_logs", []),
            "error_summary": workflow_analysis["errors"]["summary"],
            "ai_messages": results.get("ai_messages", []),
            
            "duration_info": workflow_analysis["duration"],
            "completed_nodes": state.get("completed_nodes", []),
            "workflow_stage": results.get("workflow_stage", "unknown"),
            
            "overall_success": workflow_analysis["overall"]["success"],
            "completion_score": workflow_analysis["overall"]["score"],
            "recommendations": workflow_analysis["overall"]["recommendations"]
        }
        
        return workflow_results
        
    except Exception as e:
        logger.error(f"❌ Erreur dans _prepare_workflow_results: {e}", exc_info=True)
        # Retourner un dictionnaire minimal pour éviter l'erreur 'NoneType' object has no attribute 'get'
        return {
            "task_title": state.get("task", {}).title if hasattr(state.get("task", {}), 'title') else "Tâche sans titre",
            "task_id": "unknown",
            "success_level": "error",
            "workflow_id": state.get("workflow_id", "unknown"),
            "environment_path": "Non disponible",
            "environment_valid": False,
            "modified_files": [],
            "implementation_success": False,
            "implementation_details": {},
            "test_executed": False,
            "test_success": False,
            "test_results": {},
            "test_summary": "Erreur lors de la préparation des résultats",
            "pr_created": False,
            "pr_url": None,
            "pr_status": "error",
            "workflow_metrics": {},
            "error_logs": [f"Erreur dans _prepare_workflow_results: {str(e)}"],
            "error_summary": {"severity": "critical", "total": 1},
            "ai_messages": [],
            "duration_info": {},
            "completed_nodes": [],
            "workflow_stage": "error",
            "overall_success": False,
            "completion_score": 0,
            "recommendations": ["Corriger l'erreur de préparation des résultats"]
        }


def _analyze_workflow_completion(state: Dict[str, Any], task: Any, results: Dict[str, Any], pr_url: Optional[str]) -> Dict[str, Any]:
    """
    Analyse complète et robuste de l'état d'achèvement du workflow.
    
    Cette fonction effectue une validation approfondie de tous les aspects du workflow
    pour générer des métriques fiables et des recommandations.
    
    Args:
        state: État complet du workflow
        task: Objet tâche
        results: Résultats du workflow
        pr_url: URL de la pull request si créée
        
    Returns:
        Analyse structurée avec toutes les métriques et validations
    """
    from datetime import datetime
    
    analysis = {
        "environment": {},
        "implementation": {},
        "testing": {},
        "pr": {},
        "metrics": {},
        "errors": {},
        "duration": {},
        "overall": {}
    }
    
    try:
        working_dir = get_working_directory(state)
        analysis["environment"] = {
            "path": working_dir if working_dir and working_dir != "Non disponible" else None,
            "is_valid": bool(working_dir and working_dir != "Non disponible"),
            "source": "helper_function"
        }
        
        modified_files = results.get("modified_files", [])
        code_changes = results.get("code_changes", {})
        impl_success = results.get("implementation_success", False)
        impl_metrics = results.get("implementation_metrics", {})
        
        analysis["implementation"] = {
            "success": impl_success,
            "modified_files": modified_files,
            "files_count": len(modified_files),
            "code_changes_count": len(code_changes),
            "details": {
                "has_code_changes": len(code_changes) > 0,
                "has_modified_files": len(modified_files) > 0,
                "metrics": impl_metrics,
                "consistency_check": _validate_implementation_consistency(modified_files, code_changes, impl_success)
            }
        }
        
        test_results = results.get("test_results", [])
        test_success = results.get("test_success", False)
        
        analysis["testing"] = _analyze_testing_results(test_results, test_success, results)
        
        analysis["pr"] = {
            "created": bool(pr_url),
            "url": pr_url,
            "status": "created" if pr_url else "not_created",
            "validation": _validate_pr_creation(pr_url, impl_success, modified_files)
        }
        
        analysis["metrics"] = _calculate_workflow_metrics(state, results)
        
        error_logs = results.get("error_logs", [])
        analysis["errors"] = {
            "count": len(error_logs),
            "has_errors": len(error_logs) > 0,
            "summary": _categorize_errors(error_logs),
            "critical_errors": [err for err in error_logs if "critique" in err.lower() or "critical" in err.lower()]
        }
        
        analysis["duration"] = _calculate_duration_info(state)
        
        analysis["overall"] = _calculate_overall_success(analysis, impl_success, test_success)
        
    except Exception as e:
        logger.error(f"❌ Erreur analyse workflow completion: {e}")
        analysis = _create_fallback_analysis(state, results, pr_url, str(e))
    
    return analysis


def _validate_implementation_consistency(modified_files: list, code_changes: dict, impl_success: bool) -> Dict[str, Any]:
    """Valide la cohérence entre les différents indicateurs d'implémentation."""
    return {
        "files_vs_changes_consistent": len(modified_files) == len(code_changes),
        "success_vs_changes_consistent": impl_success == (len(modified_files) > 0 or len(code_changes) > 0),
        "has_actual_work": len(modified_files) > 0 or len(code_changes) > 0,
        "potential_issues": []
    }


def _analyze_testing_results(test_results: list, test_success: bool, results: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse sophistiquée des résultats de tests."""
    return {
        "executed": len(test_results) > 0 or bool(results.get("test_executed")),
        "success": test_success,
        "results": test_results,
        "count": len(test_results),
        "summary": f"{len(test_results)} test(s) exécuté(s)" if test_results else "Aucun test exécuté",
        "details": {
            "has_results": len(test_results) > 0,
            "success_rate": _calculate_test_success_rate(test_results),
            "test_types": _identify_test_types(test_results)
        }
    }


def _validate_pr_creation(pr_url: Optional[str], impl_success: bool, modified_files: list) -> Dict[str, Any]:
    """Valide la logique de création de PR."""
    return {
        "should_have_pr": impl_success and len(modified_files) > 0,
        "has_pr": bool(pr_url),
        "consistent": bool(pr_url) == (impl_success and len(modified_files) > 0),
        "recommendation": "PR expected" if (impl_success and len(modified_files) > 0) else "No PR needed"
    }


def _calculate_workflow_metrics(state: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule des métriques avancées sur le workflow."""
    return {
        "workflow_id": state.get("workflow_id", "unknown"),
        "nodes_completed": len(state.get("completed_nodes", [])),
        "ai_messages_count": len(results.get("ai_messages", [])),
        "workflow_stage": results.get("workflow_stage", "unknown"),
        "has_monitoring": bool(state.get("monitoring_enabled")),
        "execution_environment": "production" if "prod" in str(state.get("workflow_id", "")).lower() else "development"
    }


def _categorize_errors(error_logs: list) -> Dict[str, Any]:
    """Catégorise les erreurs par type et gravité."""
    if not error_logs:
        return {"categories": {}, "severity": "none", "total": 0}
    
    categories = {
        "critical": len([e for e in error_logs if "critique" in e.lower() or "critical" in e.lower()]),
        "database": len([e for e in error_logs if "database" in e.lower() or "db" in e.lower()]),
        "network": len([e for e in error_logs if "network" in e.lower() or "connection" in e.lower()]),
        "validation": len([e for e in error_logs if "validation" in e.lower() or "invalid" in e.lower()]),
        "other": 0
    }
    
    categories["other"] = len(error_logs) - sum(categories.values())
    
    severity = "critical" if categories["critical"] > 0 else "warning" if len(error_logs) > 0 else "none"
    
    return {
        "categories": categories,
        "severity": severity,
        "total": len(error_logs),
        "most_recent": error_logs[-1] if error_logs else None
    }


def _calculate_duration_info(state: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule les informations de durée du workflow."""
    from datetime import datetime
    
    started_at = state.get("started_at")
    current_time = state.get("current_time") or datetime.now().isoformat()
    
    duration_info = {
        "started_at": started_at,
        "current_time": current_time,
        "duration_seconds": None,
        "duration_human": None
    }
    
    if started_at:
        try:
            from dateutil.parser import parse
            start_dt = parse(started_at)
            current_dt = parse(current_time) if isinstance(current_time, str) else datetime.now()
            duration = current_dt - start_dt
            
            duration_info["duration_seconds"] = duration.total_seconds()
            duration_info["duration_human"] = str(duration).split('.')[0]  # Sans microsecondes
        except Exception:
            pass
    
    return duration_info


def _calculate_overall_success(analysis: Dict[str, Any], impl_success: bool, test_success: bool) -> Dict[str, Any]:
    """Calcule le succès global avec score et recommandations."""
    score = 0
    recommendations = []
    
    if analysis["environment"]["is_valid"]:
        score += 20
    else:
        recommendations.append("Vérifier la configuration d'environnement")
    
    if impl_success and analysis["implementation"]["files_count"] > 0:
        score += 40
    elif impl_success:
        score += 20
        recommendations.append("Implémentation réussie mais aucun fichier modifié")
    else:
        recommendations.append("Revoir l'implémentation qui a échoué")
    
    if analysis["testing"]["executed"]:
        if test_success:
            score += 20
        else:
            score += 10
            recommendations.append("Corriger les tests qui ont échoué")
    else:
        recommendations.append("Ajouter des tests pour valider l'implémentation")
    
    if analysis["pr"]["created"]:
        score += 20
    elif analysis["pr"]["validation"]["should_have_pr"]:
        recommendations.append("Créer une Pull Request pour les modifications")
    else:
        score += 10  
    
    error_count = analysis["errors"]["count"]
    if error_count == 0:
        score += 5
    elif error_count > 5:
        score -= 10
        recommendations.append("Réduire le nombre d'erreurs dans le workflow")
    
    return {
        "success": score >= 80,
        "score": min(100, max(0, score)),  
        "grade": _get_grade_from_score(score),
        "recommendations": recommendations[:3]  
    }


def _get_grade_from_score(score: int) -> str:
    """Convertit un score numérique en grade lisible."""
    if score >= 90:
        return "Excellent"
    elif score >= 80:
        return "Bon"
    elif score >= 60:
        return "Acceptable"
    elif score >= 40:
        return "Insuffisant"
    else:
        return "Échec"


def _calculate_test_success_rate(test_results: list) -> float:
    """Calcule le taux de succès des tests."""
    if not test_results:
        return 0.0
    
    successful_tests = 0
    for result in test_results:
        if isinstance(result, dict):
            if result.get("success", False) or result.get("passed", False):
                successful_tests += 1
        elif isinstance(result, str) and "success" in result.lower():
            successful_tests += 1
    
    return successful_tests / len(test_results)


def _identify_test_types(test_results: list) -> list:
    """Identifie les types de tests exécutés."""
    test_types = set()
    for result in test_results:
        if isinstance(result, dict):
            test_type = result.get("type", "unknown")
            test_types.add(test_type)
        elif isinstance(result, str):
            if "unit" in result.lower():
                test_types.add("unit")
            elif "integration" in result.lower():
                test_types.add("integration")
            else:
                test_types.add("unknown")
    
    return list(test_types)


def _create_fallback_analysis(state: Dict[str, Any], results: Dict[str, Any], pr_url: Optional[str], error: str) -> Dict[str, Any]:
    """Crée une analyse minimale en cas d'erreur."""
    return {
        "environment": {"path": "Non disponible", "is_valid": False},
        "implementation": {"success": False, "modified_files": [], "files_count": 0, "details": {}},
        "testing": {"executed": False, "success": False, "results": [], "summary": "Analyse impossible"},
        "pr": {"created": bool(pr_url), "url": pr_url, "status": "unknown"},
        "metrics": {"error": error},
        "errors": {"count": 1, "summary": {"severity": "critical", "total": 1}},
        "duration": {"started_at": None, "current_time": None},
        "overall": {"success": False, "score": 0, "grade": "Erreur", "recommendations": ["Corriger l'erreur d'analyse"]}
    } 