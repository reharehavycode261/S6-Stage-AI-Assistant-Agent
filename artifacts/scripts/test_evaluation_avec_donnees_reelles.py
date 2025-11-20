#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test du système d'évaluation avec les VRAIES données Monday.com

Ce script:
1. Charge les vraies interactions depuis agent_interactions_log.csv
2. Les transforme en format golden dataset
3. Teste le système LLM-as-judge avec ces données réelles
4. Sauvegarde les résultats
"""

import sys
from pathlib import Path
import pandas as pd
import asyncio
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from services.evaluation.llm_judge_service_simplified import LLMJudgeServiceSimplified
from utils.logger import get_logger

logger = get_logger(__name__)


async def charger_donnees_reelles():
    """
    Charge les vraies interactions depuis agent_interactions_log.csv
    
    Returns:
        DataFrame avec les colonnes: input_text, agent_output, success
    """
    print("\n📂 Chargement des vraies données Monday.com...")
    
    csv_path = Path(__file__).parent.parent / "data/golden_datasets/agent_interactions_log.csv"
    
    if not csv_path.exists():
        print(f"❌ Fichier introuvable: {csv_path}")
        return None
    
    df = pd.read_csv(csv_path)
    
    # Filtrer seulement les interactions réussies
    df_success = df[df['success'] == True].copy()
    
    # Nettoyer les NaN
    df_success['input_text'] = df_success['input_text'].fillna("")
    df_success['agent_output'] = df_success['agent_output'].fillna("")
    
    # Filtrer les lignes vides
    df_success = df_success[
        (df_success['input_text'].str.len() > 10) & 
        (df_success['agent_output'].str.len() > 10)
    ]
    
    print(f"✅ {len(df_success)} interactions réussies chargées")
    print(f"   Total original: {len(df)} interactions")
    print(f"   Filtrées: {len(df) - len(df_success)} (échecs ou données vides)")
    
    return df_success


async def evaluer_interaction_reelle(
    judge: LLMJudgeServiceSimplified,
    input_text: str,
    agent_output: str,
    index: int,
    total: int,
    verbose: bool = False
):
    """
    Évalue une interaction réelle avec le LLM-as-judge
    
    Args:
        judge: Service LLM-as-judge
        input_text: Question de l'utilisateur
        agent_output: Réponse générée par l'agent
        index: Index de l'interaction
        total: Nombre total de tests
        verbose: Afficher les détails (False par défaut)
        
    Returns:
        Résultat de l'évaluation
    """
    # Affichage simplifié : juste une ligne de progression
    print(f"🧪 Test {index + 1}/{total}... ", end='', flush=True)
    
    # Pour l'évaluation, l'output_reference est le même que agent_output
    # car ce sont des données réelles, on teste juste si le système fonctionne
    # On pourrait aussi demander au LLM de juger la qualité de la réponse de façon absolue
    
    # Option 1: Évaluation "neutre" - l'output est-il de bonne qualité ?
    output_reference = "Une réponse complète, précise et actionnnable qui répond correctement à la question de l'utilisateur."
    
    try:
        result = await judge.evaluate_response(
            reference_input=input_text,
            reference_output=output_reference,
            adam_response=agent_output
        )
        
        # Afficher juste le résultat
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        print(f"{status} (Score: {result['llm_score']}/100)")
        
        # Le résultat est déjà au bon format dict
        return result
        
    except Exception as e:
        print(f"❌ ERREUR")
        logger.error(f"Erreur lors de l'évaluation: {e}", exc_info=True)
        return {
            "timestamp": datetime.now().isoformat(),
            "input_reference": input_text,
            "output_reference": output_reference,
            "agent_output": agent_output,
            "llm_score": 0.0,
            "llm_reasoning": f"Erreur: {str(e)}",
            "passed": False,
            "duration_seconds": None
        }


async def main():
    """
    Fonction principale
    """
    print("\n" + "="*70)
    print("🎯 TEST D'ÉVALUATION AVEC DONNÉES RÉELLES MONDAY.COM")
    print("="*70)
    
    # 1. Charger les vraies données
    df_real = await charger_donnees_reelles()
    
    if df_real is None or len(df_real) == 0:
        print("❌ Aucune donnée réelle disponible")
        return
    
    # 2. Initialiser les services
    print("\n📂 Initialisation des services...")
    manager = GoldenDatasetManager()
    judge = LLMJudgeServiceSimplified(provider="anthropic")
    print("✅ Services initialisés")
    
    # 3. Tester sur quelques interactions (limiter pour la démo)
    num_tests = min(5, len(df_real))  # Max 5 tests
    print(f"\n🧪 Évaluation de {num_tests} interactions réelles...\n")
    
    results = []
    passed = 0
    failed = 0
    total_score = 0
    
    for i in range(num_tests):
        row = df_real.iloc[i]
        
        result = await evaluer_interaction_reelle(
            judge=judge,
            input_text=row['input_text'],
            agent_output=row['agent_output'],
            index=i,
            total=num_tests,
            verbose=False  # Mode silencieux
        )
        
        results.append(result)
        
        if result['passed']:
            passed += 1
        else:
            failed += 1
        
        total_score += result['llm_score']
        
        # Sauvegarder le résultat (silencieusement)
        try:
            manager.save_evaluation_result(result)
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
    
    # 4. Afficher le résumé
    print("\n" + "="*70)
    print("📈 RÉSUMÉ DE L'ÉVALUATION")
    print("="*70)
    print(f"Total de tests: {num_tests}")
    print(f"✅ Réussis: {passed}")
    print(f"❌ Échoués: {failed}")
    print(f"📊 Score moyen: {total_score/num_tests if num_tests > 0 else 0:.1f}/100")
    print(f"🎯 Taux de réussite: {(passed/num_tests*100) if num_tests > 0 else 0:.1f}%")
    
    # 5. Statistiques globales
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
    print("✅ Test terminé avec les données réelles !")
    print("="*70)
    print("\n📝 Notes:")
    print("   • Les données proviennent de agent_interactions_log.csv")
    print("   • Ce sont de VRAIES interactions avec Monday.com")
    print("   • Les résultats sont sauvegardés dans evaluation_results.csv")
    print(f"   • {len(df_real)} interactions disponibles au total")
    print()


if __name__ == "__main__":
    asyncio.run(main())

