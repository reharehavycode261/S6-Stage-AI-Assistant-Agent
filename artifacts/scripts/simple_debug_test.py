#!/usr/bin/env python3
"""
Test simplifié pour vérifier la logique de debug sans dépendances.
"""

def mock_should_debug(state):
    """Version simplifiée de _should_debug pour test."""
    
    # Vérifier si on a des résultats de tests
    if not state.get("results") or "test_results" not in state.get("results", {}):
        print("⚠️ Aucun résultat de test trouvé")
        return "continue"
    
    test_results = state["results"]["test_results"]
    
    # Si aucun test n'a été exécuté
    if not test_results:
        print("📝 Aucun test exécuté - passage à l'assurance qualité")
        return "continue"
    
    # Analyser les résultats des tests
    tests_passed = test_results.get("success", False)
    total_tests = test_results.get("total_tests", 0)
    
    # Détecter le flag spécial "no_tests_found"
    if test_results.get("no_tests_found", False):
        print("📝 Flag 'no_tests_found' détecté - passage à l'assurance qualité")
        return "continue"
    
    # CAS SPÉCIAL : Si total_tests = 0, considérer comme "aucun test trouvé"
    if total_tests == 0:
        print("📝 Aucun test trouvé (0/0) - passage à l'assurance qualité")
        return "continue"
    
    # SYSTÈME DE COMPTAGE ROBUSTE DES TENTATIVES DE DEBUG
    if "debug_attempts" not in state["results"]:
        state["results"]["debug_attempts"] = 0
    
    debug_attempts = state["results"]["debug_attempts"]
    MAX_DEBUG_ATTEMPTS = 3  # Limite hardcodée pour le test
    
    print(f"🔧 Debug attempts: {debug_attempts}/{MAX_DEBUG_ATTEMPTS}, Tests: {total_tests} total")
    
    # LOGIQUE DE DÉCISION SIMPLIFIÉE
    if tests_passed:
        print("✅ Tests réussis - passage à l'assurance qualité")
        return "continue"
    
    if debug_attempts >= MAX_DEBUG_ATTEMPTS:
        print(f"⚠️ Limite de debug atteinte ({debug_attempts}/{MAX_DEBUG_ATTEMPTS}) - passage forcé à QA")
        state["results"]["error"] = f"Tests échoués après {debug_attempts} tentatives de debug"
        return "continue"
    
    # Incrémenter le compteur AVANT de retourner "debug"
    state["results"]["debug_attempts"] += 1
    print(f"🔧 Tests échoués - lancement debug {state['results']['debug_attempts']}/{MAX_DEBUG_ATTEMPTS}")
    return "debug"


def test_debug_logic():
    """Test de la logique de debug."""
    
    print("🧪 TEST DE LA LOGIQUE DE DEBUG")
    print("="*50)
    
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
    result1 = mock_should_debug(state1)
    print(f"   ✅ Résultat: {result1} ({'✅' if result1 == 'continue' else '❌'})")
    
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
    result2 = mock_should_debug(state2)
    print(f"   ✅ Résultat: {result2} ({'✅' if result2 == 'continue' else '❌'})")
    
    # Test 3: Simulation de boucle de debug
    print("\n🔄 Test 3: Simulation de boucle de debug")
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
    
    decisions = []
    for i in range(10):  # Maximum 10 itérations pour éviter boucle infinie
        decision = mock_should_debug(state3)
        decisions.append(decision)
        
        print(f"   Itération {i+1}: {decision} (attempts: {state3['results'].get('debug_attempts', 0)})")
        
        if decision == "continue":
            print(f"   ✅ Boucle stoppée après {i+1} itérations")
            break
        elif decision != "debug":
            print(f"   ❌ Décision inattendue: {decision}")
            break
    
    print(f"   📊 Séquence: {' → '.join(decisions)}")
    
    # Vérifications
    success = True
    if len(decisions) > 4:  # Max 3 debug + 1 continue
        print("   ❌ Trop d'itérations")
        success = False
    
    if decisions[-1] != "continue":
        print("   ❌ Ne se termine pas par 'continue'")
        success = False
    
    if success:
        print("   ✅ Test réussi - la boucle s'arrête correctement !")
    
    return success


def main():
    """Fonction principale."""
    
    print("🔧 TEST DES CORRECTIONS DE BOUCLE INFINIE")
    print("⏰ Test simplifié sans dépendances")
    print()
    
    try:
        success = test_debug_logic()
        
        if success:
            print("\n" + "="*50)
            print("🎉 TEST RÉUSSI !")
            print("✅ La logique de debug fonctionne correctement")
            print("✅ Les boucles infinies sont évitées")
            print("="*50)
            return True
        else:
            print("\n❌ ÉCHEC DU TEST")
            return False
            
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 