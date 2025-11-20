#!/usr/bin/env python3
"""Script de test pour le workflow LangGraph."""

import asyncio
import sys
import os

# Ajouter le répertoire racine au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models.schemas import TaskRequest, TaskType, TaskPriority
from graph.workflow_graph import run_workflow, create_workflow_graph
from utils.logger import get_logger

logger = get_logger(__name__)

async def test_workflow_structure():
    """Test de la structure du graphe LangGraph."""
    print("🔍 Test de la structure du graphe LangGraph...")
    
    try:
        # Créer le graphe
        workflow_graph = create_workflow_graph()
        print("✅ Graphe créé avec succès")
        
        # Vérifier les nœuds
        nodes = workflow_graph.nodes
        print(f"📊 Nœuds trouvés: {list(nodes.keys())}")
        
        # Vérifier les connexions
        edges = workflow_graph.edges
        print(f"🔗 Connexions trouvées: {len(edges)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création du graphe: {e}")
        return False

async def test_workflow_execution():
    """Test d'exécution du workflow avec des données simulées."""
    print("\n🚀 Test d'exécution du workflow...")
    
    # Créer une tâche de test simulée
    task_request = TaskRequest(
        task_id="test_workflow_001",
        title="Test de workflow LangGraph",
        description="Ceci est un test du workflow LangGraph pour vérifier que tout fonctionne correctement.",
        task_type=TaskType.FEATURE,
        priority=TaskPriority.MEDIUM,
        repository_url="https://github.com/test/repo",
        branch_name="test-workflow",
        base_branch="main",
        acceptance_criteria="Le workflow doit s'exécuter sans erreur",
        technical_context="Test de simulation",
        files_to_modify=["test_file.py"],
        estimated_complexity="low"
    )
    
    print(f"📝 Tâche de test créée: {task_request.title}")
    
    try:
        # Exécuter le workflow
        print("🔄 Démarrage de l'exécution du workflow...")
        result = await run_workflow(task_request)
        
        print("✅ Workflow terminé!")
        print(f"📊 Résultat: {result}")
        
        return result
        
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du workflow: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_monday_api_error():
    """Test de l'erreur Monday.com API après l'exécution du workflow."""
    print("\n🔧 Test de l'erreur Monday.com API après l'exécution du workflow...")
    
    # Créer une tâche de test simulée qui provoquera une erreur Monday.com
    task_request = TaskRequest(
        task_id="test_monday_api_error_001",
        title="Test d'erreur Monday.com API",
        description="Ceci est un test pour vérifier la gestion de l'erreur Monday.com API.",
        task_type=TaskType.BUG,
        priority=TaskPriority.HIGH,
        repository_url="https://github.com/test/repo",
        branch_name="test-workflow",
        base_branch="main",
        acceptance_criteria="Le workflow doit gérer l'erreur Monday.com API sans planter.",
        technical_context="Test de simulation",
        files_to_modify=["test_file.py"],
        estimated_complexity="medium"
    )
    
    print(f"📝 Tâche de test créée: {task_request.title}")
    
    try:
        # Exécuter le workflow
        print("🔄 Démarrage de l'exécution du workflow...")
        result = await run_workflow(task_request)
        
        print("✅ Workflow terminé!")
        print(f"📊 Résultat: {result}")
        
        # Vérifier que le résultat contient l'erreur Monday.com
        if "monday_api_error" in result and result["monday_api_error"] is True:
            print("✅ Test de l'erreur Monday.com API réussi!")
            return True
        else:
            print("❌ Le résultat ne contient pas l'erreur Monday.com API.")
            return False
        
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du workflow: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Fonction principale de test."""
    print("🧪 Démarrage des tests du workflow LangGraph")
    print("=" * 50)
    
    # Test 1: Structure du graphe
    structure_ok = await test_workflow_structure()
    
    if not structure_ok:
        print("❌ Test de structure échoué - arrêt des tests")
        return
    
    # Test 2: Exécution du workflow
    result = await test_workflow_execution()
    
    if result:
        print("\n🎉 Tous les tests sont passés avec succès!")
        print(f"📈 Métriques: {result.get('metrics', {})}")
    else:
        print("\n❌ Certains tests ont échoué")

    # Test 3: Test de l'erreur Monday.com API
    monday_api_error_ok = await test_monday_api_error()
    if monday_api_error_ok:
        print("\n🎉 Test de l'erreur Monday.com API réussi!")
    else:
        print("\n❌ Test de l'erreur Monday.com API échoué.")

if __name__ == "__main__":
    asyncio.run(main())
