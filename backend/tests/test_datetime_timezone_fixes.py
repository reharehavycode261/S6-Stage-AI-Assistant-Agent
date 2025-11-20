"""
Tests unitaires pour valider les corrections de timezone et sérialisation Pydantic.

Ces tests vérifient que :
1. Tous les datetime créés ont une timezone (UTC)
2. La sérialisation Pydantic ne génère pas de warnings pour les IDs
3. Les modèles acceptent des int et les convertissent en str correctement
"""

import pytest
import warnings
from datetime import datetime, timezone
from typing import Any
import json

# Import des modèles à tester
from models.schemas import (
    TaskRequest,
    TaskStatusResponse,
    WorkflowStateModel,
    HumanValidationRequest,
    HumanValidationResponse,
    HumanValidationSummary,
    HumanValidationStatus,
    ErrorResponse,
    PullRequestInfo,
    WorkflowStatus
)


class TestDatetimeTimezone:
    """Tests pour vérifier que tous les datetime ont une timezone UTC."""
    
    def test_error_response_timestamp_has_timezone(self):
        """Vérifie que ErrorResponse.timestamp a une timezone UTC."""
        error = ErrorResponse(error="Test error", details="Test details")
        
        assert error.timestamp.tzinfo is not None, "timestamp devrait avoir une timezone"
        assert error.timestamp.tzinfo == timezone.utc, "timestamp devrait être en UTC"
    
    def test_human_validation_request_created_at_has_timezone(self):
        """Vérifie que HumanValidationRequest.created_at a une timezone UTC."""
        validation_req = HumanValidationRequest(
            validation_id="val_123",
            workflow_id="wf_456",
            task_id="task_789",
            task_title="Test Task",
            generated_code={"main.py": "print('test')"},
            code_summary="Added main.py file",
            original_request="Add a main file",
            test_results={"success": True},
            files_modified=["main.py"]
        )
        
        assert validation_req.created_at.tzinfo is not None, "created_at devrait avoir une timezone"
        assert validation_req.created_at.tzinfo == timezone.utc, "created_at devrait être en UTC"
    
    def test_human_validation_response_validated_at_has_timezone(self):
        """Vérifie que HumanValidationResponse.validated_at a une timezone UTC."""
        validation_resp = HumanValidationResponse(
            validation_id="val_123",
            status=HumanValidationStatus.APPROVED
        )
        
        assert validation_resp.validated_at.tzinfo is not None, "validated_at devrait avoir une timezone"
        assert validation_resp.validated_at.tzinfo == timezone.utc, "validated_at devrait être en UTC"
    
    def test_pull_request_info_created_at_with_timezone(self):
        """Vérifie que PullRequestInfo accepte des datetime avec timezone."""
        pr = PullRequestInfo(
            number=42,
            title="Test PR",
            url="https://github.com/test/repo/pull/42",
            branch="feature/test",
            base_branch="main",
            status="open",
            created_at=datetime.now(timezone.utc)
        )
        
        assert pr.created_at.tzinfo is not None, "created_at devrait avoir une timezone"
        assert pr.created_at.tzinfo == timezone.utc, "created_at devrait être en UTC"


