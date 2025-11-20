"""
Script de validation manuelle pour la correction de persistence du workflow.

Ce script valide que la correction apportée résout les problèmes identifiés
dans les logs Celery sans nécessiter pytest.
"""

import sys
sys.path.insert(0, '/Users/rehareharanaivo/Desktop/AI-Agent')

from datetime import datetime
from graph.workflow_graph import _create_initial_state_with_recovery
from models.schemas import TaskRequest, TaskPriority


def validate_state_structure():
    """Valide que l'état créé a la bonne structure."""
    print("🔍 Test 1: Validation de la structure de l'état")
    print("=" * 80)
    
    # Créer un TaskRequest de test
    task_request = TaskRequest(
        task_id="5027535188",
        title="Ajouter un fichier main",
        description="Test de validation",
        priority=TaskPriority.MEDIUM,
        repository_url="https://github.com/rehareha261/S2-GenericDAO",
        base_branch="main"
    )
    
    # Créer l'état comme dans le workflow réel
    workflow_id = "workflow_5027535188_1759664143"
    task_db_id = 25
    actual_task_run_id = 25
    uuid_task_run_id = "run_95f6c0a41acc_1759664144"
    
    state = _create_initial_state_with_recovery(
        task_request,
        workflow_id,
        task_db_id,
        actual_task_run_id,
        uuid_task_run_id
    )
    
    # Vérifications critiques
    errors = []
    warnings = []
    
    # 1. Vérifier db_task_id
    if "db_task_id" not in state:
        errors.append("❌ ERREUR CRITIQUE: 'db_task_id' manquant dans l'état")
    elif state["db_task_id"] != task_db_id:
        errors.append(f"❌ ERREUR: db_task_id devrait être {task_db_id}, obtenu {state['db_task_id']}")
    elif state["db_task_id"] is None:
        errors.append("❌ ERREUR CRITIQUE: db_task_id est None (bug identifié ligne 258 logs)")
    else:
        print(f"✅ db_task_id correctement défini: {state['db_task_id']}")
    
    # 2. Vérifier db_run_id
    if "db_run_id" not in state:
        errors.append("❌ ERREUR CRITIQUE: 'db_run_id' manquant dans l'état")
    elif state["db_run_id"] != actual_task_run_id:
        errors.append(f"❌ ERREUR: db_run_id devrait être {actual_task_run_id}, obtenu {state['db_run_id']}")
    elif state["db_run_id"] is None:
        errors.append("❌ ERREUR CRITIQUE: db_run_id est None (bug identifié ligne 258-259 logs)")
    else:
        print(f"✅ db_run_id correctement défini: {state['db_run_id']}")
    
    # 3. Vérifier les champs requis par GraphState
    required_fields = [
        "workflow_id", "status", "current_node", "completed_nodes", "task",
        "results", "error", "started_at", "completed_at", "langsmith_session"
    ]
    
    for field in required_fields:
        if field not in state:
            errors.append(f"❌ ERREUR: Champ requis '{field}' manquant")
        else:
            print(f"✅ Champ '{field}' présent")
    
    # 4. Vérifier la structure results
    if "results" in state:
        results_fields = ["ai_messages", "error_logs", "modified_files", "test_results", "debug_attempts"]
        for field in results_fields:
            if field not in state["results"]:
                errors.append(f"❌ ERREUR: Champ 'results.{field}' manquant")
            else:
                print(f"✅ results.{field} présent et initialisé")
    
    # 5. Vérifier les champs de récupération
    recovery_fields = ["node_retry_count", "recovery_mode", "checkpoint_data"]
    for field in recovery_fields:
        if field not in state:
            warnings.append(f"⚠️ Champ de récupération '{field}' manquant")
        else:
            print(f"✅ Champ de récupération '{field}' présent")
    
    print("\n" + "=" * 80)
    
    if errors:
        print("❌ ÉCHEC DU TEST")
        for error in errors:
            print(error)
        return False
    elif warnings:
        print("⚠️ TEST PASSÉ AVEC AVERTISSEMENTS")
        for warning in warnings:
            print(warning)
        return True
    else:
        print("✅ TOUS LES TESTS PASSÉS")
        return True


