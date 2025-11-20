"""
Service orchestrateur pour le système d'agent conversationnel @vydata.

Ce service coordonne l'ensemble du flux:
1. Réception webhook Monday.com
2. Détection mention @vydata
3. Classification d'intention (Question vs Commande)
4. Routage vers l'action appropriée
5. Gestion des 2 modes d'activation (statut + @vydata)
"""

from typing import Dict, Any, Optional
from utils.logger import get_logger
from services.mention_parser_service import mention_parser_service
from services.intent_classifier_service import intent_classifier_service, IntentType
from services.intent_router_service import intent_router_service
from services.semantic_search_service import semantic_search_service

logger = get_logger(__name__)


class VydataOrchestratorService:
    """
    Service orchestrateur principal du système @vydata.
    
    Architecture complète:
    
    Webhook Monday.com
        ↓
    [VydataOrchestratorService]
        ↓
    1. Détection @vydata (MentionParserService)
        ↓ (si @vydata trouvé)
    2. Classification intention (IntentClassifierService)
        ↓
        ├─> QUESTION (Type 1)
        │   └─> AgentResponseService
        │       └─> Réponse directe dans Monday.com
        │       └─> FIN (pas de workflow)
        │
        └─> COMMAND (Type 2)
            └─> WorkflowReactivationService
                └─> Workflow complet (PR + validation)
    
    Modes d'activation:
    - Mode 1: Statut "Working on it" → Workflow complet (comme avant)
    - Mode 2: Mention @vydata → Question ou Commande (nouveau)
    """
    
    def __init__(self):
        """Initialise l'orchestrateur."""
        pass
    
    async def process_monday_update(
        self,
        update_text: str,
        task_id: int,
        task_context: Dict[str, Any],
        monday_item_id: str,
        board_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Traite un update Monday.com et détermine l'action à effectuer.
        
        Args:
            update_text: Texte du commentaire Monday.com
            task_id: ID de la tâche en base
            task_context: Contexte de la tâche (titre, description, statut, etc.)
            monday_item_id: ID de l'item Monday.com
            board_id: ID du board Monday.com (optionnel)
            
        Returns:
            Résultat du traitement avec les actions effectuées
        """
        logger.info("="*80)
        logger.info("🎯 TRAITEMENT UPDATE MONDAY.COM")
        logger.info("="*80)
        logger.info(f"📝 Task ID: {task_id}")
        logger.info(f"📌 Monday Item ID: {monday_item_id}")
        logger.info(f"💬 Update (50 car.): '{update_text[:50]}...'")
        logger.info("="*80)
        
        try:
            if mention_parser_service.is_agent_message(update_text):
                logger.info("🤖 Message de l'agent détecté - ignoré")
                return {
                    "success": True,
                    "action": "ignored_agent_message",
                    "message": "Message de l'agent ignoré"
                }
            
            parse_result = mention_parser_service.parse_mention(update_text)
            
            if not parse_result.has_mention:
                logger.info("ℹ️ Pas de mention @vydata détectée")
                logger.info(f"   Raison: {parse_result.error_message}")
                return {
                    "success": True,
                    "action": "no_mention",
                    "message": "Pas de mention @vydata - update ignoré"
                }
            
            if not parse_result.is_valid:
                logger.warning(f"⚠️ Mention @vydata invalide: {parse_result.error_message}")
                return {
                    "success": False,
                    "action": "invalid_mention",
                    "error": parse_result.error_message
                }
            
            cleaned_text = parse_result.cleaned_text
            logger.info(f"✅ Mention @vydata détectée et valide")
            logger.info(f"   Texte nettoyé: '{cleaned_text[:100]}...'")
            
            logger.info(f"💾 Stockage du message dans le vector store...")
            user_language = 'en'  # Valeur par défaut
            try:
                user_language = await semantic_search_service._detect_language(cleaned_text)
                logger.info(f"🌍 Langue de l'utilisateur détectée: {user_language}")
                
                message_id = await semantic_search_service.store_user_message(
                    message_text=cleaned_text,
                    monday_item_id=str(monday_item_id) if monday_item_id else None,
                    task_id=task_id,
                    metadata={
                        "board_id": str(board_id) if board_id else None,
                        "task_title": task_context.get("title", ""),
                        "user_language": user_language
                    }
                )
                logger.info(f"✅ Message stocké: ID={message_id}, langue utilisateur: {user_language}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur stockage message (non-bloquant): {e}")
            
            logger.info(f"🔍 Classification de l'intention...")
            
            intent_analysis = await intent_classifier_service.classify_intent(
                text=cleaned_text,
                task_context=task_context
            )
            
            logger.info(f"✅ Intention classifiée: {intent_analysis.intent_type.value}")
            logger.info(f"   Confidence: {intent_analysis.confidence:.2f}")
            logger.info(f"   Raisonnement: {intent_analysis.reasoning}")
            
            logger.info(f"🔍 Enrichissement avec contexte sémantique (RAG)...")
            enriched_context = None
            try:
                repository_url = task_context.get("repository_url")
                enriched_context = await semantic_search_service.enrich_query_with_context(
                    query=cleaned_text,
                    repository_url=repository_url,
                    monday_item_id=str(monday_item_id) if monday_item_id else None
                )
                
                logger.info(f"✅ Contexte enrichi: {enriched_context.total_sources} sources trouvées")
                logger.info(f"   • Score de pertinence: {enriched_context.relevance_score:.2f}")
                logger.info(f"   • Messages similaires: {len(enriched_context.similar_messages)}")
                logger.info(f"   • Contexte projet: {len(enriched_context.project_context)}")
                
                if enriched_context.relevance_score > 0.5:
                    task_context["rag_context"] = enriched_context.formatted_context
                    task_context["rag_metadata"] = {
                        "total_sources": enriched_context.total_sources,
                        "relevance_score": enriched_context.relevance_score
                    }
                    logger.info("✅ Contexte RAG ajouté au task_context pour le LLM")
                else:
                    logger.info("ℹ️  Score de pertinence faible - pas de contexte RAG ajouté")
                    
            except Exception as e:
                logger.warning(f"⚠️ Erreur enrichissement RAG (non-bloquant): {e}")
            
            logger.info(f"🌍 Détection de la langue du projet...")
            project_language = 'en'  # Valeur par défaut
            try:
                repository_url = task_context.get("repository_url")
                working_dir = task_context.get("working_directory", "/tmp")
                
                if repository_url:
                    from services.project_language_detector import project_language_detector
                    project_lang_info = await project_language_detector.detect_project_language(
                        working_directory=working_dir,
                        repository_url=repository_url
                    )
                    project_language = project_lang_info.language_code
                    logger.info(f"✅ Langue du projet: {project_lang_info.language_name} ({project_language})")
                    logger.info(f"   Confiance: {project_lang_info.confidence:.2f}, sources: {', '.join(project_lang_info.detection_sources)}")
                    
                    task_context["project_language"] = project_language
                    task_context["project_language_info"] = {
                        "language_code": project_language,
                        "language_name": project_lang_info.language_name,
                        "confidence": project_lang_info.confidence
                    }
                else:
                    logger.info("ℹ️  Pas de repository_url, langue par défaut: anglais")
            except Exception as e:
                logger.warning(f"⚠️ Erreur détection langue projet (non-bloquant): {e}")
            
            task_context["user_language"] = user_language
            task_context["project_language"] = project_language
            
            logger.info(f"📋 Contexte multilingue configuré:")
            logger.info(f"   • Langue utilisateur (messages Monday.com): {user_language}")
            logger.info(f"   • Langue projet (PR/commits): {project_language}")
            
            logger.info(f"🎯 Routage vers le gestionnaire approprié...")
            
            routing_result = await intent_router_service.route_intent(
                intent_analysis=intent_analysis,
                task_id=task_id,
                task_context=task_context,
                original_text=cleaned_text,
                monday_item_id=monday_item_id,
                board_id=board_id
            )
            
            if routing_result.get("success"):
                action_type = routing_result.get("action_type", "unknown")
                logger.info("="*80)
                logger.info(f"✅ TRAITEMENT RÉUSSI - {action_type.upper()}")
                logger.info("="*80)
                
                if action_type == "question_answered":
                    logger.info(f"💬 Type: Question (réponse directe)")
                    logger.info(f"📝 Réponse postée dans Monday.com")
                    logger.info(f"🚫 Pas de workflow déclenché")
                elif action_type == "command_workflow":
                    logger.info(f"⚙️ Type: Commande (workflow complet)")
                    logger.info(f"🔄 Workflow run créé: {routing_result.get('run_id')}")
                    logger.info(f"✅ Workflow en cours d'exécution")
                
                logger.info("="*80)
            else:
                logger.error(f"❌ Échec du routage: {routing_result.get('error')}")
            
            return routing_result
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement update Monday.com: {e}", exc_info=True)
            return {
                "success": False,
                "action": "error",
                "error": f"Erreur traitement: {str(e)}"
            }
    
    async def should_trigger_workflow_from_status(
        self,
        old_status: str,
        new_status: str,
        task_context: Dict[str, Any]
    ) -> bool:
        """
        Détermine si un changement de statut doit déclencher un workflow.
        
        Mode d'activation 1: Statut "Working on it" (comportement original)
        
        Args:
            old_status: Ancien statut
            new_status: Nouveau statut
            task_context: Contexte de la tâche
            
        Returns:
            True si le workflow doit être déclenché
        """
        working_statuses = [
            "en cours", "à faire", "to do",
            "in progress", "working on it", "working"
        ]
        
        completed_statuses = [
            "completed", "failed", "quality_check", "done"
        ]
        
        is_completed = old_status.lower() in completed_statuses
        is_working = new_status.lower() in working_statuses
        
        should_trigger = is_completed and is_working
        
        if should_trigger:
            logger.info("="*80)
            logger.info("🔄 DÉCLENCHEMENT PAR CHANGEMENT DE STATUT")
            logger.info("="*80)
            logger.info(f"📊 Ancien statut: {old_status}")
            logger.info(f"🔄 Nouveau statut: {new_status}")
            logger.info(f"✅ Workflow déclenché (Mode 1: Statut)")
            logger.info("="*80)
        
        return should_trigger
    
    def get_activation_modes_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé des modes d'activation disponibles.
        
        Returns:
            Dictionnaire avec les modes d'activation
        """
        return {
            "modes": [
                {
                    "id": 1,
                    "name": "Changement de statut",
                    "description": "Workflow déclenché quand statut passe à 'Working on it'",
                    "triggers": ["status_change"],
                    "workflow_type": "full",
                    "requires_mention": False
                },
                {
                    "id": 2,
                    "name": "Mention @vydata",
                    "description": "Question ou commande avec @vydata",
                    "triggers": ["@vydata_mention"],
                    "workflow_type": "conditional",
                    "sub_modes": [
                        {
                            "type": "question",
                            "description": "Réponse directe sans workflow",
                            "examples": ["@vydata Pourquoi ce projet utilise Java?"]
                        },
                        {
                            "type": "command",
                            "description": "Workflow complet avec PR",
                            "examples": ["@vydata Ajoute un fichier README"]
                        }
                    ]
                }
            ],
            "summary": "2 modes d'activation: statut 'Working on it' OU mention @vydata"
        }

vydata_orchestrator_service = VydataOrchestratorService()

