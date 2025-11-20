#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Évaluation finale avec le Golden Set (structure Monday conforme)

Évalue l'agent en comparant ses outputs avec le Golden Set de référence.
Donne UN SEUL SCORE GLOBAL /100 pour toutes les interactions.

Structure:
- input: updateMday_ITEM_ID
- output: Contenu de référence (texte ou JSON PR)
- type: "analysis" ou "pr"
"""

import sys
from pathlib import Path
import pandas as pd
import asyncio
from datetime import datetime
import json

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from services.evaluation.llm_judge_service_simplified import LLMJudgeServiceSimplified
from utils.logger import get_logger

logger = get_logger(__name__)


async def charger_golden_set():
    """Charge le Golden Set"""
    print("\n📂 Chargement du Golden Set...")
    
    csv_path = Path(__file__).parent.parent / "data/golden_datasets/golden_sets.csv"
    
    if not csv_path.exists():
        print(f"❌ Fichier introuvable: {csv_path}")
        print("💡 Exécutez d'abord: python scripts/generer_golden_set_depuis_monday.py")
        return None
    
    df = pd.read_csv(csv_path)
    
    print(f"✅ {len(df)} entrées chargées")
    print(f"   • Analyses: {len(df[df['type'] == 'analysis'])}")
    print(f"   • PR: {len(df[df['type'] == 'pr'])}")
    
    return df


async def charger_outputs_agent():
    """Charge les outputs réels de l'agent depuis agent_interactions_log.csv"""
    print("\n📂 Chargement des outputs de l'agent...")
    
    csv_path = Path(__file__).parent.parent / "data/golden_datasets/agent_interactions_log.csv"
    
    if not csv_path.exists():
        print(f"❌ Fichier introuvable: {csv_path}")
        return None
    
    df = pd.read_csv(csv_path)
    df_success = df[df['success'] == True].copy()
    
    # Créer un mapping updateMday_ITEM_ID → agent_output
    agent_outputs = {}
    for idx, row in df_success.iterrows():
        monday_item_id = row.get('monday_item_id', 'unknown')
        input_id = f"updateMday_{monday_item_id}"
        agent_outputs[input_id] = row.get('agent_output', '')
    
    print(f"✅ {len(agent_outputs)} outputs récupérés")
    
    return agent_outputs


async def evaluer_globalement(
    judge: LLMJudgeServiceSimplified,
    golden_set: pd.DataFrame,
    agent_outputs: dict
):
    """
    Évalue GLOBALEMENT toutes les interactions
    
    Args:
        judge: Service LLM-as-judge
        golden_set: DataFrame du Golden Set
        agent_outputs: Dict mapping input_id → agent_output
        
    Returns:
        Score global et reasoning
    """
    print(f"\n⚖️  Évaluation globale de {len(golden_set)} interactions...")
    print("   (Le LLM compare les outputs agent vs golden set)\n")
    
    # Construire le texte pour le LLM Judge
    evaluation_text = """Évalue la performance GLOBALE de l'agent IA en comparant ses outputs avec les outputs de référence (Golden Set).

Les outputs peuvent être au format texte brut (analyses) ou contenir des informations sur des Pull Requests.

"""
    
    comparisons = []
    analyses_count = 0
    pr_count = 0
    
    for idx, row in golden_set.iterrows():
        input_id = row['input']
        golden_output = row['output']
        interaction_type = row['type']
        
        # Récupérer l'output de l'agent
        agent_output = agent_outputs.get(input_id, "NON TROUVÉ")
        
        if interaction_type == 'analysis':
            analyses_count += 1
        else:
            pr_count += 1
        
        evaluation_text += f"\n{'='*70}\n"
        evaluation_text += f"Interaction #{idx+1} - Type: {interaction_type.upper()}\n"
        evaluation_text += f"{'='*70}\n"
        evaluation_text += f"Input ID: {input_id}\n\n"
        evaluation_text += f"📋 OUTPUT GOLDEN (Référence attendue):\n{golden_output[:500]}...\n\n"
        evaluation_text += f"🤖 OUTPUT AGENT (Produit par l'IA):\n{agent_output[:500]}...\n\n"
        
        comparisons.append({
            'input_id': input_id,
            'type': interaction_type,
            'golden': golden_output,
            'agent': agent_output,
            'match': golden_output.strip().lower() == agent_output.strip().lower()
        })
    
    # Instruction pour le LLM Judge
    reference_output = f"""Évalue la performance GLOBALE de l'agent sur ces {len(golden_set)} interactions ({analyses_count} analyses + {pr_count} PR).

Donne UN SEUL score global /100 qui évalue:

1. **Exactitude** (40 pts): Les outputs agent correspondent-ils aux golden outputs ?
   - Le contenu des réponses est-il similaire ou identique ?
   - Les informations clés sont-elles présentes (numéros de PR, branches, fichiers, etc.) ?

2. **Complétude** (30 pts): Les outputs agent couvrent-ils tous les éléments du golden set ?

3. **Cohérence** (20 pts): Les outputs sont-ils cohérents entre eux ?

4. **Qualité** (10 pts): La présentation et la clarté sont-elles bonnes ?

Le score doit refléter la capacité de l'agent à REPRODUIRE fidèlement les outputs de référence."""
    
    try:
        result = await judge.evaluate_response(
            reference_input=evaluation_text,
            reference_output=reference_output,
            adam_response=f"Agent évalué sur {len(golden_set)} interactions ({analyses_count} analyses, {pr_count} PR)"
        )
        
        # Ajouter les comparaisons dans le résultat
        result['comparisons'] = comparisons
        result['analyses_count'] = analyses_count
        result['pr_count'] = pr_count
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de l'évaluation globale: {e}", exc_info=True)
        return {
            "timestamp": datetime.now().isoformat(),
            "input_reference": f"{len(golden_set)} interactions",
            "output_reference": reference_output,
            "agent_output": "Évaluation globale",
            "llm_score": 0.0,
            "llm_reasoning": f"Erreur: {str(e)}",
            "passed": False,
            "duration_seconds": None,
            "comparisons": comparisons,
            "analyses_count": analyses_count,
            "pr_count": pr_count
        }


