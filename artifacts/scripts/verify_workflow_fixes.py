#!/usr/bin/env python3
"""
Script pour vérifier que les corrections de boucle infinie fonctionnent.
"""

from datetime import datetime
from graph.workflow_graph import _should_debug
from config.workflow_limits import WorkflowLimits
from utils.logger import get_logger

logger = get_logger(__name__)


def test_should_debug_logic():
    """Teste la logique de _should_debug avec différents scénarios."""
    
    print("\n" + "="*60)
    print("🧪 TEST DE LA LOGIQUE _should_debug")
    print("="*60)
    
    # Test 1: Aucun test trouvé (0/0)
    print("\n📋 Test 1: Aucun test trouvé (0/0)")
    state1 = {
        "results": {
            "test_results": {
                "success": True,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "no_tests_found": True
            }
        }
    }
    result1 = _should_debug(state1)
    print(f"   Résultat: {result1} (attendu: 'continue')")
    assert result1 == "continue", f"Échec Test 1: {result1} != 'continue'"
    
    # Test 2: Tests qui passent
    print("\n✅ Test 2: Tests qui passent")
    state2 = {
        "results": {
            "test_results": {
                "success": True,
                "total_tests": 5,
                "passed_tests": 5,
                "failed_tests": 0
            }
        }
    }
    result2 = _should_debug(state2)
    print(f"   Résultat: {result2} (attendu: 'continue')")
    assert result2 == "continue", f"Échec Test 2: {result2} != 'continue'"
    
    # Test 3: Premier échec de test
    print("\n❌ Test 3: Premier échec de test")
    state3 = {
        "results": {
            "test_results": {
                "success": False,
                "total_tests": 5,
                "passed_tests": 3,
                "failed_tests": 2
            }
        }
    }
    result3 = _should_debug(state3)
    print(f"   Résultat: {result3} (attendu: 'debug')")
    print(f"   Compteur debug: {state3['results'].get('debug_attempts', 0)}")
    assert result3 == "debug", f"Échec Test 3: {result3} != 'debug'"
    assert state3['results']['debug_attempts'] == 1, f"Compteur incorrect: {state3['results']['debug_attempts']}"
    
    # Test 4: Deuxième tentative de debug
    print("\n🔧 Test 4: Deuxième tentative de debug")
    state4 = {
        "results": {
            "test_results": {
                "success": False,
                "total_tests": 5,
                "passed_tests": 3,
                "failed_tests": 2
            },
            "debug_attempts": 1  # Déjà une tentative
        }
    }
    result4 = _should_debug(state4)
    print(f"   Résultat: {result4} (attendu: 'debug')")
    print(f"   Compteur debug: {state4['results']['debug_attempts']}")
    assert result4 == "debug", f"Échec Test 4: {result4} != 'debug'"
    assert state4['results']['debug_attempts'] == 2, f"Compteur incorrect: {state4['results']['debug_attempts']}"
    
    # Test 5: Limite atteinte après 2 tentatives - passage forcé à QA
    print("\n⚠️ Test 5: Limite atteinte après 2 tentatives - passage forcé à QA")
    state5 = {
        "results": {
            "test_results": {
                "success": False,
                "total_tests": 5,
                "passed_tests": 3,
                "failed_tests": 2
            },
            "debug_attempts": 2  # Déjà deux tentatives
        }
    }
    result5 = _should_debug(state5)
    print(f"   Résultat: {result5} (attendu: 'continue')")
    print(f"   Compteur debug: {state5['results']['debug_attempts']}")
    assert result5 == "continue", f"Échec Test 5: {result5} != 'continue'"
    # Avec MAX_DEBUG_ATTEMPTS = 2, après 2 tentatives on passe à QA
    
    # Test 5 couvre maintenant la limite atteinte avec MAX_DEBUG_ATTEMPTS = 2
    
    print("\n✅ Tous les tests _should_debug passent !")


def test_workflow_limits():
    """Teste les limites de workflow configurées."""
    
    print("\n" + "="*60)
    print("⚙️ TEST DES LIMITES DE WORKFLOW")
    print("="*60)
    
    print("📊 Limites actuelles:")
    print(f"   MAX_DEBUG_ATTEMPTS: {WorkflowLimits.MAX_DEBUG_ATTEMPTS}")
    print(f"   MAX_NODES_SAFETY_LIMIT: {WorkflowLimits.MAX_NODES_SAFETY_LIMIT}")
    print(f"   WORKFLOW_TIMEOUT: {WorkflowLimits.WORKFLOW_TIMEOUT}")
    print(f"   MAX_RETRY_ATTEMPTS: {WorkflowLimits.MAX_RETRY_ATTEMPTS}")
    
    # Vérifier les valeurs réduites pour éviter les boucles infinies
    assert WorkflowLimits.MAX_DEBUG_ATTEMPTS == 2, f"MAX_DEBUG_ATTEMPTS incorrect: {WorkflowLimits.MAX_DEBUG_ATTEMPTS}"
    assert WorkflowLimits.MAX_NODES_SAFETY_LIMIT == 15, f"MAX_NODES_SAFETY_LIMIT incorrect: {WorkflowLimits.MAX_NODES_SAFETY_LIMIT}"
    
    print("✅ Toutes les limites sont correctement configurées !")


def simulate_debug_loop():
    """Simule une boucle de debug pour vérifier qu'elle s'arrête."""
    
    print("\n" + "="*60)
    print("🔄 SIMULATION D'UNE BOUCLE DE DEBUG")
    print("="*60)
    
    # État initial avec tests qui échouent
    state = {
        "results": {
            "test_results": {
                "success": False,
                "total_tests": 5,
                "passed_tests": 3,
                "failed_tests": 2
            }
        }
    }
    
    decisions = []
    max_iterations = 10  # Garde-fou pour le test
    
    for i in range(max_iterations):
        decision = _should_debug(state)
        decisions.append(decision)
        
        print(f"   Itération {i+1}: {decision} (debug_attempts: {state['results'].get('debug_attempts', 0)})")
        
        if decision == "continue":
            print(f"✅ Boucle stoppée après {i+1} itérations")
            break
        elif decision == "debug":
            # Simuler que le debug n'a pas résolu le problème
            # (les test_results restent en échec)
            continue
        else:
            print(f"❌ Décision inattendue: {decision}")
            break
    else:
        print(f"❌ La boucle n's'est pas arrêtée après {max_iterations} itérations !")
        return False
    
    # Vérifier que la boucle s'est bien arrêtée
    assert decisions[-1] == "continue", f"Dernière décision doit être 'continue': {decisions[-1]}"
    assert len(decisions) <= WorkflowLimits.MAX_DEBUG_ATTEMPTS + 1, f"Trop d'itérations: {len(decisions)}"
    
    print(f"📊 Séquence des décisions: {' → '.join(decisions)}")
    print("✅ Simulation réussie - la boucle s'arrête correctement !")
    
    return True


def main():
    """Fonction principale des tests."""
    
    print("🧪 VÉRIFICATION DES CORRECTIONS DE BOUCLE INFINIE")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Test 1: Logique de base
        test_should_debug_logic()
        
        # Test 2: Configuration des limites
        test_workflow_limits()
        
        # Test 3: Simulation de boucle
        simulate_debug_loop()
        
        print("\n" + "="*60)
        print("🎉 TOUS LES TESTS PASSENT !")
        print("✅ Les corrections de boucle infinie fonctionnent correctement")
        print("✅ Le workflow respectera maintenant les limites configurées")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERREUR LORS DES TESTS: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 