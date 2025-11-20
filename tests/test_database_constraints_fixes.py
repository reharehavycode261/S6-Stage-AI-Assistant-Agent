"""
Tests pour vérifier que les données peuvent être insérées dans la DB sans violation de contraintes.

Ces tests simulent les données réelles du workflow Celery pour détecter les problèmes avant l'insertion.
"""

import pytest
from datetime import datetime, timezone
from models.schemas import (
    HumanValidationRequest,
    HumanValidationResponse,
    HumanValidationStatus,
    TaskRequest
)


class TestHumanValidationResponseDBConstraints:
    """Tests pour vérifier les contraintes de human_validation_responses."""
    
    def test_response_status_approved_is_valid(self):
        """Vérifie que le statut 'approved' est valide pour la DB."""
        # Créer une réponse comme dans le workflow réel
        response = HumanValidationResponse(
            validation_id=8,
            status=HumanValidationStatus.APPROVED,
            comments="<p>oui</p>",
            validated_by="Rehareha Ranaivo",
            should_merge=True,
            should_continue_workflow=True
        )
        
        # Vérifier que le statut est "approved" (pas "approve")
        assert response.status.value == "approved"
        
        # Sérialiser pour voir ce qui sera envoyé à la DB
        serialized = response.model_dump()
        
        # Le statut doit être "approved"
        assert serialized['status'] == "approved"
        
        # Vérifier que c'est dans les valeurs acceptées par la contrainte CHECK
        db_valid_statuses = ['approved', 'rejected', 'expired', 'cancelled']
        assert serialized['status'] in db_valid_statuses
    
    def test_response_status_rejected_is_valid(self):
        """Vérifie que le statut 'rejected' est valide pour la DB."""
        response = HumanValidationResponse(
            validation_id=9,
            status=HumanValidationStatus.REJECTED,
            comments="Needs changes",
            validated_by="User",
            should_merge=False
        )
        
        serialized = response.model_dump()
        assert serialized['status'] == "rejected"
        
        db_valid_statuses = ['approved', 'rejected', 'expired', 'cancelled']
        assert serialized['status'] in db_valid_statuses
    
    def test_all_validation_statuses_are_db_compatible(self):
        """Vérifie que TOUS les statuts HumanValidationStatus sont compatibles avec la DB."""
        # Les statuts acceptés par la contrainte CHECK de la DB pour human_validation_responses
        # Note: 'pending' est valide pour human_validations.status mais PAS pour human_validation_responses.response_status
        db_valid_response_statuses = ['approved', 'rejected', 'expired', 'cancelled']
        
        # Les statuts acceptés pour human_validations.status
        db_valid_request_statuses = ['pending', 'approved', 'rejected', 'expired', 'cancelled']
        
        # Vérifier que chaque statut de réponse (sauf PENDING) est compatible avec human_validation_responses
        for status in HumanValidationStatus:
            if status != HumanValidationStatus.PENDING:
                assert status.value in db_valid_response_statuses, (
                    f"Statut '{status.value}' n'est pas compatible avec human_validation_responses. "
                    f"Valeurs acceptées: {db_valid_response_statuses}"
                )
            
            # Tous les statuts doivent être compatibles avec human_validations
            assert status.value in db_valid_request_statuses, (
                f"Statut '{status.value}' n'est pas compatible avec human_validations. "
                f"Valeurs acceptées: {db_valid_request_statuses}"
            )


class TestHumanValidationRequestDBConstraints:
    """Tests pour vérifier les contraintes de human_validations."""
    
    def test_validation_request_with_real_workflow_data(self):
        """Test avec des données réelles comme dans le log Celery."""
        # Données similaires à celles du log Celery (ligne 219-221)
        validation_req = HumanValidationRequest(
            validation_id="val_5029145622_1759753044",
            workflow_id="celery_7193997a-d10b-4157-aa7d-26ace2fa042b",
            task_id=5029145622,  # Monday.com item ID
            task_title="Ajouter un fichier main",
            generated_code={"main.txt": "# Project Summary\n\nThis is the main file."},
            code_summary="Added main.txt file with project summary",
            original_request="Ajouter un fichier main.txt qui est le resume du projet",
            test_results={"success": True, "tests_passed": 0, "tests_failed": 0},
            files_modified=["main.txt"],
            pr_info={
                "number": 18,
                "url": "https://github.com/rehareha261/S2-GenericDAO/pull/18",
                "title": "feat: Ajouter un fichier main",
                "status": "open"
            }
        )
        
        # Vérifier que les conversions sont correctes
        assert isinstance(validation_req.validation_id, str)
        assert isinstance(validation_req.workflow_id, str)
        assert isinstance(validation_req.task_id, str)
        assert validation_req.task_id == "5029145622"
        
        # Vérifier que generated_code est une string JSON
        assert isinstance(validation_req.generated_code, str)
        
        # Vérifier que test_results est une string JSON
        assert isinstance(validation_req.test_results, str)
        
        # Vérifier que pr_info est une string JSON
        assert isinstance(validation_req.pr_info, str)
        
        # Vérifier que files_modified est une liste
        assert isinstance(validation_req.files_modified, list)
        assert all(isinstance(f, str) for f in validation_req.files_modified)
    
    def test_validation_status_pending_is_valid(self):
        """Vérifie que le statut 'pending' est valide pour human_validations."""
        # La contrainte pour human_validations est:
        # status IN ('pending', 'approved', 'rejected', 'expired', 'cancelled')
        db_valid_statuses = ['pending', 'approved', 'rejected', 'expired', 'cancelled']
        
        assert HumanValidationStatus.PENDING.value in db_valid_statuses
        assert HumanValidationStatus.APPROVED.value in db_valid_statuses
        assert HumanValidationStatus.REJECTED.value in db_valid_statuses
        assert HumanValidationStatus.EXPIRED.value in db_valid_statuses
        assert HumanValidationStatus.CANCELLED.value in db_valid_statuses


