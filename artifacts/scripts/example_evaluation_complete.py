#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exemple complet d'évaluation avec LLM-as-judge simplifié.

Ce script démontre comment utiliser le système d'évaluation complet:
1. Charger le Golden Dataset (input_reference, output_reference)
2. Envoyer l'input_reference au système pour obtenir une réponse
3. Évaluer la réponse avec le LLM-as-judge
4. Sauvegarder les résultats
"""

import sys
import asyncio
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from services.evaluation.llm_judge_service_simplified import LLMJudgeServiceSimplified
from datetime import datetime
import time


async def simulate_agent_response(input_text: str) -> str:
    """
    Simule une réponse de l'agent VyData.
    
    Dans un vrai scénario, vous appelleriez votre agent ici.
    Pour la démo, on retourne une réponse simulée.
    """
    # Pour la démo, retourner une réponse basique
    await asyncio.sleep(0.5)  # Simuler le temps de traitement
    
    if "hello" in input_text.lower():
        return "Bonjour ! 👋 Je suis VyData, votre assistant IA. Comment puis-je vous aider ?"
    elif "main.py" in input_text.lower():
        return "Le fichier main.py contient une API FastAPI avec plusieurs endpoints."
    else:
        return f"J'ai analysé votre demande : {input_text}"


async def evaluate_single_test(
    manager: GoldenDatasetManager,
    judge: LLMJudgeServiceSimplified,
    test_index: int
) -> dict:
    """
    Évalue un test individuel.
    
    Args:
        manager: Gestionnaire du Golden Dataset
        judge: Service LLM-as-judge
        test_index: Index du test à évaluer
        
    Returns:
        Résultat de l'évaluation
    """
    # 1. Récupérer le test
    test = manager.get_test_by_index(test_index)
    
    print(f"\n{'='*70}")
    print(f"🧪 Test #{test_index + 1}")
    print(f"{'='*70}")
    print(f"\n📝 Input: {test['input_reference'][:100]}...")
    print(f"📄 Output attendu: {test['output_reference'][:100]}...")
    
    # 2. Obtenir la réponse de l'agent
    print(f"\n🤖 Envoi de l'input au système...")
    start_time = time.time()
    agent_response = await simulate_agent_response(test['input_reference'])
    duration = time.time() - start_time
    
    print(f"✅ Réponse reçue ({duration:.2f}s):")
    print(f"   {agent_response[:150]}...")
    
    # 3. Évaluer avec le LLM-as-judge
    print(f"\n⚖️  Évaluation par LLM-as-judge...")
    result = await judge.evaluate_response(
        reference_input=test['input_reference'],
        reference_output=test['output_reference'],
        adam_response=agent_response
    )
    
    # Ajouter la durée
    result['duration_seconds'] = duration
    
    # 4. Afficher les résultats
    print(f"\n📊 Résultats:")
    print(f"   Score: {result['llm_score']}/100")
    print(f"   Statut: {'✅ PASS' if result['passed'] else '❌ FAIL'} (seuil: 70)")
    print(f"   Reasoning:")
    # Afficher le reasoning avec indentation
    for line in result['llm_reasoning'].split('\n'):
        print(f"      {line}")
    
    return result


async def evaluate_all_tests():
    """
    Évalue tous les tests du Golden Dataset.
    """
    print("\n" + "="*70)
    print("🎯 ÉVALUATION COMPLÈTE DU GOLDEN DATASET")
    print("="*70)
    
    # 1. Initialiser les services
    print("\n📂 Initialisation...")
    manager = GoldenDatasetManager()
    judge = LLMJudgeServiceSimplified(provider="anthropic")  # Utilise Claude par défaut
    
    # 2. Charger le Golden Dataset
    print("📊 Chargement du Golden Dataset...")
    df = manager.load_golden_sets()
    total_tests = len(df)
    print(f"✅ {total_tests} tests chargés")
    
    # 3. Évaluer chaque test
    results = []
    passed = 0
    failed = 0
    total_score = 0
    
    for i in range(min(3, total_tests)):  # Limiter à 3 tests pour la démo
        try:
            result = await evaluate_single_test(manager, judge, i)
            results.append(result)
            
            if result['passed']:
                passed += 1
            else:
                failed += 1
            
            total_score += result['llm_score']
            
            # Sauvegarder le résultat
            manager.save_evaluation_result(result)
            
        except Exception as e:
            print(f"\n❌ Erreur lors du test #{i+1}: {e}")
            failed += 1
    
    # 4. Afficher le résumé
    print("\n" + "="*70)
    print("📈 RÉSUMÉ DE L'ÉVALUATION")
    print("="*70)
    print(f"Total de tests: {len(results)}")
    print(f"✅ Réussis: {passed}")
    print(f"❌ Échoués: {failed}")
    print(f"📊 Score moyen: {total_score/len(results) if results else 0:.1f}/100")
    print(f"🎯 Taux de réussite: {(passed/len(results)*100) if results else 0:.1f}%")
    
    # 5. Afficher les statistiques globales
    print("\n📊 Statistiques globales (toutes les évaluations):")
    stats = manager.get_statistics_summary()
    
    if "message" in stats:
        print(f"   {stats['message']}")
    else:
        print(f"   Total évaluations: {stats['total_evaluations']}")
        print(f"   Réussis: {stats['passed']}")
        print(f"   Échoués: {stats['failed']}")
        print(f"   Taux de réussite: {stats['pass_rate']}%")
        print(f"   Score moyen: {stats['avg_score']}/100")
    
    print("\n" + "="*70)
    print("✅ Évaluation terminée!")
    print("="*70)
    print("\n📝 Notes:")
    print("   • Ce script utilise un agent simulé pour la démo")
    print("   • Les résultats sont sauvegardés dans evaluation_results.csv")
    print("   • Dans un vrai scénario, remplacez simulate_agent_response()")
    print("     par votre agent VyData réel")
    print()


if __name__ == "__main__":
    # Exécuter l'évaluation
    asyncio.run(evaluate_all_tests())

