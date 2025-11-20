"""
Tests d'intégration globaux pour valider toutes les corrections.

Ces tests vérifient l'intégration complète des corrections :
- Timezone sur tous les datetime
- Sérialisation Pydantic sans warnings
- Flux complet de création/sérialisation des objets
"""

import pytest
import warnings
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

from models.schemas import (
    TaskRequest,
    HumanValidationRequest,
    HumanValidationResponse,
    HumanValidationStatus,
    ErrorResponse
)


class TestGlobalIntegration:
    """Tests d'intégration globaux."""
    
    def test_complete_validation_flow_no_warnings(self):
        """Teste un flux complet de validation sans warnings Pydantic."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # 1. Créer une TaskRequest
            task = TaskRequest(
                task_id=5029098053,  # int from Monday.com
                title="Test Task",
                description="Full integration test",
                monday_item_id=5029098053,
                task_db_id=39
            )
            
            # 2. Créer une HumanValidationRequest
            validation_req = HumanValidationRequest(
                validation_id=123,
                workflow_id=456,
                task_id=789,
                task_title=task.title,
                generated_code={"main.py": "test"},
                code_summary="Added main.py",
                original_request="Add main file",
                test_results={"success": True},
                files_modified=["main.py"]
            )
            
            # 3. Sérialiser tout
            task_json = task.model_dump_json()
            validation_json = validation_req.model_dump_json()
            
            # 4. Créer une réponse
            validation_resp = HumanValidationResponse(
                validation_id=validation_req.validation_id,
                status=HumanValidationStatus.APPROVED,
                comments="LGTM",
                should_merge=True
            )
            
            response_json = validation_resp.model_dump_json()
            
            # 5. Vérifier qu'aucun warning Pydantic n'a été émis
            pydantic_warnings = [
                warning for warning in w 
                if "Pydantic" in str(warning.message) or "serializer" in str(warning.message)
            ]
            
            assert len(pydantic_warnings) == 0, (
                f"Des warnings Pydantic ont été détectés:\n" +
                "\n".join([f"  - {w.message}" for w in pydantic_warnings])
            )
    
    def test_multiple_serialization_cycles(self):
        """Teste plusieurs cycles de sérialisation/désérialisation."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Créer un objet
            original = TaskRequest(
                task_id=12345,
                title="Test",
                description="Test"
            )
            
            # Cycle 1: Sérialiser -> Désérialiser
            json1 = original.model_dump_json()
            restored1 = TaskRequest.model_validate_json(json1)
            
            # Cycle 2: Re-sérialiser -> Re-désérialiser
            json2 = restored1.model_dump_json()
            restored2 = TaskRequest.model_validate_json(json2)
            
            # Cycle 3: Encore une fois
            json3 = restored2.model_dump_json()
            restored3 = TaskRequest.model_validate_json(json3)
            
            # Vérifier que l'ID reste une string
            assert restored3.task_id == "12345"
            
            # Vérifier qu'aucun warning n'a été émis
            pydantic_warnings = [
                warning for warning in w 
                if "Pydantic" in str(warning.message)
            ]
            assert len(pydantic_warnings) == 0
    
    def test_datetime_timezone_consistency(self):
        """Vérifie la cohérence des timezone sur tous les objets."""
        # Créer plusieurs objets avec des datetime
        error = ErrorResponse(error="test")
        validation_req = HumanValidationRequest(
            validation_id="v1",
            workflow_id="w1",
            task_id="t1",
            task_title="Test",
            generated_code={},
            code_summary="Test summary",
            original_request="Test request",
            test_results={},
            files_modified=[]
        )
        validation_resp = HumanValidationResponse(
            validation_id="v1",
            status=HumanValidationStatus.APPROVED
        )
        
        # Vérifier que tous les datetime ont UTC
        datetimes = [
            ("ErrorResponse.timestamp", error.timestamp),
            ("HumanValidationRequest.created_at", validation_req.created_at),
            ("HumanValidationResponse.validated_at", validation_resp.validated_at)
        ]
        
        for name, dt in datetimes:
            assert dt.tzinfo is not None, f"{name} devrait avoir une timezone"
            assert dt.tzinfo == timezone.utc, f"{name} devrait être en UTC"
        
        # Vérifier qu'on peut les comparer sans erreur
        try:
            diff1 = validation_req.created_at - error.timestamp
            diff2 = validation_resp.validated_at - validation_req.created_at
            # Si on arrive ici, c'est bon
            assert True
        except TypeError as e:
            pytest.fail(f"Impossible de comparer les datetime: {e}")
    
    def test_files_modified_list_validation(self):
        """Vérifie que files_modified accepte différents formats."""
        # Test avec liste
        validation1 = HumanValidationRequest(
            validation_id="1",
            workflow_id="1",
            task_id="1",
            task_title="Test",
            generated_code={},
            code_summary="Summary",
            original_request="Request",
            test_results={},
            files_modified=["file1.py", "file2.py"]
        )
        assert len(validation1.files_modified) == 2
        
        # Test avec dict (sera converti en liste de clés)
        validation2 = HumanValidationRequest(
            validation_id="2",
            workflow_id="2",
            task_id="2",
            task_title="Test 2",
            generated_code={},
            code_summary="Summary 2",
            original_request="Request 2",
            test_results={},
            files_modified={"file1.py": "content1", "file2.py": "content2"}
        )
        assert len(validation2.files_modified) == 2
    
    def test_error_scenarios_no_warnings(self):
        """Teste que même les scénarios d'erreur ne génèrent pas de warnings."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Créer des objets avec des valeurs limites (None pour les champs optionnels)
            task_with_optional_none = TaskRequest(
                task_id="test_id",  # task_id est requis, on doit donner une valeur
                title="Test",
                description="Test",
                monday_item_id=None,  # Optionnel
                board_id=None,  # Optionnel
                task_db_id=None  # Optionnel
            )
            
            # Sérialiser
            task_with_optional_none.model_dump_json()
            
            # Créer une erreur
            error = ErrorResponse(
                error="Critical error",
                details="Something went wrong"
            )
            error.model_dump_json()
            
            # Vérifier qu'aucun warning n'a été émis
            pydantic_warnings = [
                warning for warning in w 
                if "Pydantic" in str(warning.message)
            ]
            assert len(pydantic_warnings) == 0


class TestPerformance:
    """Tests de performance pour vérifier que les corrections n'impactent pas les performances."""
    
    def test_serialization_performance(self):
        """Vérifie que la sérialisation reste performante."""
        import time
        
        # Créer 100 objets
        tasks = [
            TaskRequest(
                task_id=i,
                title=f"Task {i}",
                description=f"Description {i}",
                monday_item_id=i,
                task_db_id=i
            )
            for i in range(100)
        ]
        
        # Mesurer le temps de sérialisation
        start = time.time()
        for task in tasks:
            task.model_dump_json()
        end = time.time()
        
        duration = end - start
        
        # La sérialisation de 100 objets devrait prendre moins d'1 seconde
        assert duration < 1.0, f"Sérialisation trop lente: {duration:.2f}s pour 100 objets"
    
    def test_validation_performance(self):
        """Vérifie que la validation reste performante."""
        import time
        
        # Créer 100 validations
        start = time.time()
        for i in range(100):
            HumanValidationRequest(
                validation_id=i,
                workflow_id=i,
                task_id=i,
                task_title=f"Task {i}",
                generated_code={"file.py": "code"},
                code_summary=f"Summary {i}",
                original_request=f"Request {i}",
                test_results={"success": True},
                files_modified=["file.py"]
            )
        end = time.time()
        
        duration = end - start
        
        # La création de 100 objets devrait prendre moins de 0.5 seconde
        assert duration < 0.5, f"Création trop lente: {duration:.2f}s pour 100 objets"


