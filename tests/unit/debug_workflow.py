#!/usr/bin/env python3
"""Script de debug pour comprendre la structure de l'état LangGraph"""

import asyncio
import sys
import os

# Ajouter le répertoire racine au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.schemas import TaskRequest, TaskType, TaskPriority
from graph.workflow_graph import create_workflow_graph
from langgraph.checkpoint.memory import MemorySaver
from utils.logger import get_logger

logger = get_logger(__name__)

async def debug_workflow_state():
    """Debug de la structure de l'état LangGraph."""
    print("🔍 Debug de la structure de l'état LangGraph...")
    
    # Créer une tâche de test
    task_request = TaskRequest(
        task_id="debug_001",
        title="Debug Workflow",
        description="Debug test",
        task_type=TaskType.FEATURE,
        priority=TaskPriority.MEDIUM,
        repository_url="https://github.com/test/repo",
        branch_name="debug",
        base_branch="main"
    )
    
    try:
        # Créer le graphe
        workflow_graph = create_workflow_graph()
        checkpointer = MemorySaver()
        app = workflow_graph.compile(checkpointer=checkpointer)
        
        # Créer l'état initial
        from graph.workflow_graph import _create_initial_state
        initial_state = _create_initial_state(task_request, "debug_workflow")
        
        print(f"📊 État initial: {type(initial_state)}")
        print(f"📊 Attributs: {dir(initial_state)}")
        
        # Configuration
        config = {
            "configurable": {
                "thread_id": "debug_workflow",
                "task_id": task_request.task_id
            }
        }
        
        # Tester l'itération
        print("🔄 Test de l'itération...")
        count = 0
        async for state in app.astream(initial_state, config=config):
            count += 1
            print(f"📍 Itération {count}:")
            print(f"   Type: {type(state)}")
            print(f"   Contenu: {state}")
            print(f"   Attributs: {dir(state) if hasattr(state, '__dict__') else 'N/A'}")
            
            if count >= 3:  # Limiter à 3 itérations pour le debug
                break
                
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_workflow_state())
