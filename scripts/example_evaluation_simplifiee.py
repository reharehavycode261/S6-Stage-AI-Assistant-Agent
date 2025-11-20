#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'exemple : Utilisation du Golden Dataset simplifié

Démontre comment:
1. Charger le Golden Dataset (input_reference + output_reference)
2. Simuler une réponse de l'agent
3. Utiliser un LLM-as-judge pour évaluer
4. Sauvegarder les résultats
"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from datetime import datetime
import random


def simulate_agent_response(input_text: str) -> str:
    """
    Simule une réponse de l'agent (à remplacer par votre vrai agent).
    
    Dans un vrai scénario, vous appelleriez votre agent ici.
    """
    # Pour la démo, on retourne une réponse simulée
    responses = [
        f"Réponse simulée pour: {input_text}",
        f"Traitement de: {input_text}",
        f"Analyse de: {input_text}"
    ]
    return random.choice(responses)


def simulate_llm_judge(agent_output: str, output_reference: str) -> dict:
    """
    Simule l'évaluation par un LLM-as-judge.
    
    Dans un vrai scénario, vous appelleriez un LLM (Claude, GPT, etc.) ici
    avec un prompt demandant de comparer agent_output et output_reference.
    """
    # Pour la démo, on retourne un score aléatoire
    score = random.randint(60, 100)
    passed = score >= 70
    
    reasoning = f"L'agent a fourni une réponse {'excellente' if score >= 90 else 'correcte' if score >= 70 else 'insuffisante'}. "
    reasoning += f"Comparée à la référence attendue, la réponse mérite un score de {score}/100."
    
    return {
        "score": float(score),
        "reasoning": reasoning,
        "passed": passed
    }


def main():
    """
    Fonction principale : Démontre le workflow complet.
    """
    print("\n" + "="*70)
    print("🧪 DÉMONSTRATION : Évaluation avec Golden Dataset Simplifié")
    print("="*70)
    
    # 1. Initialiser le gestionnaire
    print("\n📂 Étape 1: Initialisation du GoldenDatasetManager...")
    manager = GoldenDatasetManager()
    
    # 2. Charger le Golden Dataset
    print("\n📊 Étape 2: Chargement du Golden Dataset...")
    df_tests = manager.load_golden_sets()
    print(f"   ✅ {len(df_tests)} tests chargés")
    
    # 3. Sélectionner un test (exemple: le premier)
    print("\n🎯 Étape 3: Sélection d'un test...")
    test_index = 0
    test = manager.get_test_by_index(test_index)
    
    print(f"\n   Input reference:")
    print(f"   └─ {test['input_reference'][:100]}...")
    print(f"\n   Output reference (attendu):")
    print(f"   └─ {test['output_reference'][:100]}...")
    
    # 4. Envoyer l'input au système (simulé)
    print("\n🤖 Étape 4: Envoi de l'input au système...")
    agent_output = simulate_agent_response(test['input_reference'])
    print(f"   ✅ Réponse de l'agent reçue")
    print(f"   └─ {agent_output}")
    
    # 5. Évaluation par LLM-as-judge
    print("\n⚖️  Étape 5: Évaluation par LLM-as-judge...")
    judge_result = simulate_llm_judge(agent_output, test['output_reference'])
    
    print(f"   📊 Score: {judge_result['score']}/100")
    print(f"   ✅ Passed: {judge_result['passed']}")
    print(f"   💭 Reasoning: {judge_result['reasoning']}")
    
    # 6. Sauvegarder le résultat
    print("\n💾 Étape 6: Sauvegarde du résultat...")
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "input_reference": test['input_reference'],
        "output_reference": test['output_reference'],
        "agent_output": agent_output,
        "llm_score": judge_result['score'],
        "llm_reasoning": judge_result['reasoning'],
        "passed": judge_result['passed'],
        "duration_seconds": 2.5  # Simulé
    }
    
    manager.save_evaluation_result(result)
    print("   ✅ Résultat sauvegardé dans evaluation_results.csv")
    
    # 7. Afficher les statistiques
    print("\n📈 Étape 7: Statistiques globales...")
    stats = manager.get_statistics_summary()
    
    if "message" in stats:
        print(f"   ℹ️  {stats['message']}")
    else:
        print(f"   Total évaluations: {stats['total_evaluations']}")
        print(f"   Réussis: {stats['passed']}")
        print(f"   Échoués: {stats['failed']}")
        print(f"   Taux de réussite: {stats['pass_rate']}%")
        print(f"   Score moyen: {stats['avg_score']}/100")
    
    print("\n" + "="*70)
    print("✅ Démonstration terminée avec succès!")
    print("="*70)
    print("\n📝 Notes:")
    print("   • Ce script utilise des simulations pour la démo")
    print("   • Dans un vrai scénario, remplacez les fonctions simulate_* par:")
    print("     - Votre agent VyData pour generate_response()")
    print("     - Un vrai LLM (Claude/GPT) pour llm_judge()")
    print("\n📚 Documentation: data/golden_datasets/README_STRUCTURE_SIMPLIFIEE.md")
    print()


if __name__ == "__main__":
    main()

