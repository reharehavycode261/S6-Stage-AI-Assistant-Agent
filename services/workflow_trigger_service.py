"""Service pour déclencher de nouveaux workflows depuis des updates Monday.com."""

from typing import Dict, Any, Optional
from models.schemas import UpdateIntent, TaskRequest, TaskType, TaskPriority
from services.database_persistence_service import db_persistence
from services.celery_app import submit_task
from utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowTriggerService:
    """Service pour déclencher des workflows depuis des updates Monday."""
    
    def __init__(self):
        """Initialise le service de déclenchement de workflow."""
        logger.info("✅ WorkflowTriggerService initialisé")
    
    async def trigger_workflow_from_update(
        self, 
        task_id: int, 
        update_analysis: UpdateIntent,
        monday_item_id: int,
        update_id: str
    ) -> Dict[str, Any]:
        """
        Déclenche un nouveau workflow depuis un update Monday.
        
        Args:
            task_id: ID de la tâche dans la DB
            update_analysis: Résultat de l'analyse de l'update
            monday_item_id: ID de l'item Monday.com
            update_id: ID de l'update Monday
            
        Returns:
            Résultat du déclenchement avec run_id et celery_task_id
        """
        try:
            logger.info(f"🚀 Déclenchement workflow depuis update {update_id} pour tâche {task_id}")
            
            original_task = await self._get_task_details(task_id)
            if not original_task:
                logger.error(f"❌ Tâche {task_id} non trouvée")
                return {
                    "success": False,
                    "error": "Tâche non trouvée"
                }
            
            task_request = await self.create_task_request_from_update(
                original_task, 
                update_analysis
            )
            
            if not task_request:
                logger.error(f"❌ Impossible de créer TaskRequest depuis update")
                return {
                    "success": False,
                    "error": "Impossible de créer TaskRequest"
                }
            
            run_id = await self.create_new_task_run(
                task_id=task_id,
                task_request=task_request,
                update_id=update_id
            )
            
            if not run_id:
                logger.error(f"❌ Impossible de créer task_run")
                return {
                    "success": False,
                    "error": "Impossible de créer task_run"
                }
            
            await db_persistence.log_application_event(
                task_id=task_id,
                level="INFO",
                source_component="workflow_trigger",
                action="new_workflow_triggered_from_update",
                message=f"Nouveau workflow déclenché depuis update: {update_analysis.extracted_requirements.get('title', 'Sans titre') if update_analysis.extracted_requirements else 'Sans titre'}",
                metadata={
                    "update_id": update_id,
                    "run_id": run_id,
                    "task_type": task_request.task_type,
                    "priority": task_request.priority,
                    "confidence": update_analysis.confidence,
                    "update_type": update_analysis.type
                }
            )
            
            priority = self._determine_priority(update_analysis)
            celery_task_id = self.submit_to_celery(task_request, priority=priority)
            
            if not celery_task_id:
                logger.error(f"❌ Impossible de soumettre à Celery")
                return {
                    "success": False,
                    "error": "Impossible de soumettre à Celery"
                }
            
            await self._post_confirmation_to_monday(
                monday_item_id=monday_item_id,
                task_request=task_request,
                run_id=run_id
            )
            
            logger.info(f"✅ Workflow déclenché avec succès: run_id={run_id}, celery_task_id={celery_task_id}")
            
            return {
                "success": True,
                "run_id": run_id,
                "celery_task_id": celery_task_id,
                "task_request": task_request.dict() if hasattr(task_request, 'dict') else task_request.model_dump()
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur déclenchement workflow: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_task_details(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère les détails complets d'une tâche.
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Dictionnaire avec les détails de la tâche ou None
        """
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                task = await conn.fetchrow("""
                    SELECT 
                        tasks_id,
                        monday_item_id,
                        title,
                        description,
                        internal_status,
                        monday_status,
                        repository_url,
                        priority,
                        repository_name
                    FROM tasks 
                    WHERE tasks_id = $1
                """, task_id)
                
                if task:
                    return dict(task)
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération tâche {task_id}: {e}", exc_info=True)
            return None
    
    async def create_task_request_from_update(
        self,
        original_task: Dict[str, Any],
        update_analysis: UpdateIntent
    ) -> Optional[TaskRequest]:
        """
        Crée un nouveau TaskRequest depuis une analyse d'update.
        
        Args:
            original_task: Données de la tâche originale
            update_analysis: Résultat de l'analyse de l'update
            
        Returns:
            TaskRequest ou None
        """
        try:
            requirements = update_analysis.extracted_requirements or {}
            
            title = requirements.get('title') or f"Update: {original_task['title']}"
            
            description = requirements.get('description') or "Nouvelle demande depuis un commentaire Monday.com"
            
            task_type_str = requirements.get('task_type', 'feature')
            try:
                task_type = TaskType(task_type_str.lower())
            except ValueError:
                task_type = TaskType.FEATURE
            
            priority_str = requirements.get('priority', 'medium')
            try:
                priority = TaskPriority(priority_str.lower())
            except ValueError:
                priority = TaskPriority.MEDIUM
            
            task_request = TaskRequest(
                task_id=str(original_task['monday_item_id']),
                title=title,
                description=description,
                task_type=task_type,
                priority=priority,
                repository_url=original_task['repository_url'],
                monday_item_id=original_task['monday_item_id'],
                task_db_id=original_task['tasks_id'],
                files_to_modify=requirements.get('files_mentioned', []),
                technical_context=f"Demande depuis un commentaire sur une tâche terminée. Contexte original: {original_task.get('description', '')[:200]}"
            )
            
            logger.info(f"✅ TaskRequest créé: {title} (type={task_type}, priority={priority})")
            return task_request
            
        except Exception as e:
            logger.error(f"❌ Erreur création TaskRequest: {e}", exc_info=True)
            return None
    
    async def create_new_task_run(
        self,
        task_id: int,
        task_request: TaskRequest,
        update_id: str
    ) -> Optional[int]:
        """
        Crée un nouveau task_run pour le workflow.
        
        Args:
            task_id: ID de la tâche
            task_request: TaskRequest pour le nouveau workflow
            update_id: ID de l'update Monday qui a déclenché
            
        Returns:
            ID du nouveau run ou None
        """
        try:
            import uuid
            custom_run_id = f"update-{update_id}-{uuid.uuid4().hex[:8]}"
            
            run_id = await db_persistence.start_task_run(
                task_id=task_id,
                celery_task_id=custom_run_id,
                ai_provider="claude",
                custom_run_id=custom_run_id
            )
            
            logger.info(f"✅ Nouveau task_run créé: {run_id} (triggered by update {update_id})")
            return run_id
            
        except Exception as e:
            logger.error(f"❌ Erreur création task_run: {e}", exc_info=True)
            return None
    
    def submit_to_celery(
        self,
        task_request: TaskRequest,
        priority: int = 5
    ) -> Optional[str]:
        """
        Soumet le TaskRequest à Celery pour exécution.
        
        Args:
            task_request: TaskRequest à exécuter
            priority: Priorité Celery (0-9, 9 = urgent)
            
        Returns:
            ID de la tâche Celery ou None
        """
        try:
            task_dict = task_request.dict() if hasattr(task_request, 'dict') else task_request.model_dump()
            
            celery_task = submit_task(task_dict, priority=priority)
            
            if celery_task:
                celery_task_id = celery_task.id
                logger.info(f"✅ Tâche soumise à Celery: {celery_task_id} (priority={priority})")
                return celery_task_id
            else:
                logger.error("❌ Échec soumission à Celery: aucune tâche retournée")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur soumission Celery: {e}", exc_info=True)
            return None
    
    def _determine_priority(self, update_analysis: UpdateIntent) -> int:
        """
        Détermine la priorité Celery basée sur l'analyse.
        
        Args:
            update_analysis: Résultat de l'analyse
            
        Returns:
            Priorité Celery (0-9)
        """
        if not update_analysis.extracted_requirements:
            return 5  
        
        priority_str = update_analysis.extracted_requirements.get('priority', 'medium').lower()
        
    
        priority_map = {
            'urgent': 9,
            'high': 7,
            'medium': 5,
            'low': 3
        }
        
        return priority_map.get(priority_str, 5)
    
    async def _post_confirmation_to_monday(
        self,
        monday_item_id: int,
        task_request: TaskRequest,
        run_id: int
    ):
        """
        Poste un commentaire de confirmation dans Monday.com.
        
        Args:
            monday_item_id: ID de l'item Monday
            task_request: TaskRequest créé
            run_id: ID du run créé
        """
        try:
            from tools.monday_tool import MondayTool
            
            monday_tool = MondayTool()
            
            type_emoji = {
                'feature': '✨',
                'bugfix': '🐛',
                'refactor': '🔧',
                'documentation': '📚',
                'testing': '🧪'
            }
            
            emoji = type_emoji.get(task_request.task_type, '🚀')
            
            priority_emoji = {
                'urgent': '🔥',
                'high': '⚡',
                'medium': '📊',
                'low': '📝'
            }
            
            priority_icon = priority_emoji.get(str(task_request.priority), '📊')
            
            comment = f"""🤖 **Nouvelle demande détectée et prise en compte !**

{emoji} **{task_request.title}**

📋 **Type:** {task_request.task_type}
{priority_icon} **Priorité:** {task_request.priority}
🆔 **Run ID:** {run_id}

Le workflow a été lancé automatiquement. Je vous tiendrai informé de l'avancement.
"""
            
            result = await monday_tool._arun(
                action="add_comment",
                item_id=str(monday_item_id),
                comment=comment
            )
            
            if result:
                logger.info(f"✅ Commentaire de confirmation posté dans Monday item {monday_item_id}")
            else:
                logger.warning(f"⚠️ Échec post commentaire dans Monday item {monday_item_id}")
                
        except Exception as e:
            logger.error(f"❌ Erreur post commentaire Monday: {e}", exc_info=True)

workflow_trigger_service = WorkflowTriggerService()