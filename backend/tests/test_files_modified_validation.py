"""Tests unitaires pour la validation de files_modified dans le workflow."""

import pytest
from datetime import datetime
from models.schemas import HumanValidationRequest, PullRequestInfo
from services.human_validation_service import HumanValidationService


class TestFilesModifiedNormalization:
    """Tests pour la normalisation de files_modified."""
    
    def test_pydantic_validator_with_list(self):
        """Test: files_modified avec une liste est accepté tel quel."""
        validation = HumanValidationRequest(
            validation_id="test_001",
            workflow_id="wf_001",
            task_id="123",
            task_title="Test Task",
            generated_code={"file1.py": "content"},
            code_summary="Test summary",
            files_modified=["file1.py", "file2.py"],  # ✅ Liste
            original_request="Test request"
        )
        
        assert isinstance(validation.files_modified, list)
        assert len(validation.files_modified) == 2
        assert validation.files_modified == ["file1.py", "file2.py"]
    
    def test_pydantic_validator_with_dict(self):
        """Test: files_modified avec un dict est converti en liste de clés."""
        validation = HumanValidationRequest(
            validation_id="test_002",
            workflow_id="wf_002",
            task_id="124",
            task_title="Test Task 2",
            generated_code={"file1.py": "content"},
            code_summary="Test summary",
            files_modified={"file1.py": "content", "file2.py": "content2"},  # ❌ Dict
            original_request="Test request"
        )
        
        # Le validator Pydantic doit convertir en liste
        assert isinstance(validation.files_modified, list)
        assert len(validation.files_modified) == 2
        assert set(validation.files_modified) == {"file1.py", "file2.py"}
    
    def test_pydantic_validator_with_string(self):
        """Test: files_modified avec un string est converti en liste."""
        validation = HumanValidationRequest(
            validation_id="test_003",
            workflow_id="wf_003",
            task_id="125",
            task_title="Test Task 3",
            generated_code={"file1.py": "content"},
            code_summary="Test summary",
            files_modified="single_file.py",  # ❌ String
            original_request="Test request"
        )
        
        assert isinstance(validation.files_modified, list)
        assert len(validation.files_modified) == 1
        assert validation.files_modified == ["single_file.py"]
    
    def test_pydantic_validator_with_none(self):
        """Test: files_modified avec None retourne liste vide."""
        validation = HumanValidationRequest(
            validation_id="test_004",
            workflow_id="wf_004",
            task_id="126",
            task_title="Test Task 4",
            generated_code={"file1.py": "content"},
            code_summary="Test summary",
            files_modified=None,  # ❌ None
            original_request="Test request"
        )
        
        assert isinstance(validation.files_modified, list)
        assert len(validation.files_modified) == 0
        assert validation.files_modified == []
    
    def test_pydantic_validator_with_empty_list(self):
        """Test: files_modified avec liste vide."""
        validation = HumanValidationRequest(
            validation_id="test_005",
            workflow_id="wf_005",
            task_id="127",
            task_title="Test Task 5",
            generated_code={"file1.py": "content"},
            code_summary="Test summary",
            files_modified=[],  # ✅ Liste vide
            original_request="Test request"
        )
        
        assert isinstance(validation.files_modified, list)
        assert len(validation.files_modified) == 0
    
    def test_pydantic_validator_filters_empty_strings(self):
        """Test: files_modified filtre les strings vides."""
        validation = HumanValidationRequest(
            validation_id="test_006",
            workflow_id="wf_006",
            task_id="128",
            task_title="Test Task 6",
            generated_code={"file1.py": "content"},
            code_summary="Test summary",
            files_modified=["file1.py", "", None, "file2.py"],  # Avec éléments vides
            original_request="Test request"
        )
        
        # Le validator doit filtrer les éléments vides
        assert isinstance(validation.files_modified, list)
        assert len(validation.files_modified) == 2
        assert validation.files_modified == ["file1.py", "file2.py"]


class TestHumanValidationServiceValidator:
    """Tests pour la méthode _validate_files_modified du service."""
    
    def setup_method(self):
        """Initialiser le service avant chaque test."""
        self.service = HumanValidationService()
    
    def test_service_validator_with_list(self):
        """Test: validation service avec liste."""
        result = self.service._validate_files_modified(["file1.py", "file2.py"])
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert result == ["file1.py", "file2.py"]
    
    def test_service_validator_with_dict(self):
        """Test: validation service avec dict."""
        result = self.service._validate_files_modified({
            "file1.py": "content1",
            "file2.py": "content2"
        })
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert set(result) == {"file1.py", "file2.py"}
    
    def test_service_validator_with_string(self):
        """Test: validation service avec string."""
        result = self.service._validate_files_modified("single_file.py")
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result == ["single_file.py"]
    
    def test_service_validator_with_none(self):
        """Test: validation service avec None."""
        result = self.service._validate_files_modified(None)
        
        assert isinstance(result, list)
        assert len(result) == 0
        assert result == []
    
    def test_service_validator_with_integer(self):
        """Test: validation service avec type inattendu (int)."""
        result = self.service._validate_files_modified(123)
        
        # Type inattendu doit retourner liste vide
        assert isinstance(result, list)
        assert len(result) == 0


