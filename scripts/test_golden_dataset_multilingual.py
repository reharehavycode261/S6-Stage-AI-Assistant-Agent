#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test du Golden Dataset Multilingue avec RAG.

Ce script teste:
- Recherche sémantique multilingue
- Évaluation enrichie avec contexte
- Comparaison des méthodes d'évaluation
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.golden_dataset_rag_extension import golden_dataset_rag_extension
from utils.logger import get_logger

logger = get_logger(__name__)


async def test_multilingual_search():
    """Test de recherche multilingue."""
    print("\n" + "="*80)
    print("🌍 TEST 1: RECHERCHE SÉMANTIQUE MULTILINGUE")
    print("="*80)
    
    test_cases = [
        {
            "query": "Comment fonctionne la validation humaine?",
            "language": "Français",
            "expected_similarity": 0.7
        },
        {
            "query": "How does human validation work?",
            "language": "English",
            "expected_similarity": 0.7
        },
        {
            "query": "¿Cómo funciona la validación humana?",
            "language": "Español",
            "expected_similarity": 0.65  # Peut-être moins de correspondances
        },
        {
            "query": "人类验证是如何工作的?",
            "language": "Chinois",
            "expected_similarity": 0.60
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n🧪 Test Case {i}: {test['language']}")
        print(f"   Query: '{test['query']}'")
        print("-" * 80)
        
        try:
            similar_examples = await golden_dataset_rag_extension.find_similar_golden_examples(
                query=test['query'],
                top_k=3,
                match_threshold=0.5
            )
            
            if similar_examples:
                print(f"   ✅ {len(similar_examples)} examples trouvés")
                for j, ex in enumerate(similar_examples, 1):
                    print(f"      {j}. Similarité: {ex['similarity_score']:.3f}")
                    print(f"         Langue: {ex['language']}")
                    print(f"         Input: {ex['input_reference'][:60]}...")
                    
                    if ex['similarity_score'] >= test['expected_similarity']:
                        print(f"         ✅ Bonne similarité (>= {test['expected_similarity']})")
                    else:
                        print(f"         ⚠️  Similarité faible (< {test['expected_similarity']})")
            else:
                print(f"   ❌ Aucun example trouvé")
                
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            return False
    
    return True


async def test_evaluation_with_context():
    """Test d'évaluation enrichie avec contexte."""
    print("\n" + "="*80)
    print("🎯 TEST 2: ÉVALUATION ENRICHIE AVEC CONTEXTE")
    print("="*80)
    
    # Simuler une réponse d'agent
    agent_input = "Explique-moi comment fonctionne le workflow de l'agent"
    agent_output = """Le workflow de l'agent suit ces étapes:
1. Réception d'un webhook Monday.com
2. Classification de l'intention (question vs commande)
3. Exploration du repository si nécessaire
4. Génération de la réponse ou création de PR
5. Validation humaine optionnelle
6. Mise à jour de Monday.com"""
    
    print(f"\n📝 Agent Input: '{agent_input}'")
    print(f"📝 Agent Output: {agent_output[:100]}...")
    print("-" * 80)
    
    try:
        context = await golden_dataset_rag_extension.evaluate_with_similarity_context(
            agent_input=agent_input,
            agent_output=agent_output,
            find_similar=True,
            top_k=3
        )
        
        print(f"\n✅ Contexte d'évaluation généré:")
        print(f"   • Langue détectée: {context['input_language']}")
        print(f"   • Examples similaires trouvés: {context['similar_count']}")
        print(f"   • Similarité max: {context['max_similarity']:.3f}")
        
        if context['similar_golden_examples']:
            print(f"\n📚 Golden Examples Similaires:")
            for i, ex in enumerate(context['similar_golden_examples'], 1):
                print(f"   {i}. Similarité: {ex['similarity_score']:.3f}")
                print(f"      Input: {ex['input_reference'][:70]}...")
                print(f"      Expected Output: {ex['output_reference'][:70]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_comparison_methods():
    """Test de comparaison des méthodes d'évaluation."""
    print("\n" + "="*80)
    print("⚖️  TEST 3: COMPARAISON DES MÉTHODES D'ÉVALUATION")
    print("="*80)
    
    agent_input = "Crée un formulaire de login React"
    agent_output = "Voici un composant React avec formulaire de login incluant validation..."
    expected_output = "Un composant de login professionnel avec validation des champs..."
    
    print(f"\n📝 Input: '{agent_input}'")
    print("-" * 80)
    
    try:
        comparison = await golden_dataset_rag_extension.compare_evaluation_methods(
            agent_input=agent_input,
            agent_output=agent_output,
            expected_output=expected_output
        )
        
        print(f"\n📊 Méthode Classique:")
        print(f"   • Input: {comparison['classic_evaluation']['input'][:60]}...")
        print(f"   • Output: {comparison['classic_evaluation']['output'][:60]}...")
        
        print(f"\n📊 Méthode RAG Enrichie:")
        rag_eval = comparison['rag_enriched_evaluation']
        print(f"   • Input: {rag_eval['input'][:60]}...")
        print(f"   • Langue: {rag_eval['language']}")
        print(f"   • Examples similaires: {rag_eval['similar_examples_found']}")
        print(f"   • Similarité max: {rag_eval['max_similarity']:.3f}")
        
        print(f"\n✅ Améliorations:")
        improvements = comparison['improvement']
        print(f"   • Contexte similaire disponible: {improvements['has_similar_context']}")
        print(f"   • Boost de similarité (>0.7): {improvements['similarity_boost']}")
        print(f"   • Langue détectée: {improvements['language_detected']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Fonction principale de test."""
    print("\n" + "="*80)
    print("🧪 TEST DU GOLDEN DATASET MULTILINGUE AVEC RAG")
    print("="*80)
    print("\n💡 Fonctionnalités testées:")
    print("   • Recherche sémantique multilingue")
    print("   • Évaluation enrichie avec contexte")
    print("   • Comparaison des méthodes d'évaluation")
    
    results = {
        "multilingual_search": False,
        "evaluation_with_context": False,
        "comparison_methods": False
    }
    
    try:
        # Test 1
        results["multilingual_search"] = await test_multilingual_search()
        
        # Test 2
        results["evaluation_with_context"] = await test_evaluation_with_context()
        
        # Test 3
        results["comparison_methods"] = await test_comparison_methods()
        
        # Résumé
        print("\n" + "="*80)
        print("📋 RÉSUMÉ DES TESTS")
        print("="*80)
        
        for test_name, passed in results.items():
            status = "✅" if passed else "❌"
            print(f"{status} {test_name.replace('_', ' ').title()}")
        
        all_passed = all(results.values())
        
        print("\n" + "="*80)
        if all_passed:
            print("🎉 TOUS LES TESTS RÉUSSIS !")
            print("="*80)
            print("\n✅ Le système RAG multilingue pour golden dataset fonctionne correctement !")
            print("\n📝 Utilisation:")
            print("   from services.evaluation.golden_dataset_rag_extension import golden_dataset_rag_extension")
            print()
            print("   # Recherche d'examples similaires")
            print("   similar = await golden_dataset_rag_extension.find_similar_golden_examples(query)")
            print()
            print("   # Évaluation enrichie")
            print("   context = await golden_dataset_rag_extension.evaluate_with_similarity_context(input, output)")
            print()
            return 0
        else:
            failed_count = sum(1 for r in results.values() if not r)
            print(f"⚠️  {failed_count} TEST(S) ÉCHOUÉ(S)")
            print("="*80)
            return 1
            
    except Exception as e:
        print(f"\n❌ Erreur globale: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

