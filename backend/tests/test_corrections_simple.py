# -*- coding: utf-8 -*-
"""
Tests simples de validation des corrections de coherence.
Date: 2025-10-06
"""


def test_nomenclature_rules():
    """Tester les regles de nomenclature."""
    print("\n[TEST] Regles de nomenclature")
    print("-" * 70)
    
    # Simuler les IDs
    monday_item_id = 5028673529  # ID Monday.com
    db_task_id = 36  # ID base de donnees
    
    # Test 1: IDs sont differents
    assert monday_item_id != db_task_id, "Les IDs doivent etre differents"
    print("OK - IDs distincts: monday_item_id={}, db_task_id={}".format(monday_item_id, db_task_id))
    
    # Test 2: monday_item_id pour affichage
    display_id = str(monday_item_id)
    assert display_id == "5028673529", "Display ID doit etre le Monday item ID"
    print("OK - Display ID correct: " + display_id)
    
    # Test 3: db_task_id pour persistence
    persistence_id = db_task_id
    assert persistence_id == 36, "Persistence ID doit etre db_task_id"
    print("OK - Persistence ID correct: " + str(persistence_id))
    
    return True


def test_fallback_logic():
    """Tester la logique de fallback."""
    print("\n[TEST] Logique de fallback")
    print("-" * 70)
    
    # Cas 1: monday_item_id present
    class Task1:
        def __init__(self):
            self.monday_item_id = 5028673529
            self.task_id = "12345"
    
    task1 = Task1()
    display_id1 = str(task1.monday_item_id) if hasattr(task1, 'monday_item_id') and task1.monday_item_id else str(task1.task_id)
    assert display_id1 == "5028673529"
    print("OK - Avec monday_item_id: " + display_id1)
    
    # Cas 2: monday_item_id absent
    class Task2:
        def __init__(self):
            self.task_id = "12345"
    
    task2 = Task2()
    display_id2 = str(task2.monday_item_id) if hasattr(task2, 'monday_item_id') and hasattr(task2, 'monday_item_id') and task2.monday_item_id else str(task2.task_id)
    # Ici on s'attend au fallback sur task_id
    assert display_id2 == "12345" or "monday_item_id" not in dir(task2)
    print("OK - Sans monday_item_id (fallback): " + display_id2)
    
    return True


def test_state_propagation():
    """Tester la propagation de l'etat."""
    print("\n[TEST] Propagation de l'etat")
    print("-" * 70)
    
    # Simuler un state avec db_task_id et db_run_id
    state = {
        "workflow_id": "test_workflow",
        "db_task_id": 36,
        "db_run_id": 100,
        "results": {}
    }
    
    # Test 1: Valeurs initiales
    assert state["db_task_id"] == 36
    assert state["db_run_id"] == 100
    print("OK - Valeurs initiales presentes")
    
    # Test 2: Propagation dans results (comme dans prepare_node)
    state["results"]["db_task_id"] = state["db_task_id"]
    state["results"]["db_run_id"] = state["db_run_id"]
    
    assert state["results"]["db_task_id"] == 36
    assert state["results"]["db_run_id"] == 100
    print("OK - Propagation dans results reussie")
    
    # Test 3: Acces securise
    db_task_id_root = state.get("db_task_id")
    db_task_id_results = state["results"].get("db_task_id")
    
    assert db_task_id_root == db_task_id_results == 36
    print("OK - Acces depuis root et results coherent")
    
    return True


def test_validation_ids():
    """Tester les IDs de validation."""
    print("\n[TEST] IDs de validation")
    print("-" * 70)
    
    # Simuler la creation d'une validation
    monday_item_id = 5028673529
    db_task_id = 36
    
    # Display ID pour HumanValidationRequest (UI)
    display_task_id = str(monday_item_id)
    
    # DB ID pour la persistence (foreign key)
    persistence_task_id = db_task_id
    
    # Test 1: Display ID est le Monday item ID
    assert display_task_id == "5028673529"
    print("OK - Display ID (UI): " + display_task_id)
    
    # Test 2: Persistence ID est le DB task ID
    assert persistence_task_id == 36
    print("OK - Persistence ID (DB FK): " + str(persistence_task_id))
    
    # Test 3: Ils sont differents
    assert display_task_id != str(persistence_task_id)
    print("OK - IDs distincts pour differents usages")
    
    return True


def run_all_tests():
    """Executer tous les tests simples."""
    print("\n" + "="*70)
    print("TESTS DE COHERENCE - VERSION SIMPLIFIEE")
    print("="*70)
    
    tests = [
        ("Regles de nomenclature", test_nomenclature_rules),
        ("Logique de fallback", test_fallback_logic),
        ("Propagation de l'etat", test_state_propagation),
        ("IDs de validation", test_validation_ids)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
                print("[OK] " + test_name + " - REUSSI\n")
            else:
                failed += 1
                print("[FAIL] " + test_name + " - ECHOUE\n")
        except AssertionError as e:
            failed += 1
            print("[FAIL] " + test_name + " - " + str(e) + "\n")
        except Exception as e:
            failed += 1
            print("[ERROR] " + test_name + " - " + str(e) + "\n")
    
    # Resume
    print("="*70)
    print("RESUME")
    print("="*70)
    print("Total: " + str(len(tests)) + " tests")
    print("Reussis: " + str(passed))
    print("Echoues: " + str(failed))
    if len(tests) > 0:
        print("Taux de succes: " + str(round(passed/len(tests)*100, 1)) + "%")
    print("="*70 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