class TestPydanticSerializationIntToStr:
    """Tests pour vérifier que la sérialisation Pydantic convertit int->str sans warnings."""
    
    def test_task_request_task_id_int_conversion(self):
        """Vérifie que TaskRequest convertit task_id int en str."""
        # Créer avec un int
        task = TaskRequest(
            task_id=12345,  # int
            title="Test Task",
            description="Test description"
        )
        
        # Vérifier que c'est converti en str
        assert isinstance(task.task_id, str), "task_id devrait être converti en str"
        assert task.task_id == "12345"
        
        # Sérialiser et vérifier qu'il n'y a pas de warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            serialized = task.model_dump()
            
            # Vérifier qu'aucun warning Pydantic n'a été émis
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0, f"Warnings Pydantic détectés: {pydantic_warnings}"
        
        assert isinstance(serialized['task_id'], str), "task_id sérialisé devrait être str"
    
    def test_task_request_serialization_to_json(self):
        """Vérifie que TaskRequest peut être sérialisé en JSON sans erreur."""
        task = TaskRequest(
            task_id=99999,  # int
            title="JSON Test",
            description="Test JSON serialization",
            monday_item_id=5029098053,
            board_id=2135637353,
            task_db_id=39
        )
        
        # Sérialiser en JSON
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            json_str = task.model_dump_json()
            
            # Vérifier qu'aucun warning n'a été émis
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0, f"Warnings lors de la sérialisation JSON: {pydantic_warnings}"
        
        # Vérifier que le JSON est valide
        parsed = json.loads(json_str)
        assert parsed['task_id'] == "99999", "task_id devrait être une string dans le JSON"
    
    def test_task_status_response_task_id_conversion(self):
        """Vérifie que TaskStatusResponse convertit task_id correctement."""
        status = TaskStatusResponse(
            task_id=7890,  # int
            status=WorkflowStatus.RUNNING,
            progress=50
        )
        
        assert isinstance(status.task_id, str), "task_id devrait être converti en str"
        assert status.task_id == "7890"
        
        # Sérialiser sans warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            serialized = status.model_dump()
            
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0, f"Warnings détectés: {pydantic_warnings}"
    
    def test_workflow_state_model_workflow_id_conversion(self):
        """Vérifie que WorkflowStateModel convertit workflow_id correctement."""
        state = WorkflowStateModel(
            workflow_id=12345  # int
        )
        
        assert isinstance(state.workflow_id, str), "workflow_id devrait être converti en str"
        assert state.workflow_id == "12345"
        
        # Sérialiser sans warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            serialized = state.model_dump()
            
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0, f"Warnings détectés: {pydantic_warnings}"
    
    def test_human_validation_request_all_ids_conversion(self):
        """Vérifie que HumanValidationRequest convertit tous les IDs correctement."""
        validation = HumanValidationRequest(
            validation_id=111,     # int
            workflow_id=222,       # int
            task_id=333,          # int
            task_title="Test",
            generated_code={"test.py": "code"},
            code_summary="Test code changes",
            original_request="Test request",
            test_results={"success": True},
            files_modified=["test.py"]
        )
        
        # Vérifier les conversions
        assert isinstance(validation.validation_id, str), "validation_id devrait être str"
        assert isinstance(validation.workflow_id, str), "workflow_id devrait être str"
        assert isinstance(validation.task_id, str), "task_id devrait être str"
        
        assert validation.validation_id == "111"
        assert validation.workflow_id == "222"
        assert validation.task_id == "333"
        
        # Sérialiser sans warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            serialized = validation.model_dump()
            
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0, f"Warnings détectés: {pydantic_warnings}"
        
        # Vérifier la sérialisation JSON
        json_str = validation.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed['validation_id'] == "111"
        assert parsed['workflow_id'] == "222"
        assert parsed['task_id'] == "333"
    
    def test_human_validation_response_validation_id_conversion(self):
        """Vérifie que HumanValidationResponse convertit validation_id correctement."""
        response = HumanValidationResponse(
            validation_id=555,  # int
            status=HumanValidationStatus.APPROVED,
            comments="Looks good!",
            should_merge=True
        )
        
        assert isinstance(response.validation_id, str), "validation_id devrait être str"
        assert response.validation_id == "555"
        
        # Sérialiser sans warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            serialized = response.model_dump()
            
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0, f"Warnings détectés: {pydantic_warnings}"
    
    def test_human_validation_summary_validation_id_conversion(self):
        """Vérifie que HumanValidationSummary convertit validation_id correctement."""
        summary = HumanValidationSummary(
            validation_id=999,  # int
            task_title="Test Task",
            status=HumanValidationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            files_count=3
        )
        
        assert isinstance(summary.validation_id, str), "validation_id devrait être str"
        assert summary.validation_id == "999"
        
        # Sérialiser sans warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            serialized = summary.model_dump()
            
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0, f"Warnings détectés: {pydantic_warnings}"