async def main():
    """Fonction principale"""
    print("\n" + "="*70)
    print("🎯 ÉVALUATION FINALE - Golden Set (Structure Monday)")
    print("="*70)
    
    # 1. Charger le Golden Set
    golden_set = await charger_golden_set()
    
    if golden_set is None or len(golden_set) == 0:
        print("❌ Golden Set vide ou introuvable")
        return
    
    # 2. Charger les outputs réels de l'agent
    agent_outputs = await charger_outputs_agent()
    
    if agent_outputs is None:
        print("❌ Outputs agent introuvables")
        return
    
    # 3. Afficher les interactions à évaluer
    print("\n📝 Interactions à évaluer:")
    for idx, row in golden_set.iterrows():
        type_icon = "🔍" if row['type'] == 'analysis' else "🔧"
        print(f"   {idx+1}. {type_icon} {row['input']} ({row['type']})")
    
    # 4. Initialiser le LLM Judge
    print("\n📂 Initialisation du LLM Judge...")
    judge = LLMJudgeServiceSimplified(provider="anthropic")
    manager = GoldenDatasetManager()
    print("✅ Services initialisés")
    
    # 5. ÉVALUATION GLOBALE
    result = await evaluer_globalement(judge, golden_set, agent_outputs)
    
    # 6. Afficher le résultat
    print("\n" + "="*70)
    print("📈 RÉSULTAT DE L'ÉVALUATION GLOBALE")
    print("="*70)
    
    print(f"\n🎯 Score Global: {result['llm_score']}/100")
    print(f"   Statut: {'✅ PASS' if result['passed'] else '❌ FAIL'} (seuil: 70)")
    
    print(f"\n📊 Détails:")
    print(f"   • Analyses évaluées: {result['analyses_count']}")
    print(f"   • PR évaluées: {result['pr_count']}")
    print(f"   • Total: {len(golden_set)}")
    
    # Compter les correspondances exactes
    exact_matches = sum(1 for c in result['comparisons'] if c['match'])
    match_rate = (exact_matches / len(result['comparisons']) * 100) if result['comparisons'] else 0
    
    print(f"\n🔍 Correspondances exactes: {exact_matches}/{len(result['comparisons'])} ({match_rate:.1f}%)")
    
    print(f"\n💡 Raisonnement du LLM Judge:")
    reasoning_lines = result['llm_reasoning'].split('\n')
    for line in reasoning_lines[:10]:  # 10 premières lignes
        print(f"   {line}")
    if len(reasoning_lines) > 10:
        print(f"   ... ({len(reasoning_lines) - 10} lignes supplémentaires)")
    
    # 7. Sauvegarder
    print("\n📁 Sauvegarde du résultat...")
    try:
        result['input_reference'] = f"Évaluation Golden Set: {len(golden_set)} interactions"
        result['agent_output'] = f"Performance globale ({result['analyses_count']} analyses, {result['pr_count']} PR)"
        
        # Retirer comparisons avant sauvegarde (trop volumineux pour CSV)
        result_to_save = {k: v for k, v in result.items() if k != 'comparisons'}
        
        manager.save_evaluation_result(result_to_save)
        print("✅ Résultat sauvegardé dans evaluation_results.csv")
    except Exception as e:
        print(f"⚠️  Erreur sauvegarde: {e}")
    
    # 8. Interpréter le score
    print("\n" + "="*70)
    print("🎯 INTERPRÉTATION")
    print("="*70)
    
    score = result['llm_score']
    
    if score >= 90:
        print("\n🌟 EXCELLENT (90-100)")
        print("   L'agent reproduit fidèlement les outputs du Golden Set.")
        print("   Performance exceptionnelle !")
    elif score >= 70:
        print("\n✅ BIEN (70-89)")
        print("   L'agent produit des outputs corrects et cohérents.")
        print("   Quelques ajustements mineurs possibles.")
    elif score >= 50:
        print("\n⚠️  MOYEN (50-69)")
        print("   L'agent produit des résultats partiellement corrects.")
        print("   Des améliorations sont nécessaires.")
    else:
        print("\n❌ INSUFFISANT (0-49)")
        print("   L'agent ne reproduit pas les outputs attendus.")
        print("   Révision majeure nécessaire.")
    
    print("\n" + "="*70)
    print("✅ Évaluation terminée !")
    print("="*70)
    
    print("\n💡 Prochaines étapes:")
    print("   1. Analyser le reasoning du LLM Judge")
    print("   2. Identifier les interactions mal évaluées")
    print("   3. Améliorer les prompts ou le modèle")
    print("   4. Relancer l'évaluation et comparer")


if __name__ == "__main__":
    asyncio.run(main())

