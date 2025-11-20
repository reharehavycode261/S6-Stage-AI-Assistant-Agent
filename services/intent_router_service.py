"""
Service de routage d'intention pour diriger vers l'action appropriée.

Ce service:
- Reçoit une analyse d'intention
- Route vers le service approprié:
  * QUESTION → AgentResponseService (réponse directe)
  * COMMAND → Workflow complet (PR + validation)
- Gère les erreurs et les cas limites
"""

from typing import Dict, Any, Optional
from utils.logger import get_logger
from services.intent_classifier_service import IntentType, IntentAnalysis
from services.agent_response_service import agent_response_service
from services.workflow_reactivation_service import workflow_reactivation_service
from services.reactivation_service import UpdateAnalysis
from services.command_deduplication_service import command_deduplication_service
from services.evaluation.agent_interaction_wrapper import AgentInteractionWrapper
from services.question_light_service import QuestionLightService

logger = get_logger(__name__)


class IntentRouterService:
    """
    Service de routage pour diriger les intentions vers les bonnes actions.
    
    Architecture de décision:
    
    QUESTION (Type 1):
      └─> AgentResponseService
          └─> Génération réponse OpenAI
          └─> Post dans Monday.com
          └─> FIN (pas de workflow)
    
    COMMAND (Type 2):
      └─> WorkflowReactivationService
          └─> Création nouveau workflow run
          └─> Clone depuis MAIN
          └─> Exécution de tous les nœuds
          └─> Création PR
          └─> Validation humaine
    
    UNKNOWN:
      └─> Analyse supplémentaire ou rejet
    """
    
    def __init__(self):
        """Initialise le service de routage."""
        self.question_light_service = QuestionLightService()
    
    async def route_intent(
        self,
        intent_analysis: IntentAnalysis,
        task_id: int,
        task_context: Dict[str, Any],
        original_text: str,
        monday_item_id: str,
        board_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Route l'intention vers le service approprié.
        
        Args:
            intent_analysis: Résultat de la classification d'intention
            task_id: ID de la tâche en base
            task_context: Contexte de la tâche
            original_text: Texte original du commentaire (sans @vydata)
            monday_item_id: ID de l'item Monday.com
            board_id: ID du board Monday.com (optionnel)
            
        Returns:
            Résultat du routage avec détails de l'action effectuée
        """
        logger.info("="*80)
        logger.info("🎯 ROUTAGE D'INTENTION")
        logger.info("="*80)
        logger.info(f"📝 Task ID: {task_id}")
        logger.info(f"🔍 Type d'intention: {intent_analysis.intent_type.value}")
        logger.info(f"💪 Confidence: {intent_analysis.confidence:.2f}")
        logger.info(f"💬 Texte: '{original_text[:100]}...'")
        logger.info("="*80)
        
        MIN_CONFIDENCE = 0.5
        if intent_analysis.confidence < MIN_CONFIDENCE:
            logger.warning(f"⚠️ Confidence trop faible ({intent_analysis.confidence:.2f} < {MIN_CONFIDENCE})")
            return {
                "success": False,
                "error": f"Intention incertaine (confidence: {intent_analysis.confidence:.2f})",
                "intent_type": intent_analysis.intent_type.value,
                "requires_clarification": True
            }
        
        if intent_analysis.intent_type == IntentType.QUESTION:
            return await self._route_to_question_handler(
                question=original_text,
                task_context=task_context,
                monday_item_id=monday_item_id,
                intent_analysis=intent_analysis
            )
            
        elif intent_analysis.intent_type == IntentType.COMMAND:
            return await self._route_to_command_handler(
                command=original_text,
                task_id=task_id,
                task_context=task_context,
                monday_item_id=monday_item_id,
                board_id=board_id,
                intent_analysis=intent_analysis
            )
            
        else:
            logger.warning(f"⚠️ Type d'intention inconnu: {intent_analysis.intent_type}")
            return {
                "success": False,
                "error": "Type d'intention non supporté",
                "intent_type": intent_analysis.intent_type.value,
                "reasoning": intent_analysis.reasoning
            }
    
    async def _route_to_question_handler(
        self,
        question: str,
        task_context: Dict[str, Any],
        monday_item_id: str,
        intent_analysis: IntentAnalysis
    ) -> Dict[str, Any]:
        """
        Route vers le gestionnaire de questions (Type 1).
        
        OPTIMISATION PERFORMANCE:
        Détecte si c'est une question SIMPLE ou COMPLEXE:
        
        SIMPLE (15s):
          └─> QuestionLightService
              - Métadonnées GitHub API uniquement (pas de clone)
              - Réponse basée sur README + structure
              - Performance: 15s au lieu de 77s (80% plus rapide)
        
        COMPLEXE (77s):
          └─> AgentResponseService (flux complet)
              - Clone repository + installation
              - Analyse complète du code
              - Contexte enrichi pour réponse détaillée
        
        Nœuds exécutés (MODE COMPLEXE):
        - ✅ prepare_environment (clone repo, setup)
        - ✅ analyze_requirements (analyse complète)
        - ❌ Nœud implémentation (pas de modifications)
        - ❌ Nœud tests
        - ❌ Nœud PR
        - ❌ Nœud validation humaine
        """
        # ✅ OPTIMISATION: Détection question simple
        is_simple = await self.question_light_service.is_simple_question(question)
        
        if is_simple:
            logger.info("="*80)
            logger.info("⚡ TRAITEMENT QUESTION - MODE LIGHT (15s)")
            logger.info("="*80)
            logger.info(f"❓ Question: '{question[:100]}...'")
            logger.info(f"🚀 Mode: LIGHT (métadonnées GitHub API uniquement)")
            logger.info(f"⏱️  Temps estimé: 15 secondes")
            logger.info(f"🚫 Pas de clone, pas d'installation, pas d'analyse lourde")
            logger.info(f"💡 86% plus rapide que le mode complet (15s vs 102s)")
            logger.info("="*80)
        else:
            logger.info("="*80)
            logger.info("🔬 TRAITEMENT QUESTION COMPLEXE - MODE COMPLET (102s)")
            logger.info("="*80)
            logger.info(f"❓ Question: '{question[:100]}...'")
            logger.info(f"🔍 Question nécessite analyse approfondie du code")
            logger.info(f"📥 Clone + Installation + Analyse complète du projet")
            logger.info(f"⏱️  Temps estimé: 102 secondes (1min 42s)")
            logger.info(f"🚫 Pas de modifications, pas de PR, pas de validation humaine")
            logger.info("="*80)
        
        try:
            task = await self._load_task(task_context)
            
            if is_simple:
                response_result = await self._handle_simple_question_light(
                    question=question,
                    task=task,
                    task_context=task_context,
                    monday_item_id=monday_item_id
                )
            else:
                wrapper = AgentInteractionWrapper(agent_response_service, auto_log=True)
                
                response_result = await wrapper.process_analysis_with_logging(
                    question=question,
                    task_context=task_context,
                    monday_item_id=monday_item_id,
                    monday_update_id=f"monday_{monday_item_id}_{task_context.get('tasks_id', 'unknown')}",
                    task=task
                )
            
            if response_result.get("success"):
                logger.info(f"✅ Réponse générée et postée avec succès")
                
                from services.database_persistence_service import db_persistence
                await db_persistence.log_application_event(
                    task_id=task_context.get("tasks_id"),
                    level="INFO",
                    source_component="intent_router",
                    action="question_answered",
                    message=f"Question @vydata traitée: '{question[:100]}...'",
                    metadata={
                        "question": question,
                        "response_length": len(response_result.get("response_text", "")),
                        "monday_update_id": response_result.get("monday_update_id"),
                        "confidence": intent_analysis.confidence,
                        "reasoning": intent_analysis.reasoning
                    }
                )
                
                return {
                    "success": True,
                    "action_type": "question_answered",
                    "intent_type": IntentType.QUESTION.value,
                    "response_text": response_result.get("response_text"),
                    "monday_update_id": response_result.get("monday_update_id"),
                    "requires_workflow": False,
                    "is_reactivation": False,
                    "message": "Question traitée avec réponse directe"
                }
            else:
                error_msg = response_result.get("error", "Erreur inconnue")
                logger.error(f"❌ Échec génération réponse: {error_msg}")
                return {
                    "success": False,
                    "error": f"Échec génération réponse: {error_msg}",
                    "intent_type": IntentType.QUESTION.value
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur routage question: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Erreur traitement question: {str(e)}",
                "intent_type": IntentType.QUESTION.value
            }
    
    async def _route_to_command_handler(
        self,
        command: str,
        task_id: int,
        task_context: Dict[str, Any],
        monday_item_id: str,
        board_id: Optional[int],
        intent_analysis: IntentAnalysis
    ) -> Dict[str, Any]:
        """
        Route vers le gestionnaire de commandes (Type 2).
        
        Flux:
        1. **VÉRIFICATION DÉDUPLICATION** (nouveau) - Détecter si commande déjà traitée
        2. Créer un nouveau workflow run
        3. Cloner depuis MAIN
        4. Exécuter tous les nœuds (analyse, implémentation, tests, PR)
        5. Validation humaine
        6. Merge ou corrections
        7. **STOCKAGE DANS REDIS** (nouveau) - Sauvegarder la commande traitée
        """
        logger.info("="*80)
        logger.info("⚙️ TRAITEMENT COMMANDE (Type 2)")
        logger.info("="*80)
        logger.info(f"🎯 Commande: '{command[:100]}...'")
        logger.info(f"🔄 Action: Workflow complet (clone MAIN → PR → validation)")
        logger.info(f"✅ Workflow, PR, et validation humaine activés")
        logger.info("="*80)
        
        try:
            await command_deduplication_service.initialize()
            
            duplicate_check = await command_deduplication_service.check_duplicate_command(
                command_text=command,
                monday_item_id=monday_item_id
            )
            
            if duplicate_check.get("is_duplicate"):
                previous_command = duplicate_check.get("previous_command", {})
                pr_url = previous_command.get("pr_url", "URL non disponible")
                previous_task_id = previous_command.get("task_id")
                previous_text = previous_command.get("command_text", "")
                
                logger.warning("="*80)
                logger.warning("🚫 COMMANDE EN DOUBLON DÉTECTÉE")
                logger.warning("="*80)
                logger.warning(f"📝 Commande actuelle: '{command[:100]}...'")
                logger.warning(f"📝 Commande originale: '{previous_text[:100]}...'")
                logger.warning(f"🔗 PR existante: {pr_url}")
                logger.warning(f"🆔 Task ID originale: {previous_task_id}")
                logger.warning("="*80)
                
                try:
                    from tools.monday_tool import MondayTool
                    monday_tool = MondayTool()
                    
                    command_without_mention = command.replace("@vydata", "").replace("@VyData", "").strip()
                    
                    duplicate_message = f"""🔄 **Commande déjà traitée**

> Commande: {command_without_mention[:150]}{'...' if len(command_without_mention) > 150 else ''}

Cette tâche a déjà été traitée précédemment.

**📋 Détails de la tâche originale:**
- 🆔 Task ID: {previous_task_id}
- 🔗 Pull Request: {pr_url if pr_url != "URL non disponible" else "En cours de création..."}

---
*Pour relancer le traitement avec des modifications, reformulez différemment votre demande.*"""
                    
                    await monday_tool._arun(
                        action="post_update",
                        item_id=monday_item_id,
                        update_text=duplicate_message
                    )
                    
                    logger.info(f"✅ Message de doublon posté dans Monday.com")
                    
                except Exception as e:
                    logger.error(f"❌ Erreur post message doublon: {e}")
                
                return {
                    "success": True,
                    "action_type": "duplicate_command",
                    "intent_type": IntentType.COMMAND.value,
                    "is_duplicate": True,
                    "previous_task_id": previous_task_id,
                    "pr_url": pr_url,
                    "message": "Commande déjà traitée - PR existante retournée",
                    "previous_command": previous_command
                }
            
            logger.info(f"✅ Pas de doublon - traitement de la commande")
            
            update_analysis = UpdateAnalysis(
                requires_reactivation=True,
                confidence=intent_analysis.confidence,
                reasoning=f"Commande @vydata détectée: {intent_analysis.reasoning}",
                is_from_agent=False
            )
            
            logger.info(f"🔄 Création nouveau workflow run pour commande @vydata...")
            
            workflow_metadata = {
                "semantic_hash": duplicate_check.get("semantic_hash"),
                "is_vydata_command": True,
                "command_text": command
            }
            
            reactivation_result = await workflow_reactivation_service.create_new_workflow_run_from_update(
                task_id=task_id,
                monday_item_id=monday_item_id,
                update_analysis=update_analysis,
                update_text=command,
                board_id=board_id,
                metadata=workflow_metadata,
                task_context=task_context
            )
            
            if reactivation_result.get("success"):
                logger.info("="*80)
                logger.info("✅ WORKFLOW CRÉÉ AVEC SUCCÈS")
                logger.info("="*80)
                logger.info(f"🆔 Run ID: {reactivation_result['run_id']}")
                logger.info(f"🔄 Réactivation #{reactivation_result.get('reactivation_count', 1)}")
                logger.info(f"🌿 Clone depuis: MAIN")
                logger.info(f"📝 Commande: '{command[:100]}...'")
                logger.info("="*80)
                
                semantic_hash = duplicate_check.get("semantic_hash")
                if semantic_hash:
                    await command_deduplication_service.store_command(
                        command_text=command,
                        monday_item_id=monday_item_id,
                        task_id=task_id,
                        run_id=reactivation_result['run_id'],
                        pr_url=None,
                        metadata={
                            "reactivation_count": reactivation_result.get('reactivation_count', 1),
                            "confidence": intent_analysis.confidence,
                            "reasoning": intent_analysis.reasoning
                        }
                    )
                    logger.info(f"✅ Commande stockée dans Redis pour déduplication")
                
                from services.database_persistence_service import db_persistence
                await db_persistence.log_application_event(
                    task_id=task_id,
                    level="INFO",
                    source_component="intent_router",
                    action="command_workflow_created",
                    message=f"Commande @vydata déclenchée: '{command[:100]}...'",
                    metadata={
                        "command": command,
                        "run_id": reactivation_result['run_id'],
                        "reactivation_count": reactivation_result.get('reactivation_count', 1),
                        "confidence": intent_analysis.confidence,
                        "reasoning": intent_analysis.reasoning,
                        "semantic_hash": semantic_hash
                    }
                )
                
                return {
                    "success": True,
                    "action_type": "command_workflow",
                    "intent_type": IntentType.COMMAND.value,
                    "run_id": reactivation_result['run_id'],
                    "task_id": task_id,
                    "reactivation_count": reactivation_result.get('reactivation_count', 1),
                    "requires_workflow": True,
                    "is_reactivation": True,
                    "update_text": command,
                    "confidence": intent_analysis.confidence,
                    "reactivation_data": reactivation_result,
                    "message": "Workflow complet déclenché pour la commande"
                }
            else:
                error_msg = reactivation_result.get("error", "Erreur inconnue")
                logger.error("="*80)
                logger.error("❌ ÉCHEC CRÉATION WORKFLOW")
                logger.error("="*80)
                logger.error(f"❌ Erreur: {error_msg}")
                logger.error(f"📦 Détails: {reactivation_result}")
                logger.error("="*80)
                
                return {
                    "success": False,
                    "error": f"Échec création workflow: {error_msg}",
                    "intent_type": IntentType.COMMAND.value,
                    "reactivation_result": reactivation_result
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur routage commande: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Erreur traitement commande: {str(e)}",
                "intent_type": IntentType.COMMAND.value
            }
    
    async def _handle_simple_question_light(
        self,
        question: str,
        task: Dict[str, Any],
        task_context: Dict[str, Any],
        monday_item_id: str
    ) -> Dict[str, Any]:
        """
        Traite une question simple en mode LIGHT (15s au lieu de 77s).
        
        Flux OPTIMISÉ:
        1. Extraire l'URL du repository depuis la tâche
        2. Collecter métadonnées GitHub via API (pas de clone)
        3. Générer réponse avec OpenAI
        4. Poster réponse dans Monday.com
        5. Logger l'interaction
        
        Args:
            question: Question posée
            task: Objet Task chargé
            task_context: Contexte de la tâche
            monday_item_id: ID Monday.com
            
        Returns:
            Résultat avec success/error
        """
        try:
            repository_url = task.get("repository_url") or task_context.get("repository_url")
            task_title = task.get("title") or task_context.get("title", "Tâche sans titre")
            
            if not repository_url:
                logger.error("❌ Pas d'URL repository - impossible de répondre en mode LIGHT")
                return {
                    "success": False,
                    "error": "URL repository manquante"
                }
            
            logger.info(f"🔗 Repository URL: {repository_url}")
            logger.info(f"📋 Titre tâche: {task_title}")
            
            light_result = await self.question_light_service.answer_simple_question(
                question=question,
                repository_url=repository_url,
                task_title=task_title
            )
            
            if not light_result.get("success"):
                logger.error(f"❌ Échec génération réponse LIGHT: {light_result.get('error')}")
                return light_result
            
            response_text = light_result.get("response")
            
            formatted_response = f"""🤖 **Réponse VyData** ⚡ (Mode Rapide - 15s)

> Question: {question[:100]}{"..." if len(question) > 100 else ""}

{response_text}

---
⚡ *Réponse rapide basée sur métadonnées GitHub (README, structure, commits).*
💡 *Pour une analyse complète du code (102s), demandez : "Explique EN DÉTAIL comment fonctionne..."*
"""
            
            from tools.monday_tool import MondayTool
            monday_tool = MondayTool()
            
            logger.info(f"📤 Post réponse dans Monday.com: item {monday_item_id}")
            post_result = await monday_tool._add_comment(
                item_id=monday_item_id,
                comment=formatted_response
            )
            
            if post_result.get("success"):
                logger.info(f"✅ Réponse postée avec succès dans Monday.com")
                
                from services.evaluation.agent_output_logger import AgentOutputLogger
                output_logger = AgentOutputLogger()
                output_logger.log_agent_interaction(
                    monday_update_id=f"light_{monday_item_id}",
                    monday_item_id=str(monday_item_id),
                    input_text=question,
                    agent_output=response_text,
                    interaction_type="question_light",
                    duration_seconds=0.0,
                    success=True,
                    repository_url=repository_url,
                    metadata={
                        "mode": "light",
                        "estimated_time": "15s",
                        "task_title": task.get("title")
                    }
                )
                
                return {
                    "success": True,
                    "response_text": response_text,
                    "monday_update_id": post_result.get("comment_id"),
                    "mode": "light"
                }
            else:
                logger.error(f"❌ Échec post Monday.com: {post_result.get('error')}")
                return {
                    "success": False,
                    "error": f"Échec post Monday.com: {post_result.get('error')}",
                    "response_text": response_text
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur traitement question LIGHT: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Erreur mode LIGHT: {str(e)}"
            }
    
    async def _load_task(self, task_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Charge les données de la tâche depuis le contexte.
        
        Args:
            task_context: Contexte de la tâche
            
        Returns:
            Dictionnaire avec les données de la tâche ou None
        """
        try:
            from services.database_persistence_service import db_persistence
            
            logger.info("="*80)
            logger.info("📥 CHARGEMENT TASK (IntentRouter)")
            logger.info("="*80)
            logger.info(f"📋 Clés disponibles: {list(task_context.keys())}")
            
            task_id = task_context.get("tasks_id")
            if not task_id:
                logger.error("❌ tasks_id NON TROUVÉ dans task_context")
                logger.error(f"📦 task_context complet: {task_context}")
                return None
            
            logger.info(f"🔍 Chargement tâche ID: {task_id}")
            
            task_data = await db_persistence.get_task_by_id(task_id)
            if not task_data:
                logger.error(f"❌ Tâche {task_id} NON TROUVÉE en base")
                return None
            
            logger.info(f"✅ Task {task_id} chargée pour exploration")
            logger.info(f"📋 Titre: {task_data.get('title', 'N/A')}")
            logger.info(f"🔗 Repository: {task_data.get('repository_url', 'N/A')}")
            logger.info("="*80)
            return task_data
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement tâche: {e}", exc_info=True)
            return None

intent_router_service = IntentRouterService()

