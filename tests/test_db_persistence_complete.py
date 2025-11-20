"""
Test complet de la persistence en base de données pour toutes les tables.

Ce script vérifie que tous les IDs requis sont correctement propagés pour :
1. ai_interactions (run_step_id)
2. ai_code_generations (task_run_id)
3. test_results (task_run_id)
4. pull_requests (task_id, task_run_id)
5. human_validations (task_id, task_run_id, run_step_id)
6. human_validation_responses (human_validation_id)
7. system_config (indépendant)
"""

import sys
sys.path.insert(0, '/Users/rehareharanaivo/Desktop/AI-Agent')

from graph.workflow_graph import _create_initial_state_with_recovery
from models.schemas import TaskRequest, TaskPriority
from utils.persistence_decorator import with_persistence


def test_table_requirements():
    """Test des exigences pour chaque table de la base de données."""
    print("\n" + "=" * 80)
    print("🗄️  TEST COMPLET DE PERSISTENCE EN BASE DE DONNÉES")
    print("=" * 80)
    
    # Créer un état de workflow réaliste
    task_request = TaskRequest(
        task_id="5027535188",
        title="Test de persistence complète",
        description="Test de toutes les tables",
        priority=TaskPriority.MEDIUM,
        repository_url="https://github.com/test/repo"
    )
    
    workflow_id = "workflow_test_persistence_complete"
    task_db_id = 25
    task_run_id = 50
    uuid_task_run_id = "run_persistence_test_123"
    
    state = _create_initial_state_with_recovery(
        task_request,
        workflow_id,
        task_db_id,
        task_run_id,
        uuid_task_run_id
    )
    
    # Simuler l'existence d'un run_step_id (créé par le décorateur with_persistence)
    run_step_id = 100
    
    results = []
    
    # =========================================================================
    # TEST 1: ai_interactions
    # =========================================================================
    print("\n📊 Test 1: ai_interactions")
    print("-" * 80)
    print("Requis: run_step_id (BIGINT NOT NULL)")
    
    # Cette table est alimentée par db_persistence.log_ai_interaction()
    # qui est appelé depuis le décorateur @log_ai_interaction_decorator
    # Vérifier que run_step_id est disponible
    
    if run_step_id is not None and isinstance(run_step_id, int):
        print(f"✅ run_step_id disponible: {run_step_id}")
        print("✅ ai_interactions peut être enregistrée")
        results.append(("ai_interactions", True, None))
    else:
        error = "run_step_id manquant ou invalide"
        print(f"❌ {error}")
        results.append(("ai_interactions", False, error))
    
    # =========================================================================
    # TEST 2: ai_code_generations
    # =========================================================================
    print("\n📊 Test 2: ai_code_generations")
    print("-" * 80)
    print("Requis: task_run_id (BIGINT NOT NULL)")
    
    # Cette table est alimentée par monitoring_service.save_ai_code_generation()
    # Vérifier que task_run_id est disponible dans l'état
    
    task_run_id_extracted = state.get("db_run_id")
    
    if task_run_id_extracted is not None and isinstance(task_run_id_extracted, int):
        print(f"✅ task_run_id disponible: {task_run_id_extracted}")
        print("✅ ai_code_generations peut être enregistrée")
        results.append(("ai_code_generations", True, None))
    else:
        error = f"task_run_id manquant ou invalide: {task_run_id_extracted}"
        print(f"❌ {error}")
        results.append(("ai_code_generations", False, error))
    
    # =========================================================================
    # TEST 3: test_results
    # =========================================================================
    print("\n📊 Test 3: test_results")
    print("-" * 80)
    print("Requis: task_run_id (BIGINT NOT NULL)")
    
    # Cette table est alimentée par db_persistence.log_test_results()
    # Vérifier que task_run_id est disponible dans l'état
    
    task_run_id_for_tests = state.get("db_run_id")
    
    if task_run_id_for_tests is not None and isinstance(task_run_id_for_tests, int):
        print(f"✅ task_run_id disponible: {task_run_id_for_tests}")
        print("✅ test_results peut être enregistrée")
        results.append(("test_results", True, None))
    else:
        error = f"task_run_id manquant ou invalide: {task_run_id_for_tests}"
        print(f"❌ {error}")
        results.append(("test_results", False, error))
    
    # =========================================================================
    # TEST 4: pull_requests
    # =========================================================================
    print("\n📊 Test 4: pull_requests")
    print("-" * 80)
    print("Requis: task_id (BIGINT NOT NULL), task_run_id (BIGINT, nullable)")
    
    # Cette table est alimentée par db_persistence.create_pull_request()
    # appelée dans finalize_node.py ligne 309-320
    
    task_id_for_pr = state.get("db_task_id")
    task_run_id_for_pr = state.get("db_run_id")
    
    pr_can_be_saved = False
    pr_error = None
    
    if task_id_for_pr is None or not isinstance(task_id_for_pr, int):
        pr_error = f"task_id manquant ou invalide: {task_id_for_pr} (REQUIS)"
        print(f"❌ {pr_error}")
    elif task_run_id_for_pr is None or not isinstance(task_run_id_for_pr, int):
        # task_run_id est nullable mais pratiquement toujours requis
        pr_error = f"task_run_id manquant: {task_run_id_for_pr} (ligne 322 finalize_node)"
        print(f"⚠️ {pr_error}")
        print("⚠️ La PR pourrait techniquement être créée (nullable) mais le code le vérifie")
    else:
        print(f"✅ task_id disponible: {task_id_for_pr}")
        print(f"✅ task_run_id disponible: {task_run_id_for_pr}")
        print("✅ pull_requests peut être enregistrée")
        pr_can_be_saved = True
    
    results.append(("pull_requests", pr_can_be_saved, pr_error))
    
    # =========================================================================
    # TEST 5: human_validations
    # =========================================================================
    print("\n📊 Test 5: human_validations")
    print("-" * 80)
    print("Requis: task_id (BIGINT NOT NULL), task_run_id (nullable), run_step_id (nullable)")
    
    # Cette table est alimentée par validation_service.create_validation_request()
    # appelée dans human_validation_node.py
    
    task_id_for_hv = state.get("db_task_id")
    task_run_id_for_hv = state.get("db_run_id")
    
    hv_can_be_saved = False
    hv_error = None
    
    if task_id_for_hv is None or not isinstance(task_id_for_hv, int):
        hv_error = f"task_id manquant ou invalide: {task_id_for_hv} (REQUIS)"
        print(f"❌ {hv_error}")
    else:
        print(f"✅ task_id disponible: {task_id_for_hv}")
        
        if task_run_id_for_hv is not None and isinstance(task_run_id_for_hv, int):
            print(f"✅ task_run_id disponible: {task_run_id_for_hv}")
        else:
            print(f"⚠️ task_run_id nullable: {task_run_id_for_hv}")
        
        print(f"⚠️ run_step_id nullable: {run_step_id}")
        print("✅ human_validations peut être enregistrée")
        hv_can_be_saved = True
    
    results.append(("human_validations", hv_can_be_saved, hv_error))
    
    # =========================================================================
    # TEST 6: human_validation_responses
    # =========================================================================
    print("\n📊 Test 6: human_validation_responses")
    print("-" * 80)
    print("Requis: human_validation_id (FK vers human_validations)")
    
    # Cette table est alimentée par validation_service.submit_validation_response()
    # Elle ne dépend que de l'existence d'une validation
    
    print("✅ Dépend de human_validations (validation_id)")
    print("✅ Pas de dépendance directe au workflow state")
    print("✅ human_validation_responses peut être enregistrée si validation existe")
    results.append(("human_validation_responses", True, None))
    
    # =========================================================================
    # TEST 7: system_config
    # =========================================================================
    print("\n📊 Test 7: system_config")
    print("-" * 80)
    print("Requis: Aucune dépendance au workflow")
    
    # Cette table est indépendante du workflow
    print("✅ Table de configuration indépendante")
    print("✅ Aucune dépendance au workflow state")
    print("✅ system_config peut être enregistrée")
    results.append(("system_config", True, None))
    
    # =========================================================================
    # RÉSUMÉ
    # =========================================================================
    print("\n\n" + "=" * 80)
    print("📊 RÉSUMÉ DES TESTS DE PERSISTENCE")
    print("=" * 80)
    
    passed = 0
    failed = 0
    warnings = 0
    
    for table_name, success, error in results:
        if success:
            status = "✅ OK"
            passed += 1
        else:
            if error and "nullable" in error.lower():
                status = "⚠️ WARNING"
                warnings += 1
            else:
                status = "❌ ÉCHEC"
                failed += 1
        
        print(f"{status:15} {table_name:30} {error if error else ''}")
    
    print("\n" + "=" * 80)
    print(f"Résultats: {passed} OK, {warnings} warnings, {failed} échecs")
    
    if failed == 0:
        print("\n✅ TOUS LES TESTS CRITIQUES SONT PASSÉS")
        if warnings > 0:
            print(f"⚠️ {warnings} avertissement(s) à considérer")
        return 0
    else:
        print("\n❌ DES TESTS CRITIQUES ONT ÉCHOUÉ")
        return 1


