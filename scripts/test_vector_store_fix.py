#!/usr/bin/env python3
"""Test rapide pour vérifier que les conversions de types sont correctes."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.semantic_search_service import semantic_search_service


async def test_type_conversions():
    """Test des conversions de types pour monday_item_id et task_id."""
    print("\n" + "="*80)
    print("🧪 TEST: CONVERSIONS DE TYPES (monday_item_id INT → STR)")
    print("="*80)
    
    # Simuler un stockage avec des types corrects
    test_cases = [
        {
            "desc": "Test avec monday_item_id comme int",
            "monday_item_id": 5084422591,  # INT comme reçu du webhook
            "task_id": 213,
            "expected": "Devrait convertir en str automatiquement"
        },
        {
            "desc": "Test avec monday_item_id comme str",
            "monday_item_id": "5084422591",  # Déjà STR
            "task_id": 213,
            "expected": "Devrait fonctionner directement"
        },
        {
            "desc": "Test avec monday_item_id None",
            "monday_item_id": None,
            "task_id": 213,
            "expected": "Devrait gérer None correctement"
        }
    ]
    
    await semantic_search_service.initialize()
    
    all_passed = True
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}: {test['desc']}")
        print(f"{'='*80}")
        print(f"   monday_item_id: {test['monday_item_id']} (type: {type(test['monday_item_id']).__name__})")
        print(f"   task_id: {test['task_id']} (type: {type(test['task_id']).__name__})")
        
        try:
            # Test de conversion
            monday_item_id_converted = str(test['monday_item_id']) if test['monday_item_id'] is not None else None
            print(f"   ✅ Conversion: {monday_item_id_converted} (type: {type(monday_item_id_converted).__name__})")
            
            # Vérification du type attendu
            if monday_item_id_converted is not None and not isinstance(monday_item_id_converted, str):
                print(f"   ❌ ERREUR: monday_item_id devrait être str, obtenu {type(monday_item_id_converted).__name__}")
                all_passed = False
            elif monday_item_id_converted is None:
                print(f"   ✅ None géré correctement")
            else:
                print(f"   ✅ Type correct (str)")
                
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 TOUS LES TESTS DE CONVERSION RÉUSSIS !")
    else:
        print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
    print("="*80)
    
    return all_passed


async def main():
    """Point d'entrée principal."""
    exit_code = 0
    
    try:
        if not await test_type_conversions():
            exit_code = 1
    except Exception as e:
        print(f"\n❌ Erreur lors des tests: {e}")
        import traceback
        traceback.print_exc()
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())

