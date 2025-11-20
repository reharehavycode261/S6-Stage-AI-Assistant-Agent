#!/usr/bin/env python3
"""
Analyse sémantique détaillée avec le LLM Judge.
Compare chaque interaction individuellement pour un verdict précis.
"""

import pandas as pd
import asyncio
from pathlib import Path
import sys

# Ajouter le chemin racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.evaluation.llm_judge_service_simplified import LLMJudgeServiceSimplified
from utils.logger import get_logger

logger = get_logger(__name__)

async def evaluate_single_interaction(
    judge: LLMJudgeServiceSimplified,
    interaction_input: str,
    interaction_output: str,
    golden_set: pd.DataFrame,
    interaction_num: int
):
    """Évalue une interaction contre le Golden Set."""
    
    print(f"\n{'='*80}")
    print(f"🔍 ÉVALUATION INTERACTION #{interaction_num}")
    print(f"{'='*80}")
    print(f"\n📝 Input: {interaction_input[:100]}...")
    print(f"✅ Output: {interaction_output[:150]}...")
    
    # Préparer le contexte pour le LLM
    golden_examples = "\n\n".join([
        f"Golden Example #{i+1}:\n"
        f"Input: {row['input_text_original']}\n"
        f"Output: {row['output'][:200]}..."
        for i, row in golden_set.head(20).iterrows()  # Top 20 exemples
    ])
    
    # Prompt pour évaluation détaillée
    evaluation_prompt = f"""Tu es un évaluateur expert. Analyse si cette interaction de l'agent correspond au Golden Set.

INTERACTION AGENT:
Input: {interaction_input}
Output: {interaction_output}

EXEMPLES DU GOLDEN SET (20 premiers):
{golden_examples}

ÉVALUE:
1. Est-ce que l'input de l'agent correspond au PATTERN des inputs du Golden Set ?
2. Est-ce que l'output de l'agent correspond au STYLE des outputs du Golden Set ?
3. Est-ce que le DOMAINE de la question est le même ?

Réponds en JSON avec:
{{
  "pattern_match": true/false,
  "style_match": true/false,
  "domain_match": true/false,
  "score": 0-100,
  "reasoning": "explication détaillée"
}}
"""

    reference_output = """Évalue la COMPATIBILITÉ entre l'interaction agent et le Golden Set.
    
Score:
- 80-100: Parfaite correspondance (même pattern, style, domaine)
- 60-79: Bonne correspondance (2/3 critères)
- 40-59: Correspondance partielle (1/3 critères)
- 0-39: Pas de correspondance (domaines différents)
"""
    
    try:
        result = await judge.evaluate_response(
            reference_input=evaluation_prompt,
            reference_output=reference_output,
            adam_response=f"Interaction: {interaction_input}\nRéponse: {interaction_output}"
        )
        
        print(f"\n📊 Résultat:")
        print(f"   Score: {result['llm_score']}/100")
        print(f"   Status: {'✅ COMPATIBLE' if result['passed'] else '❌ INCOMPATIBLE'}")
        print(f"\n💭 Raisonnement:")
        reasoning_lines = result['llm_reasoning'].split('\n')[:5]
        for line in reasoning_lines:
            if line.strip():
                print(f"   {line.strip()[:100]}")
        
        return {
            'interaction_num': interaction_num,
            'score': result['llm_score'],
            'passed': result['passed'],
            'reasoning': result['llm_reasoning']
        }
        
    except Exception as e:
        logger.error(f"Erreur évaluation interaction #{interaction_num}: {e}")
        return {
            'interaction_num': interaction_num,
            'score': 0,
            'passed': False,
            'reasoning': f"Erreur: {e}"
        }