class TestRegressionPrevention:
    """Tests spécifiques pour empêcher la régression des bugs corrigés."""
    
    def test_no_naive_datetime_error(self):
        """Vérifie qu'on ne peut plus avoir l'erreur 'can't subtract offset-naive and offset-aware datetimes'."""
        # Créer deux objets avec des datetime
        obj1 = HumanValidationRequest(
            validation_id="1",
            workflow_id="1",
            task_id="1",
            task_title="Test",
            generated_code={},
            code_summary="Summary 1",
            original_request="Request 1",
            test_results={},
            files_modified=[]
        )
        
        obj2 = HumanValidationRequest(
            validation_id="2",
            workflow_id="2",
            task_id="2",
            task_title="Test 2",
            generated_code={},
            code_summary="Summary 2",
            original_request="Request 2",
            test_results={},
            files_modified=[]
        )
        
        # Cette opération devrait fonctionner sans erreur
        try:
            time_diff = obj2.created_at - obj1.created_at
            assert time_diff.total_seconds() >= 0
        except TypeError as e:
            pytest.fail(f"Erreur de timezone détectée (bug non corrigé): {e}")
    
    def test_no_pydantic_serialization_warning(self):
        """Vérifie qu'on ne génère plus le warning 'Expected str but got int'."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Créer un objet avec des int pour les IDs
            task = TaskRequest(
                task_id=5029098053,  # Le vrai cas d'usage de Monday.com
                title="Test",
                description="Test",
                monday_item_id=5029098053,
                board_id=2135637353,
                task_db_id=39
            )
            
            # Sérialiser (c'est ici que le warning apparaissait)
            task.model_dump()
            task.model_dump_json()
            
            # Chercher spécifiquement le warning qu'on avait
            warning_texts = [str(warning.message) for warning in w]
            problematic_warnings = [
                text for text in warning_texts
                if "Expected `str` but got `int`" in text
            ]
            
            assert len(problematic_warnings) == 0, (
                f"Le warning 'Expected str but got int' est réapparu:\n" +
                "\n".join(problematic_warnings)
            )
    
    def test_all_datetime_fields_have_timezone(self):
        """Vérifie que TOUS les champs datetime générés ont une timezone."""
        objects_to_test = [
            ("ErrorResponse", ErrorResponse(error="test")),
            ("HumanValidationRequest", HumanValidationRequest(
                validation_id="1", workflow_id="1", task_id="1",
                task_title="Test", generated_code={}, code_summary="Summary",
                original_request="Request", test_results={}, files_modified=[]
            )),
            ("HumanValidationResponse", HumanValidationResponse(
                validation_id="1", status=HumanValidationStatus.APPROVED
            ))
        ]
        
        for obj_name, obj in objects_to_test:
            # Récupérer tous les champs datetime
            for field_name, field_value in obj.__dict__.items():
                if isinstance(field_value, datetime):
                    assert field_value.tzinfo is not None, (
                        f"{obj_name}.{field_name} n'a pas de timezone"
                    )
                    assert field_value.tzinfo == timezone.utc, (
                        f"{obj_name}.{field_name} n'est pas en UTC"
                    )


if __name__ == "__main__":
    # Exécuter les tests avec pytest
    pytest.main([__file__, "-v", "--tb=short", "-s"])

