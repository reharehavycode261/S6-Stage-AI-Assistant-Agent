"""Tests unitaires simples pour la validation de files_modified."""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from models.schemas import HumanValidationRequest


def test_pydantic_validator_with_list():
    """Test: files_modified avec une liste est accepté tel quel."""
    print("\n✅ Test 1: Liste de fichiers")
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
    
    assert isinstance(validation.files_modified, list), f"Type incorrect: {type(validation.files_modified)}"
    assert len(validation.files_modified) == 2, f"Longueur incorrecte: {len(validation.files_modified)}"
    assert validation.files_modified == ["file1.py", "file2.py"]
    print(f"   ✓ Liste acceptée: {validation.files_modified}")


def test_pydantic_validator_with_dict():
    """Test: files_modified avec un dict est converti en liste de clés."""
    print("\n✅ Test 2: Dict converti en liste")
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
    assert isinstance(validation.files_modified, list), f"Type incorrect: {type(validation.files_modified)}"
    assert len(validation.files_modified) == 2, f"Longueur incorrecte: {len(validation.files_modified)}"
    assert set(validation.files_modified) == {"file1.py", "file2.py"}
    print(f"   ✓ Dict converti en liste: {validation.files_modified}")


def test_pydantic_validator_with_string():
    """Test: files_modified avec un string est converti en liste."""
    print("\n✅ Test 3: String converti en liste")
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
    
    assert isinstance(validation.files_modified, list), f"Type incorrect: {type(validation.files_modified)}"
    assert len(validation.files_modified) == 1, f"Longueur incorrecte: {len(validation.files_modified)}"
    assert validation.files_modified == ["single_file.py"]
    print(f"   ✓ String converti en liste: {validation.files_modified}")


def test_pydantic_validator_with_none():
    """Test: files_modified avec None retourne liste vide."""
    print("\n✅ Test 4: None converti en liste vide")
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
    
    assert isinstance(validation.files_modified, list), f"Type incorrect: {type(validation.files_modified)}"
    assert len(validation.files_modified) == 0, f"Longueur incorrecte: {len(validation.files_modified)}"
    assert validation.files_modified == []
    print(f"   ✓ None converti en liste vide: {validation.files_modified}")


def test_pydantic_validator_with_empty_list():
    """Test: files_modified avec liste vide."""
    print("\n✅ Test 5: Liste vide")
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
    print(f"   ✓ Liste vide acceptée: {validation.files_modified}")


def test_pydantic_validator_filters_empty_strings():
    """Test: files_modified filtre les strings vides."""
    print("\n✅ Test 6: Filtrage des éléments vides")
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
    assert len(validation.files_modified) == 2, f"Longueur incorrecte: {len(validation.files_modified)}"
    assert validation.files_modified == ["file1.py", "file2.py"]
    print(f"   ✓ Éléments vides filtrés: {validation.files_modified}")


def test_workflow_integration_dict():
    """Test: Simulation du cas réel où modified_files vient de code_changes (dict)."""
    print("\n✅ Test 7: Intégration workflow avec dict")
    
    # Simuler workflow_results avec modified_files comme dict (cas réel de l'erreur)
    workflow_results = {
        "modified_files": {
            "main.txt": "# Résumé du Projet...",
            "README.md": "# Documentation..."
        }
    }
    
    # Extraire et normaliser comme dans monday_validation_node.py
    modified_files_raw = workflow_results.get("modified_files", [])
    
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
    print(f"   ✓ Workflow dict→list: {validation.files_modified}")


def test_workflow_integration_list():
    """Test: Simulation du cas où modified_files vient de git status (list)."""
    print("\n✅ Test 8: Intégration workflow avec list")
    
    workflow_results = {
        "modified_files": ["src/main.py", "tests/test_main.py"]
    }
    
    modified_files_raw = workflow_results.get("modified_files", [])
    
    if isinstance(modified_files_raw, dict):
        modified_files = list(modified_files_raw.keys())
    elif isinstance(modified_files_raw, list):
        modified_files = modified_files_raw
    else:
        modified_files = []
    
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
    
    assert isinstance(validation.files_modified, list)
    assert validation.files_modified == ["src/main.py", "tests/test_main.py"]
    print(f"   ✓ Workflow list→list: {validation.files_modified}")


def test_database_array_compatibility():
    """Test: files_modified est compatible avec TEXT[] PostgreSQL."""
    print("\n✅ Test 9: Compatibilité PostgreSQL TEXT[]")
    
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
    
    # Simuler la conversion PostgreSQL
    pg_array = validation.files_modified
    assert pg_array == ["file1.py", "file2.py", "file3.py"]
    print(f"   ✓ Compatible PostgreSQL: {pg_array}")


def run_all_tests():
    """Exécuter tous les tests."""
    print("\n" + "="*70)
    print("  TESTS DE VALIDATION DE files_modified")
    print("="*70)
    
    tests = [
        test_pydantic_validator_with_list,
        test_pydantic_validator_with_dict,
        test_pydantic_validator_with_string,
        test_pydantic_validator_with_none,
        test_pydantic_validator_with_empty_list,
        test_pydantic_validator_filters_empty_strings,
        test_workflow_integration_dict,
        test_workflow_integration_list,
        test_database_array_compatibility,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ ÉCHEC: {test_func.__name__}")
            print(f"   Erreur: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERREUR: {test_func.__name__}")
            print(f"   Exception: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"  RÉSULTATS: {passed} réussis, {failed} échoués sur {len(tests)} tests")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