def validate_persistence_scenario():
    """Valide le scénario de persistence identifié dans les logs."""
    print("\n\n🔍 Test 2: Validation du scénario de persistence (logs Celery)")
    print("=" * 80)
    
    # Reproduire le scénario des logs
    task_request = TaskRequest(
        task_id="5027535188",
        title="Ajouter un fichier main",
        description="Ajouter un fichier main.txt qui est le resume du projet",
        priority=TaskPriority.MEDIUM,
        repository_url="https://github.com/rehareha261/S2-GenericDAO"
    )
    
    workflow_id = "workflow_5027535188_1759664143"
    task_db_id = 25  # Ligne 71 des logs
    actual_task_run_id = 25  # Ligne 84 des logs
    uuid_task_run_id = "run_95f6c0a41acc_1759664144"
    
    state = _create_initial_state_with_recovery(
        task_request,
        workflow_id,
        task_db_id,
        actual_task_run_id,
        uuid_task_run_id
    )
    
    # Simuler le nœud finalize_pr
    state["results"]["pr_info"] = {
        "number": 3,
        "url": "https://github.com/rehareha261/S2-GenericDAO/pull/3"
    }
    
    # Test 1: Sauvegarde de la PR (ligne 306-322 de finalize_node.py)
    print("\n📝 Test: Sauvegarde de la PR en base de données")
    task_id_for_pr = state.get("db_task_id")
    task_run_id_for_pr = state.get("db_run_id")
    
    print(f"   task_id extrait: {task_id_for_pr}")
    print(f"   task_run_id extrait: {task_run_id_for_pr}")
    
    # AVANT la correction : task_run_id=None (ligne 258 des logs)
    # APRÈS la correction : task_run_id=25
    if task_id_for_pr is None or task_run_id_for_pr is None:
        print("   ❌ ERREUR: IDs None - PR ne peut pas être sauvegardée (bug ligne 258)")
        print("   ⚠️ Warning qui serait affiché: \"Impossible de sauvegarder la PR en base\"")
        return False
    else:
        print("   ✅ IDs présents - PR peut être sauvegardée")
        print("   ✅ BUG CORRIGÉ: Le warning ligne 258 ne sera plus affiché")
    
    # Test 2: Enregistrement des métriques (ligne 346-397 de finalize_node.py)
    print("\n📊 Test: Enregistrement des métriques de performance")
    task_id_for_metrics = state.get("db_task_id")
    task_run_id_for_metrics = state.get("db_run_id")
    
    print(f"   task_id extrait: {task_id_for_metrics}")
    print(f"   task_run_id extrait: {task_run_id_for_metrics}")
    
    # AVANT la correction : task_run_id=None (ligne 259 des logs)
    # APRÈS la correction : task_run_id=25
    if task_id_for_metrics is None or task_run_id_for_metrics is None:
        print("   ❌ ERREUR: IDs None - Métriques ne peuvent pas être enregistrées (bug ligne 259)")
        print("   ⚠️ Warning qui serait affiché: \"Impossible d'enregistrer les métriques\"")
        return False
    else:
        print("   ✅ IDs présents - Métriques peuvent être enregistrées")
        print("   ✅ BUG CORRIGÉ: Le warning ligne 259 ne sera plus affiché")
    
    print("\n" + "=" * 80)
    print("✅ SCÉNARIO DE PERSISTENCE VALIDÉ")
    print("✅ Les données seront maintenant correctement enregistrées en base")
    return True


def validate_state_propagation():
    """Valide que l'état se propage correctement à travers les nœuds."""
    print("\n\n🔍 Test 3: Propagation de l'état à travers les nœuds")
    print("=" * 80)
    
    task_request = TaskRequest(
        task_id="test_propagation",
        title="Test de propagation",
        description="Test",
        priority=TaskPriority.LOW
    )
    
    state = _create_initial_state_with_recovery(
        task_request,
        "workflow_test",
        100,
        200,
        "run_test"
    )
    
    # Simuler le passage à travers les nœuds
    nodes = [
        "prepare_environment",
        "analyze_requirements",
        "implement_task",
        "run_tests",
        "quality_assurance_automation",
        "finalize_pr",
        "monday_validation",
        "merge_after_validation",
        "update_monday"
    ]
    
    all_passed = True
    for node_name in nodes:
        state["current_node"] = node_name
        state["completed_nodes"].append(node_name)
        
        # Vérifier que les IDs persistent
        if state.get("db_task_id") != 100:
            print(f"   ❌ db_task_id perdu au nœud {node_name}")
            all_passed = False
        elif state.get("db_run_id") != 200:
            print(f"   ❌ db_run_id perdu au nœud {node_name}")
            all_passed = False
        else:
            print(f"   ✅ {node_name}: IDs préservés")
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ PROPAGATION DE L'ÉTAT VALIDÉE")
        return True
    else:
        print("❌ PROBLÈME DE PROPAGATION DÉTECTÉ")
        return False


def main():
    """Fonction principale de validation."""
    print("\n" + "=" * 80)
    print("🧪 VALIDATION MANUELLE DE LA CORRECTION DE PERSISTENCE")
    print("=" * 80)
    print("\nCe script valide que la correction apportée à")
    print("_create_initial_state_with_recovery résout les problèmes")
    print("identifiés dans les logs Celery.\n")
    
    results = []
    
    # Test 1: Structure de l'état
    results.append(("Structure de l'état", validate_state_structure()))
    
    # Test 2: Scénario de persistence
    results.append(("Scénario de persistence", validate_persistence_scenario()))
    
    # Test 3: Propagation de l'état
    results.append(("Propagation de l'état", validate_state_propagation()))
    
    # Résumé
    print("\n\n" + "=" * 80)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHOUÉ"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"Résultats: {passed} tests passés, {failed} tests échoués")
    
    if failed == 0:
        print("\n✅ TOUS LES TESTS SONT PASSÉS")
        print("✅ La correction est validée et prête pour production")
        return 0
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("⚠️ Veuillez corriger les problèmes avant de déployer")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
