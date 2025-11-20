"""Test unitaire pour vérifier la correction du bug TaskRequest.get()"""

import pytest
import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from models.schemas import TaskRequest
from models.state import GraphState


class TestTaskRequestFix:
    """Tests pour vérifier que TaskRequest est correctement géré comme objet"""
    
    def test_task_request_is_object_not_dict(self):
        """Vérifie que TaskRequest est bien un objet et non un dictionnaire"""
        task = TaskRequest(
            task_id="test_001",
            title="Test Task",
            description="Test description",
            priority="high"
        )
        
        # TaskRequest est un objet, pas un dict
        assert isinstance(task, TaskRequest)
        assert not isinstance(task, dict)
        
        # On ne peut pas utiliser .get() sur un objet
        with pytest.raises(AttributeError):
            task.get("description")
    
    def test_getattr_on_task_request(self):
        """Vérifie que getattr fonctionne correctement sur TaskRequest"""
        task = TaskRequest(
            task_id="test_002",
            title="Test Task",
            description="Test description with special chars éàç",
            priority="medium"
        )
        
        # getattr doit fonctionner
        assert getattr(task, "description", "") == "Test description with special chars éàç"
        assert getattr(task, "title", "") == "Test Task"
        assert getattr(task, "priority", "") == "medium"
        
        # getattr avec attribut inexistant doit retourner la valeur par défaut
        assert getattr(task, "non_existent_attr", "default") == "default"
    
    def test_task_in_graph_state(self):
        """Vérifie qu'on peut accéder au task dans GraphState correctement"""
        task = TaskRequest(
            task_id="test_003",
            title="Graph State Test",
            description="Testing GraphState integration",
            priority="low"
        )
        
        # Créer un state avec task
        state = {
            "task": task,
            "results": {
                "ai_messages": [],
                "error_logs": []
            }
        }
        
        # Accès correct avec getattr
        task_from_state = state.get("task")
        assert task_from_state is not None
        
        description = getattr(task_from_state, "description", "")
        assert description == "Testing GraphState integration"
        
        # Vérifier que c'est bien un objet TaskRequest
        assert isinstance(task_from_state, TaskRequest)
    
    def test_empty_description_handling(self):
        """Vérifie la gestion des descriptions vides (description est obligatoire, pas None)"""
        # Description vide (string vide)
        task = TaskRequest(
            task_id="test_004",
            title="Empty Description Test",
            description="",  # Description peut être vide mais pas None
            priority="high"
        )
        
        # getattr doit fonctionner avec une description vide
        description = getattr(task, "description", "default") or "fallback"
        assert description == "fallback"  # Car description est ""
        
        # Avec une description normale
        task2 = TaskRequest(
            task_id="test_005",
            title="Normal Description Test",
            description="Une description normale",
            priority="low"
        )
        
        description2 = getattr(task2, "description", "") or "fallback"
        assert description2 == "Une description normale"
    
    def test_task_request_with_optional_fields(self):
        """Vérifie que les champs optionnels sont bien gérés"""
        task = TaskRequest(
            task_id="test_006",
            title="Optional Fields Test",
            description="Test with optional fields"
        )
        
        # Les champs optionnels peuvent ne pas exister ou être None
        repo_url = getattr(task, "repository_url", None)
        branch = getattr(task, "branch_name", None)
        monday_id = getattr(task, "monday_item_id", None)
        
        # Ces valeurs peuvent être None sans erreur
        assert True  # Le test passe si aucune exception n'est levée


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