class TestEdgeCases:
    """Tests pour les cas limites et edge cases."""
    
    def test_task_request_with_none_values(self):
        """Vérifie que TaskRequest gère correctement les valeurs None."""
        task = TaskRequest(
            task_id="123",
            title="Test",
            description="Test",
            monday_item_id=None,
            board_id=None,
            task_db_id=None
        )
        
        serialized = task.model_dump()
        assert serialized['monday_item_id'] is None
        assert serialized['board_id'] is None
        assert serialized['task_db_id'] is None
    
    def test_mixed_int_and_str_ids(self):
        """Vérifie que les modèles acceptent à la fois int et str pour les IDs."""
        # Test avec str
        task1 = TaskRequest(task_id="abc123", title="Test 1", description="Desc")
        assert task1.task_id == "abc123"
        
        # Test avec int
        task2 = TaskRequest(task_id=456, title="Test 2", description="Desc")
        assert task2.task_id == "456"
        
        # Les deux doivent se sérialiser sans problème
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            task1.model_dump()
            task2.model_dump()
            
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0
    
    def test_datetime_comparison_after_serialization(self):
        """Vérifie que les datetime avec timezone peuvent être comparés après sérialisation."""
        validation1 = HumanValidationRequest(
            validation_id="v1",
            workflow_id="w1",
            task_id="t1",
            task_title="Test",
            generated_code={},
            code_summary="Test 1",
            original_request="Request 1",
            test_results={},
            files_modified=[]
        )
        
        validation2 = HumanValidationRequest(
            validation_id="v2",
            workflow_id="w2",
            task_id="t2",
            task_title="Test 2",
            generated_code={},
            code_summary="Test 2",
            original_request="Request 2",
            test_results={},
            files_modified=[]
        )
        
        # Les deux created_at devraient être comparables (pas d'erreur timezone)
        try:
            # Ceci devrait fonctionner sans lever d'exception
            diff = validation2.created_at - validation1.created_at
            assert diff.total_seconds() >= 0
        except TypeError as e:
            pytest.fail(f"Impossible de comparer les datetime: {e}")


class TestRealWorldScenarios:
    """Tests simulant des scénarios réels d'utilisation."""
    
    def test_full_workflow_state_serialization(self):
        """Teste la sérialisation complète d'un WorkflowStateModel."""
        task = TaskRequest(
            task_id=5029098053,
            title="Ajouter un fichier main",
            description="Test description",
            monday_item_id=5029098053,
            board_id=2135637353,
            task_db_id=39
        )
        
        state = WorkflowStateModel(
            workflow_id=12345,
            status=WorkflowStatus.RUNNING,
            current_node="implement_task",
            completed_nodes=["prepare_environment", "analyze_requirements"],
            task=task,
            results={
                "ai_messages": [],
                "modified_files": ["main.txt"],
                "test_results": []
            }
        )
        
        # Sérialiser sans warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            serialized = state.model_dump()
            json_str = state.model_dump_json()
            
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0, f"Warnings lors de la sérialisation: {pydantic_warnings}"
        
        # Vérifier que tout est bien sérialisé
        assert isinstance(serialized['workflow_id'], str)
        assert isinstance(serialized['task']['task_id'], str)
    
    def test_validation_request_with_complex_data(self):
        """Teste HumanValidationRequest avec des données complexes."""
        validation = HumanValidationRequest(
            validation_id=123456,
            workflow_id=789012,
            task_id=345678,
            task_title="Complex Task",
            generated_code={
                "main.py": "print('hello')",
                "utils.py": "def helper(): pass",
                "tests/test_main.py": "def test(): assert True"
            },
            code_summary="Added main module with utilities and tests",
            original_request="Create a main module with helper functions",
            test_results={
                "success": True,
                "total_tests": 10,
                "passed": 9,
                "failed": 1
            },
            files_modified=["main.py", "utils.py", "tests/test_main.py"],
            pr_info=None,
            quality_report={"score": 85}
        )
        
        # Sérialiser sans warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            json_str = validation.model_dump_json()
            
            pydantic_warnings = [warning for warning in w if "Pydantic" in str(warning.message)]
            assert len(pydantic_warnings) == 0, f"Warnings détectés: {pydantic_warnings}"
        
        # Vérifier que le JSON est valide et complet
        parsed = json.loads(json_str)
        assert parsed['validation_id'] == "123456"
        assert parsed['workflow_id'] == "789012"
        assert parsed['task_id'] == "345678"
        # generated_code est sérialisé en JSON string
        generated_code_dict = json.loads(parsed['generated_code'])
        assert len(generated_code_dict) == 3
        assert len(parsed['files_modified']) == 3


if __name__ == "__main__":
    # Exécuter les tests avec pytest
    pytest.main([__file__, "-v", "--tb=short"])

