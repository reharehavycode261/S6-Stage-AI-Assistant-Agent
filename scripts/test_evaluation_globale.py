#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test d'évaluation GLOBALE avec les VRAIES données Monday.com

Ce script évalue TOUTES les réponses en une seule fois et donne UN SEUL SCORE GLOBAL.
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
    """Charge les vraies interactions depuis agent_interactions_log.csv"""
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
    
    return df_success


async def evaluer_globalement(
    judge: LLMJudgeServiceSimplified,
    interactions: pd.DataFrame
):
    """
    Évalue TOUTES les interactions en une seule fois
    
    Args:
        judge: Service LLM-as-judge
        interactions: DataFrame avec toutes les interactions
        
    Returns:
        Score global et reasoning
    """
    print(f"\n⚖️  Évaluation globale de {len(interactions)} interactions...")
    print("   (Le LLM analyse toutes les réponses ensemble)\n")
    
    # Construire un texte avec toutes les interactions
    batch_input = "Voici plusieurs questions posées par des utilisateurs et les réponses générées par l'agent IA :\n\n"
    
    for i, row in interactions.iterrows():
        batch_input += f"=== Interaction {i+1} ===\n"
        batch_input += f"❓ Question: {row['input_text'][:200]}...\n"
        batch_input += f"🤖 Réponse: {row['agent_output'][:300]}...\n\n"
    
    # Instruction pour le LLM Judge
    reference_output = f"""Évalue la qualité GLOBALE de l'agent sur ces {len(interactions)} interactions.

Donne UN SEUL score global /100 qui représente:
- La cohérence générale des réponses
- Le niveau de détail moyen
- La précision des informations
- L'utilité des réponses
- La clarté de communication

Le score doit refléter la performance GLOBALE de l'agent, pas chaque réponse individuellement."""
    
    try:
        result = await judge.evaluate_response(
            reference_input=batch_input,
            reference_output=reference_output,
            adam_response=f"Agent évalué sur {len(interactions)} interactions"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de l'évaluation globale: {e}", exc_info=True)
        return {
            "timestamp": datetime.now().isoformat(),
            "input_reference": f"{len(interactions)} interactions",
            "output_reference": reference_output,
            "agent_output": "Évaluation globale",
            "llm_score": 0.0,
            "llm_reasoning": f"Erreur: {str(e)}",
            "passed": False,
            "duration_seconds": None
        }


async def main():
    """Fonction principale"""
    print("\n" + "="*70)
    print("🎯 ÉVALUATION GLOBALE - Données réelles Monday.com")
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
    
    # 3. Limiter le nombre d'interactions pour la démo (optionnel)
    num_tests = min(5, len(df_real))
    df_to_evaluate = df_real.head(num_tests)
    
    print(f"\n📊 {num_tests} interactions à évaluer globalement")
    
    # Afficher la liste des questions
    print("\n📝 Questions à évaluer:")
    for i, row in df_to_evaluate.iterrows():
        print(f"   {i+1}. {row['input_text'][:80]}...")
    
    # 4. ÉVALUATION GLOBALE (1 seul appel LLM)
    result = await evaluer_globalement(judge, df_to_evaluate)
    
    # 5. Afficher le résultat global
    print("\n" + "="*70)
    print("📈 RÉSULTAT DE L'ÉVALUATION GLOBALE")
    print("="*70)
    print(f"\n🎯 Score Global: {result['llm_score']}/100")
    print(f"   Statut: {'✅ PASS' if result['passed'] else '❌ FAIL'} (seuil: 70)")
    print(f"\n💡 Raisonnement:")
    print(f"   {result['llm_reasoning']}")
    
    # 6. Sauvegarder le résultat
    print("\n📁 Sauvegarde du résultat...")
    try:
        # Ajouter des métadonnées
        result['input_reference'] = f"Évaluation globale de {num_tests} interactions"
        result['agent_output'] = f"Performance globale de l'agent"
        
        manager.save_evaluation_result(result)
        print("✅ Résultat sauvegardé dans evaluation_results.csv")
    except Exception as e:
        print(f"⚠️  Erreur sauvegarde: {e}")
    
    # 7. Statistiques
    print("\n" + "="*70)
    print("📊 STATISTIQUES")
    print("="*70)
    print(f"Interactions évaluées: {num_tests}")
    print(f"Score global: {result['llm_score']}/100")
    print(f"Seuil de réussite: 70/100")
    print(f"Performance: {'✅ Satisfaisante' if result['passed'] else '❌ À améliorer'}")
    
    if result['llm_score'] >= 90:
        print("\n🌟 Excellent ! L'agent performe très bien.")
    elif result['llm_score'] >= 70:
        print("\n✅ Bien ! L'agent répond correctement aux attentes.")
    elif result['llm_score'] >= 50:
        print("\n⚠️  Moyen. Des améliorations sont nécessaires.")
    else:
        print("\n❌ Insuffisant. L'agent nécessite des améliorations majeures.")
    
    print("\n" + "="*70)
    print("✅ Évaluation globale terminée !")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())

