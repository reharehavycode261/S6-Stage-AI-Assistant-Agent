"""Définition de l'état pour LangGraph."""

from typing import Dict, Any, Optional, List
from typing_extensions import Annotated, TypedDict
from datetime import datetime

from .schemas import TaskRequest, WorkflowStatus, add_to_list, merge_results


class GraphState(TypedDict, total=False):
    """État principal pour LangGraph - compatibilité avec WorkflowState."""
    workflow_id: str
    status: WorkflowStatus  
    current_node: Optional[str]
    completed_nodes: Annotated[List[str], add_to_list]
    task: Optional[TaskRequest]
    results: Annotated[Dict[str, Any], merge_results]
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    langsmith_session: Optional[str]  
    
    db_task_id: Optional[int]  
    db_run_id: Optional[int]   
    db_step_id: Optional[int]  
    current_step_id: Optional[int]  
    
    queue_id: Optional[str]  
    run_id: Optional[int]  
    uuid_run_id: Optional[str]  
    task_context: Optional[Dict[str, Any]]  
    node_retry_count: Optional[Dict[str, int]]  
    recovery_mode: Optional[bool]  
    checkpoint_data: Optional[Dict[str, Any]]  


WorkflowState = GraphState 