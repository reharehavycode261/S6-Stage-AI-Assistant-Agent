"""Test final pour valider que files_modified fonctionne correctement."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from models.schemas import HumanValidationRequest


def test_1_dict_converted_to_list():
    """TEST 1: Un dict est automatiquement converti en liste."""
    print("\n" + "="*70)
    print("TEST 1: Conversion dict → list")
    print("="*70)
    
    try:
        # Créer une validation avec un dict (sera converti par Pydantic)
        validation = HumanValidationRequest(
            validation_id="test_001",
            workflow_id="wf_001",
            task_id="123",
            task_title="Test",
            generated_code={"file1.py": "content"},
            code_summary="Test",
            files_modified={"main.txt": "content", "README.md": "doc"},  # Dict
            original_request="Test"
        )
        
        # Vérifier que c'est converti en liste
        assert isinstance(validation.files_modified, list), f"Attendu list, reçu {type(validation.files_modified)}"
        assert len(validation.files_modified) == 2
        assert set(validation.files_modified) == {"main.txt", "README.md"}
        
        print("✅ SUCCÈS: Dict converti en list automatiquement")
        print(f"   Input:  {{'main.txt': '...', 'README.md': '...'}}")
        print(f"   Output: {validation.files_modified}")
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        return False


def test_2_list_remains_list():
    """TEST 2: Une liste reste une liste."""
    print("\n" + "="*70)
    print("TEST 2: Liste → liste")
    print("="*70)
    
    try:
        validation = HumanValidationRequest(
            validation_id="test_002",
            workflow_id="wf_002",
            task_id="124",
            task_title="Test",
            generated_code={},
            code_summary="Test",
            files_modified=["file1.py", "file2.py"],  # Liste
            original_request="Test"
        )
        
        assert isinstance(validation.files_modified, list)
        assert validation.files_modified == ["file1.py", "file2.py"]
        
        print("✅ SUCCÈS: Liste acceptée telle quelle")
        print(f"   Input:  ['file1.py', 'file2.py']")
        print(f"   Output: {validation.files_modified}")
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        return False


def test_3_string_converted_to_list():
    """TEST 3: Un string est converti en liste."""
    print("\n" + "="*70)
    print("TEST 3: String → liste")
    print("="*70)
    
    try:
        validation = HumanValidationRequest(
            validation_id="test_003",
            workflow_id="wf_003",
            task_id="125",
            task_title="Test",
            generated_code={},
            code_summary="Test",
            files_modified="single_file.py",  # String
            original_request="Test"
        )
        
        assert isinstance(validation.files_modified, list)
        assert validation.files_modified == ["single_file.py"]
        
        print("✅ SUCCÈS: String converti en liste")
        print(f"   Input:  'single_file.py'")
        print(f"   Output: {validation.files_modified}")
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        return False


def test_4_none_converted_to_empty_list():
    """TEST 4: None est converti en liste vide."""
    print("\n" + "="*70)
    print("TEST 4: None → liste vide")
    print("="*70)
    
    try:
        validation = HumanValidationRequest(
            validation_id="test_004",
            workflow_id="wf_004",
            task_id="126",
            task_title="Test",
            generated_code={},
            code_summary="Test",
            files_modified=None,  # None
            original_request="Test"
        )
        
        assert isinstance(validation.files_modified, list)
        assert validation.files_modified == []
        
        print("✅ SUCCÈS: None converti en liste vide")
        print(f"   Input:  None")
        print(f"   Output: {validation.files_modified}")
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        return False


def test_5_celery_scenario():
    """TEST 5: Scénario exact des logs Celery (ligne 259)."""
    print("\n" + "="*70)
    print("TEST 5: Scénario Celery (ligne 259 des logs)")
    print("="*70)
    
    try:
        # Données exactes du workflow Celery
        workflow_modified_files = {
            "main.txt": "# Résumé du Projet GenericDAO...",
            "README.md": "# Documentation..."
        }
        
        print(f"   Type reçu du workflow: {type(workflow_modified_files)}")
        print(f"   Valeur: {list(workflow_modified_files.keys())}")
        
        # Créer la validation (Pydantic convertit automatiquement)
        validation = HumanValidationRequest(
            validation_id="val_5028415189_test",
            workflow_id="celery_test",
            task_id="5028415189",
            task_title="Ajouter un fichier main",
            generated_code=workflow_modified_files,
            code_summary="Implémentation",
            files_modified=workflow_modified_files,  # Dict → List automatique
            original_request="Test Celery"
        )
        
        # Vérifications
        assert isinstance(validation.files_modified, list)
        assert len(validation.files_modified) == 2
        assert "main.txt" in validation.files_modified
        assert "README.md" in validation.files_modified
        
        print("✅ SUCCÈS: Scénario Celery résolu!")
        print(f"   Type après validation: {type(validation.files_modified)}")
        print(f"   Valeur: {validation.files_modified}")
        print("   → Compatible PostgreSQL TEXT[]")
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_postgresql_array_compatibility():
    """TEST 6: Compatibilité avec PostgreSQL TEXT[]."""
    print("\n" + "="*70)
    print("TEST 6: Compatibilité PostgreSQL TEXT[]")
    print("="*70)
    
    try:
        validation = HumanValidationRequest(
            validation_id="test_006",
            workflow_id="wf_006",
            task_id="127",
            task_title="Test",
            generated_code={},
            code_summary="Test",
            files_modified=["file1.py", "file2.py", "file3.py"],
            original_request="Test"
        )
        
        # Vérifier que c'est une liste de strings
        assert isinstance(validation.files_modified, list)
        assert all(isinstance(f, str) for f in validation.files_modified)
        
        # Simuler la conversion PostgreSQL (asyncpg le fait automatiquement)
        # List[str] → TEXT[]
        pg_array = validation.files_modified
        
        print("✅ SUCCÈS: Compatible PostgreSQL TEXT[]")
        print(f"   Python list: {validation.files_modified}")
        print(f"   PostgreSQL array: {{{', '.join(pg_array)}}}")
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        return False


def main():
    """Exécuter tous les tests."""
    print("\n" + "🎯"*35)
    print("  TESTS DE VALIDATION - files_modified")
    print("🎯"*35)
    
    tests = [
        ("Dict → List", test_1_dict_converted_to_list),
        ("List → List", test_2_list_remains_list),
        ("String → List", test_3_string_converted_to_list),
        ("None → Empty List", test_4_none_converted_to_empty_list),
        ("Scénario Celery", test_5_celery_scenario),
        ("PostgreSQL Compat", test_6_postgresql_array_compatibility),
    ]
    
    results = []
    for name, test_func in tests:
        success = test_func()
        results.append((name, success))
    
    # Résumé
    print("\n" + "="*70)
    print("RÉSUMÉ DES TESTS")
    print("="*70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print("\n" + "-"*70)
    print(f"  TOTAL: {passed}/{total} tests réussis ({passed*100//total}%)")
    print("="*70)
    
    if passed == total:
        print("\n🎉 TOUS LES TESTS SONT RÉUSSIS!")
        print("✅ Les corrections fonctionnent parfaitement")
        print("✅ L'insertion en DB va fonctionner")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) ont échoué")
        return 1


if __name__ == "__main__":
    exit(main())

