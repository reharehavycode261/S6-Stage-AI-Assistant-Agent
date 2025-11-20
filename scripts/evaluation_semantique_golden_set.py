#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Évaluation sémantique intelligente avec le Golden Set

Le LLM Judge compare chaque réponse de l'agent avec TOUTES les réponses
du Golden Set pour trouver les correspondances sémantiques.

Approche:
1. Pour chaque réponse agent, chercher les réponses Golden similaires
2. Évaluer la correspondance sémantique
3. Donner un score global de qualité
"""

import sys
from pathlib import Path
import pandas as pd
import asyncio
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from services.evaluation.llm_judge_service_simplified import LLMJudgeServiceSimplified
from utils.logger import get_logger

logger = get_logger(__name__)


async def charger_golden_set_reference():
    """Charge le Golden Set de référence (91 exemples parfaits)"""
    print("\n📂 Chargement du Golden Set de référence...")
    
    csv_path = Path(__file__).parent.parent / "data/golden_datasets/golden_sets.csv"
    
    if not csv_path.exists():
        print(f"❌ Fichier introuvable: {csv_path}")
        return None
    
    df = pd.read_csv(csv_path)
    print(f"✅ {len(df)} exemples de référence chargés")
    
    return df


async def charger_reponses_agent():
    """Charge les vraies réponses de l'agent depuis Monday"""
    print("\n📂 Chargement des réponses de l'agent...")
    
    csv_path = Path(__file__).parent.parent / "data/golden_datasets/agent_interactions_log.csv"
    
    if not csv_path.exists():
        print(f"❌ Fichier introuvable: {csv_path}")
        return None
    
    df = pd.read_csv(csv_path)
    df_success = df[df['success'] == True].copy()
    
    # Nettoyer
    df_success['input_text'] = df_success['input_text'].fillna("")
    df_success['agent_output'] = df_success['agent_output'].fillna("")
    
    # Filtrer les vides
    df_success = df_success[
        (df_success['input_text'].str.len() > 10) & 
        (df_success['agent_output'].str.len() > 10)
    ]
    
    print(f"✅ {len(df_success)} réponses agent chargées")
    
    return df_success


async def evaluer_avec_correspondance_semantique(
    judge: LLMJudgeServiceSimplified,
    reponses_agent: pd.DataFrame,
    golden_set: pd.DataFrame
):
    """
    Évalue les réponses de l'agent en les comparant sémantiquement
    avec TOUTES les réponses du Golden Set
    
    Args:
        judge: Service LLM Judge
        reponses_agent: DataFrame avec les réponses de l'agent
        golden_set: DataFrame avec les 91 exemples de référence
        
    Returns:
        Résultat d'évaluation avec score global
    """
    print(f"\n⚖️  Évaluation sémantique intelligente...")
    print(f"   {len(reponses_agent)} réponses agent vs {len(golden_set)} exemples Golden Set\n")
    
    # Construire le contexte pour le LLM
    evaluation_text = f"""Tu es un évaluateur expert qui doit comparer les réponses d'un agent IA avec une base de référence (Golden Set).

📚 GOLDEN SET (Base de référence - {len(golden_set)} exemples de réponses PARFAITES):

"""
    
    # Ajouter un échantillon du Golden Set (limiter pour ne pas dépasser le contexte)
    golden_sample_size = min(30, len(golden_set))  # Max 30 exemples pour le contexte
    for idx, row in golden_set.head(golden_sample_size).iterrows():
        evaluation_text += f"\n[Exemple Golden #{idx+1}]\n"
        evaluation_text += f"Question: {row['input']}\n"
        evaluation_text += f"Réponse parfaite: {row['output'][:200]}...\n"
    
    if len(golden_set) > golden_sample_size:
        evaluation_text += f"\n... et {len(golden_set) - golden_sample_size} autres exemples\n"
    
    evaluation_text += f"\n\n{'='*70}\n\n"
    evaluation_text += f"🤖 RÉPONSES DE L'AGENT À ÉVALUER ({len(reponses_agent)} réponses):\n\n"
    
    # Ajouter les réponses de l'agent
    for idx, row in reponses_agent.iterrows():
        evaluation_text += f"\n[Réponse Agent #{idx+1}]\n"
        evaluation_text += f"Question: {row['input_text'][:150]}\n"
        evaluation_text += f"Réponse: {row['agent_output'][:300]}...\n"
    
    # Instruction pour le LLM
    reference_output = f"""Évalue la qualité GLOBALE de l'agent en comparant ses {len(reponses_agent)} réponses avec la base Golden Set de {len(golden_set)} exemples.

MÉTHODOLOGIE D'ÉVALUATION :

1. **Correspondance Sémantique** (40 pts):
   - Pour chaque réponse agent, cherche si une réponse similaire existe dans le Golden Set
   - Évalue si le contenu et la structure correspondent
   - Une réponse agent peut correspondre à plusieurs exemples Golden
   - Compte le nombre de correspondances trouvées

2. **Qualité du Contenu** (30 pts):
   - Les réponses sont-elles complètes et précises ?
   - Le niveau de détail est-il comparable au Golden Set ?
   - Les informations sont-elles correctes ?

3. **Style et Format** (20 pts):
   - Le style de réponse est-il cohérent avec le Golden Set ?
   - La structure est-elle claire et professionnelle ?
   - Le format (listes, étapes, exemples) est-il approprié ?

4. **Couverture des Connaissances** (10 pts):
   - L'agent démontre-t-il une connaissance comparable au Golden Set ?
   - Les réponses couvrent-elles les domaines représentés dans le Golden Set ?

IMPORTANT:
- Ne cherche PAS de correspondance exacte (input ID)
- Cherche des correspondances SÉMANTIQUES (contenu similaire)
- Une réponse agent peut correspondre partiellement à plusieurs exemples Golden
- Évalue la qualité globale, pas chaque réponse individuellement

Donne UN SEUL score global /100."""
    
    try:
        result = await judge.evaluate_response(
            reference_input=evaluation_text,
            reference_output=reference_output,
            adam_response=f"Agent évalué sur {len(reponses_agent)} réponses vs {len(golden_set)} exemples Golden"
        )
        
        # Ajouter métadonnées
        result['agent_responses_count'] = len(reponses_agent)
        result['golden_set_size'] = len(golden_set)
        result['evaluation_type'] = 'semantic_matching'
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de l'évaluation: {e}", exc_info=True)
        return {
            "timestamp": datetime.now().isoformat(),
            "input_reference": f"{len(reponses_agent)} réponses agent",
            "output_reference": reference_output,
            "agent_output": f"Évaluation sémantique vs {len(golden_set)} exemples",
            "llm_score": 0.0,
            "llm_reasoning": f"Erreur: {str(e)}",
            "passed": False,
            "duration_seconds": None,
            "agent_responses_count": len(reponses_agent),
            "golden_set_size": len(golden_set),
            "evaluation_type": 'semantic_matching'
        }


