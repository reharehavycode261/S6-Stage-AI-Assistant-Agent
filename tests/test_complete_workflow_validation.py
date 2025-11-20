"""
Tests d'intégration complets pour valider que toutes les erreurs des logs Celery sont corrigées.

Ces tests simulent le flux exact du workflow de bout en bout pour détecter tous les problèmes.
"""

import pytest
import json
import warnings
from datetime import datetime, timezone
from models.schemas import (
    TaskRequest,
    HumanValidationRequest,
    HumanValidationResponse,
    HumanValidationStatus,
    PullRequestInfo,
    WorkflowStateModel,
    WorkflowStatus
)


class TestCeleryLogErrors:
    """Tests spécifiques pour les erreurs détectées dans les logs Celery."""
    
    def test_error_ligne_119_estimated_complexity_int(self):
        """
        Erreur ligne 119 des logs Celery:
        'estimated_complexity' Input should be a valid string [type=string_type, input_value=3, input_type=int]
        """
        # Simuler l'erreur exacte: estimated_complexity reçoit un int
        task = TaskRequest(
            task_id="40",
            title="Ajouter un fichier main",
            description="Test description",
            estimated_complexity=3  # ⚠️ int comme dans l'erreur
        )
        
        # Vérification: devrait être converti en str sans erreur
        assert isinstance(task.estimated_complexity, str)
        assert task.estimated_complexity == "3"
        
        # Vérifier qu'aucune exception Pydantic n'est levée
        serialized = task.model_dump()
        assert serialized['estimated_complexity'] == "3"
    
    def test_error_ligne_296_approve_status_invalid(self):
        """
        Erreur ligne 296 des logs Celery:
        new row for relation "human_validation_responses" violates check constraint
        "human_validation_responses_status_chk"
        Status was 'approve' but DB expects 'approved'
        """
        # Simuler la création d'une réponse comme dans le log
        response = HumanValidationResponse(
            validation_id="val_5029145622_1759753044",
            status=HumanValidationStatus.APPROVED,  # ⚠️ Doit être 'approved' pas 'approve'
            comments="<p>oui</p>",
            validated_by="Rehareha Ranaivo",
            should_merge=True,
            should_continue_workflow=True
        )
        
        # Vérification: le statut doit être 'approved'
        assert response.status.value == "approved"
        assert response.status.value != "approve"
        
        # Vérifier la sérialisation
        serialized = response.model_dump()
        assert serialized['status'] == "approved"
        
        # Vérifier que c'est compatible avec la contrainte DB
        db_valid_statuses = ['approved', 'rejected', 'expired', 'cancelled']
        assert serialized['status'] in db_valid_statuses


