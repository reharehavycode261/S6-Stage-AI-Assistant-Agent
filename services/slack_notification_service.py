"""
Service de notification Slack pour les validations humaines et réussites de tâches.

Ce service permet d'envoyer des messages directs Slack aux utilisateurs pour :
- Notifications de timeout de validation humaine
- Notifications de succès de tâches traitées par l'agent
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class SlackNotificationService:
    """
    Service pour envoyer des notifications Slack en messages directs.
    
    Utilise l'API Slack pour:
    - Notifications de timeout de validation
    - Notifications de succès de tâches
    - Messages directs à l'utilisateur (pas au channel)
    """
    
    def __init__(self):
        """Initialise le service Slack."""
        self.slack_enabled = settings.slack_enabled
        self.slack_bot_token = settings.slack_bot_token
        self.slack_client = None
        
        if not self.slack_enabled:
            logger.warning("⚠️ Service Slack désactivé - Les notifications ne seront pas envoyées")
        else:
            self._init_slack_client()
    
    def _init_slack_client(self):
        """Initialise le client Slack SDK."""
        try:
            from slack_sdk.web.async_client import AsyncWebClient
            import ssl
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.slack_client = AsyncWebClient(
                token=self.slack_bot_token,
                ssl=ssl_context
            )
            logger.info("✅ Client Slack initialisé avec succès (SSL vérifié désactivé)")
        except ImportError:
            logger.error("❌ Module slack_sdk non installé. Installez-le avec: pip install slack-sdk")
            self.slack_enabled = False
        except Exception as e:
            logger.error(f"❌ Erreur initialisation client Slack: {e}")
            self.slack_enabled = False
    
    async def send_validation_waiting_notification(
        self,
        user_slack_id: str,
        task_title: str,
        task_id: str,
        monday_item_id: str,
        pr_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envoie une notification d'attente de validation humaine.
        
        Args:
            user_slack_id: ID Slack de l'utilisateur (format: U0123456789)
            task_title: Titre de la tâche
            task_id: ID de la tâche en base
            monday_item_id: ID de l'item Monday.com
            pr_url: URL de la Pull Request (optionnel)
            
        Returns:
            Résultat de l'envoi avec succès/erreur
        """
        if not self.slack_enabled:
            logger.info("💬 Envoi Slack skippé (service désactivé)")
            return {
                "success": False,
                "skipped": True,
                "reason": "Service Slack désactivé"
            }
        
        if not user_slack_id:
            logger.warning("⚠️ Aucun ID Slack utilisateur fourni - notification impossible")
            return {
                "success": False,
                "error": "ID Slack utilisateur manquant"
            }
        
        logger.info(f"💬 Envoi notification d'attente de validation à <@{user_slack_id}>")
        logger.info(f"   • Tâche: {task_title}")
        logger.info(f"   • Monday ID: {monday_item_id}")
        
        try:
            monday_link = f"https://smartelia.monday.com/boards/5084415062/pulses/{monday_item_id}"
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⏳ Validation humaine requise",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Bonjour <@{user_slack_id}>,\n\nVotre demande *@vydata* a été traitée avec succès ! 🎉"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*📋 Tâche:*\n{task_title}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*🆔 Monday ID:*\n{monday_item_id}"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*✅ Que s'est-il passé ?*\nL'agent IA *VyData* a terminé le travail et créé une Pull Request. *Votre validation est maintenant requise.*"
                    }
                }
            ]
            
            if pr_url:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🔗 Pull Request:*\n<{pr_url}|Voir la PR sur GitHub>"
                    }
                })
            
            blocks.extend([
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*💬 Comment répondre ?*\nRendez-vous sur Monday.com et répondez à la validation :\n• `oui` → pour valider et merger\n• `non [instructions]` → pour demander des modifications\n• `abandonne` → pour annuler"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📋 Ouvrir dans Monday.com",
                                "emoji": True
                            },
                            "url": monday_link,
                            "style": "primary"
                        }
                    ]
                }
            ])
            
            result = await self._send_direct_message(
                user_id=user_slack_id,
                blocks=blocks,
                text=f"🔔 Validation VyData requise pour: {task_title}"
            )
            
            if result.get("success"):
                logger.info(f"✅ Notification d'attente envoyée à <@{user_slack_id}>")
            else:
                logger.error(f"❌ Échec envoi notification: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur notification d'attente Slack: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_validation_timeout_notification(
        self,
        user_slack_id: str,
        task_title: str,
        task_id: str,
        monday_item_id: str,
        timeout_duration: int = 20
    ) -> Dict[str, Any]:
        """
        Envoie une notification de timeout de validation humaine.
        
        Args:
            user_slack_id: ID Slack de l'utilisateur (format: U0123456789)
            task_title: Titre de la tâche
            task_id: ID de la tâche en base
            monday_item_id: ID de l'item Monday.com
            timeout_duration: Durée du timeout en secondes
            
        Returns:
            Résultat de l'envoi avec succès/erreur
        """
        if not self.slack_enabled:
            logger.info("💬 Envoi Slack skippé (service désactivé)")
            return {
                "success": False,
                "skipped": True,
                "reason": "Service Slack désactivé"
            }
        
        if not user_slack_id:
            logger.warning("⚠️ Aucun ID Slack utilisateur fourni - notification impossible")
            return {
                "success": False,
                "error": "ID Slack utilisateur manquant"
            }
        
        logger.info(f"💬 Envoi notification timeout à <@{user_slack_id}>")
        logger.info(f"   • Tâche: {task_title}")
        logger.info(f"   • Monday ID: {monday_item_id}")
        logger.info(f"   • Timeout: {timeout_duration}s")
        
        try:
            monday_link = f"https://smartelia.monday.com/boards/5084415062/pulses/{monday_item_id}"
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⏰ Timeout de validation",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Bonjour <@{user_slack_id}>,\n\nLe délai de validation pour votre tâche *@vydata* a expiré."
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*📋 Tâche:*\n{task_title}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*🆔 Monday ID:*\n{monday_item_id}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*⏱️ Timeout:*\n{timeout_duration} secondes"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*🕐 Date/Heure:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*❓ Que s'est-il passé ?*\nL'agent IA *VyData* a terminé le travail et créé une Pull Request, mais vous n'avez pas répondu dans le délai imparti (*{timeout_duration} secondes*)."
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*💡 Que faire maintenant ?*\n• Consultez la Pull Request sur Monday.com\n• Répondez avec `oui` pour valider et merger\n• Répondez avec `non [instructions]` pour demander des modifications\n• Répondez avec `abandonne` pour annuler"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📋 Voir sur Monday.com",
                                "emoji": True
                            },
                            "url": monday_link,
                            "style": "danger"
                        }
                    ]
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "ℹ️ _Ce timeout permet d'éviter les blocages du système. Les prochaines commandes ont pu être traitées normalement._"
                        }
                    ]
                }
            ]
            
            result = await self._send_direct_message(
                user_id=user_slack_id,
                blocks=blocks,
                text=f"⏰ RAPPEL: Validation VyData en attente pour {task_title}"  # Fallback visible
            )
            
            if result.get("success"):
                logger.info(f"✅ Notification timeout envoyée à <@{user_slack_id}>")
            else:
                logger.error(f"❌ Échec envoi notification: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur notification timeout Slack: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_task_success_notification(
        self,
        user_slack_id: str,
        task_title: str,
        monday_item_id: str,
        pr_url: Optional[str] = None,
        merged: bool = False
    ) -> Dict[str, Any]:
        """
        Envoie une notification de succès de tâche.
        
        Args:
            user_slack_id: ID Slack de l'utilisateur
            task_title: Titre de la tâche
            monday_item_id: ID de l'item Monday.com
            pr_url: URL de la Pull Request (optionnel)
            merged: True si la PR a été mergée
            
        Returns:
            Résultat de l'envoi avec succès/erreur
        """
        if not self.slack_enabled:
            logger.info("💬 Envoi Slack skippé (service désactivé)")
            return {
                "success": False,
                "skipped": True,
                "reason": "Service Slack désactivé"
            }
        
        if not user_slack_id:
            logger.warning("⚠️ Aucun ID Slack utilisateur fourni - notification impossible")
            return {
                "success": False,
                "error": "ID Slack utilisateur manquant"
            }
        
        logger.info(f"💬 Envoi notification de succès à <@{user_slack_id}>")
        logger.info(f"   • Tâche: {task_title}")
        logger.info(f"   • Monday ID: {monday_item_id}")
        logger.info(f"   • PR mergée: {merged}")
        
        try:
            monday_link = f"https://smartelia.monday.com/boards/5084415062/pulses/{monday_item_id}"
            
            status_text = "mergée avec succès" if merged else "créée et prête"
            emoji = "🎉" if merged else "✅"
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} Tâche terminée avec succès !",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Bonjour <@{user_slack_id}>,\n\nVotre demande *@vydata* a été traitée avec succès ! {emoji}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*📋 Tâche:*\n{task_title}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*🆔 Monday ID:*\n{monday_item_id}"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*✅ Résultat:*\nLa Pull Request a été {status_text}."
                    }
                }
            ]
            
            action_elements = [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📋 Voir sur Monday.com",
                        "emoji": True
                    },
                    "url": monday_link,
                    "style": "primary"
                }
            ]
            
            if pr_url:
                action_elements.append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🔗 Voir la PR",
                        "emoji": True
                    },
                    "url": pr_url
                })
            
            blocks.append({
                "type": "actions",
                "elements": action_elements
            })
            
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "🤖 _Merci d'avoir utilisé VyData AI Agent !_"
                    }
                ]
            })
            
            result = await self._send_direct_message(
                user_id=user_slack_id,
                blocks=blocks,
                text=f"✅ VyData - Tâche terminée avec succès: {task_title}"
            )
            
            if result.get("success"):
                logger.info(f"✅ Notification de succès envoyée à <@{user_slack_id}>")
            else:
                logger.error(f"❌ Échec envoi notification: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur notification de succès Slack: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _send_direct_message(
        self,
        user_id: str,
        blocks: list,
        text: str
    ) -> Dict[str, Any]:
        """
        Envoie un message direct à un utilisateur Slack.
        
        Args:
            user_id: ID Slack de l'utilisateur
            blocks: Liste de blocks Slack pour le formatage
            text: Texte fallback pour les notifications
            
        Returns:
            Résultat de l'envoi
        """
        if not self.slack_client:
            return {
                "success": False,
                "error": "Client Slack non initialisé"
            }
        
        try:
            logger.debug(f"💬 Ouverture conversation DM avec {user_id}...")
            dm_response = await self.slack_client.conversations_open(users=user_id)
            
            if not dm_response["ok"]:
                logger.error(f"❌ Erreur ouverture DM: {dm_response.get('error')}")
                return {
                    "success": False,
                    "error": f"Erreur ouverture DM: {dm_response.get('error')}"
                }
            
            channel_id = dm_response["channel"]["id"]
            logger.debug(f"✅ DM ouvert: {channel_id}")            
            logger.debug(f"📤 Envoi message DM à {user_id} (channel: {channel_id})...")            
            message_response = await self.slack_client.chat_postMessage(
                channel=channel_id,
                blocks=blocks,
                text=text,  # Texte de fallback pour notifications push
                unfurl_links=False,
                unfurl_media=False,
                # ✅ Personnalisation (nécessite chat:write.customize)
                username="VyData Notification",  # Nom affiché dans le DM
                icon_emoji=":robot_face:",  # Icône du bot
                mrkdwn=True
            )
            
            if not message_response["ok"]:
                logger.error(f"❌ Erreur envoi message: {message_response.get('error')}")
                return {
                    "success": False,
                    "error": f"Erreur envoi message: {message_response.get('error')}"
                }
            
            logger.info(f"✅ Message Slack envoyé avec succès à {user_id}")
            
            return {
                "success": True,
                "user_id": user_id,
                "channel_id": channel_id,
                "message_ts": message_response["ts"],
                "sent_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi message Slack: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_id_by_email(self, email: str) -> Optional[str]:
        """
        Récupère l'ID Slack d'un utilisateur à partir de son email.
        
        Args:
            email: Adresse email de l'utilisateur
            
        Returns:
            ID Slack de l'utilisateur ou None si non trouvé
        """
        if not self.slack_client:
            logger.warning("⚠️ Client Slack non initialisé")
            return None
        
        try:
            logger.debug(f"🔍 Recherche utilisateur Slack par email: {email}")
            response = await self.slack_client.users_lookupByEmail(email=email)
            
            if response["ok"]:
                user_id = response["user"]["id"]
                user_name = response["user"]["name"]
                logger.info(f"✅ Utilisateur Slack trouvé: {user_name} ({user_id})")
                return user_id
            else:
                logger.warning(f"⚠️ Utilisateur non trouvé pour email {email}: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur recherche utilisateur Slack: {e}")
            return None
    
    async def get_user_id_by_monday_id(self, monday_user_id: str) -> Optional[str]:
        """
        Récupère l'ID Slack à partir de l'ID utilisateur Monday.com.
        
        Stratégie:
        1. Récupère l'email depuis Monday.com via l'ID utilisateur
        2. Utilise l'email pour trouver l'ID Slack
        
        Args:
            monday_user_id: ID de l'utilisateur Monday.com
            
        Returns:
            ID Slack de l'utilisateur ou None si non trouvé
        """
        try:
            from tools.monday_tool import MondayTool
            monday_tool = MondayTool()
            
            query = """
            query ($userId: [ID!]) {
                users(ids: $userId) {
                    id
                    email
                    name
                }
            }
            """
            
            result = await monday_tool._make_request(query, {"userId": [int(monday_user_id)]})
            
            if result and isinstance(result, dict) and result.get("data", {}).get("users"):
                users = result["data"]["users"]
                if users and len(users) > 0:
                    user = users[0]
                    email = user.get("email")
                    name = user.get("name", "Unknown")
                    
                    if email:
                        logger.info(f"✅ Email trouvé pour utilisateur Monday.com {name}: {email}")
                        # Trouver l'ID Slack via l'email
                        return await self.get_user_id_by_email(email)
            
            logger.warning(f"⚠️ Aucun email trouvé pour l'utilisateur Monday.com {monday_user_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération ID Slack depuis Monday ID: {e}")
            return None


# Instance globale
slack_notification_service = SlackNotificationService()