async def main():
    print("\n" + "=" * 80)
    print("🎯 ANALYSE SÉMANTIQUE DÉTAILLÉE (LLM JUDGE)")
    print("   Évaluation interaction par interaction")
    print("=" * 80)
    
    # Chemins
    base_path = Path(__file__).parent.parent / "data/golden_datasets"
    logs_path = base_path / "agent_interactions_log.csv"
    golden_path = base_path / "golden_sets_detailed.csv"
    
    # Charger les données
    print("\n📂 Chargement des données...")
    df_logs = pd.read_csv(logs_path)
    df_golden = pd.read_csv(golden_path)
    
    # Filtrer les interactions réelles
    df_real = df_logs.iloc[3:].copy()
    
    print(f"✅ {len(df_real)} interactions réelles chargées")
    print(f"✅ {len(df_golden)} exemples Golden Set chargés")
    
    # Initialiser le LLM Judge
    print("\n🤖 Initialisation du LLM Judge...")
    judge = LLMJudgeServiceSimplified(provider="anthropic")
    print("✅ LLM Judge prêt")
    
    # Évaluer chaque interaction
    results = []
    
    for idx, row in df_real.iterrows():
        result = await evaluate_single_interaction(
            judge=judge,
            interaction_input=row['input_text'],
            interaction_output=row['agent_output'],
            golden_set=df_golden,
            interaction_num=idx - 2
        )
        results.append(result)
        
        # Pause pour éviter rate limiting
        await asyncio.sleep(2)
    
    # Calculer les statistiques
    print("\n" + "=" * 80)
    print("📊 STATISTIQUES GLOBALES")
    print("=" * 80)
    
    total = len(results)
    compatible = sum(1 for r in results if r['passed'])
    incompatible = total - compatible
    avg_score = sum(r['score'] for r in results) / total if total > 0 else 0
    
    print(f"\n📈 Résumé:")
    print(f"   • Total interactions: {total}")
    print(f"   • Compatible (≥70): {compatible} ({compatible/total*100:.1f}%)")
    print(f"   • Incompatible (<70): {incompatible} ({incompatible/total*100:.1f}%)")
    print(f"   • Score moyen: {avg_score:.1f}/100")
    
    # Verdict final
    print("\n" + "=" * 80)
    print("🎯 VERDICT FINAL")
    print("=" * 80)
    
    if incompatible >= total * 0.6:  # 60% ou plus incompatible
        print("\n❌ ÉVALUATION GLOBALE: FAUSSÉE")
        print(f"   Raison: {incompatible}/{total} interactions ({incompatible/total*100:.0f}%)")
        print("   sont INCOMPATIBLES avec le Golden Set")
        print(f"\n   Score moyen: {avg_score:.1f}/100")
        print("   Score évaluation réelle: 75/100")
        print("\n   ⚠️  Le score de 75/100 est NON FIABLE car:")
        print("   • La majorité des questions ne correspondent pas au Golden Set")
        print("   • Les domaines sont différents")
        print("   • Pas de référence pour ces types de questions")
        verdict = "FAUSSÉE"
    elif incompatible >= total * 0.4:  # 40-60% incompatible
        print("\n⚠️  ÉVALUATION GLOBALE: PARTIELLEMENT FAUSSÉE")
        print(f"   Raison: {incompatible}/{total} interactions ({incompatible/total*100:.0f}%)")
        print("   ne correspondent pas au Golden Set")
        print(f"\n   Score moyen compatibilité: {avg_score:.1f}/100")
        print("   Score évaluation réelle: 75/100")
        print("\n   ⚠️  Le score de 75/100 est PARTIELLEMENT FIABLE:")
        print("   • Certaines questions correspondent")
        print("   • D'autres sont hors scope")
        print("   • Utiliser avec prudence")
        verdict = "PARTIELLEMENT FAUSSÉE"
    else:  # Moins de 40% incompatible
        print("\n✅ ÉVALUATION GLOBALE: VALIDE")
        print(f"   Raison: {compatible}/{total} interactions ({compatible/total*100:.0f}%)")
        print("   sont COMPATIBLES avec le Golden Set")
        print(f"\n   Score moyen compatibilité: {avg_score:.1f}/100")
        print("   Score évaluation réelle: 75/100")
        print("\n   ✅ Le score de 75/100 est FIABLE:")
        print("   • La majorité correspond au Golden Set")
        print("   • Les patterns sont similaires")
        print("   • L'évaluation est représentative")
        verdict = "VALIDE"
    
    print("\n" + "=" * 80)
    print(f"🏁 RÉSULTAT: {verdict}")
    print("=" * 80)
    
    # Recommandations
    print("\n💡 RECOMMANDATIONS:")
    
    if verdict == "FAUSSÉE":
        print("\n   ❌ Le système d'évaluation actuel n'est PAS adapté")
        print("   ✅ Actions recommandées:")
        print("      1. Créer un nouveau Golden Set pour les analyses de projets")
        print("      2. Utiliser les logs réels comme base")
        print("      3. Ajouter 20-30 exemples de questions similaires")
        print("      4. Séparer l'évaluation en 2 catégories distinctes")
    elif verdict == "PARTIELLEMENT FAUSSÉE":
        print("\n   ⚠️  Le système d'évaluation a des lacunes")
        print("   ✅ Actions recommandées:")
        print("      1. Enrichir le Golden Set avec des exemples mixtes")
        print("      2. Documenter les limitations actuelles")
        print("      3. Ajouter au moins 10 exemples d'analyse de projets")
        print("      4. Suivre l'évolution du score dans le temps")
    else:
        print("\n   ✅ Le système d'évaluation fonctionne correctement")
        print("   ✅ Actions recommandées:")
        print("      1. Continuer avec le Golden Set actuel")
        print("      2. Monitorer les nouveaux types de questions")
        print("      3. Mettre à jour régulièrement")
        print("      4. Maintenir la qualité des réponses")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

