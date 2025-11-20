"""Service pour traiter et persister les webhooks Monday.com."""

import re
import html
import traceback
from typing import Dict, Any, Optional
from services.database_persistence_service import db_persistence
from utils.logger import get_logger
from utils.task_lock_manager import task_lock_manager  
from services.redis_idempotence_service import redis_idempotence_service  
from services.webhook_signature_validator import webhook_signature_validator  
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class WebhookPersistenceService:
    """Service pour traiter et persister les webhooks Monday.com en temps réel."""
    
    @staticmethod
    async def process_monday_webhook(payload: Dict[str, Any], headers: Dict[str, str] = None, 
                                   signature: str = None) -> Dict[str, Any]:
        """
        Traite un webhook Monday.com et l'enregistre en base.
        
        Args:
            payload: Données du webhook
            headers: Headers HTTP
            signature: Signature de sécurité
            
        Returns:
            Résultat du traitement avec task_id créé
        """
        if not redis_idempotence_service._initialized:
            await redis_idempotence_service.initialize()
        
        if not db_persistence.db_manager._is_initialized:
            await db_persistence.initialize()
        
        webhook_id = None
        task_id = None
        monday_item_id = None
        
        try:
            if not settings.vydata_reactivation_v2:
                logger.warning("⚠️ Système @vydata désactivé (VYDATA_REACTIVATION_V2=false)")
                return {
                    "success": False,
                    "error": "Système @vydata désactivé",
                    "feature_disabled": True
                }
            
            if settings.monday_signing_secret:
                is_valid, error_msg = webhook_signature_validator.validate_request(
                    payload=payload,
                    headers=headers or {}
                )
                
                if not is_valid:
                    logger.error(f"❌ Signature HMAC invalide: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "status_code": 401
                    }
            
            if not payload or not isinstance(payload, dict):
                raise ValueError("Payload webhook invalide")
                
            event = payload.get("event", {})
            if not event:
                raise ValueError("Aucun événement dans le payload webhook")
            
            is_retry = event.get("isRetry", False)
            if is_retry:
                logger.warning("="*80)
                logger.warning("🔄 WEBHOOK EN RETRY DÉTECTÉ - IGNORÉ")
                logger.warning("="*80)
                logger.warning(f"📌 Pulse ID: {event.get('pulseId')}")
                logger.warning(f"📋 Type: {event.get('type')}")
                logger.warning(f"🔄 isRetry: {is_retry}")
                logger.warning("💡 Monday.com renvoie ce webhook - on l'ignore pour éviter les doublons")
                logger.warning("="*80)
                return {
                    "success": True,
                    "message": "Webhook en retry ignoré (isRetry=True)",
                    "skipped_retry": True,
                    "pulse_id": event.get('pulseId'),
                    "event_type": event.get('type')
                }
            
            monday_item_id = event.get("pulseId") or event.get("itemId")
            event_type = payload.get("type", "unknown")
            update_id = event.get("updateId") or event.get("update_id") or f"{monday_item_id}_{event_type}"
            
            if await redis_idempotence_service.is_webhook_processed(update_id):
                logger.info(f"🚫 Webhook déjà traité: {update_id} (Redis)")
                return {
                    "success": True,
                    "message": "Webhook déjà traité (idempotence Redis)",
                    "deduplicated": True
                }
            
            payload_hash = redis_idempotence_service.create_payload_hash(payload)
            
            if await redis_idempotence_service.is_event_duplicate(
                monday_item_id, event_type, payload_hash
            ):
                logger.info(f"🚫 Événement doublon: {monday_item_id}/{event_type}")
                return {
                    "success": True,
                    "message": "Événement doublon (déduplication fine)",
                    "deduplicated": True
                }
            
            if monday_item_id and not await task_lock_manager.acquire_with_cooldown(monday_item_id, timeout=2.0):
                logger.warning(
                    f"🚫 Webhook bloqué pour item {monday_item_id} - déjà en traitement ou cooldown actif",
                    monday_item_id=monday_item_id
                )
                return {
                    "success": False,
                    "error": "Webhook already being processed or in cooldown",
                    "monday_item_id": monday_item_id,
                    "locked": True
                }
            
            try:
                webhook_id = await db_persistence._log_webhook_event(
                    source="monday",
                    event_type=payload.get("type", "unknown"),
                    payload=payload,
                    headers=headers or {},
                    signature=signature
                )
                
                logger.info(f"📨 Webhook Monday.com reçu: {webhook_id}")
                
                event_type = event.get("type", "unknown")
                
                logger.info(f"🔍 Type d'événement détecté: '{event_type}'")
                
                if event_type in ["create_update", "create_reply"]:
                    logger.info("="*80)
                    logger.info(f"🔔 TRAITEMENT ÉVÉNEMENT UPDATE/REPLY PRIORITAIRE")
                    logger.info("="*80)
                    logger.info(f"📋 Type: {event_type}")
                    logger.info(f"🆔 Webhook ID: {webhook_id}")
                    
                    reactivation_result = await WebhookPersistenceService._handle_update_event(event, webhook_id)
                    
                    if reactivation_result and reactivation_result.get('is_reactivation'):
                        await db_persistence._mark_webhook_processed(webhook_id, True)
                        
                        await redis_idempotence_service.mark_webhook_processed(
                            update_id, 
                            {
                                "task_id": reactivation_result['task_id'],
                                "run_id": reactivation_result.get('run_id'),
                                "action": "reactivation"
                            },
                            ttl_seconds=3600  # 1h
                        )
                        await redis_idempotence_service.mark_event_processed(
                            monday_item_id, event_type, payload_hash
                        )
                        
                        logger.info("="*80)
                        logger.info("🎉 RÉACTIVATION DÉTECTÉE !")
                        logger.info("="*80)
                        logger.info(f"📝 Task ID: {reactivation_result['task_id']}")
                        logger.info(f"🔄 Run ID: {reactivation_result.get('run_id')}")
                        logger.info(f"💪 Confidence: {reactivation_result.get('confidence', 'N/A')}")
                        logger.info(f"📊 Raison: {reactivation_result.get('reactivation_reason', 'N/A')}")
                        logger.info("="*80)
                        
                        return {
                            "success": True,
                            "webhook_id": webhook_id,
                            "task_id": reactivation_result['task_id'],
                            "task_exists": True,
                            "is_reactivation": True,
                            "message": f"Réactivation de la tâche suite à update Monday.com",
                            "reactivation_data": reactivation_result
                        }
                    else:
                        await db_persistence._mark_webhook_processed(webhook_id, True)
                        return {
                            "success": True,
                            "webhook_id": webhook_id,
                            "task_id": None,
                            "task_exists": True,
                            "is_reactivation": False,
                            "message": "Update/commentaire traité sans réactivation"
                        }
                        
                elif event_type in ["create_pulse", "update_column_value"]:
                    logger.info(f"📝 Traitement événement item: {event_type}")
                    task_result = await WebhookPersistenceService._handle_item_event(event, webhook_id)
                    
                    if task_result:
                        if isinstance(task_result, dict):
                            task_id = task_result["task_id"]
                            is_existing = task_result.get("existing", False)
                            is_reactivation = task_result.get("is_reactivation", False)
                            
                            await db_persistence._mark_webhook_processed(webhook_id, True)
                            
                            return {
                                "success": True,
                                "webhook_id": webhook_id,
                                "task_id": task_id,
                                "task_exists": is_existing and not is_reactivation,
                                "is_reactivation": is_reactivation,
                                "message": "Tâche réactivée" if is_reactivation else ("Tâche mise à jour" if is_existing else "Nouvelle tâche créée")
                            }
                        else:
                            task_id = task_result
                            await db_persistence._mark_webhook_processed(webhook_id, True)
                            return {
                                "success": True,
                                "webhook_id": webhook_id,
                                "task_id": task_id,
                                "task_exists": False,
                                "is_reactivation": False,
                                "message": "Nouvelle tâche créée (format legacy)"
                            }
                    else:
                        logger.warning("⚠️ Aucune tâche créée/mise à jour")
                        return {
                            "success": False,
                            "webhook_id": webhook_id,
                            "error": "Aucune tâche créée"
                        }
                    
                elif False and event_type in ["create_update", "create_reply"]:
                    logger.error("="*80)
                    logger.error("❌ ERREUR: Cette section ne devrait jamais s'exécuter")
                    logger.error("Le code a été déplacé au début du traitement (ligne 60)")
                    logger.error("="*80)
                    
                    reactivation_result = await WebhookPersistenceService._handle_update_event(event, webhook_id)
                    
                    if reactivation_result is None:
                        await db_persistence._mark_webhook_processed(webhook_id, True)
                        logger.info("ℹ️ Update traité mais aucune réactivation déclenchée")
                        return {
                            "success": True,
                            "webhook_id": webhook_id,
                            "task_id": None,
                            "task_exists": True,
                            "is_reactivation": False,
                            "message": "Update/commentaire traité sans réactivation"
                        }
                    elif reactivation_result.get('is_reactivation'):
                        await db_persistence._mark_webhook_processed(webhook_id, True)
                        logger.info("="*80)
                        logger.info("🎉 RÉACTIVATION DÉTECTÉE ET RÉUSSIE !")
                        logger.info("="*80)
                        logger.info(f"📝 Task ID: {reactivation_result['task_id']}")
                        logger.info(f"🔄 Run ID: {reactivation_result.get('run_id')}")
                        logger.info(f"💪 Confidence: {reactivation_result.get('confidence', 'N/A')}")
                        logger.info(f"📊 Raison: {reactivation_result.get('reactivation_reason', 'N/A')}")
                        logger.info("="*80)
                        
                        return {
                            "success": True,
                            "webhook_id": webhook_id,
                            "task_id": reactivation_result['task_id'],
                            "task_exists": True,
                            "is_reactivation": True,
                            "message": f"Réactivation de la tâche suite à update Monday.com",
                            "reactivation_data": reactivation_result
                        }
                    else:
                        await db_persistence._mark_webhook_processed(webhook_id, True)
                        logger.info("ℹ️ Update traité normalement sans réactivation")
                        return {
                            "success": True,
                            "webhook_id": webhook_id,
                            "task_id": reactivation_result.get('task_id'),
                            "task_exists": True,
                            "is_reactivation": False,
                            "message": "Update/commentaire traité sans réactivation"
                        }
                else:
                    logger.warning(f"⚠️ Type d'événement non supporté: {event_type}")
                    await db_persistence._mark_webhook_processed(webhook_id, True, f"Type non supporté: {event_type}")
                    
                    return {
                        "success": True,
                        "webhook_id": webhook_id,
                        "task_id": None,
                        "task_exists": True,
                        "is_reactivation": False,
                        "message": f"Événement ignoré: {event_type}"
                    }
            
            finally:
                if monday_item_id:
                    task_lock_manager.release(monday_item_id)
                    logger.debug(f"🔓 Verrou libéré pour item {monday_item_id}")
                    
        except Exception as e:
            logger.error(f"❌ Erreur traitement webhook: {e}")
            
            if webhook_id:
                await db_persistence._mark_webhook_processed(webhook_id, False, str(e))
            
            if monday_item_id:
                task_lock_manager.release(monday_item_id)
            
            return {
                "success": False,
                "webhook_id": webhook_id,
                "task_id": None,
                "task_exists": False,
                "is_reactivation": False,
                "error": str(e),
                "message": "Erreur lors du traitement du webhook"
            }
    
    @staticmethod
    async def _handle_item_event(payload: Dict[str, Any], webhook_id: int) -> Optional[int]:
        """Traite un événement d'item Monday.com (création/modification)."""
        try:
            pulse_id = payload.get("pulseId")
            pulse_name = payload.get("pulseName", "Tâche sans titre")
            board_id = payload.get("boardId")
            
            column_values = payload.get("columnValues", {})
            
            if not column_values or len(column_values) < 2:
                logger.info(f"🔄 Enrichissement du payload via API Monday.com pour item {pulse_id}")
                
                try:
                    from tools.monday_tool import MondayTool
                    monday_tool = MondayTool()
                    item_info = await monday_tool._arun(action="get_item_info", item_id=str(pulse_id))
                    
                    if item_info.get("success") and item_info.get("column_values"):
                        payload["columnValues"] = item_info["column_values"]
                        payload["column_values"] = item_info["column_values"]
                        logger.info(f"✅ Payload enrichi avec {len(item_info['column_values'])} colonnes")
                        logger.info(f"📋 Colonnes récupérées: {list(item_info['column_values'].keys())}")
                    else:
                        logger.warning(f"⚠️ Impossible d'enrichir le payload pour item {pulse_id}: {item_info.get('error', 'Erreur inconnue')}")
                        
                except Exception as e:
                    logger.error(f"❌ Erreur lors de l'enrichissement du payload: {e}")
            else:
                logger.info(f"✅ Payload contient déjà {len(column_values)} colonnes")
            
            existing_task = await db_persistence._find_task_by_monday_id(pulse_id)
            
            if existing_task:
                logger.info(f"🔍 Tâche existante trouvée: ID={existing_task}")
            else:
                logger.info(f"✨ Nouvelle tâche à créer pour pulse_id={pulse_id}")
            
            if existing_task:
                async with db_persistence.db_manager.get_connection() as conn:
                    existing_task_info = await conn.fetchrow("""
                        SELECT internal_status, monday_status, reactivation_count
                        FROM tasks
                        WHERE tasks_id = $1
                    """, existing_task)
                    
                    task_details = await conn.fetchrow("""
                        SELECT monday_item_id, title, description, repository_url
                        FROM tasks
                        WHERE tasks_id = $1
                    """, existing_task)
                
                current_status = payload.get("value", {}).get("label", {}).get("text", "")
                
                is_completed = existing_task_info and existing_task_info['internal_status'] in ['completed', 'failed', 'quality_check']
                is_working_status = current_status.lower() in ["en cours", "à faire", "to do", "in progress", "working on it", "working"]
                
                logger.info(f"🔍 Vérification réactivation:")
                logger.info(f"   - internal_status en DB: {existing_task_info['internal_status'] if existing_task_info else 'N/A'}")
                logger.info(f"   - monday_status en DB: {existing_task_info['monday_status'] if existing_task_info else 'N/A'}")
                logger.info(f"   - current_status du webhook: '{current_status}'")
                logger.info(f"   - is_completed: {is_completed}")
                logger.info(f"   - is_working_status: {is_working_status}")
                logger.info(f"   - columnId: {payload.get('columnId')}")
                
                if is_completed and is_working_status:
                    logger.info("="*80)
                    logger.info("🔄 RÉACTIVATION DÉTECTÉE VIA CHANGEMENT DE STATUT")
                    logger.info("="*80)
                    logger.info(f"🆔 Task ID: {existing_task}")
                    logger.info(f"📊 Ancien statut: {existing_task_info['internal_status']}")
                    logger.info(f"🔄 Nouveau statut: {current_status}")
                    logger.info(f"🔢 Réactivations précédentes: {existing_task_info['reactivation_count']}")
                    logger.info("="*80)
                    
                    from services.workflow_reactivation_service import workflow_reactivation_service
                    from services.reactivation_service import UpdateAnalysis
                    
                    update_analysis = UpdateAnalysis(
                        requires_reactivation=True,
                        confidence=1.0,
                        reasoning=f"Changement de statut vers '{current_status}' sur une tâche terminée",
                        is_from_agent=False
                    )
                    
                    update_text = f"Réactivation via changement de statut vers '{current_status}'"
                    try:
                        from tools.monday_tool import MondayTool
                        monday_tool = MondayTool()
                        
                        updates_result = await monday_tool._arun(
                            action="get_item_updates",
                            item_id=str(task_details['monday_item_id'])
                        )
                        
                        if isinstance(updates_result, dict):
                            updates = updates_result.get('updates', [])
                        elif isinstance(updates_result, list):
                            updates = updates_result
                        else:
                            updates = []
                        
                        if updates and len(updates) > 0:
                            logger.info(f"🔍 DEBUG: {len(updates)} updates à analyser")
                            for i, u in enumerate(updates):
                                text = u.get('body', '')
                                logger.info(f"  Update {i+1}: body='{text[:80] if text else 'VIDE'}...'")
                            
                            human_updates = [
                                u for u in updates 
                                if u.get('body', '').strip() 
                                and not u.get('body', '').startswith('🤖')
                                and not u.get('body', '').startswith('✅ Validation')
                            ]
                            
                            logger.info(f"🔍 DEBUG: {len(human_updates)} commentaires humains après filtrage")
                            
                            if human_updates:
                                latest_update = human_updates[0]
                                update_text_raw = latest_update.get('body', '').strip()
                                
                                update_text = re.sub(r'<[^>]+>', '', update_text_raw)
                                update_text = html.unescape(update_text).strip()
                                
                                logger.info(f"✅ Dernier commentaire humain récupéré (nettoyé): '{update_text[:100]}...'")
                            else:
                                logger.info("⚠️ Aucun commentaire humain trouvé, utilisation du texte par défaut")
                        else:
                            logger.info("⚠️ Aucun update trouvé pour cette tâche")
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur récupération dernier commentaire (non-bloquant): {e}")
                        import traceback
                        logger.debug(f"Stack trace: {traceback.format_exc()}")
                    
                    try:
                        reactivation_result = await workflow_reactivation_service.create_new_workflow_run_from_update(
                            task_id=existing_task,
                            monday_item_id=str(task_details['monday_item_id']),
                            update_analysis=update_analysis,
                            update_text=update_text,
                            board_id=board_id
                        )
                        
                        if reactivation_result.get('success'):
                            logger.info(f"✅ Workflow de réactivation créé: run_id={reactivation_result['run_id']}")
                            return {
                                "task_id": existing_task,
                                "is_reactivation": True,
                                "existing": True,
                                "run_id": reactivation_result['run_id'],
                                "reactivation_data": reactivation_result,
                                "reactivation_count": reactivation_result['reactivation_count'],
                                "source_branch": reactivation_result.get('source_branch', 'main'),
                                "update_text": reactivation_result.get('update_text', '')
                            }
                        else:
                            error_msg = reactivation_result.get('error', 'Erreur inconnue')
                            logger.error("="*80)
                            logger.error("❌ ÉCHEC CRITIQUE DE RÉACTIVATION VIA STATUT")
                            logger.error("="*80)
                            logger.error(f"🆔 Task ID: {existing_task}")
                            logger.error(f"❌ Erreur: {error_msg}")
                            logger.error(f"📦 Résultat complet: {reactivation_result}")
                            logger.error("="*80)
                            
                            return {
                                "task_id": existing_task,
                                "is_reactivation": False,
                                "existing": True,
                                "error": error_msg,
                                "message": f"Échec réactivation: {error_msg}"
                            }
                    except Exception as e:
                        logger.error("="*80)
                        logger.error("❌ EXCEPTION DURANT RÉACTIVATION VIA STATUT")
                        logger.error("="*80)
                        logger.error(f"🆔 Task ID: {existing_task}")
                        logger.error(f"❌ Exception: {str(e)}")
                        logger.error(f"📍 Type: {type(e).__name__}")
                        logger.error("="*80)
                        logger.error(f"❌ Erreur réactivation via statut: {e}", exc_info=True)
                        
                        return {
                            "task_id": existing_task,
                            "is_reactivation": False,
                            "existing": True,
                            "error": str(e),
                            "message": f"Exception durant réactivation: {str(e)}"
                        }
                else:
                    logger.info("ℹ️ Update sur colonne sans changement de statut - pas de réactivation automatique")
                    logger.info("💡 Pour réactiver une tâche complétée, utilisez:")
                    logger.info("   1. @vydata [votre commande]")
                    logger.info("   2. Ou changez le statut à 'Working on it'")
                    
                    task_id = await db_persistence._update_task_from_monday(existing_task, payload)
                    logger.info(f"📝 Tâche mise à jour: {task_id} - {pulse_name}")
                    return {"task_id": task_id, "is_reactivation": False, "existing": True}
            else:
                task_id = await db_persistence.create_task_from_monday(payload)
                logger.info(f"✨ Nouvelle tâche créée: {task_id} - {pulse_name}")
                await db_persistence._link_webhook_to_task(webhook_id, task_id)
                return {"task_id": task_id, "is_reactivation": False, "existing": False}
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement item event: {e}")
            raise
    
    @staticmethod
    async def _handle_update_event(payload: Dict[str, Any], webhook_id: int):
        """
        Traite un événement d'update/commentaire Monday.com.
        
        NOUVEAU SYSTÈME @vydata:
        1. Détecte la mention @vydata
        2. Classifie l'intention (Question vs Commande)
        3. Route vers l'action appropriée
        
        Modes d'activation:
        - Mode 1: Changement de statut à "Working on it" 
        - Mode 2: Mention @vydata (Question ou Commande)
        """
        try:
            pulse_id = payload.get("pulseId") or payload.get("pulse_id")
            update_text = payload.get("textBody") or payload.get("text_body") or payload.get("body", "")
            update_id = payload.get("updateId") or payload.get("update_id") or payload.get("id") or f"update_{pulse_id}_{webhook_id}"
            event_type = payload.get("type", "unknown")
            
            logger.info("="*80)
            logger.info("🔔 WEBHOOK UPDATE REÇU")
            logger.info("="*80)
            logger.info(f"📋 Type: {event_type}")
            logger.info(f"📌 Pulse ID: {pulse_id}")
            logger.info(f"🆔 Update ID: {update_id}")
            logger.info(f"🆔 Webhook ID: {webhook_id}")
            logger.info(f"💬 Texte (50 car.): '{update_text[:50]}...'")
            logger.info("="*80)
            
            task_id = await db_persistence._find_task_by_monday_id(pulse_id)
            
            if not task_id:
                logger.warning("="*80)
                logger.warning("⚠️ TÂCHE NON TROUVÉE - CRÉATION AUTOMATIQUE")
                logger.warning("="*80)
                logger.warning(f"📌 Pulse ID: {pulse_id}")
                logger.warning(f"🆔 Webhook ID: {webhook_id}")
                logger.warning(f"💬 Update: '{update_text[:100]}...'")
                logger.warning("="*80)
                
                try:
                    board_id = payload.get('boardId') or payload.get('board_id')
                    
                    item_title = f"Tâche {pulse_id}"
                    repository_url = 'https://github.com/placeholder'  
                    
                    try:
                        from tools.monday_tool import MondayTool
                        from config.settings import get_settings
                        
                        monday_tool = MondayTool()
                        settings = get_settings()
                        
                        logger.info(f"🔍 Récupération infos item Monday {pulse_id}...")
                        item_info_result = await monday_tool._arun(
                            action="get_item_info",
                            item_id=str(pulse_id)
                        )
                        
                        if item_info_result and item_info_result.get('success'):
                            item_title = item_info_result.get('name', item_title)
                            logger.info(f"✅ Titre récupéré: {item_title}")
                            
                            column_values = item_info_result.get('column_values', {})
                            
                            def safe_extract_text(col_id: str) -> Optional[str]:
                                """Extrait le texte d'une colonne Monday.com de manière sécurisée."""
                                col_data = column_values.get(col_id)
                                if col_data and isinstance(col_data, dict):
                                    col_value = col_data.get('value')
                                    col_text = col_data.get('text')
                                    
                                    if col_text and col_text.strip():
                                        return col_text.strip()
                                    
                                    if col_value:
                                        try:
                                            import json
                                            value_data = json.loads(col_value) if isinstance(col_value, str) else col_value
                                            return value_data.get('url') or value_data.get('text') or value_data.get('label')
                                        except Exception:
                                            return str(col_value).strip() if col_value else None
                                return None
                            
                            if settings.monday_repository_url_column_id:
                                extracted_url = safe_extract_text(settings.monday_repository_url_column_id)
                                if extracted_url and 'github.com' in extracted_url:
                                    repository_url = extracted_url.strip()
                                    logger.info(f"✅ URL repository depuis colonne configurée: {repository_url}")
                            
                            if repository_url == 'https://github.com/placeholder':
                                for col_id, col_data in column_values.items():
                                    if any(keyword in col_id.lower() for keyword in ["repo", "repository", "url", "github", "git", "project", "link"]):
                                        extracted_url = safe_extract_text(col_id)
                                        if extracted_url and 'github.com' in extracted_url:
                                            repository_url = extracted_url.strip()
                                            logger.info(f"✅ URL repository trouvée dans colonne '{col_id}': {repository_url}")
                                            break
                                
                    except Exception as api_error:
                        logger.warning(f"⚠️ Impossible de récupérer infos depuis API Monday: {api_error}")
                        logger.info(f"📝 Utilisation valeurs par défaut: titre='{item_title}', url='{repository_url}'")
                    
                    if repository_url == 'https://github.com/placeholder':
                        logger.info(f"🔄 URL repository non définie - recherche via PR précédentes...")
                        try:
                            from services.repository_url_resolver import RepositoryUrlResolver
                            resolved_url = await RepositoryUrlResolver.resolve_repository_url(
                                task_db_id=None,
                                monday_item_id=str(pulse_id)
                            )
                            
                            if resolved_url:
                                repository_url = resolved_url
                                logger.info(f"✅ URL repository résolue via PR: {repository_url}")
                        except Exception as resolver_error:
                            logger.warning(f"⚠️ Erreur résolution URL repository: {resolver_error}")
                    
                    async with db_persistence.db_manager.get_connection() as conn:
                        result = await conn.fetchrow("""
                            INSERT INTO tasks (
                                monday_item_id,
                                monday_board_id,
                                title,
                                description,
                                repository_url,
                                internal_status,
                                monday_status,
                                priority,
                                created_at,
                                updated_at
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW()
                            )
                            ON CONFLICT (monday_item_id) 
                            DO UPDATE SET
                                updated_at = NOW()
                            RETURNING tasks_id
                        """, 
                        pulse_id,                           
                        board_id,                           
                        item_title,                         
                        update_text[:500],                  
                        repository_url,                     
                        'pending',                         
                        'New request',                      
                        'medium'                           
                        )
                        
                        task_id = result['tasks_id']
                        logger.info(f"✅ Tâche {task_id} créée automatiquement (monday_item_id={pulse_id})")
                        
                except Exception as create_error:
                    logger.error(f"❌ Erreur création automatique de la tâche: {create_error}")
                    logger.error(f"Stack trace: {traceback.format_exc()}")
                    
                    await db_persistence.log_application_event(
                        task_id=None,
                        level="ERROR",
                        source_component="webhook_persistence",
                        action="task_creation_failed",
                        message=f"Échec création tâche pour pulse_id {pulse_id}",
                        metadata={
                            "pulse_id": pulse_id,
                            "update_text": update_text[:200],
                            "error": str(create_error)
                        }
                    )
                    return None
            
            async with db_persistence.db_manager.get_connection() as conn:
                task_details = await conn.fetchrow("""
                    SELECT 
                        tasks_id,
                        monday_item_id,
                        title,
                        description,
                        internal_status,
                        monday_status,
                        repository_url,
                        priority,
                        monday_board_id
                    FROM tasks 
                    WHERE tasks_id = $1
                """, task_id)
            
            if not task_details:
                logger.error(f"❌ Impossible de récupérer les détails de la tâche {task_id}")
                return None
            
            await db_persistence.log_application_event(
                task_id=task_id,
                level="INFO",
                source_component="monday_webhook",
                action="item_update_received",
                message=f"Commentaire Monday.com: {update_text[:200]}...",
                metadata={
                    "webhook_id": webhook_id,
                    "full_text": update_text,
                    "monday_pulse_id": pulse_id,
                    "update_id": update_id
                }
            )
            
            await db_persistence._link_webhook_to_task(webhook_id, task_id)
            
            from services.vydata_orchestrator_service import vydata_orchestrator_service
            
            task_context = {
                "tasks_id": task_details['tasks_id'],
                "monday_item_id": task_details['monday_item_id'],
                "title": task_details['title'],
                "description": task_details['description'],
                "internal_status": task_details['internal_status'],
                    "monday_status": task_details['monday_status'],
                "repository_url": task_details['repository_url'],
                "priority": task_details['priority'],
                "monday_board_id": task_details.get('monday_board_id')
                }
                
            orchestrator_result = await vydata_orchestrator_service.process_monday_update(
                    update_text=update_text,
                task_id=task_id,
                task_context=task_context,
                monday_item_id=task_details['monday_item_id'],
                board_id=task_details.get('monday_board_id')
            )
            
            if orchestrator_result.get("action") == "ignored_agent_message":
                logger.info("ℹ️ Update ignoré - message de l'agent")
                return None
                
            elif orchestrator_result.get("action_type") in ["question_answered", "command_workflow"] or orchestrator_result.get("action") in ["question_answered", "command_workflow"]:
                action = orchestrator_result.get("action_type") or orchestrator_result.get("action")
                
                if action == "question_answered":
                    logger.info("✅ Question @vydata traitée avec réponse directe")
                    return None  
                    
                elif action == "command_workflow":
                    logger.info("✅ Commande @vydata traitée avec workflow")
                    logger.info("="*80)
                    logger.info("📦 RETOUR RÉSULTAT DE RÉACTIVATION")
                    logger.info("="*80)
                    logger.info(f"📝 Task ID: {task_id}")
                    logger.info(f"🔄 Run ID: {orchestrator_result.get('run_id')}")
                    logger.info(f"✅ Is Reactivation: True")
                    logger.info("="*80)
                    return {
                        'task_id': task_id,
                        'run_id': orchestrator_result.get('run_id'),
                        'is_reactivation': True,
                        'requires_workflow': True,
                        'update_text': update_text,
                        'confidence': orchestrator_result.get('confidence', 1.0),
                        'monday_item_id': task_details['monday_item_id'],
                        'reactivation_reason': 'vydata_command',
                        'reactivation_count': orchestrator_result.get('reactivation_count', 1),
                        'source_branch': 'main',
                        'reactivation_data': orchestrator_result.get('reactivation_data', {})
                    }
                    
            elif orchestrator_result.get("action") == "no_mention":
                logger.info("ℹ️ Pas de mention @vydata - Update traité normalement")
                logger.info("💡 Pour déclencher le workflow, utilisez @vydata ou changez le statut")
                return None
                
            else:
                error_msg = orchestrator_result.get("error", "Erreur inconnue")
                action_found = orchestrator_result.get("action") or orchestrator_result.get("action_type") or "non défini"
                logger.warning(f"⚠️ Résultat orchestrateur non standard: {error_msg}")
                logger.warning(f"   Action reçue: {action_found}")
                logger.warning(f"   Résultat complet: {orchestrator_result}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur traitement update event: {e}", exc_info=True)
            raise
    
    @staticmethod
    async def _handle_board_event(payload: Dict[str, Any], webhook_id: int):
        """Traite un événement de board Monday.com."""
        try:
            board_id = payload.get("boardId")
            board_name = payload.get("boardName", "Board sans nom")
            
            await db_persistence.log_application_event(
                level="INFO",
                source_component="monday_webhook",
                action="board_event",
                message=f"Événement board Monday.com: {board_name}",
                metadata={
                    "webhook_id": webhook_id,
                    "board_id": board_id,
                    "board_name": board_name
                }
            )
            
            logger.info(f"📋 Événement board traité: {board_name}")
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement board event: {e}")
            raise

webhook_persistence = WebhookPersistenceService() 