async def main():
    """Fonction principale"""
    print("\n" + "="*70)
    print("🎯 ÉVALUATION SÉMANTIQUE INTELLIGENTE")
    print("   Comparaison agent vs Golden Set (sans mapping IDs)")
    print("="*70)
    
    # 1. Charger le Golden Set de référence (91 exemples)
    golden_set = await charger_golden_set_reference()
    
    if golden_set is None or len(golden_set) == 0:
        print("❌ Golden Set vide ou introuvable")
        return
    
    # 2. Charger les réponses réelles de l'agent
    reponses_agent = await charger_reponses_agent()
    
    if reponses_agent is None or len(reponses_agent) == 0:
        print("❌ Aucune réponse agent disponible")
        return
    
    # 3. Initialiser les services
    print("\n📂 Initialisation du LLM Judge...")
    judge = LLMJudgeServiceSimplified(provider="anthropic")
    manager = GoldenDatasetManager()
    print("✅ Services initialisés")
    
    # 4. Évaluation sémantique
    result = await evaluer_avec_correspondance_semantique(
        judge, reponses_agent, golden_set
    )
    
    # 5. Afficher les résultats
    print("\n" + "="*70)
    print("📈 RÉSULTAT DE L'ÉVALUATION SÉMANTIQUE")
    print("="*70)
    
    print(f"\n🎯 Score Global: {result['llm_score']}/100")
    print(f"   Statut: {'✅ PASS' if result['passed'] else '❌ FAIL'} (seuil: 70)")
    
    print(f"\n📊 Détails:")
    print(f"   • Réponses agent évaluées: {result['agent_responses_count']}")
    print(f"   • Exemples Golden Set: {result['golden_set_size']}")
    print(f"   • Type d'évaluation: {result['evaluation_type']}")
    
    print(f"\n💡 Raisonnement du LLM Judge:")
    reasoning_lines = result['llm_reasoning'].split('\n')
    for line in reasoning_lines[:15]:  # 15 premières lignes
        if line.strip():
            print(f"   {line}")
    if len(reasoning_lines) > 15:
        print(f"   ... ({len(reasoning_lines) - 15} lignes supplémentaires)")
    
    # 6. Sauvegarder
    print("\n📁 Sauvegarde du résultat...")
    try:
        result['input_reference'] = f"Évaluation sémantique: {result['agent_responses_count']} réponses vs {result['golden_set_size']} exemples"
        result['agent_output'] = f"Correspondance sémantique intelligente"
        
        # Retirer métadonnées non-CSV
        result_to_save = {k: v for k, v in result.items() if k not in ['agent_responses_count', 'golden_set_size', 'evaluation_type']}
        
        manager.save_evaluation_result(result_to_save)
        print("✅ Résultat sauvegardé dans evaluation_results.csv")
    except Exception as e:
        print(f"⚠️  Erreur sauvegarde: {e}")
    
    # 7. Interpréter
    print("\n" + "="*70)
    print("🎯 INTERPRÉTATION")
    print("="*70)
    
    score = result['llm_score']
    
    if score >= 90:
        print("\n🌟 EXCELLENT (90-100)")
        print("   L'agent produit des réponses de qualité comparable au Golden Set.")
        print("   Les réponses correspondent sémantiquement aux exemples de référence.")
    elif score >= 70:
        print("\n✅ BIEN (70-89)")
        print("   L'agent produit de bonnes réponses.")
        print("   Quelques différences avec le Golden Set mais qualité satisfaisante.")
    elif score >= 50:
        print("\n⚠️  MOYEN (50-69)")
        print("   L'agent produit des réponses correctes mais manque de profondeur.")
        print("   Écart notable avec le niveau du Golden Set.")
    else:
        print("\n❌ INSUFFISANT (0-49)")
        print("   Les réponses de l'agent ne correspondent pas au Golden Set.")
        print("   Amélioration majeure nécessaire.")
    
    print("\n💡 Avantages de cette approche:")
    print("   • Pas besoin de mapping exact des IDs")
    print("   • Correspondance sémantique intelligente")
    print("   • Une réponse peut correspondre à plusieurs exemples")
    print("   • Évaluation de la qualité globale")
    
    print("\n" + "="*70)
    print("✅ Évaluation terminée !")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())