class TestCompleteWorkflowSimulation:
    """Simulation complète du workflow Celery de bout en bout."""
    
    def test_complete_workflow_from_logs(self):
        """
        Simule le flux complet du workflow basé sur les logs Celery (lignes 46-341).
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # ÉTAPE 1: Création de la tâche (ligne 65-70)
            task = TaskRequest(
                task_id=5029145622,  # Monday.com item ID
                title="Ajouter un fichier main",
                description="Ajouter un fichier main.txt qui est le resume du projet",
                monday_item_id=5029145622,
                board_id=2135637353,
                task_db_id=40,
                repository_url="https://github.com/rehareha261/S2-GenericDAO",
                branch_name="feature/ajouter-un-fichier-main-cab96c-1516"
            )
            
            # ÉTAPE 2: Analyse des requirements (ligne 117)
            # L'IA génère une analyse avec estimated_complexity=3 (int)
            task.estimated_complexity = 3  # Simuler l'erreur de la ligne 119
            
            # Vérification: devrait être converti en str
            assert isinstance(task.estimated_complexity, str)
            
            # ÉTAPE 3: Création de l'état du workflow (ligne 77-85)
            workflow_state = WorkflowStateModel(
                workflow_id="celery_7193997a-d10b-4157-aa7d-26ace2fa042b",
                status=WorkflowStatus.RUNNING,
                current_node="implement_task",
                completed_nodes=["prepare_environment", "analyze_requirements"],
                task=task
            )
            
            # ÉTAPE 4: Implémentation terminée avec résultats (ligne 168-169)
            workflow_state.results = {
                "modified_files": ["main.txt"],
                "ai_messages": ["✅ Implémentation terminée avec succès"],
                "test_results": [{"success": True, "tests_passed": 0}]
            }
            
            # ÉTAPE 5: Création PR (ligne 209-211)
            pr_info = PullRequestInfo(
                number=18,
                title="feat: Ajouter un fichier main",
                url="https://github.com/rehareha261/S2-GenericDAO/pull/18",
                branch="feature/ajouter-un-fichier-main-cab96c-1516",
                base_branch="main",
                status="open",
                created_at=datetime.now(timezone.utc)
            )
            
            # ÉTAPE 6: Demande de validation humaine (ligne 218-226)
            validation_request = HumanValidationRequest(
                validation_id="val_5029145622_1759753044",
                workflow_id=workflow_state.workflow_id,
                task_id=task.task_id,
                task_title=task.title,
                generated_code={"main.txt": "# Project Summary\n\nContent here"},
                code_summary="Added main.txt file with project summary",
                original_request=task.description,
                test_results={"success": True, "tests_passed": 0, "tests_failed": 0},
                files_modified=["main.txt"],
                pr_info=pr_info
            )
            
            # ÉTAPE 7: Réception de la réponse humaine "oui" (ligne 287-296)
            validation_response = HumanValidationResponse(
                validation_id=validation_request.validation_id,
                status=HumanValidationStatus.APPROVED,  # ⚠️ Doit être 'approved'
                comments="<p>oui</p>",
                validated_by="Rehareha Ranaivo",
                should_merge=True,
                should_continue_workflow=True
            )
            
            # VÉRIFICATIONS GLOBALES
            
            # Vérifier qu'aucun warning Pydantic n'a été émis
            pydantic_warnings = [
                warning for warning in w 
                if "Pydantic" in str(warning.message) or "serializer" in str(warning.message)
            ]
            assert len(pydantic_warnings) == 0, (
                f"Des warnings Pydantic ont été détectés:\n" +
                "\n".join([f"  - {w.message}" for w in pydantic_warnings])
            )
            
            # Vérifier les conversions de types
            assert isinstance(task.task_id, str)
            assert isinstance(task.estimated_complexity, str)
            assert isinstance(workflow_state.workflow_id, str)
            assert isinstance(validation_request.validation_id, str)
            assert isinstance(validation_request.generated_code, str)  # JSON string
            assert isinstance(validation_request.test_results, str)   # JSON string
            assert isinstance(validation_request.pr_info, str)         # JSON string
            
            # Vérifier le statut de validation
            assert validation_response.status.value == "approved"
            assert validation_response.status.value != "approve"


class TestDatabaseInsertionCompatibility:
    """Tests pour vérifier que toutes les données peuvent être insérées dans la DB."""
    
    def test_human_validation_request_db_ready(self):
        """Vérifie que HumanValidationRequest est prêt pour l'insertion DB."""
        validation = HumanValidationRequest(
            validation_id="val_5029145622_1759753044",
            workflow_id="celery_7193997a-d10b-4157-aa7d-26ace2fa042b",
            task_id=5029145622,
            task_title="Ajouter un fichier main",
            generated_code={"main.txt": "content"},  # Dict sera converti
            code_summary="Added main.txt",
            original_request="Add main file",
            test_results={"success": True},           # Dict sera converti
            files_modified=["main.txt"],
            pr_info={                                  # Dict sera converti
                "number": 18,
                "url": "https://github.com/test/pr/18"
            }
        )
        
        # Vérifier les types pour la DB
        assert isinstance(validation.validation_id, str)
        assert isinstance(validation.workflow_id, str)
        assert isinstance(validation.task_id, str)
        assert isinstance(validation.generated_code, str)
        assert isinstance(validation.test_results, str)
        assert isinstance(validation.pr_info, str)
        assert isinstance(validation.files_modified, list)
        
        # Vérifier que les JSON strings sont valides
        json.loads(validation.generated_code)
        json.loads(validation.test_results)
        json.loads(validation.pr_info)
    
    def test_human_validation_response_db_ready(self):
        """Vérifie que HumanValidationResponse est prêt pour l'insertion DB."""
        response = HumanValidationResponse(
            validation_id=8,  # Int sera converti
            status=HumanValidationStatus.APPROVED,
            comments="<p>oui</p>",
            validated_by="Rehareha Ranaivo",
            should_merge=True,
            should_continue_workflow=True
        )
        
        # Vérifier les types pour la DB
        assert isinstance(response.validation_id, str)
        assert response.status.value == "approved"
        
        # Vérifier la compatibilité avec la contrainte CHECK
        db_valid_statuses = ['approved', 'rejected', 'expired', 'cancelled']
        assert response.status.value in db_valid_statuses
    
    def test_task_request_db_ready(self):
        """Vérifie que TaskRequest est prêt pour l'insertion DB."""
        task = TaskRequest(
            task_id=5029145622,
            title="Test Task",
            description="Test description",
            monday_item_id=5029145622,
            board_id=2135637353,
            task_db_id=40,
            estimated_complexity=3  # Int sera converti
        )
        
        # Vérifier les types pour la DB
        assert isinstance(task.task_id, str)
        assert isinstance(task.estimated_complexity, str)
        assert isinstance(task.monday_item_id, int)
        assert isinstance(task.board_id, int)
        assert isinstance(task.task_db_id, int)