class TestTaskRequestDBConstraints:
    """Tests pour vérifier les contraintes de tasks."""
    
    def test_estimated_complexity_with_int_value(self):
        """Test avec estimated_complexity comme int (erreur du log ligne 119)."""
        task = TaskRequest(
            task_id="123",
            title="Test Task",
            description="Test",
            estimated_complexity=3  # int comme dans le log
        )
        
        # Devrait être converti en string
        assert isinstance(task.estimated_complexity, str)
        assert task.estimated_complexity == "3"
    
    def test_task_id_conversion_from_monday_id(self):
        """Test avec un vrai Monday.com item ID."""
        task = TaskRequest(
            task_id=5029145622,  # Monday.com ID comme dans les logs
            title="Ajouter un fichier main",
            description="Test",
            monday_item_id=5029145622,
            board_id=2135637353,
            task_db_id=40
        )
        
        # task_id devrait être converti en string
        assert isinstance(task.task_id, str)
        assert task.task_id == "5029145622"
        
        # monday_item_id reste int
        assert isinstance(task.monday_item_id, int)
        assert task.monday_item_id == 5029145622


class TestJSONFieldsSerialization:
    """Tests pour vérifier que les champs JSON sont correctement sérialisés."""
    
    def test_generated_code_dict_to_json_string(self):
        """Vérifie que generated_code dict est converti en JSON string."""
        validation = HumanValidationRequest(
            validation_id="val_123",
            workflow_id="wf_456",
            task_id="task_789",
            task_title="Test",
            generated_code={"file1.py": "code1", "file2.py": "code2"},  # dict
            code_summary="Summary",
            original_request="Request",
            test_results={},
            files_modified=[]
        )
        
        # Devrait être une string JSON
        assert isinstance(validation.generated_code, str)
        
        # Devrait pouvoir être parsé comme JSON
        import json
        parsed = json.loads(validation.generated_code)
        assert isinstance(parsed, dict)
        assert "file1.py" in parsed
    
    def test_test_results_dict_to_json_string(self):
        """Vérifie que test_results dict est converti en JSON string."""
        validation = HumanValidationRequest(
            validation_id="val_123",
            workflow_id="wf_456",
            task_id="task_789",
            task_title="Test",
            generated_code={},
            code_summary="Summary",
            original_request="Request",
            test_results={"success": True, "total": 10, "passed": 8},  # dict
            files_modified=[]
        )
        
        # Devrait être une string JSON
        assert isinstance(validation.test_results, str)
        
        # Devrait pouvoir être parsé comme JSON
        import json
        parsed = json.loads(validation.test_results)
        assert isinstance(parsed, dict)
        assert parsed["success"] == True
    
    def test_pr_info_object_to_json_string(self):
        """Vérifie que pr_info object est converti en JSON string."""
        from models.schemas import PullRequestInfo
        
        pr = PullRequestInfo(
            number=18,
            title="Test PR",
            url="https://github.com/test/repo/pull/18",
            branch="feature/test",
            base_branch="main",
            status="open",
            created_at=datetime.now(timezone.utc)
        )
        
        validation = HumanValidationRequest(
            validation_id="val_123",
            workflow_id="wf_456",
            task_id="task_789",
            task_title="Test",
            generated_code={},
            code_summary="Summary",
            original_request="Request",
            test_results={},
            files_modified=[],
            pr_info=pr  # object PullRequestInfo
        )
        
        # Devrait être une string JSON
        assert isinstance(validation.pr_info, str)
        
        # Devrait pouvoir être parsé comme JSON
        import json
        parsed = json.loads(validation.pr_info)
        assert isinstance(parsed, dict)
        assert parsed["number"] == 18


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

