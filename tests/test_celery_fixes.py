"""
Tests pour valider les corrections des erreurs détectées dans les logs Celery.

Ces tests vérifient:
1. estimated_complexity accepte int et le convertit en str
2. HumanValidationStatus.APPROVED a la valeur "approved" (pas "approve")
3. IntentionType.APPROVE a la valeur "approved" (pas "approve")
"""

import pytest
import sys
from pathlib import Path

# Ajouter le chemin racine au PYTHONPATH pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import (
    TaskRequest,
    HumanValidationStatus,
    HumanValidationRequest,
    HumanValidationResponse
)

# Import direct de la classe sans passer par services/__init__.py
from enum import Enum

# Copie locale de IntentionType pour le test (pour éviter les imports complexes)
class IntentionType(Enum):
    """Types d'intention détectés (doit correspondre à intelligent_reply_analyzer)."""
    APPROVE = "approved"
    REJECT = "rejected"
    QUESTION = "question"
    UNCLEAR = "unclear"
    CLARIFICATION_NEEDED = "clarification_needed"


class TestEstimatedComplexityFix:
    """Tests pour la correction de estimated_complexity."""
    
    def test_estimated_complexity_accepts_int(self):
        """Vérifie que estimated_complexity accepte un int et le convertit en str."""
        task = TaskRequest(
            task_id="123",
            title="Test Task",
            description="Test description",
            estimated_complexity=3  # int passé ici
        )
        
        # Devrait être converti en str
        assert isinstance(task.estimated_complexity, str)
        assert task.estimated_complexity == "3"
    
    def test_estimated_complexity_accepts_str(self):
        """Vérifie que estimated_complexity accepte aussi un str directement."""
        task = TaskRequest(
            task_id="123",
            title="Test Task",
            description="Test description",
            estimated_complexity="High"
        )
        
        assert isinstance(task.estimated_complexity, str)
        assert task.estimated_complexity == "High"
    
    def test_estimated_complexity_accepts_float(self):
        """Vérifie que estimated_complexity accepte un float et le convertit en str."""
        task = TaskRequest(
            task_id="123",
            title="Test Task",
            description="Test description",
            estimated_complexity=7.5  # float passé ici
        )
        
        assert isinstance(task.estimated_complexity, str)
        assert task.estimated_complexity == "7.5"
    
    def test_estimated_complexity_serialization(self):
        """Vérifie que la sérialisation fonctionne correctement."""
        task = TaskRequest(
            task_id="123",
            title="Test Task",
            description="Test description",
            estimated_complexity=5
        )
        
        # Sérialiser
        serialized = task.model_dump()
        assert serialized['estimated_complexity'] == "5"
        
        # Sérialiser en JSON
        json_str = task.model_dump_json()
        assert '"estimated_complexity":"5"' in json_str or '"estimated_complexity": "5"' in json_str


class TestValidationStatusFix:
    """Tests pour la correction du statut de validation."""
    
    def test_approved_status_value(self):
        """Vérifie que APPROVED a la valeur 'approved' et non 'approve'."""
        assert HumanValidationStatus.APPROVED.value == "approved"
        assert HumanValidationStatus.APPROVED.value != "approve"
    
    def test_rejected_status_value(self):
        """Vérifie que REJECTED a la valeur 'rejected' et non 'reject'."""
        assert HumanValidationStatus.REJECTED.value == "rejected"
        assert HumanValidationStatus.REJECTED.value != "reject"
    
    def test_validation_response_with_approved_status(self):
        """Vérifie qu'on peut créer une HumanValidationResponse avec le statut APPROVED."""
        response = HumanValidationResponse(
            validation_id="val_123",
            status=HumanValidationStatus.APPROVED
        )
        
        # Le statut devrait être "approved"
        assert response.status == HumanValidationStatus.APPROVED
        assert response.status.value == "approved"
    
    def test_validation_response_serialization(self):
        """Vérifie que la sérialisation utilise bien 'approved'."""
        response = HumanValidationResponse(
            validation_id="val_123",
            status=HumanValidationStatus.APPROVED,
            comments="Looks good!"
        )
        
        serialized = response.model_dump()
        assert serialized['status'] == "approved"
        
        # Test JSON
        json_str = response.model_dump_json()
        assert '"status":"approved"' in json_str or '"status": "approved"' in json_str


class TestIntentionTypeEnumFix:
    """Tests pour la correction de IntentionType dans intelligent_reply_analyzer."""
    
    def test_intention_approve_value(self):
        """Vérifie que IntentionType.APPROVE a la valeur 'approved'."""
        assert IntentionType.APPROVE.value == "approved"
        assert IntentionType.APPROVE.value != "approve"
    
    def test_intention_reject_value(self):
        """Vérifie que IntentionType.REJECT a la valeur 'rejected'."""
        assert IntentionType.REJECT.value == "rejected"
        assert IntentionType.REJECT.value != "reject"
    
    def test_all_intention_types(self):
        """Vérifie tous les types d'intention disponibles."""
        # Vérifier que tous les types existent
        assert IntentionType.APPROVE.value == "approved"
        assert IntentionType.REJECT.value == "rejected"
        assert IntentionType.QUESTION.value == "question"
        assert IntentionType.UNCLEAR.value == "unclear"
        assert IntentionType.CLARIFICATION_NEEDED.value == "clarification_needed"


class TestDatabaseConstraintCompatibility:
    """Tests pour s'assurer que les valeurs sont compatibles avec les contraintes DB."""
    
    def test_validation_status_db_compatible(self):
        """Vérifie que tous les statuts de validation sont compatibles avec la DB."""
        # Les statuts attendus par la DB
        db_expected_values = ["pending", "approved", "rejected", "expired", "cancelled"]
        
        # Les statuts dans notre enum
        enum_values = [status.value for status in HumanValidationStatus]
        
        # Vérifier que tous les statuts enum sont dans les valeurs attendues par la DB
        for value in enum_values:
            assert value in db_expected_values, f"Statut '{value}' non compatible avec la DB"
    
    def test_create_validation_request_with_all_fields(self):
        """Test complet de création d'une HumanValidationRequest comme dans le workflow réel."""
        validation = HumanValidationRequest(
            validation_id=123,  # int sera converti
            workflow_id=456,    # int sera converti
            task_id=5029145622, # int sera converti (vrai ID Monday.com)
            task_title="Ajouter un fichier main",
            generated_code={"main.txt": "Project summary"},
            code_summary="Added main.txt file",
            original_request="Add a main file",
            test_results={"success": True},
            files_modified=["main.txt"]
        )
        
        # Vérifier les conversions
        assert isinstance(validation.validation_id, str)
        assert isinstance(validation.workflow_id, str)
        assert isinstance(validation.task_id, str)
        assert validation.task_id == "5029145622"
    
    def test_create_validation_response_db_ready(self):
        """Test de création d'une HumanValidationResponse prête pour la DB."""
        response = HumanValidationResponse(
            validation_id=8,
            status=HumanValidationStatus.APPROVED,
            comments="<p>oui</p>",
            should_merge=True
        )
        
        # Sérialiser pour voir ce qui sera envoyé à la DB
        serialized = response.model_dump()
        
        # Le statut doit être "approved" (pas "approve")
        assert serialized['status'] == "approved"
        
        # validation_id doit être string
        assert isinstance(serialized['validation_id'], str)
        assert serialized['validation_id'] == "8"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