class TestWorkflowIntegration:
    """Tests d'intégration pour le workflow complet."""
    
    def test_dict_from_workflow_results(self):
        """Test: Simulation du cas réel où modified_files vient de code_changes (dict)."""
        # Simuler workflow_results avec modified_files comme dict
        workflow_results = {
            "modified_files": {
                "main.txt": "# Résumé du Projet...",
                "README.md": "# Documentation..."
            },
            "ai_messages": ["Message 1", "Message 2"],
            "test_results": {"success": True}
        }
        
        # Extraire modified_files_raw
        modified_files_raw = workflow_results.get("modified_files", [])
        
        # Normaliser comme dans monday_validation_node.py
        if isinstance(modified_files_raw, dict):
            modified_files = list(modified_files_raw.keys())
        elif isinstance(modified_files_raw, list):
            modified_files = modified_files_raw
        else:
            modified_files = []
        
        # Créer la validation request
        validation = HumanValidationRequest(
            validation_id="test_integration_001",
            workflow_id="wf_integration_001",
            task_id="5028415189",
            task_title="Ajouter un fichier main",
            generated_code=modified_files_raw if isinstance(modified_files_raw, dict) else {},
            code_summary="Implémentation test",
            files_modified=modified_files,  # ✅ Liste après normalisation
            original_request="Test request"
        )
        
        # Vérifications
        assert isinstance(validation.files_modified, list)
        assert len(validation.files_modified) == 2
        assert set(validation.files_modified) == {"main.txt", "README.md"}
    
    def test_list_from_git_status(self):
        """Test: Simulation du cas où modified_files vient de git status (list)."""
        # Simuler modified_files depuis git status
        workflow_results = {
            "modified_files": ["src/main.py", "tests/test_main.py"],
            "ai_messages": [],
            "test_results": {}
        }
        
        modified_files_raw = workflow_results.get("modified_files", [])
        
        # Normaliser
        if isinstance(modified_files_raw, dict):
            modified_files = list(modified_files_raw.keys())
        elif isinstance(modified_files_raw, list):
            modified_files = modified_files_raw
        else:
            modified_files = []
        
        # Créer validation
        validation = HumanValidationRequest(
            validation_id="test_integration_002",
            workflow_id="wf_integration_002",
            task_id="123",
            task_title="Test Git Status",
            generated_code={},
            code_summary="Test",
            files_modified=modified_files,
            original_request="Test"
        )
        
        # Vérifications
        assert isinstance(validation.files_modified, list)
        assert validation.files_modified == ["src/main.py", "tests/test_main.py"]


class TestDatabaseCompatibility:
    """Tests pour vérifier la compatibilité avec la base de données."""
    
    def test_files_modified_is_postgres_array_compatible(self):
        """Test: files_modified est compatible avec le type TEXT[] de PostgreSQL."""
        validation = HumanValidationRequest(
            validation_id="test_db_001",
            workflow_id="wf_db_001",
            task_id="123",
            task_title="Test DB",
            generated_code={"file1.py": "content"},
            code_summary="Test",
            files_modified=["file1.py", "file2.py", "file3.py"],
            original_request="Test"
        )
        
        # Vérifier que c'est une liste de strings (compatible TEXT[])
        assert isinstance(validation.files_modified, list)
        assert all(isinstance(f, str) for f in validation.files_modified)
        
        # Simuler la conversion PostgreSQL (asyncpg le fait automatiquement)
        # Une liste de strings Python est directement compatible avec TEXT[]
        pg_array = validation.files_modified
        assert pg_array == ["file1.py", "file2.py", "file3.py"]
    
    def test_empty_files_modified_is_compatible(self):
        """Test: Liste vide est compatible avec TEXT[]."""
        validation = HumanValidationRequest(
            validation_id="test_db_002",
            workflow_id="wf_db_002",
            task_id="124",
            task_title="Test DB Empty",
            generated_code={},
            code_summary="Test",
            files_modified=[],
            original_request="Test"
        )
        
        # Liste vide doit être compatible
        assert isinstance(validation.files_modified, list)
        assert len(validation.files_modified) == 0
        assert validation.files_modified == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

