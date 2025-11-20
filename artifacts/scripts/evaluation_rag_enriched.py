#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Évaluation Enrichie avec RAG Multilingue.

Ce script utilise le nouveau LLMJudgeRAGEnriched pour évaluer le golden dataset
avec enrichissement par recherche sémantique.

Comparaison:
- Évaluation classique (sans contexte)
- Évaluation enrichie RAG (avec examples similaires)
"""

import asyncio
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from services.evaluation.llm_judge_rag_enriched import LLMJudgeRAGEnriched
from services.evaluation.llm_judge_service_simplified import LLMJudgeServiceSimplified
from utils.logger import get_logger

logger = get_logger(__name__)


async def evaluer_avec_rag(
    judge_rag: LLMJudgeRAGEnriched,
    manager: GoldenDatasetManager,
    test_index: int = 0
) -> dict:
    """
    Évalue un test spécifique avec RAG enrichi.
    
    Args:
        judge_rag: Instance du LLM Judge enrichi RAG
        manager: Instance du Golden Dataset Manager
        test_index: Index du test à évaluer
        
    Returns:
        Résultat d'évaluation enrichi
    """
    print(f"\n{'='*80}")
    print(f"🧪 TEST #{test_index + 1} - ÉVALUATION AVEC RAG ENRICHI")
    print('='*80)
    
    # 1. Récupérer le test
    test = manager.get_test_by_index(test_index)
    
    print(f"\n📝 Input: {test['input_reference'][:100]}...")
    print(f"📝 Expected Output: {test['output_reference'][:150]}...")
    
    # 2. Simuler une réponse d'agent (pour la démo)
    # En production, ceci viendrait de l'agent réel
    agent_response = test['output_reference']  # Pour tester, on utilise la réponse attendue
    
    print(f"\n🤖 Agent Response: {agent_response[:150]}...")
    
    # 3. Évaluation enrichie avec RAG
    print(f"\n🔍 Recherche d'examples similaires dans le Golden Dataset...")
    
    result = await judge_rag.evaluate_response_with_rag(
        reference_input=test['input_reference'],
        reference_output=test['output_reference'],
        agent_response=agent_response,
        use_rag=True
    )
    
    # 4. Afficher les résultats
    print(f"\n📊 Résultat de l'Évaluation RAG:")
    print(f"   • Score: {result['score']}/100")
    print(f"   • RAG activé: {result['rag_enabled']}")
    print(f"   • Examples similaires trouvés: {result['rag_similar_count']}")
    print(f"   • Langue détectée: {result['rag_language_detected']}")
    
    if result.get('rag_similar_examples'):
        print(f"\n📚 Examples similaires utilisés:")
        for i, ex in enumerate(result['rag_similar_examples'], 1):
            print(f"   {i}. Similarité: {ex['similarity']:.2f} | Langue: {ex['language']}")
            print(f"      Input: {ex['input'][:70]}...")
    
    print(f"\n💡 Raisonnement:")
    reasoning_lines = result['reasoning'].split('\n')
    for line in reasoning_lines[:10]:
        if line.strip():
            print(f"   {line}")
    
    return result


async def comparer_classic_vs_rag(
    judge_rag: LLMJudgeRAGEnriched,
    manager: GoldenDatasetManager,
    test_index: int = 0
) -> dict:
    """
    Compare l'évaluation classique vs RAG enrichie.
    
    Args:
        judge_rag: Instance du LLM Judge enrichi RAG
        manager: Instance du Golden Dataset Manager
        test_index: Index du test
        
    Returns:
        Comparaison des résultats
    """
    print(f"\n{'='*80}")
    print(f"⚖️  COMPARAISON: CLASSIC vs RAG ENRICHI")
    print('='*80)
    
    # 1. Récupérer le test
    test = manager.get_test_by_index(test_index)
    
    print(f"\n📝 Test: {test['input_reference'][:100]}...")
    
    # Simuler une réponse d'agent
    agent_response = test['output_reference']
    
    # 2. Comparer les deux méthodes
    print(f"\n⏳ Évaluation en cours (2 méthodes)...")
    
    comparison = await judge_rag.compare_classic_vs_rag(
        reference_input=test['input_reference'],
        reference_output=test['output_reference'],
        agent_response=agent_response
    )
    
    # 3. Afficher la comparaison
    print(f"\n📊 Résultats:")
    print(f"\n   🔹 MÉTHODE CLASSIQUE:")
    print(f"      • Score: {comparison['classic']['score']}/100")
    print(f"      • Méthode: {comparison['classic']['method']}")
    
    print(f"\n   🔸 MÉTHODE RAG ENRICHIE:")
    print(f"      • Score: {comparison['rag_enriched']['score']}/100")
    print(f"      • Méthode: {comparison['rag_enriched']['method']}")
    print(f"      • Examples similaires: {comparison['rag_enriched']['similar_count']}")
    print(f"      • Langue: {comparison['rag_enriched']['language']}")
    print(f"      • Similarité max: {comparison['rag_enriched']['max_similarity']:.2f}")
    
    print(f"\n   📈 DIFFÉRENCE:")
    print(f"      • Delta de score: {comparison['difference']['score_delta']:+.1f}")
    print(f"      • Contexte fourni par RAG: {comparison['difference']['rag_provides_context']}")
    
    # 4. Comparaison des raisonnements
    print(f"\n💡 Raisonnement CLASSIQUE:")
    for line in comparison['classic']['reasoning'].split('\n')[:5]:
        if line.strip():
            print(f"   {line}")
    
    print(f"\n💡 Raisonnement RAG ENRICHI:")
    for line in comparison['rag_enriched']['reasoning'].split('\n')[:5]:
        if line.strip():
            print(f"   {line}")
    
    return comparison


async def evaluer_dataset_complet_avec_rag(
    judge_rag: LLMJudgeRAGEnriched,
    manager: GoldenDatasetManager,
    max_tests: int = 10
) -> dict:
    """
    Évalue un ensemble de tests avec RAG.
    
    Args:
        judge_rag: Instance du LLM Judge enrichi RAG
        manager: Instance du Golden Dataset Manager
        max_tests: Nombre maximum de tests à évaluer
        
    Returns:
        Statistiques d'évaluation
    """
    print(f"\n{'='*80}")
    print(f"📊 ÉVALUATION COMPLÈTE DU DATASET AVEC RAG")
    print('='*80)
    
    # Charger le dataset
    df = manager.load_golden_sets()
    total_tests = min(len(df), max_tests)
    
    print(f"\n📂 Dataset: {len(df)} tests disponibles")
    print(f"   Évaluation de {total_tests} tests...")
    
    results = []
    total_score_classic = 0
    total_score_rag = 0
    total_with_rag_context = 0
    
    for i in range(total_tests):
        try:
            test = manager.get_test_by_index(i)
            agent_response = test['output_reference']  # Simulation
            
            # Évaluer avec RAG
            result_rag = await judge_rag.evaluate_response_with_rag(
                reference_input=test['input_reference'],
                reference_output=test['output_reference'],
                agent_response=agent_response,
                use_rag=True
            )
            
            # Évaluer sans RAG (pour comparaison)
            result_classic = await judge_rag.evaluate_response_with_rag(
                reference_input=test['input_reference'],
                reference_output=test['output_reference'],
                agent_response=agent_response,
                use_rag=False
            )
            
            results.append({
                'test_index': i,
                'score_classic': result_classic['score'],
                'score_rag': result_rag['score'],
                'rag_similar_count': result_rag.get('rag_similar_count', 0),
                'rag_language': result_rag.get('rag_language_detected', 'en'),
                'delta': result_rag['score'] - result_classic['score']
            })
            
            total_score_classic += result_classic['score']
            total_score_rag += result_rag['score']
            
            if result_rag.get('rag_similar_count', 0) > 0:
                total_with_rag_context += 1
            
            print(f"   Test {i+1}/{total_tests}: Classic={result_classic['score']:.1f}, RAG={result_rag['score']:.1f} (Δ={result_rag['score'] - result_classic['score']:+.1f})")
            
        except Exception as e:
            print(f"   ❌ Erreur test {i+1}: {e}")
    
    # Statistiques finales
    avg_classic = total_score_classic / len(results) if results else 0
    avg_rag = total_score_rag / len(results) if results else 0
    improvement = avg_rag - avg_classic
    
    print(f"\n{'='*80}")
    print(f"📈 STATISTIQUES FINALES")
    print('='*80)
    print(f"\n📊 Scores Moyens:")
    print(f"   • Classique: {avg_classic:.1f}/100")
    print(f"   • RAG Enrichi: {avg_rag:.1f}/100")
    print(f"   • Amélioration: {improvement:+.1f} points")
    
    print(f"\n🔍 Contexte RAG:")
    print(f"   • Tests avec contexte RAG: {total_with_rag_context}/{len(results)}")
    print(f"   • Taux d'utilisation RAG: {(total_with_rag_context/len(results)*100) if results else 0:.1f}%")
    
    return {
        'total_tests': len(results),
        'avg_score_classic': avg_classic,
        'avg_score_rag': avg_rag,
        'improvement': improvement,
        'rag_usage_rate': (total_with_rag_context/len(results)) if results else 0,
        'results': results
    }


async def main():
    """Fonction principale."""
    print("\n" + "="*80)
    print("🌍 ÉVALUATION ENRICHIE AVEC RAG MULTILINGUE")
    print("="*80)
    print("\n💡 Fonctionnalités:")
    print("   • Recherche d'examples similaires dans le Golden Dataset")
    print("   • Évaluation enrichie avec contexte multilingue")
    print("   • Comparaison Classic vs RAG")
    
    # Initialiser les services
    print("\n📂 Initialisation des services...")
    manager = GoldenDatasetManager()
    judge_rag = LLMJudgeRAGEnriched(
        provider="anthropic",
        use_rag=True,
        rag_top_k=3,
        rag_threshold=0.6
    )
    print("✅ Services initialisés")
    
    # Menu
    print("\n" + "="*80)
    print("Choisissez une option:")
    print("1. Évaluer un test spécifique avec RAG")
    print("2. Comparer Classic vs RAG (1 test)")
    print("3. Évaluer le dataset complet avec RAG (10 tests)")
    print("4. Quitter")
    print("="*80)
    
    choice = input("\nVotre choix (1-4): ").strip()
    
    try:
        if choice == "1":
            test_index = int(input("Index du test (0-based): ").strip())
            await evaluer_avec_rag(judge_rag, manager, test_index)
            
        elif choice == "2":
            test_index = int(input("Index du test (0-based): ").strip())
            await comparer_classic_vs_rag(judge_rag, manager, test_index)
            
        elif choice == "3":
            max_tests = int(input("Nombre de tests à évaluer (max 50): ").strip())
            max_tests = min(max_tests, 50)
            await evaluer_dataset_complet_avec_rag(judge_rag, manager, max_tests)
            
        elif choice == "4":
            print("\n👋 Au revoir!")
            return 0
            
        else:
            print("❌ Choix invalide")
            return 1
        
        print("\n" + "="*80)
        print("✅ ÉVALUATION TERMINÉE")
        print("="*80)
        print("\n📝 Note: L'évaluation RAG enrichie:")
        print("   • Recherche automatiquement des examples similaires")
        print("   • Détecte la langue du test")
        print("   • Fournit un contexte au LLM Judge")
        print("   • Améliore la précision de l'évaluation")
        print()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompu par l'utilisateur")
        return 1
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