class TestDatetimeTimezoneConsistency:
    """Tests pour vérifier la cohérence des timezone sur tous les datetime."""
    
    def test_all_datetime_fields_have_utc_timezone(self):
        """Vérifie que tous les champs datetime générés ont une timezone UTC."""
        # Créer une PR
        pr = PullRequestInfo(
            number=1,
            title="Test",
            url="https://test.com/pr/1",
            branch="feature/test",
            base_branch="main",
            status="open",
            created_at=datetime.now(timezone.utc)
        )
        
        # Créer une validation request
        validation_req = HumanValidationRequest(
            validation_id="val_1",
            workflow_id="wf_1",
            task_id="task_1",
            task_title="Test",
            generated_code={},
            code_summary="Test",
            original_request="Test",
            test_results={},
            files_modified=[]
        )
        
        # Créer une validation response
        validation_resp = HumanValidationResponse(
            validation_id="val_1",
            status=HumanValidationStatus.APPROVED
        )
        
        # Vérifier que tous les datetime ont UTC
        assert pr.created_at.tzinfo == timezone.utc
        assert validation_req.created_at.tzinfo == timezone.utc
        assert validation_resp.validated_at.tzinfo == timezone.utc
        
        # Vérifier qu'on peut les comparer sans erreur
        try:
            diff = validation_resp.validated_at - validation_req.created_at
            assert diff.total_seconds() >= 0
        except TypeError as e:
            pytest.fail(f"Impossible de comparer les datetime: {e}")


class TestNoRegressions:
    """Tests de non-régression pour s'assurer qu'aucune ancienne erreur ne revient."""
    
    def test_no_approve_status_in_code(self):
        """Vérifie qu'on n'utilise plus 'approve' mais 'approved'."""
        # Tous les statuts doivent être 'approved' ou 'rejected', pas 'approve' ou 'reject'
        assert HumanValidationStatus.APPROVED.value == "approved"
        assert HumanValidationStatus.REJECTED.value == "rejected"
        
        # Vérifier qu'on peut créer une réponse avec APPROVED
        response = HumanValidationResponse(
            validation_id="test",
            status=HumanValidationStatus.APPROVED
        )
        assert response.status.value == "approved"
    
    def test_no_int_for_estimated_complexity(self):
        """Vérifie que estimated_complexity accepte les int et les convertit."""
        task1 = TaskRequest(
            task_id="1",
            title="Test",
            description="Test",
            estimated_complexity=5  # int
        )
        assert isinstance(task1.estimated_complexity, str)
        
        task2 = TaskRequest(
            task_id="2",
            title="Test",
            description="Test",
            estimated_complexity="High"  # str
        )
        assert isinstance(task2.estimated_complexity, str)
    
    def test_no_naive_datetime_errors(self):
        """Vérifie qu'on ne peut plus avoir d'erreur de timezone naive."""
        obj1 = HumanValidationRequest(
            validation_id="1",
            workflow_id="1",
            task_id="1",
            task_title="Test",
            generated_code={},
            code_summary="Test",
            original_request="Test",
            test_results={},
            files_modified=[]
        )
        
        obj2 = HumanValidationRequest(
            validation_id="2",
            workflow_id="2",
            task_id="2",
            task_title="Test 2",
            generated_code={},
            code_summary="Test 2",
            original_request="Test 2",
            test_results={},
            files_modified=[]
        )
        
        # Cette opération devrait fonctionner sans erreur
        try:
            time_diff = obj2.created_at - obj1.created_at
            assert time_diff.total_seconds() >= 0
        except TypeError as e:
            pytest.fail(f"Erreur de timezone détectée: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

