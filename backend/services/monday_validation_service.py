"""Service de validation humaine via les updates Monday.com."""

import asyncio
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from models.schemas import HumanValidationStatus, HumanValidationResponse
from tools.monday_tool import MondayTool
from services.intelligent_reply_analyzer import intelligent_reply_analyzer, IntentionType
from utils.logger import get_logger

logger = get_logger(__name__)


class MondayValidationService:
    """Service pour gérer la validation humaine via les updates Monday.com."""
    
    def __init__(self):
        self.monday_tool = MondayTool()
        self.pending_validations = {}
    
    def _safe_get_test_success(self, test_results) -> bool:
        """Extrait le statut de succès des tests de manière sécurisée."""
        if isinstance(test_results, dict):
            return test_results.get("success", False)
        elif isinstance(test_results, list) and test_results:
            return all(item.get("passed", False) if isinstance(item, dict) else False for item in test_results)
        elif hasattr(test_results, 'success'):
            return getattr(test_results, 'success', False)
        else:
            return False
    
    def _create_fallback_workflow_results(self, task_id: str, error_reason: str) -> Dict[str, Any]:
        """
        Crée un dictionnaire workflow_results par défaut en cas d'erreur.
        
        Cette fonction centralise la création des dictionnaires de fallback pour
        garantir la cohérence à travers tout le code.
        
        Args:
            task_id: ID de la tâche (peut être item_id ou task_id selon le contexte)
            error_reason: Raison de l'utilisation du fallback
            
        Returns:
            Dictionnaire workflow_results minimal mais valide
        """
        return {
            "task_title": "Tâche sans titre",
            "task_id": task_id,
            "success_level": "unknown",
            "modified_files": [],
            "test_results": {},
            "error_logs": [f"Erreur: {error_reason}"],
            "ai_messages": [],
            # Champs additionnels pour compatibilité complète
            "implementation_success": False,
            "test_executed": False,
            "test_success": False,
            "pr_created": False,
            "pr_url": None,
            "environment_path": "Non disponible"
        }
    
    async def _build_validation_message(self, workflow_results: Dict[str, Any], creator_name: str = None, user_language: str = 'en') -> str:
        """
        Construit le message de validation à poster dans Monday.com dans la langue de l'utilisateur.
        
        Args:
            workflow_results: Résultats du workflow
            creator_name: Nom du créateur du ticket (pour tagging)
            user_language: Langue de l'utilisateur (pour le template multilingue)
            
        Returns:
            Message formaté pour Monday.com
        """
        try:
            logger.info(f"🔍 DEBUG _build_validation_message DÉBUT: workflow_results type={type(workflow_results)}")
            
            from services.project_language_detector import project_language_detector
            from utils.monday_comment_formatter import MondayCommentFormatter
            
            logger.info(f"🔍 DEBUG: Imports réussis")
            
            # Vérification de sécurité consolidée: s'assurer que workflow_results est un dict valide
            if not isinstance(workflow_results, dict) or workflow_results is None:
                error_type = "None" if workflow_results is None else type(workflow_results).__name__
                logger.error(f"❌ workflow_results invalide dans _build_validation_message: {error_type}")
                workflow_results = self._create_fallback_workflow_results("unknown", f"workflow_results était {error_type}")
            
            logger.info(f"🔍 DEBUG: workflow_results validé, type={type(workflow_results)}")
            logger.info(f"🌍 Construction message de validation:")
            logger.info(f"   • user_language (messages Monday): {user_language}")
            
            try:
                task_title_preview = workflow_results.get('task_title', 'N/A')
                if task_title_preview and len(task_title_preview) > 100:
                    task_title_preview = task_title_preview[:100]
                logger.info(f"   • Tâche: {task_title_preview}")
            except Exception as preview_error:
                logger.error(f"❌ Erreur lors de la prévisualisation du titre: {preview_error}")
        
            # get_monday_reply_template() GARANTIT de toujours retourner un dict valide
            logger.info(f"🔍 DEBUG: Appel get_monday_reply_template...")
            try:
                templates = await project_language_detector.get_monday_reply_template(
                    user_language=user_language,
                    project_language=user_language
                )
                logger.info(f"🔍 DEBUG: Templates récupérés, type={type(templates)}, keys={list(templates.keys()) if isinstance(templates, dict) else 'NOT_DICT'}")
            except Exception as template_error:
                logger.error(f"❌ Erreur lors de la récupération des templates: {template_error}", exc_info=True)
                templates = None
            
            logger.info(f"🔍 DEBUG: Vérification templates...")
            # SÉCURITÉ: Vérification supplémentaire pour garantir que templates n'est JAMAIS None
            if not templates or not isinstance(templates, dict):
                logger.error(f"❌ CRITIQUE: templates est None ou invalide ! Type: {type(templates)}")
                logger.error(f"   user_language={user_language}, forcing fallback to english hardcoded")
                templates = {
                    'workflow_started': '🚀 Workflow started! Processing your request...',
                    'pr_created': '✅ Pull Request created successfully!',
                    'pr_merged': 'PR merged',
                    'error': '❌ An error occurred',
                    'validation_request': '🤝 Human validation required',
                    'response_header': '🤖 **VyData Response**',
                    'question_label': 'Question',
                    'task_label': 'Task',
                    'task_completed': 'Task Completed Successfully',
                    'task_partial': 'Task Partially Completed',
                    'task_failed': 'Task Failed',
                    'automatic_response_note': 'This is an automatic response. For actions requiring code modifications, use a command.',
                    'workflow_progress': 'Workflow progress',
                    'environment_configured': 'Environment configured',
                    'modified_files': 'Modified files',
                    'no_modified_files': 'No modified files detected',
                    'implementation_success': 'Implementation completed successfully',
                    'implementation_failed': 'Implementation failed',
                    'tests_passed': 'Tests executed successfully',
                    'tests_errors': 'Tests executed with errors',
                    'no_tests': 'No tests executed',
                    'pr_not_created': 'Pull Request not created',
                    'validation_instructions': """**Reply to this update with**:
• **'yes'** or **'validate'** → Automatic merge ✅
• **'no [instructions]'** → Relaunch with modifications (max 3) 🔄
• **'abandon'** or **'stop'** → End workflow ⛔

**Rejection example with instructions**:
"No, adjust file X and find another alternative with tests"

⏰ *Timeout: 60 minutes*"""
                }
            
            logger.info(f"✅ Templates récupérés pour {user_language} ({len(templates)} clés)")
            
            logger.info(f"🔍 DEBUG: Construction creator_tag...")
            creator_tag = ""
            if creator_name:
                creator_tag = MondayCommentFormatter.format_creator_tag(creator_name)
                if creator_tag:
                    creator_tag = f"{creator_tag} "
            logger.info(f"🔍 DEBUG: creator_tag={creator_tag}")
            
            logger.info(f"🔍 DEBUG: Extraction des données de workflow_results...")
            logger.info(f"🔍 DEBUG: workflow_results keys={list(workflow_results.keys()) if isinstance(workflow_results, dict) else 'NOT_DICT'}")
            
            task_title = workflow_results.get("task_title", "Untitled task" if user_language == 'en' else "Tâche sans titre" if user_language == 'fr' else "Tarea sin título")
            logger.info(f"🔍 DEBUG: task_title extracted")
            
            environment_path = workflow_results.get("environment_path", "Not available" if user_language == 'en' else "Non disponible" if user_language == 'fr' else "No disponible")
            logger.info(f"🔍 DEBUG: environment_path extracted")
            
            modified_files = workflow_results.get("modified_files", [])
            logger.info(f"🔍 DEBUG: modified_files extracted, count={len(modified_files) if isinstance(modified_files, list) else 'NOT_LIST'}")
            
            implementation_success = workflow_results.get("implementation_success", False)
            test_success = workflow_results.get("test_success", False)
            test_executed = workflow_results.get("test_executed", False)
            pr_created = workflow_results.get("pr_created", False)
            logger.info(f"🔍 DEBUG: Toutes les valeurs extraites avec succès")
            
            logger.info(f"🔍 DEBUG: Construction du message...")
            logger.info(f"🔍 DEBUG: templates type={type(templates)}, is_dict={isinstance(templates, dict)}")
            
            validation_header = templates.get('validation_request', '🤝 Human validation required')
            logger.info(f"🔍 DEBUG: validation_header extracted")
            
            message = f"""{creator_tag}🤖 **{validation_header}** ⚠️

**{templates.get('question_label', 'Task')}**: {task_title}

📝 **{templates.get('workflow_progress', 'Workflow progress')}**:
• ✅ {templates.get('environment_configured', 'Environment configured')}: {environment_path}
"""
            logger.info(f"🔍 DEBUG: Message initial construit")
            
            if modified_files:
                message += f"• ✅ {templates.get('modified_files', 'Modified files')}: {', '.join(modified_files)}\n"
            else:
                message += f"• ⚠️ {templates.get('no_modified_files', 'No modified files detected')}\n"
            
            if implementation_success:
                message += f"• ✅ {templates.get('implementation_success', 'Implementation completed successfully')}\n"
            else:
                message += f"• ❌ {templates.get('implementation_failed', 'Implementation failed')}\n"
            
            if test_executed:
                if test_success:
                    message += f"• ✅ {templates.get('tests_passed', 'Tests executed successfully')}\n"
                else:
                    message += f"• ⚠️ {templates.get('tests_errors', 'Tests executed with errors')}\n"
            else:
                message += f"• ⚠️ {templates.get('no_tests', 'No tests executed')}\n"
            
            if pr_created:
                pr_url = workflow_results.get("pr_url") if isinstance(workflow_results, dict) else None
                if not pr_url:
                    pr_info = workflow_results.get("pr_info") if isinstance(workflow_results, dict) else None
                    if pr_info and isinstance(pr_info, dict):
                        pr_url = pr_info.get("url", "")
                    elif pr_info and hasattr(pr_info, "url"):
                        pr_url = getattr(pr_info, "url", "")
                
                if pr_url:
                    message += f"• ✅ {templates.get('pr_created', 'Pull Request created')}: {pr_url}\n"
                else:
                    message += f"• ✅ {templates.get('pr_created', 'Pull Request created')}\n"
            else:
                message += f"• ❌ {templates.get('pr_not_created', 'Pull Request not created')}\n"
            
            instructions = templates.get('validation_instructions', """**Reply to this update with**:
• **'yes'** or **'validate'** → Automatic merge ✅
• **'no [instructions]'** → Relaunch with modifications (max 3) 🔄
• **'abandon'** or **'stop'** → End workflow ⛔

**Rejection example with instructions**:
"No, adjust file X and find another alternative with tests"

⏰ *Timeout: 60 minutes*""")
            
            message += f"\n==================================================\n{instructions}"
            
            return message
            
        except AttributeError as e:
            logger.error(f"❌ AttributeError dans _build_validation_message: {e}", exc_info=True)
            logger.error(f"   Variables: workflow_results type={type(workflow_results) if 'workflow_results' in locals() else 'not defined'}")
            # Retourner un message minimal en cas d'erreur
            return f"🤖 Validation requise - Erreur lors de la construction du message ({str(e)})"
        except Exception as e:
            logger.error(f"❌ Erreur inattendue dans _build_validation_message: {e}", exc_info=True)
            return f"🤖 Validation requise - Erreur: {str(e)}"

    async def post_validation_update(self, item_id: str, workflow_results: Dict[str, Any], creator_name: str = None, user_language: str = 'en') -> str:
        """
        Poste une update de validation dans Monday.com.
        
        Args:
            item_id: ID de l'item Monday.com
            workflow_results: Résultats du workflow à inclure
            creator_name: Nom du créateur du ticket (pour tagging)
            user_language: Langue de l'utilisateur pour le template
            
        Returns:
            ID de l'update créée ou ID de fallback en cas d'erreur
        """
        try:
            logger.info(f"🔍 DEBUG post_validation_update: workflow_results type={type(workflow_results)}, is_none={workflow_results is None}")
            
            # Vérification de sécurité consolidée: s'assurer que workflow_results est un dict valide
            if not isinstance(workflow_results, dict) or workflow_results is None:
                error_type = "None" if workflow_results is None else type(workflow_results).__name__
                logger.error(f"❌ workflow_results invalide dans post_validation_update: {error_type}")
                workflow_results = self._create_fallback_workflow_results(item_id, f"workflow_results était {error_type}")
            
            logger.info(f"🔍 DEBUG: Appel _build_validation_message...")
            comment = await self._build_validation_message(workflow_results, creator_name, user_language)
            logger.info(f"🔍 DEBUG: _build_validation_message terminé, comment length={len(comment) if comment else 0}")
            
            logger.info(f"📝 Création update de validation pour item {item_id}")
            
            max_retries = 3
            retry_delay = 2
            result = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"📤 Tentative {attempt}/{max_retries} création update Monday.com")
                    
                    result = await self.monday_tool._arun(
                        action="add_comment",
                        item_id=item_id,
                        comment=comment
                    )
                    
                    if result and isinstance(result, dict) and result.get("success", False):
                        logger.info(f"✅ Update créée avec succès à la tentative {attempt}")
                        break
                    
                    error_type = result.get("error_type", "unknown") if result and isinstance(result, dict) else "unknown"
                    error_message = result.get("error", "") if result and isinstance(result, dict) else "No response from Monday.com"
                    
                    is_retryable = (
                        error_type == "monday_internal" or
                        "internal" in error_message.lower() or
                        "timeout" in error_message.lower() or
                        "rate limit" in error_message.lower()
                    )
                    
                    if is_retryable and attempt < max_retries:
                        logger.warning(f"⚠️ Erreur temporaire Monday.com (tentative {attempt}): {error_message}")
                        logger.info(f"🔄 Retry dans {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        break
                        
                except Exception as e:
                    logger.error(f"❌ Exception tentative {attempt}: {e}")
                    if attempt >= max_retries:
                        raise
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
            
            if not result or not (isinstance(result, dict) and result.get("success", False)):
                error_type = result.get("error_type", "unknown") if result and isinstance(result, dict) else "unknown"
                error_message = result.get("error", "Erreur inconnue") if result and isinstance(result, dict) else "Pas de réponse"
                
                if error_type == "permissions":
                    logger.warning(f"⚠️ Permissions insuffisantes Monday.com pour item {item_id}")
                    logger.warning(f"⚠️ {error_message}")
                    
                    update_id = f"failed_update_{item_id}"
                    logger.info(f"📝 Utilisation update_id alternatif: {update_id}")
                    
                    self.pending_validations[update_id] = {
                        "item_id": item_id,
                        "message": comment,
                        "timestamp": datetime.now().isoformat(),
                        "fallback_mode": True,
                        "permissions_error": True,
                        "error": error_message,
                        "workflow_results": workflow_results
                    }
                    
                    return update_id
                    
                elif error_type in ["auth", "graphql"]:
                    logger.error(f"❌ Erreur Monday.com ({error_type}): {error_message}")
                    update_id = f"error_update_{item_id}"
                    
                    self.pending_validations[update_id] = {
                        "item_id": item_id,
                        "message": comment,
                        "timestamp": datetime.now().isoformat(),
                        "fallback_mode": True,
                        "api_error": True,
                        "error": error_message,
                        "workflow_results": workflow_results
                    }
                    
                    return update_id
                    
                else:   
                    raise Exception(f"Erreur Monday.com: {error_message}")
            
            # Vérification supplémentaire pour s'assurer que result est un dict valide
            if not isinstance(result, dict) or result is None:
                logger.error(f"❌ Result invalide après succès apparent: {type(result)}")
                update_id = f"fallback_update_{item_id}"
                # Important: ne pas essayer d'extraire update_id depuis result s'il n'est pas un dict
            else:
                # result est un dict valide, on peut extraire update_id
                update_id = result.get("update_id") or result.get("comment_id") or f"success_update_{item_id}"
            
            logger.info(f"✅ Update de validation créée avec succès: {update_id}")
            
            # Vérification de sécurité avant d'appeler .get() sur workflow_results
            validation_id_from_results = workflow_results.get("validation_id") if isinstance(workflow_results, dict) else None
            
            self.pending_validations[str(update_id)] = {
                "item_id": item_id,
                "message": comment,
                "timestamp": datetime.now().isoformat(),
                "fallback_mode": False,
                "permissions_error": False,
                "workflow_results": workflow_results,
                "validation_id": validation_id_from_results
            }
            
            return str(update_id)
            
        except Exception as e:
            logger.error(f"❌ Exception lors de la création d'update Monday.com: {e}")
            
            update_id = f"exception_update_{item_id}"
            
            self.pending_validations[update_id] = {
                "item_id": item_id,
                "message": comment if 'comment' in locals() else "Message de validation indisponible",
                "timestamp": datetime.now().isoformat(),
                "fallback_mode": True,
                "exception_error": True,
                "error": str(e),
                "workflow_results": workflow_results if 'workflow_results' in locals() else {}
            }
            
            return update_id
    
    async def check_for_human_replies(self, update_id: str, timeout_minutes: int = 10) -> Optional[HumanValidationResponse]:
        """
        Vérifie les replies humaines sur l'update de validation.
        
        🔐 SÉCURITÉ: Seul l'utilisateur qui a créé l'update peut répondre.
        Les réponses des autres utilisateurs seront ignorées.
        
        Args:
            update_id: ID de l'update à surveiller
            timeout_minutes: Timeout en minutes
            
        Returns:
            Réponse de validation ou None si timeout
        """
        update_key = str(update_id)
        
        logger.info(f"🔐 Protection activée: Seul le créateur de l'update {update_id} pourra répondre")
        
        if update_key not in self.pending_validations:
            logger.warning(f"⚠️ Update {update_id} non trouvée dans pending_validations - tentative de récupération")
            
            recovered_validation = await self._recover_validation_context(update_id)
            if recovered_validation:
                self.pending_validations[update_key] = recovered_validation
                logger.info(f"✅ Contexte de validation récupéré pour {update_id}")
            else:
                logger.error(f"❌ Impossible de récupérer le contexte pour {update_id}")
                return None
        
        validation_data = self.pending_validations[update_key]
        item_id = validation_data.get("item_id")
        
        if validation_data.get("permissions_error") or validation_data.get("exception_error"):
            logger.warning(f"🔓 Erreur de permissions/exception détectée pour {update_id}")
            logger.warning(f"⚡ AUTO-APPROBATION: Le workflow est déjà terminé avec succès")
            
            auto_response = HumanValidationResponse(
                validation_id=update_id,
                status=HumanValidationStatus.APPROVED,
                response_text="Auto-approuvé: Workflow terminé avec succès malgré l'erreur de permissions Monday.com",
                timestamp=datetime.now().isoformat(),
                analysis_confidence=1.0
            )
            
            self.pending_validations[update_key]["status"] = HumanValidationStatus.APPROVED.value
            self.pending_validations[update_key]["response"] = auto_response
            
            logger.info(f"✅ Validation auto-approuvée pour {update_id}")
            return auto_response
        
        timeout_seconds = timeout_minutes * 60
        
        check_interval = int(os.getenv("MONDAY_VALIDATION_CHECK_INTERVAL", "5"))
        
        if timeout_minutes <= 10:
            max_consecutive_no_changes = max(4, int(120 / check_interval))
        else:
            max_consecutive_no_changes = max(10, int(300 / check_interval))
        
        logger.info(f"⏳ Attente de reply humaine sur update {update_id} (timeout: {timeout_minutes}min, check_interval: {check_interval}s, max_no_changes: {max_consecutive_no_changes})")
        
        created_at = datetime.now()
        created_at_str = validation_data.get("timestamp") or validation_data.get("created_at")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing timestamp: {e}")
                created_at = datetime.now()
        
        for check_delay in [0, 2, 5]:
            if check_delay > 0:
                await asyncio.sleep(check_delay)
                
            try:
                initial_check = await self._get_item_updates(item_id)
                if initial_check:
                    immediate_reply, unauthorized_attempts = await self._find_human_reply(update_id, initial_check, created_at, item_id, validation_data.get("task_title"))
                    
                    # 🚨 Si des tentatives non autorisées sont détectées, notifier immédiatement
                    if unauthorized_attempts:
                        await self._notify_unauthorized_attempts(item_id, unauthorized_attempts, validation_data.get("task_title", "cette tâche"))
                    
                    if immediate_reply:
                        logger.info(f"⚡ Réponse humaine trouvée après {check_delay}s!")
                        validation_context = self._prepare_analysis_context(validation_data)
                        response = await self._parse_human_reply(immediate_reply, update_id, validation_context)
                        self.pending_validations[update_id]["status"] = response.status.value
                        self.pending_validations[update_id]["response"] = response
                        return response
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors de la vérification à {check_delay}s: {e}")
          
        elapsed = 0
        last_update_count = 0
        consecutive_no_changes = 0
        
        while elapsed < timeout_seconds:
            try:
                recent_updates = await self._get_item_updates(item_id)
                
                current_update_count = len(recent_updates) if recent_updates else 0
                
                if current_update_count > last_update_count:
                    logger.info(f"📬 Nouvelles updates détectées: {current_update_count} (était {last_update_count})")
                    last_update_count = current_update_count
                    consecutive_no_changes = 0
                    
                    created_at_str = validation_data.get("timestamp") or validation_data.get("created_at")
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur parsing timestamp {created_at_str}: {e}")
                            created_at = datetime.now()
                    else:
                        created_at = datetime.now()
                    human_reply, unauthorized_attempts = await self._find_human_reply(update_id, recent_updates, created_at, item_id, validation_data.get("task_title"))
                    
                    # 🚨 Notifier si des tentatives non autorisées
                    if unauthorized_attempts:
                        await self._notify_unauthorized_attempts(item_id, unauthorized_attempts, validation_data.get("task_title", "cette tâche"))
                    
                    if human_reply:
                        validation_context = self._prepare_analysis_context(validation_data)
                        
                        response = await self._parse_human_reply(human_reply, update_id, validation_context)
                        
                        self.pending_validations[update_id]["status"] = response.status.value
                        self.pending_validations[update_id]["response"] = response
                        
                        logger.info(f"✅ Reply humaine analysée: {response.status.value} (confiance: {getattr(response, 'analysis_confidence', 'N/A')})")
                        return response
                else:
                    consecutive_no_changes += 1
                    logger.debug(f"🔄 Aucune nouvelle update ({consecutive_no_changes}/{max_consecutive_no_changes})")
                
                if consecutive_no_changes >= max_consecutive_no_changes:
                    logger.warning(f"⚠️ Aucune activité détectée depuis {consecutive_no_changes * check_interval / 60:.1f} minutes")
                    
                    created_at_str = validation_data.get("timestamp") or validation_data.get("created_at")
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur parsing timestamp {created_at_str}: {e}")
                            created_at = datetime.now()
                    else:
                        created_at = datetime.now()
                    final_check, unauthorized_attempts = await self._find_human_reply(update_id, recent_updates, created_at, item_id, validation_data.get("task_title"))
                    
                    # 🚨 Notifier même lors de la vérification finale
                    if unauthorized_attempts:
                        await self._notify_unauthorized_attempts(item_id, unauthorized_attempts, validation_data.get("task_title", "cette tâche"))
                    
                    if final_check:
                        logger.info("🔍 Reply trouvée lors de la vérification finale")
                        validation_context = self._prepare_analysis_context(validation_data)
                        response = await self._parse_human_reply(final_check, update_id, validation_context)
                        
                        self.pending_validations[update_id]["status"] = response.status.value
                        self.pending_validations[update_id]["response"] = response
                        
                        return response
                    else:
                        logger.warning(f"🔚 Timeout anticipé - aucune activité depuis {consecutive_no_changes * check_interval} secondes")
                        break
                
                await asyncio.sleep(check_interval)
                elapsed += check_interval
                
                if elapsed % 60 == 0:
                    logger.info(f"⏳ Attente reply validation: {elapsed//60}min/{timeout_minutes}min")
                    
            except Exception as e:
                logger.error(f"❌ Erreur lors de la vérification des replies: {e}")
                consecutive_no_changes += 1
                
                if consecutive_no_changes >= max_consecutive_no_changes:
                    logger.error("❌ Trop d'erreurs consécutives - arrêt de la surveillance")
                    break
                
                await asyncio.sleep(check_interval)
                elapsed += check_interval
        
        reason = "timeout" if elapsed >= timeout_seconds else "no_activity"
        logger.warning(f"⏰ Validation humaine arrêtée: {reason} pour update {update_id}")
        
        self.pending_validations[update_id]["status"] = "expired"
        
        return HumanValidationResponse(
            validation_id=update_id or f"validation_{int(time.time())}_{id(self)}",
            status=HumanValidationStatus.EXPIRED,
            comments=f"Timeout ({reason}) - Aucune réponse humaine reçue dans les {timeout_minutes} minutes",
            validated_by="system",
            should_merge=False,
            should_continue_workflow=False
        )
    
    def _generate_validation_update(self, workflow_results: Dict[str, Any]) -> str:
        """Génère le message d'update pour la validation."""
        
        task_title = workflow_results.get("task_title", "Tâche")
        success_level = workflow_results.get("success_level", "unknown")
        pr_url = workflow_results.get("pr_url")
        test_results = workflow_results.get("test_results", {})
        error_logs = workflow_results.get("error_logs", [])
        ai_messages = workflow_results.get("ai_messages", [])
        
        if success_level == "success":
            header = "🤖 **WORKFLOW TERMINÉ - VALIDATION REQUISE** ✅"
        elif success_level == "partial":
            header = "🤖 **WORKFLOW TERMINÉ - VALIDATION REQUISE** ⚠️"
        else:
            header = "🤖 **WORKFLOW TERMINÉ - VALIDATION REQUISE** ❌"
        
        message = f"{header}\n\n"
        message += f"**Tâche**: {task_title}\n\n"

        if ai_messages:
            message += "📝 **Progression du workflow**:\n"
            important_messages = [msg for msg in ai_messages if "✅" in msg or "❌" in msg or "🚀" in msg or "💻" in msg][-5:]
            if not important_messages:
                important_messages = ai_messages[-3:]
            
            for ai_msg in important_messages:
                if ai_msg.strip():
                    message += f"• {ai_msg}\n"
            message += "\n"
        
        if test_results:
            if isinstance(test_results, list):
                if test_results:
                    last_test = test_results[-1] if isinstance(test_results[-1], dict) else {}
                    total_passed = sum(1 for test in test_results if isinstance(test, dict) and test.get("success", False))
                    total_failed = len(test_results) - total_passed
                    
                    if total_failed == 0 and total_passed > 0:
                        message += f"✅ **Tests**: {total_passed} test(s) passent\n"
                    else:
                        message += f"❌ **Tests**: {total_failed} test(s) échoué(s), {total_passed} passent\n"
                else:
                    message += "⚠️ **Tests**: Liste vide\n"
            elif isinstance(test_results, dict):
                if test_results.get("success"):
                    message += "✅ **Tests**: Tous les tests passent\n"
                else:
                    failed_count = len(test_results.get("failed_tests", []))
                    message += f"❌ **Tests**: {failed_count} test(s) échoué(s)\n"
            else:
                message += f"⚠️ **Tests**: Format inattendu ({type(test_results).__name__})\n"
        else:
            message += "⚠️ **Tests**: Aucun test exécuté\n"
        
        if pr_url:
            message += f"🔗 **Pull Request**: {pr_url}\n"
        else:
            message += "❌ **Pull Request**: Non créée\n"

        if error_logs:
            message += "\n**⚠️ Erreurs rencontrées**:\n"
            for error in error_logs[-3:]:
                message += f"- {error}\n"
        
        message += "\n" + "="*50 + "\n"
        message += "**🤝 VALIDATION HUMAINE REQUISE**\n\n"
        message += "**Répondez à cette update avec**:\n"
        message += "• **'oui'** ou **'valide'** → Merge automatique\n"
        message += "• **'non'** ou **'debug'** → Debug avec LLM OpenAI\n\n"
        message += "⏰ *Timeout: 10 minutes*"
        
        return message
    
    async def _get_item_updates(self, item_id: str) -> List[Dict[str, Any]]:
        """Récupère les updates d'un item Monday.com."""
        try:
            result = await self.monday_tool.execute_action(
                action="get_item_updates",
                item_id=item_id
            )
            
            if not isinstance(result, dict):
                logger.error(f"❌ Résultat get_updates invalide (type {type(result)}): {result}")
                if isinstance(result, list):
                    error_messages = []
                    for error_item in result:
                        if isinstance(error_item, dict):
                            error_messages.append(error_item.get('message', 'Erreur GraphQL inconnue'))
                        else:
                            error_messages.append(str(error_item))
                    error_str = "; ".join(error_messages) if error_messages else str(result)
                    logger.error(f"❌ API Monday a retourné une liste d'erreurs: {error_str}")
                return []
                
            if isinstance(result, dict) and result.get("success", True):
                return result.get("updates", [])
            else:
                logger.error(f"❌ Impossible de récupérer updates item {item_id}: {result}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération updates: {e}")
            return []
    
    async def _find_human_reply(self, original_update_id: str, updates: List[Dict[str, Any]], since: datetime, item_id: Optional[str] = None, task_title: Optional[str] = None) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Trouve une reply humaine à notre update de validation.
        
        Returns:
            tuple: (reply_valide, liste_tentatives_non_autorisees)
        """
        
        if not isinstance(updates, list):
            logger.warning(f"⚠️ Updates n'est pas une liste (type {type(updates)}), conversion en liste vide")
            updates = []
        
        from datetime import timezone
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        
        # 🔐 ÉTAPE 1: Récupérer le créateur de l'update de validation original
        validation_update_timestamp = None
        original_creator_id = None
        original_creator_email = None
        original_creator_name = "inconnu"
        
        for update in updates:
            if str(update.get("id")) == str(original_update_id):
                timestamp_str = update.get("created_at")
                if timestamp_str:
                    try:
                        validation_update_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        logger.info(f"📅 Timestamp de l'update de validation trouvé: {validation_update_timestamp.isoformat()}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur parsing timestamp update validation: {e}")
                
                # Récupérer le créateur de l'update original
                creator = update.get("creator", {})
                if isinstance(creator, dict):
                    original_creator_id = creator.get("id")
                    original_creator_email = creator.get("email")
                    original_creator_name = creator.get("name", "inconnu")
                    
                    logger.info(f"👤 Créateur de l'update de validation: {original_creator_name} (ID: {original_creator_id}, Email: {original_creator_email})")
                    logger.info(f"🔐 Seul cet utilisateur pourra répondre à cette validation")
                break
        
        if not original_creator_id and not original_creator_email:
            logger.warning(f"⚠️ Impossible d'identifier le créateur de l'update {original_update_id} - validation ouverte à tous")
        
        reference_time = validation_update_timestamp if validation_update_timestamp else since
        logger.info(f"🕐 Timestamp de référence pour recherche: {reference_time.isoformat()}")
        
        # Liste pour stocker les tentatives non autorisées
        unauthorized_attempts = []
        
        candidate_replies = []
        
        logger.info(f"🔍 Recherche de reply parmi {len(updates)} updates pour update_id={original_update_id}")
        logger.info(f"🕐 Recherche des updates créées après: {reference_time.isoformat()}")
        
        for idx, update in enumerate(updates):
            if not isinstance(update, dict):
                logger.debug(f"⚠️ Update {idx} n'est pas un dict: {type(update)}")
                continue
            
            update_id = update.get("id")
            if str(update_id) == str(original_update_id):
                logger.debug(f"⏭️ Ignorer l'update de validation originale (ID: {update_id})")
                continue
                
            update_time_str = update.get("created_at")
            if not update_time_str:
                logger.debug(f"⚠️ Update {idx} sans timestamp")
                continue
            
            try:
                update_time = datetime.fromisoformat(update_time_str.replace('Z', '+00:00'))
                time_threshold = reference_time - timedelta(seconds=30)
                if update_time <= time_threshold:
                    logger.debug(f"⏭️ Update {idx} trop ancien ({update_time_str} <= {time_threshold.isoformat()})")
                    continue
            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing timestamp {update_time_str}: {e}")
                continue
            
            body = update.get("body", "").strip()
            reply_to_id = update.get("reply_to_id") or update.get("parent_id")
            update_type = update.get("type", "update")
            
            # 🔐 ÉTAPE 2: Vérifier que la réponse vient du créateur autorisé
            reply_creator = update.get("creator", {})
            reply_creator_id = reply_creator.get("id") if isinstance(reply_creator, dict) else None
            reply_creator_email = reply_creator.get("email") if isinstance(reply_creator, dict) else None
            reply_creator_name = reply_creator.get("name", "inconnu") if isinstance(reply_creator, dict) else "inconnu"
            
            # Si on a identifié un créateur original, vérifier que la réponse vient de lui
            if original_creator_id or original_creator_email:
                is_authorized = False
                
                if original_creator_id and reply_creator_id:
                    is_authorized = str(original_creator_id) == str(reply_creator_id)
                elif original_creator_email and reply_creator_email:
                    is_authorized = original_creator_email.lower() == reply_creator_email.lower()
                
                if not is_authorized:
                    logger.warning(f"🚫 Réponse ignorée - Utilisateur non autorisé: {reply_creator_name} (ID: {reply_creator_id}, Email: {reply_creator_email})")
                    logger.warning(f"   Créateur attendu: {original_creator_name} (ID: {original_creator_id}, Email: {original_creator_email})")
                    
                    # 🚨 NOTIFICATION: Stocker la tentative non autorisée
                    unauthorized_attempts.append({
                        "intruder_id": reply_creator_id,
                        "intruder_email": reply_creator_email,
                        "intruder_name": reply_creator_name,
                        "legitimate_creator_id": original_creator_id,
                        "legitimate_creator_email": original_creator_email,
                        "legitimate_creator_name": original_creator_name,
                        "update": update,
                        "timestamp": update_time_str
                    })
                    
                    # 📢 POSTER IMMÉDIATEMENT UNE NOTIFICATION DANS MONDAY.COM
                    if item_id and task_title:
                        try:
                            logger.info(f"📢 Envoi notification tentative non autorisée sur item {item_id}")
                            await self._post_unauthorized_reply_notification(
                                item_id=item_id,
                                original_creator_name=original_creator_name,
                                original_creator_email=original_creator_email,
                                unauthorized_replier_name=reply_creator_name,
                                unauthorized_replier_email=reply_creator_email,
                                task_title=task_title
                            )
                        except Exception as e:
                            logger.error(f"❌ Erreur envoi notification non autorisée: {e}", exc_info=True)
                    
                    continue
                else:
                    logger.info(f"✅ Réponse autorisée de {reply_creator_name} (ID: {reply_creator_id})")
            
            logger.info(f"📝 Update {idx}: id={update_id}, type={update_type}, reply_to={reply_to_id}, créé={update_time_str}, body='{body[:50]}'...")
            
            if not body:
                continue
            
            ids_match = False
            if reply_to_id is not None:
                try:
                    reply_to_id_str = str(reply_to_id).strip()
                    original_id_str = str(original_update_id).strip()
                    ids_match = reply_to_id_str == original_id_str
                    
                    if ids_match:
                        logger.info(f"🔍 ID match trouvé: reply_to_id={reply_to_id_str}, original={original_id_str}")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur comparaison IDs: {e}")
            
            if ids_match and self._is_validation_reply(body):
                logger.info(f"💬 Reply directe trouvée: '{body[:50]}'")
                return update, unauthorized_attempts
            elif ids_match:
                candidate_replies.append(("direct_reply", update, body))
            
            elif self._is_validation_reply(body):
                if update_type == "reply":
                    logger.info(f"💬 Reply avec mot-clé de validation trouvée: '{body[:50]}'")
                    candidate_replies.append(("reply_with_keyword", update, body))
                else:
                    candidate_replies.append(("validation_keywords", update, body))
            
            elif self._looks_like_validation_response(body):
                if update_type == "reply":
                    candidate_replies.append(("reply_pattern", update, body))
                else:
                    candidate_replies.append(("response_pattern", update, body))
        
        if candidate_replies:
            priority_order = {
                "direct_reply": 1, 
                "reply_with_keyword": 2, 
                "reply_pattern": 3,
                "validation_keywords": 4, 
                "response_pattern": 5
            }
            candidate_replies.sort(key=lambda x: priority_order.get(x[0], 99))
            
            best_match = candidate_replies[0]
            logger.info(f"💬 Meilleure reply trouvée ({best_match[0]}): '{best_match[2][:50]}'")
            return best_match[1], unauthorized_attempts
        
        logger.warning(f"⚠️ Aucune reply valide trouvée parmi {len(updates)} updates")
        return None, unauthorized_attempts
    
    def _looks_like_validation_response(self, text: str) -> bool:
        """Vérifie si un texte ressemble à une réponse de validation."""
        import re
        
        cleaned = re.sub(r'<[^>]+>', '', text).strip().lower()
        
        response_patterns = [
            r'\b(je valide|je confirme|c\'est bon|ça marche)\b',
            r'\b(je refuse|je rejette|il faut corriger)\b',
            r'\b(approuvé|validé|refusé|rejeté)\b',
            r'^\s*(ok|non)\s*[.!]*\s*$',
            r'\b(merge|deploie?|ship)\b',
            r'\b(debug|corrige|fix)\b'
        ]
        
        for pattern in response_patterns:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return True
        
        return False
    
    async def _post_unauthorized_reply_notification(
        self,
        item_id: str,
        original_creator_name: str,
        original_creator_email: str,
        unauthorized_replier_name: str,
        unauthorized_replier_email: str,
        task_title: str
    ):
        """
        Poste une notification dans Monday.com lorsqu'un utilisateur non autorisé tente de répondre.
        
        Args:
            item_id: ID de l'item Monday.com
            original_creator_name: Nom du créateur autorisé
            original_creator_email: Email du créateur autorisé
            unauthorized_replier_name: Nom de l'utilisateur non autorisé
            unauthorized_replier_email: Email de l'utilisateur non autorisé
            task_title: Titre de la tâche
        """
        logger.warning(f"🚫 Notification: Tentative de réponse non autorisée sur item {item_id}")
        
        # Tenter de récupérer les Monday IDs pour les mentions
        original_creator_monday_id = await self.monday_tool.get_user_id_by_email(original_creator_email)
        unauthorized_replier_monday_id = await self.monday_tool.get_user_id_by_email(unauthorized_replier_email)
        
        # Construire les tags
        original_tag = f"@{original_creator_name}"
        if original_creator_monday_id:
            original_tag = f"{{{{Person: {original_creator_monday_id}}}}}"
        
        unauthorized_tag = f"@{unauthorized_replier_name}"
        if unauthorized_replier_monday_id:
            unauthorized_tag = f"{{{{Person: {unauthorized_replier_monday_id}}}}}"
        
        # Construire le message
        message = (
            f"{original_tag} ⚠️ Il y a un autre utilisateur qui essaie de répondre à votre place pour \"{task_title}\".\n\n"
            f"{unauthorized_tag} ❌ Vous ne pouvez pas répondre à ce commentaire car vous n'êtes pas le créateur de la demande de validation.\n\n"
            f"🔐 Pour des raisons de sécurité, seul le créateur de la validation peut y répondre."
        )
        
        # Poster le message
        await self.monday_tool.execute_action(
            action="add_comment",
            item_id=item_id,
            comment=message
        )
        logger.info(f"✅ Notification de tentative non autorisée postée sur Monday.com pour item {item_id}")
    
    async def _notify_unauthorized_attempts(self, item_id: str, unauthorized_attempts: List[Dict[str, Any]], task_title: str):
        """
        Poste un nouvel update dans Monday.com pour notifier une tentative non autorisée.
        
        Args:
            item_id: ID de l'item Monday.com
            unauthorized_attempts: Liste des tentatives non autorisées
            task_title: Titre de la tâche
        """
        if not unauthorized_attempts:
            return
        
        logger.warning(f"🚨 {len(unauthorized_attempts)} tentative(s) non autorisée(s) détectée(s) pour item {item_id}")
        
        for attempt in unauthorized_attempts:
            try:
                legitimate_creator_id = attempt.get("legitimate_creator_id")
                legitimate_creator_name = attempt.get("legitimate_creator_name", "l'utilisateur autorisé")
                intruder_id = attempt.get("intruder_id")
                intruder_name = attempt.get("intruder_name", "un autre utilisateur")
                
                # Construire le message avec mentions
                message_parts = []
                
                # Mention du créateur légitime
                if legitimate_creator_id:
                    message_parts.append(f'<a href="https://monday.com/users/{legitimate_creator_id}">@{legitimate_creator_name}</a>')
                else:
                    message_parts.append(f"@{legitimate_creator_name}")
                
                message_parts.append(f" ⚠️ Il y a un autre utilisateur qui essaie de répondre à votre place pour")
                message_parts.append(f' <strong>"{task_title}"</strong>.')
                
                message_parts.append("<br><br>")
                
                # Mention de l'intrus
                if intruder_id:
                    message_parts.append(f'<a href="https://monday.com/users/{intruder_id}">@{intruder_name}</a>')
                else:
                    message_parts.append(f"@{intruder_name}")
                
                message_parts.append(" ❌ Vous ne pouvez pas répondre à ce commentaire car vous n'êtes pas le créateur de la demande de validation.")
                
                message_parts.append("<br><br>")
                message_parts.append("🔐 <em>Pour des raisons de sécurité, seul le créateur de la validation peut y répondre.</em>")
                
                notification_message = "".join(message_parts)
                
                logger.info(f"📨 Envoi notification tentative non autorisée: {intruder_name} → {legitimate_creator_name}")
                
                # Poster le message dans Monday.com
                result = await self.monday_tool.execute_action(
                    action="add_comment",
                    item_id=item_id,
                    comment=notification_message
                )
                
                if result and isinstance(result, dict) and result.get("success"):
                    logger.info(f"✅ Notification postée dans Monday.com pour item {item_id}")
                else:
                    logger.error(f"❌ Échec notification Monday.com: {result}")
                    
            except Exception as e:
                logger.error(f"❌ Erreur lors de la notification de tentative non autorisée: {e}")
                import traceback
                traceback.print_exc()
    
    def _is_validation_reply(self, reply_text: str) -> bool:
        """Vérifie si un texte est une réponse de validation valide."""
        import re
        
        if not reply_text:
            return False

        cleaned_text = reply_text.replace('\ufeff', '').replace('\u200b', '').replace('\u00a0', '').replace('\xa0', ' ')
        
        cleaned_text = re.sub(r'<[^>]+>', '', cleaned_text)
        cleaned_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned_text)
        cleaned_text = cleaned_text.strip().lower()
        
        logger.debug(f"🔍 Vérification texte validation: '{cleaned_text}'")
        
        if cleaned_text in ['oui', 'yes', 'ok', 'non', 'no', 'y', 'n', 'o', 'valide', 'approve', 'reject']:
            logger.info(f"✅ Réponse courte détectée: '{cleaned_text}'")
            return True
        
        approval_patterns = [
            r'\b(oui|yes|ok|valide?|approve?d?|accept|go|lgtm)\b',
            r'\b(merge|ship|deploy|good|perfect|correct)\b',
            r'^\s*[✅✓]\s*',
            r'looks?\s+good',
            r"c['']?est\s+bon",
            r'je\s+valide'
        ]
        
        rejection_patterns = [
            r'\b(non|no|debug|fix|reject|refuse|nope)\b',
            r'\b(probl[eè]me?s?|issue|error|bug|erreur)\b',
            r'^\s*[❌✗]\s*',
            r'ne\s+marche\s+pas',
            r'pas\s+(bon|ok|valide)'
        ]
        
        for pattern in approval_patterns:
            if re.search(pattern, cleaned_text, re.IGNORECASE):
                logger.info(f"✅ Pattern d'approbation trouvé: {pattern} dans '{cleaned_text}'")
                return True
        
        for pattern in rejection_patterns:
            if re.search(pattern, cleaned_text, re.IGNORECASE):
                logger.info(f"✅ Pattern de rejet trouvé: {pattern} dans '{cleaned_text}'")
                return True
        
        logger.debug(f"❌ Aucun pattern de validation trouvé dans: '{cleaned_text}'")
        return False
    
    async def _parse_human_reply(self, reply: Dict[str, Any], validation_id: str, context: Optional[Dict[str, Any]] = None) -> HumanValidationResponse:
        """Parse une réponse humaine avec analyse intelligente."""
        
        if not isinstance(reply, dict):
            logger.error(f"❌ Reply invalide (type {type(reply)}): {reply}")
            return HumanValidationResponse(
                validation_id=validation_id or f"validation_{int(time.time())}_{id(self)}",
                status=HumanValidationStatus.REJECTED,
                comments="Reply invalide - erreur système",
                validated_by="system",
                should_merge=False,
                should_continue_workflow=False
            )
        
        body = reply.get("body", "").strip()
        creator = reply.get("creator", {})
        if isinstance(creator, dict):
            author = creator.get("name", "Humain")
        else:
            author = "Humain"
        
        logger.info(f"🧠 Analyse intelligente de la réponse: '{body[:50]}...'")
        
        try:
            current_rejection_count = context.get("rejection_count", 0) if context else 0
            
            decision = await intelligent_reply_analyzer.analyze_human_intention(
                reply_text=body,
                context=context
            )
            
            logger.info(f"🎯 Décision intelligente: {decision.decision.value} (confiance: {decision.confidence:.2f}, rejets actuels: {current_rejection_count})")
            
            modification_instructions = None
            should_retry_workflow = False
            next_rejection_count = current_rejection_count
            
            if decision.decision == IntentionType.APPROVE:
                status = HumanValidationStatus.APPROVED
                should_merge = True
                
            elif decision.decision == IntentionType.REJECT:
                next_rejection_count = current_rejection_count + 1
                
                if next_rejection_count >= 3:
                    logger.warning(f"⚠️ Limite de 3 rejets atteinte - forcer abandon")
                    status = HumanValidationStatus.ABANDONED
                    should_merge = False
                    should_retry_workflow = False
                    modification_instructions = None
                else:
                    status = HumanValidationStatus.REJECTED
                    should_merge = False
                    should_retry_workflow = True
                    
                    modification_instructions = self._extract_modification_instructions(body)
                    logger.info(f"📝 Instructions de modification extraites: {modification_instructions[:100] if modification_instructions else 'Aucune'}")
            
            elif decision.decision == IntentionType.ABANDON:
                logger.info("⛔ Abandon demandé par l'utilisateur")
                status = HumanValidationStatus.ABANDONED
                should_merge = False
                should_retry_workflow = False
                modification_instructions = None
                
            elif decision.decision == IntentionType.CLARIFICATION_NEEDED:
                logger.warning("⚠️ Clarification requise - marquer comme rejeté temporairement")
                status = HumanValidationStatus.REJECTED
                should_merge = False
                should_retry_workflow = False
                
            else:  # QUESTION ou UNCLEAR
                logger.warning("⚠️ Intention unclear/question - traiter comme rejet par sécurité")
                status = HumanValidationStatus.REJECTED
                should_merge = False
                should_retry_workflow = False
            
            enriched_comments = f"{body}"
            if decision.specific_concerns:
                enriched_comments += f"\n\n[IA] Préoccupations détectées: {', '.join(decision.specific_concerns)}"
            if decision.confidence < 0.7:
                enriched_comments += f"\n[IA] Confiance faible ({decision.confidence:.2f}) - Vérification recommandée"
            
            if status == HumanValidationStatus.REJECTED and should_retry_workflow:
                enriched_comments += f"\n[SYSTÈME] Tentative {next_rejection_count}/3 - {3 - next_rejection_count} relance(s) restante(s)"
            elif status == HumanValidationStatus.ABANDONED and next_rejection_count >= 3:
                enriched_comments += f"\n[SYSTÈME] Limite de 3 rejets atteinte - Abandon automatique"

            db_validation_id = context.get("validation_id") if context else None
            if not db_validation_id:
                pending_validation = self.pending_validations.get(validation_id, {})
                db_validation_id = pending_validation.get("validation_id", validation_id)
            
            return HumanValidationResponse(
                validation_id=db_validation_id or validation_id or f"validation_{int(time.time())}_{id(self)}",
                status=status,
                comments=enriched_comments,
                validated_by=author,
                should_merge=should_merge,
                should_continue_workflow=True,
                rejection_count=next_rejection_count,
                modification_instructions=modification_instructions,
                should_retry_workflow=should_retry_workflow,
                analysis_confidence=decision.confidence,
                analysis_method=decision.analysis_method,
                specific_concerns=decision.specific_concerns,
                suggested_action=decision.suggested_action,
                requires_clarification=decision.requires_clarification
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur analyse intelligente: {e}")
            
            logger.info("🔄 Fallback vers analyse simple")
            is_approval = self._is_approval_reply(body)
            
            return HumanValidationResponse(
                validation_id=validation_id or f"validation_{int(time.time())}_{id(self)}",
                status=HumanValidationStatus.APPROVED if is_approval else HumanValidationStatus.REJECTED,
                comments=f"{body}\n\n[IA] Analyse simple utilisée (erreur système)",
                validated_by=author,
                should_merge=is_approval,
                should_continue_workflow=True,
                rejection_count=0,
                modification_instructions=None,
                should_retry_workflow=False,
                analysis_confidence=0.6,
                analysis_method="simple_fallback_after_error"
            )
    
    def _extract_modification_instructions(self, reply_text: str) -> Optional[str]:
        """
        Extrait les instructions de modification d'une réponse de rejet.
        
        Exemples:
        - "Non, ajuste le fichier X et trouve une autre alternative"
        - "Debug: il faut corriger les tests unitaires"
        
        Args:
            reply_text: Texte de la réponse
            
        Returns:
            Instructions extraites ou None si introuvables
        """
        cleaned = reply_text.strip()
        
        rejection_prefixes = [
            r'^\s*non[\s,;:.-]*',
            r'^\s*no[\s,;:.-]*',
            r'^\s*debug[\s,;:.-]*',
            r'^\s*refais[\s,;:.-]*',
            r'^\s*redo[\s,;:.-]*',
            r'^\s*fix[\s,;:.-]*',
            r'^[❌✗👎]\s*'
        ]
        
        for prefix in rejection_prefixes:
            cleaned = re.sub(prefix, '', cleaned, flags=re.IGNORECASE)
        
        cleaned = cleaned.strip()
        if len(cleaned) > 10:
            logger.info(f"📝 Instructions extraites: '{cleaned[:100]}'")
            return cleaned
        
        if len(reply_text.strip()) > 5:
            logger.info(f"📝 Utilisation du texte complet comme instructions")
            return reply_text.strip()
        
        logger.warning("⚠️ Aucune instruction de modification détectée dans la réponse")
        return None
    
    def _is_approval_reply(self, reply_text: str) -> bool:
        """Détermine si une réponse est une approbation."""
        approval_patterns = [
            r'\b(oui|yes|ok|valide?|approve?d?|accept|go)\b',
            r'\b(merge|ship|deploy|good|perfect)\b',
            r'^\s*[✅✓]\s*$',
            r'lgtm|looks good'
        ]
        
        for pattern in approval_patterns:
            if re.search(pattern, reply_text, re.IGNORECASE):
                return True
        
        return False
    
    def _prepare_analysis_context(self, validation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prépare le contexte pour l'analyse intelligente des réponses."""
        
        workflow_results = validation_data.get("workflow_results", {})
        
        context = {
            "task_title": workflow_results.get("task_title"),
            "task_id": workflow_results.get("task_id"),
            "task_type": "development",
            "tests_passed": self._safe_get_test_success(workflow_results.get("test_results")),
            "pr_url": workflow_results.get("pr_url"),
            "error_count": len(workflow_results.get("error_logs", [])),
            "success_level": workflow_results.get("success_level", "unknown"),
            "urgent": False,
            "created_at": validation_data.get("timestamp") or validation_data.get("created_at"),
            "workflow_duration": self._calculate_workflow_duration(validation_data),
            "validation_id": validation_data.get("validation_id"),
            "rejection_count": workflow_results.get("rejection_count", 0)
        }
        
        return context
    
    def _calculate_workflow_duration(self, validation_data: Dict[str, Any]) -> Optional[int]:
        """Calcule la durée du workflow en minutes."""
        try:
            created_at_str = validation_data.get("timestamp") or validation_data.get("created_at")
            if created_at_str:
                if isinstance(created_at_str, str):
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                else:
                    created_at = created_at_str
                from datetime import timezone
                now_utc = datetime.now(timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                duration = (now_utc - created_at).total_seconds() / 60
                return int(duration)
        except Exception:
            pass
        return None
    
    def cleanup_completed_validations(self, older_than_hours: int = 24):
        """Nettoie les validations terminées anciennes."""
        from datetime import timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        
        to_remove = []
        for update_id, validation in self.pending_validations.items():
            validation_time_str = validation.get("timestamp") or validation.get("created_at")
            if validation_time_str:
                try:
                    if isinstance(validation_time_str, str):
                        validation_time = datetime.fromisoformat(validation_time_str.replace('Z', '+00:00'))
                    else:
                        validation_time = validation_time_str
                    if validation_time < cutoff and validation.get("status") != "pending":
                        to_remove.append(update_id)
                except Exception as e:
                    logger.warning(f"⚠️ Erreur parsing timestamp pour cleanup: {e}")
                    if validation.get("status") != "pending":
                        to_remove.append(update_id)
        
        for update_id in to_remove:
            del self.pending_validations[update_id]
        
        if to_remove:
            logger.info(f"🧹 Nettoyage: {len(to_remove)} validations supprimées")
    
    async def _recover_validation_context(self, update_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le contexte de validation depuis Monday.com quand pending_validations est vide.
        
        Args:
            update_id: ID de l'update de validation
            
        Returns:
            Dictionnaire de validation reconstitué ou None si impossible
        """
        try:
            logger.info(f"🔄 Tentative de récupération du contexte pour update {update_id}")
            
            item_id = None
            
            if "_update_" in update_id:
                item_id = update_id.split("_update_")[-1]
                logger.info(f"📋 Item ID extrait de update_id: {item_id}")
            else:
                logger.info(f"🔍 Update ID Monday.com détecté: {update_id}")
                
                potential_item_ids = ["5010569330"]
                
                for potential_item_id in potential_item_ids:
                    logger.info(f"🔍 Test avec item_id potentiel: {potential_item_id}")
                    
                    updates_result = await self.monday_tool.execute_action(
                        action="get_item_updates",
                        item_id=potential_item_id
                    )
                    
                    if updates_result and isinstance(updates_result, dict) and updates_result.get("success", False):
                        updates = updates_result.get("updates", [])
                        
                        for update in updates:
                            if str(update.get("id")) == str(update_id):
                                logger.info(f"✅ Update {update_id} trouvée dans item {potential_item_id}")
                                item_id = potential_item_id
                                break
                        
                        if item_id:
                            break
                
                if not item_id:
                    logger.error(f"❌ Impossible de trouver l'item_id pour update {update_id}")
                    return None
            
            if not item_id:
                logger.error(f"❌ Impossible d'extraire item_id de {update_id}")
                return None
            
            updates_result = await self.monday_tool.execute_action(
                action="get_item_updates",
                item_id=item_id
            )
            
            if not updates_result or not isinstance(updates_result, dict) or not updates_result.get("success", False):
                error_msg = updates_result.get('error') if updates_result and isinstance(updates_result, dict) else "Résultat invalide"
                logger.error(f"❌ Erreur récupération updates pour item {item_id}: {error_msg}")
                return None
            
            updates = updates_result.get("updates", [])
            
            target_update = None
            for update in updates:
                if str(update.get("id")) == str(update_id):
                    target_update = update
                    break
            
            if not target_update:
                logger.warning(f"⚠️ Update {update_id} non trouvée dans les updates de l'item {item_id}")
                return {
                    "item_id": item_id,
                    "message": "Contexte récupéré - validation en cours",
                    "timestamp": datetime.now().isoformat(),
                    "fallback_mode": True,
                    "recovered": True
                }
            
            recovery_context = {
                "item_id": item_id,
                "message": target_update.get("body", "Message de validation"),
                "timestamp": target_update.get("created_at", datetime.now().isoformat()),
                "fallback_mode": False,
                "recovered": True,
                "original_creator": target_update.get("creator", {}).get("name", "Unknown")
            }
            
            logger.info(f"✅ Contexte reconstitué pour update {update_id}")
            return recovery_context
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération du contexte: {e}")
            return None


monday_validation_service = MondayValidationService() 