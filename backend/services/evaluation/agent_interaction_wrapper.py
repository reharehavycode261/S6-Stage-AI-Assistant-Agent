"""
Agent Interaction Wrapper - Wrapper pour capturer automatiquement les inputs/outputs de l'agent.

Ce service s'intègre avec votre agent existant et log automatiquement
toutes les interactions dans Excel sans nécessiter de modifications majeures.

Usage:
    wrapper = AgentInteractionWrapper(your_agent_service)
    result = await wrapper.process_with_logging(input_text, context)
    # → L'input et l'output sont automatiquement loggés dans Excel
"""

from typing import Dict, Any, Optional, Callable
import time
from datetime import datetime
from services.evaluation.agent_output_logger import AgentOutputLogger
from utils.logger import get_logger

logger = get_logger(__name__)


class AgentInteractionWrapper:
    """
    Wrapper pour capturer automatiquement les interactions de l'agent.
    """
    
    def __init__(self, agent_service: Any, auto_log: bool = True):
        """
        Initialise le wrapper.
        
        Args:
            agent_service: Votre service agent (ex: AgentResponseService).
            auto_log: Si True, log automatiquement toutes les interactions.
        """
        self.agent_service = agent_service
        self.logger = AgentOutputLogger()
        self.auto_log = auto_log
        
        logger.info("✅ AgentInteractionWrapper initialisé")
    
    async def process_analysis_with_logging(
        self,
        question: str,
        task_context: Dict[str, Any],
        monday_item_id: str,
        monday_update_id: Optional[str] = None,
        task: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Traite une question d'analyse et log automatiquement l'interaction.
        
        Args:
            question: La question posée.
            task_context: Contexte de la tâche.
            monday_item_id: ID de l'item Monday.
            monday_update_id: ID de l'update Monday.
            task: Objet task (optionnel).
            
        Returns:
            Résultat de l'agent + interaction_id.
        """
        start_time = time.time()
        success = False
        error_message = None
        agent_response = ""
        
        try:
            logger.info(f"🔄 Traitement analyse avec logging: {question[:50]}...")
            
            result = await self.agent_service.generate_and_post_response(
                question=question,
                task_context=task_context,
                monday_item_id=monday_item_id,
                task=task
            )
            
            success = result.get("success", False)
            agent_response = result.get("response_text", "")
            
            if not success:
                error_message = result.get("error", "Unknown error")
            
            duration = time.time() - start_time
            
            if self.auto_log:
                interaction_id = self.logger.log_agent_interaction(
                    monday_update_id=monday_update_id or f"auto_{monday_item_id}",
                    monday_item_id=monday_item_id,
                    input_text=question,
                    agent_output=agent_response,
                    interaction_type='analysis',
                    duration_seconds=duration,
                    success=success,
                    error_message=error_message,
                    metadata=task_context,
                    repository_url=task_context.get('repository_url'),
                    creator_name=task.creator_name if task and hasattr(task, 'creator_name') else None
                )
                
                result['interaction_id'] = interaction_id
                result['logged'] = True
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement analyse: {e}", exc_info=True)
            
            duration = time.time() - start_time
            error_message = str(e)
            
            if self.auto_log:
                interaction_id = self.logger.log_agent_interaction(
                    monday_update_id=monday_update_id or f"auto_{monday_item_id}",
                    monday_item_id=monday_item_id,
                    input_text=question,
                    agent_output=agent_response or f"Error: {error_message}",
                    interaction_type='analysis',
                    duration_seconds=duration,
                    success=False,
                    error_message=error_message,
                    metadata=task_context
                )
            
            return {
                "success": False,
                "error": error_message,
                "interaction_id": interaction_id if self.auto_log else None,
                "logged": self.auto_log
            }
    
    async def process_pr_with_logging(
        self,
        command: str,
        task_context: Dict[str, Any],
        monday_item_id: str,
        monday_update_id: Optional[str] = None,
        task: Optional[Any] = None,
        pr_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log une création de PR avec ses détails.
        
        Args:
            command: La commande qui a déclenché la PR.
            task_context: Contexte de la tâche.
            monday_item_id: ID de l'item Monday.
            monday_update_id: ID de l'update Monday.
            task: Objet task.
            pr_result: Résultat de la création de PR (de PullRequestService).
            
        Returns:
            Résultat + interaction_id.
        """
        start_time = time.time()
        
        try:
            logger.info(f"🔄 Logging PR: {command[:50]}...")
            
            if pr_result is None:
                raise ValueError("PR result is None")
            
            success = pr_result.get("success", False)
            pr_url = pr_result.get("pr_url", "")
            pr_number = pr_result.get("pr_number", "")
            branch_name = pr_result.get("branch_name", "")
            error_message = pr_result.get("error")
            
            if success:
                agent_output = f"PR #{pr_number} créée avec succès sur la branche {branch_name}. URL: {pr_url}"
            else:
                agent_output = f"Échec création PR: {error_message}"
            
            duration = time.time() - start_time
            
            if self.auto_log:
                interaction_id = self.logger.log_agent_interaction(
                    monday_update_id=monday_update_id or f"auto_{monday_item_id}",
                    monday_item_id=monday_item_id,
                    input_text=command,
                    agent_output=agent_output,
                    interaction_type='pr',
                    duration_seconds=duration,
                    success=success,
                    error_message=error_message,
                    metadata=task_context,
                    repository_url=task_context.get('repository_url'),
                    branch_name=branch_name,
                    pr_number=str(pr_number) if pr_number else None,
                    pr_url=pr_url,
                    creator_name=task.creator_name if task and hasattr(task, 'creator_name') else None
                )
                
                pr_result['interaction_id'] = interaction_id
                pr_result['logged'] = True
            
            return pr_result
            
        except Exception as e:
            logger.error(f"❌ Erreur logging PR: {e}", exc_info=True)
            
            duration = time.time() - start_time
            error_message = str(e)
            
            if self.auto_log:
                interaction_id = self.logger.log_agent_interaction(
                    monday_update_id=monday_update_id or f"auto_{monday_item_id}",
                    monday_item_id=monday_item_id,
                    input_text=command,
                    agent_output=f"Error: {error_message}",
                    interaction_type='pr',
                    duration_seconds=duration,
                    success=False,
                    error_message=error_message,
                    metadata=task_context
                )
            
            return {
                "success": False,
                "error": error_message,
                "interaction_id": interaction_id if self.auto_log else None,
                "logged": self.auto_log
            }
    
    def calculate_daily_metrics(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Calcule les métriques quotidiennes.
        
        Args:
            date: Date (YYYY-MM-DD). Par défaut: aujourd'hui.
            
        Returns:
            Métriques calculées.
        """
        return self.logger.calculate_performance_metrics(
            date=date,
            save_to_metrics=True
        )
    
    def get_recent_interactions(self, limit: int = 10) -> Any:
        """Récupère les dernières interactions."""
        return self.logger.get_interactions(limit=limit)
    
    def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Récupère les statistiques sur N jours."""
        return self.logger.get_statistics_summary(days=days)

