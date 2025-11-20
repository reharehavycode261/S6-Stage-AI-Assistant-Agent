"""
Service de gestion des webhooks Monday.com pour les notifications Slack.

Ce service écoute les webhooks Monday.com et envoie des notifications Slack
aux utilisateurs concernés en fonction des événements.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from utils.logger import get_logger
from config.settings import get_settings
from services.slack_notification_service import slack_notification_service

logger = get_logger(__name__)
settings = get_settings()


class MondaySlackWebhookService:
    """
    Service pour gérer les webhooks Monday.com → Slack.
    
    Écoute les événements Monday.com et déclenche les notifications Slack appropriées.
    """
    
    def __init__(self):
        """Initialise le service de webhooks."""
        self.slack_service = slack_notification_service
        self._processed_updates = {}
    
    async def handle_update_created(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gère l'événement de création d'une update dans Monday.com.
        
        Déclenche une notification Slack si l'update nécessite une action de l'utilisateur.
        
        Args:
            payload: Payload du webhook Monday.com
            
        Returns:
            Résultat du traitement
        """
        try:
            event = payload.get("event", {})
            
            update_id = event.get("updateId")
            item_id = event.get("pulseId")
            item_name = event.get("pulseName", "Tâche")
            update_text = event.get("textBody", "")
            creator_id = event.get("userId")
            
            logger.info(f"📥 Webhook reçu: Update {update_id} sur item {item_id}")
            logger.info(f"   Créateur: {creator_id}")
            logger.info(f"   Texte: {update_text[:100]}...")
            
            if self._is_validation_request(update_text):
                logger.info("✅ Update de validation détectée")
                
                user_slack_id = await self.slack_service.get_user_id_by_monday_id(str(creator_id))
                
                if user_slack_id:
                    pr_url = self._extract_pr_url(update_text)
                    
                    result = await self.slack_service.send_validation_waiting_notification(
                        user_slack_id=user_slack_id,
                        task_title=item_name,
                        task_id=str(item_id),
                        monday_item_id=str(item_id),
                        pr_url=pr_url
                    )
                    
                    if result.get("success"):
                        logger.info(f"✅ Notification Slack envoyée à {user_slack_id}")
                        return {
                            "status": "notification_sent",
                            "user_slack_id": user_slack_id,
                            "item_id": item_id
                        }
                    else:
                        logger.warning(f"⚠️ Échec envoi notification: {result.get('error')}")
                        return {
                            "status": "notification_failed",
                            "error": result.get("error")
                        }
                else:
                    logger.warning(f"⚠️ Aucun ID Slack trouvé pour l'utilisateur {creator_id}")
                    return {
                        "status": "user_not_found",
                        "monday_user_id": creator_id
                    }
            else:
                logger.info("ℹ️ Update normale, pas de notification nécessaire")
                return {
                    "status": "ignored",
                    "reason": "Not a validation request"
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur traitement webhook: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def handle_status_changed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gère l'événement de changement de statut dans Monday.com.
        
        Envoie une notification de succès si la tâche est validée/terminée.
        
        Args:
            payload: Payload du webhook Monday.com
            
        Returns:
            Résultat du traitement
        """
        try:
            event = payload.get("event", {})
            
            item_id = event.get("pulseId")
            item_name = event.get("pulseName", "Tâche")
            column_id = event.get("columnId")
            new_value = event.get("value", {})
            previous_value = event.get("previousValue", {})
            changed_by_id = event.get("userId")
            
            logger.info(f"📥 Webhook statut changé: Item {item_id}")
            logger.info(f"   Colonne: {column_id}")
            logger.info(f"   Nouvelle valeur: {new_value}")
            
            if self._is_completion_status(new_value):
                logger.info("✅ Statut de complétion détecté")
                
                user_slack_id = await self._get_task_creator_slack_id(item_id)
                
                if user_slack_id:
                    pr_url = await self._get_pr_url_from_item(item_id)
                    
                    result = await self.slack_service.send_task_success_notification(
                        user_slack_id=user_slack_id,
                        task_title=item_name,
                        monday_item_id=str(item_id),
                        pr_url=pr_url,
                        merged=True
                    )
                    
                    if result.get("success"):
                        logger.info(f"✅ Notification de succès envoyée à {user_slack_id}")
                        return {
                            "status": "success_notification_sent",
                            "user_slack_id": user_slack_id,
                            "item_id": item_id
                        }
                    else:
                        logger.warning(f"⚠️ Échec envoi notification: {result.get('error')}")
                        return {
                            "status": "notification_failed",
                            "error": result.get("error")
                        }
                else:
                    logger.warning(f"⚠️ Aucun ID Slack trouvé pour le créateur de l'item {item_id}")
                    return {
                        "status": "user_not_found",
                        "item_id": item_id
                    }
            else:
                logger.info("ℹ️ Changement de statut normal, pas de notification")
                return {
                    "status": "ignored",
                    "reason": "Not a completion status"
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur traitement webhook statut: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _is_validation_request(self, update_text: str) -> bool:
        """
        Détermine si une update est une demande de validation humaine.
        
        Args:
            update_text: Texte de l'update
            
        Returns:
            True si c'est une demande de validation
        """
        validation_markers = [
            "validation requise",
            "validation humaine",
            "pull request créée",
            "pr créée",
            "veuillez valider",
            "à valider"
        ]
        
        update_lower = update_text.lower()
        return any(marker in update_lower for marker in validation_markers)
    
    def _is_completion_status(self, status_value: Dict[str, Any]) -> bool:
        """
        Détermine si un statut indique une complétion.
        
        Args:
            status_value: Valeur du statut Monday.com
            
        Returns:
            True si c'est un statut de complétion
        """
        label = status_value.get("label", {})
        if isinstance(label, dict):
            label_text = label.get("text", "").lower()
        else:
            label_text = str(label).lower()
        
        completion_statuses = [
            "terminé",
            "done",
            "validé",
            "approved",
            "mergé",
            "merged",
            "completed"
        ]
        
        return any(status in label_text for status in completion_statuses)
    
    def _extract_pr_url(self, text: str) -> Optional[str]:
        """
        Extrait l'URL d'une Pull Request depuis un texte.
        
        Args:
            text: Texte contenant potentiellement une URL de PR
            
        Returns:
            URL de la PR ou None
        """
        import re
        
        github_pr_pattern = r'https://github\.com/[^/]+/[^/]+/pull/\d+'
        match = re.search(github_pr_pattern, text)
        
        if match:
            return match.group(0)
        
        return None
    
    async def _get_task_creator_slack_id(self, item_id: str) -> Optional[str]:
        """
        Récupère l'ID Slack du créateur d'un item Monday.com.
        
        Args:
            item_id: ID de l'item Monday.com
            
        Returns:
            ID Slack du créateur ou None
        """
        try:
            from tools.monday_tool import MondayTool
            monday_tool = MondayTool()
            
            query = """
            query ($itemId: [ID!]) {
                items(ids: $itemId) {
                    creator {
                        id
                        email
                        name
                    }
                }
            }
            """
            
            result = await monday_tool._make_request(query, {"itemId": [int(item_id)]})
            
            if result and isinstance(result, dict) and result.get("data", {}).get("items"):
                items = result["data"]["items"]
                if items and len(items) > 0:
                    creator = items[0].get("creator", {})
                    creator_id = creator.get("id")
                    
                    if creator_id:
                        return await self.slack_service.get_user_id_by_monday_id(str(creator_id))
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération créateur: {e}")
            return None
    
    async def _get_pr_url_from_item(self, item_id: str) -> Optional[str]:
        """
        Récupère l'URL de la PR depuis les updates d'un item.
        
        Args:
            item_id: ID de l'item Monday.com
            
        Returns:
            URL de la PR ou None
        """
        try:
            from tools.monday_tool import MondayTool
            monday_tool = MondayTool()
            
            query = """
            query ($itemId: [ID!]) {
                items(ids: $itemId) {
                    updates {
                        body
                        created_at
                    }
                }
            }
            """
            
            result = await monday_tool._make_request(query, {"itemId": [int(item_id)]})
            
            if result and isinstance(result, dict) and result.get("data", {}).get("items"):
                items = result["data"]["items"]
                if items and len(items) > 0:
                    updates = items[0].get("updates", [])
                    
                    for update in reversed(updates):
                        body = update.get("body", "")
                        pr_url = self._extract_pr_url(body)
                        if pr_url:
                            return pr_url
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération PR URL: {e}")
            return None


monday_slack_webhook_service = MondaySlackWebhookService()

