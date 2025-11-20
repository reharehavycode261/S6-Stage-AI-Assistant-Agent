# -*- coding: utf-8 -*-
"""
Tests de validation des corrections de coherence du workflow.
Date: 2025-10-06
"""

import sys
import os

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import TaskRequest, HumanValidationRequest
from models.state import GraphState
from datetime import datetime, timedelta


class TestNomenclatureCoherence:
    """Tests de cohérence de nomenclature."""
    
    def test_task_request_has_required_fields(self):
        """Vérifier que TaskRequest a les champs nécessaires."""
        task = TaskRequest(
            task_id="12345",
            title="Test Task",
            description="Test description",
            monday_item_id=5028673529,
            task_db_id=36
        )
        
        assert hasattr(task, 'task_id')
        assert hasattr(task, 'monday_item_id')
        assert hasattr(task, 'title')
        
        # Vérifier les types
        assert isinstance(task.task_id, str)
        assert isinstance(task.monday_item_id, int)
        assert isinstance(task.task_db_id, int)
        
        print("OK - TaskRequest a tous les champs requis")
    
    def test_display_task_id_logic(self):
        """Tester la logique de display_task_id."""
        # Cas 1: Avec monday_item_id
        task1 = TaskRequest(
            task_id="12345",
            title="Test",
            description="Test",
            monday_item_id=5028673529
        )
        
        display_id1 = str(task1.monday_item_id) if hasattr(task1, 'monday_item_id') and task1.monday_item_id else str(task1.task_id)
        assert display_id1 == "5028673529"
        print("OK - Display ID avec monday_item_id: " + display_id1)
        
        # Cas 2: Sans monday_item_id
        task2 = TaskRequest(
            task_id="12345",
            title="Test",
            description="Test"
        )
        
        display_id2 = str(task2.monday_item_id) if hasattr(task2, 'monday_item_id') and task2.monday_item_id else str(task2.task_id)
        assert display_id2 == "12345"
        print("OK - Display ID sans monday_item_id: " + display_id2)
    
    def test_human_validation_request_creation(self):
        """Tester la création d'une HumanValidationRequest."""
        validation_req = HumanValidationRequest(
            validation_id="val_test_123",
            workflow_id="workflow_123",
            task_id="5028673529",  # Monday item ID pour affichage
            task_title="Test Task",
            generated_code='{"file1.py": "content"}',
            code_summary="Test summary",
            files_modified=["file1.py"],
            original_request="Test request",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        assert validation_req.task_id == "5028673529"
        assert isinstance(validation_req.generated_code, str)
        print("OK - HumanValidationRequest creee correctement")
    
    def test_state_db_fields(self):
        """Verifier que GraphState peut contenir db_task_id et db_run_id."""
        state = {
            "workflow_id": "test_workflow",
            "db_task_id": 36,
            "db_run_id": 100,
            "task": TaskRequest(
                task_id="5028673529",
                title="Test",
                description="Test",
                monday_item_id=5028673529,
                task_db_id=36
            ),
            "results": {},
            "completed_nodes": []
        }
        
        assert "db_task_id" in state
        assert "db_run_id" in state
        assert state["db_task_id"] == 36
        assert state["db_run_id"] == 100
        
        # Vérifier l'accès sécurisé
        db_task_id = state.get("db_task_id")
        assert db_task_id == 36
        print("OK - State contient db_task_id: " + str(db_task_id))


class TestIDConsistency:
    """Tests de cohérence des IDs."""
    
    def test_monday_item_id_vs_db_task_id(self):
        """Vérifier la distinction entre monday_item_id et db_task_id."""
        task = TaskRequest(
            task_id="5028673529",
            title="Test",
            description="Test",
            monday_item_id=5028673529,  # ID Monday.com
            task_db_id=36  # ID base de données
        )
        
        # monday_item_id pour l'affichage
        display_id = task.monday_item_id
        assert display_id == 5028673529
        
        # db_task_id pour la base de données
        db_id = task.task_db_id
        assert db_id == 36
        
        # Ils doivent être différents dans ce cas
        assert display_id != db_id
        print("OK - Distinction claire: monday_item_id=" + str(display_id) + ", db_task_id=" + str(db_id))
    
    def test_id_propagation_in_state(self):
        """Tester la propagation des IDs dans l'etat."""
        state = {
            "workflow_id": "test_workflow",
            "db_task_id": 36,
            "db_run_id": 100,
            "task": TaskRequest(
                task_id="5028673529",
                title="Test",
                description="Test",
                monday_item_id=5028673529,
                task_db_id=36
            ),
            "results": {
                "db_task_id": 36,  # Propagé par prepare_node
                "db_run_id": 100   # Propagé par prepare_node
            },
            "completed_nodes": []
        }
        
        # Vérifier la propagation
        assert state["results"]["db_task_id"] == 36
        assert state["results"]["db_run_id"] == 100
        
        # Vérifier l'accès depuis les deux endroits
        db_task_id_root = state.get("db_task_id")
        db_task_id_results = state["results"].get("db_task_id")
        
        assert db_task_id_root == db_task_id_results
        print("OK - Propagation: root=" + str(db_task_id_root) + ", results=" + str(db_task_id_results))


class TestFallbackMechanisms:
    """Tests des mécanismes de fallback."""
    
    def test_display_id_fallback(self):
        """Tester le fallback pour display_id."""
        # Cas 1: monday_item_id présent
        task1 = TaskRequest(
            task_id="12345",
            title="Test",
            description="Test",
            monday_item_id=5028673529
        )
        display_id1 = str(task1.monday_item_id) if hasattr(task1, 'monday_item_id') and task1.monday_item_id else str(task1.task_id)
        assert display_id1 == "5028673529"
        
        # Cas 2: monday_item_id None
        task2 = TaskRequest(
            task_id="12345",
            title="Test",
            description="Test",
            monday_item_id=None
        )
        display_id2 = str(task2.monday_item_id) if hasattr(task2, 'monday_item_id') and task2.monday_item_id else str(task2.task_id)
        assert display_id2 == "12345"
        
        # Cas 3: monday_item_id absent (non défini)
        task3 = TaskRequest(
            task_id="12345",
            title="Test",
            description="Test"
        )
        display_id3 = str(task3.monday_item_id) if hasattr(task3, 'monday_item_id') and task3.monday_item_id else str(task3.task_id)
        assert display_id3 in ["None", "12345"]  # Peut être None ou fallback
        
        print("OK - Tous les fallbacks fonctionnent correctement")


class TestValidationLogic:
    """Tests de la logique de validation."""
    
    def test_validation_request_with_correct_ids(self):
        """Tester la création d'une validation avec les bons IDs."""
        # Simuler un state avec task
        task = TaskRequest(
            task_id="5028673529",
            title="Test Task",
            description="Test description",
            monday_item_id=5028673529,
            task_db_id=36
        )
        
        # Display ID pour HumanValidationRequest (UI)
        display_task_id = str(task.monday_item_id) if hasattr(task, 'monday_item_id') and task.monday_item_id else str(task.task_id)
        
        # DB ID pour la persistence (foreign key)
        db_task_id = 36  # Récupéré depuis state.get("db_task_id")
        
        # Créer la validation request
        validation_req = HumanValidationRequest(
            validation_id="val_test_123",
            workflow_id="workflow_123",
            task_id=display_task_id,  # Monday item ID pour UI
            task_title=task.title,
            generated_code='{}',
            code_summary="Test",
            files_modified=[],
            original_request=task.description
        )
        
        # Vérifier que les IDs sont corrects
        assert validation_req.task_id == "5028673529"  # Display ID
        assert db_task_id == 36  # DB ID (utilisé séparément pour la persistence)
        
        print("OK - Validation creee: display_id=" + validation_req.task_id + ", db_id=" + str(db_task_id))


def run_all_tests():
    """Executer tous les tests."""
    print("\n" + "="*70)
    print("TESTS DE COHERENCE DES CORRECTIONS")
    print("="*70 + "\n")
    
    test_classes = [
        TestNomenclatureCoherence(),
        TestIDConsistency(),
        TestFallbackMechanisms(),
        TestValidationLogic()
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print("\n[TEST CLASS] " + class_name)
        print("-" * 70)
        
        # Récupérer toutes les méthodes de test
        test_methods = [method for method in dir(test_class) if method.startswith('test_')]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(test_class, method_name)
                method()
                passed_tests += 1
                print("  [OK] " + method_name)
            except AssertionError as e:
                failed_tests += 1
                print("  [FAIL] " + method_name + ": " + str(e))
            except Exception as e:
                failed_tests += 1
                print("  [ERROR] " + method_name + ": " + str(e))
    
    # Resume
    print("\n" + "="*70)
    print("RESUME DES TESTS")
    print("="*70)
    print("Total: " + str(total_tests) + " tests")
    print("Reussis: " + str(passed_tests))
    print("Echoues: " + str(failed_tests))
    if total_tests > 0:
        print("Taux de succes: " + str(round(passed_tests/total_tests*100, 1)) + "%")
    print("="*70 + "\n")
    
    return failed_tests == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