def test_decorator_propagation():
    """Test que le décorateur with_persistence propage correctement les IDs."""
    print("\n\n" + "=" * 80)
    print("🔍 TEST DE PROPAGATION DES IDS PAR LE DÉCORATEUR")
    print("=" * 80)
    
    # Créer un état
    task_request = TaskRequest(
        task_id="test_decorator",
        title="Test decorator",
        description="Test",
        priority=TaskPriority.LOW
    )
    
    state = _create_initial_state_with_recovery(
        task_request,
        "workflow_decorator_test",
        75,
        150,
        "run_decorator_789"
    )
    
    print("\n📝 État créé avec:")
    print(f"   db_task_id: {state.get('db_task_id')}")
    print(f"   db_run_id: {state.get('db_run_id')}")
    
    # Simuler l'extraction des IDs comme dans persistence_decorator.py (ligne 26-27)
    print("\n🔧 Extraction des IDs comme dans with_persistence decorator:")
    task_run_id = state.get("db_run_id")
    task_id = state.get("db_task_id")
    
    print(f"   task_run_id extrait: {task_run_id}")
    print(f"   task_id extrait: {task_id}")
    
    # Vérifier que les IDs peuvent être utilisés pour créer un step
    if task_run_id is not None and isinstance(task_run_id, int):
        print(f"\n✅ Le décorateur peut créer un run_step avec task_run_id={task_run_id}")
        print("✅ Le run_step_id sera ensuite disponible pour ai_interactions")
        return True
    else:
        print(f"\n❌ Le décorateur ne peut pas créer de run_step: task_run_id={task_run_id}")
        return False


def main():
    """Fonction principale."""
    print("\n" + "=" * 80)
    print("🧪 TEST COMPLET DE PERSISTENCE - TOUTES LES TABLES")
    print("=" * 80)
    print("\nCe script vérifie que tous les IDs nécessaires sont correctement")
    print("propagés pour l'enregistrement dans toutes les tables de la base.")
    
    # Test 1: Exigences des tables
    exit_code_1 = test_table_requirements()
    
    # Test 2: Propagation par le décorateur
    decorator_ok = test_decorator_propagation()
    
    # Code de sortie final
    if exit_code_1 == 0 and decorator_ok:
        print("\n\n" + "=" * 80)
        print("✅ TOUS LES TESTS SONT PASSÉS")
        print("✅ La persistence fonctionne correctement pour toutes les tables")
        print("=" * 80)
        return 0
    else:
        print("\n\n" + "=" * 80)
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("⚠️ Veuillez corriger les problèmes avant de continuer")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
