"""
Analyse complète des correspondances entre les logs réels et le Golden Set.
Compare chaque interaction pour déterminer si l'évaluation est faussée.
"""

import pandas as pd
from pathlib import Path

def main():
    print("\n" + "=" * 80)
    print("🔍 ANALYSE DÉTAILLÉE: LOGS RÉELS vs GOLDEN SET")
    print("=" * 80)
    
    base_path = Path(__file__).parent.parent / "data/golden_datasets"
    logs_path = base_path / "agent_interactions_log.csv"
    golden_path = base_path / "golden_sets_detailed.csv"
    
    print("\n📂 Chargement des données...")
    df_logs = pd.read_csv(logs_path)
    df_golden = pd.read_csv(golden_path)
    
    df_real = df_logs.iloc[3:].copy()
    
    print(f"✅ {len(df_real)} interactions réelles chargées")
    print(f"✅ {len(df_golden)} exemples Golden Set chargés")
    
    print("\n" + "=" * 80)
    print("📊 ANALYSE INTERACTION PAR INTERACTION")
    print("=" * 80)
    
    correspondances = []
    
    for idx, log_row in df_real.iterrows():
        print(f"\n🔹 INTERACTION #{idx-2}")
        print(f"   📝 Input: {log_row['input_text'][:80]}...")
        print(f"   Type: {log_row['interaction_type']}")
        
        input_lower = str(log_row['input_text']).lower()
        
        is_feature_check = any(keyword in input_lower for keyword in [
            "est ce que", "existe dans le projet", "est présent", 
            "fonctionnalité", "implémenté", "disponible"
        ])
        
        is_project_analysis = "projet" in input_lower or "repository" in input_lower
        
        print(f"\n   🎯 Classification:")
        print(f"      • Question sur fonctionnalité externe: {is_feature_check}")
        print(f"      • Analyse de projet externe: {is_project_analysis}")
        
        found_matches = []
        
        for _, golden_row in df_golden.iterrows():
            golden_input = str(golden_row['input_text_original']).lower()
            
            if "structure" in input_lower and "structure" in golden_input:
                found_matches.append({
                    'id': golden_row['input'],
                    'input': golden_row['input_text_original'][:60],
                    'similarity': 40,
                    'reason': "Pattern 'structure' commun"
                })
            
            if is_feature_check and ("comment" in golden_input or "quels sont" in golden_input):
                found_matches.append({
                    'id': golden_row['input'],
                    'input': golden_row['input_text_original'][:60],
                    'similarity': 30,
                    'reason': "Questions documentaires"
                })
        
        found_matches = sorted(found_matches, key=lambda x: x['similarity'], reverse=True)[:3]
        
        if found_matches:
            print(f"\n   ✅ Correspondances trouvées: {len(found_matches)}")
            for match in found_matches:
                print(f"      • {match['id']}: {match['input']}...")
                print(f"        Similarité: {match['similarity']}% - {match['reason']}")
            correspondances.append({
                'interaction': idx-2,
                'has_match': True,
                'best_similarity': found_matches[0]['similarity']
            })
        else:
            print(f"\n   ❌ AUCUNE correspondance trouvée dans le Golden Set")
            print(f"      Raison: Pattern de question non couvert")
            correspondances.append({
                'interaction': idx-2,
                'has_match': False,
                'best_similarity': 0
            })
    
    print("\n" + "=" * 80)
    print("📈 STATISTIQUES GLOBALES")
    print("=" * 80)
    
    total = len(correspondances)
    with_match = sum(1 for c in correspondances if c['has_match'])
    without_match = total - with_match
    avg_similarity = sum(c['best_similarity'] for c in correspondances) / total if total > 0 else 0
    
    print(f"\n📊 Résumé:")
    print(f"   • Total interactions: {total}")
    print(f"   • Avec correspondance: {with_match} ({with_match/total*100:.1f}%)")
    print(f"   • Sans correspondance: {without_match} ({without_match/total*100:.1f}%)")
    print(f"   • Similarité moyenne: {avg_similarity:.1f}%")
    
    print("\n" + "=" * 80)
    print("🎯 VERDICT FINAL")
    print("=" * 80)
    
    if without_match >= total * 0.6:  
        print("\n❌ ÉVALUATION FAUSSÉE")
        print(f"   Raison: {without_match}/{total} interactions ({without_match/total*100:.0f}%)")
        print("   n'ont AUCUNE correspondance dans le Golden Set")
        print("\n   Le score de 75/100 est NON REPRÉSENTATIF car:")
        print("   • Les questions portent sur l'analyse de projets externes")
        print("   • Le Golden Set couvre l'architecture interne de l'agent")
        print("   • Il n'y a pas de référence pour évaluer ces réponses")
        verdict = "FAUSSÉE"
    elif without_match >= total * 0.4: 
        print("\n⚠️  ÉVALUATION PARTIELLEMENT FAUSSÉE")
        print(f"   Raison: {without_match}/{total} interactions ({without_match/total*100:.0f}%)")
        print("   n'ont pas de correspondance directe")
        print("\n   Le score de 75/100 est PARTIELLEMENT VALIDE:")
        print("   • Certaines questions correspondent au Golden Set")
        print("   • D'autres sont hors scope du Golden Set")
        print("   • Le score reflète un mélange de qualité et d'inadéquation")
        verdict = "PARTIELLEMENT FAUSSÉE"
    else:  
        print("\n✅ ÉVALUATION VALIDE")
        print(f"   Raison: {with_match}/{total} interactions ({with_match/total*100:.0f}%)")
        print("   ont une correspondance dans le Golden Set")
        print("\n   Le score de 75/100 est REPRÉSENTATIF car:")
        print("   • La majorité des questions correspondent au Golden Set")
        print("   • Les patterns sont compatibles")
        print("   • L'évaluation compare des éléments similaires")
        verdict = "VALIDE"
    
    print("\n" + "=" * 80)
    print(f"🏁 RÉSULTAT: {verdict}")
    print("=" * 80)
    
    print("\n💡 RECOMMANDATIONS:")
    
    if verdict == "FAUSSÉE":
        print("\n   1. ❌ NE PAS utiliser ce score pour évaluer l'agent")
        print("   2. ✅ Créer un nouveau Golden Set adapté aux questions d'analyse")
        print("   3. ✅ Séparer en 2 Golden Sets:")
        print("      • Golden Set A: Architecture agent (existant)")
        print("      • Golden Set B: Analyse projets (à créer)")
        print("   4. ✅ Utiliser les 5 logs réels comme base pour Golden Set B")
    elif verdict == "PARTIELLEMENT FAUSSÉE":
        print("\n   1. ⚠️  Utiliser ce score avec prudence")
        print("   2. ✅ Enrichir le Golden Set avec des questions d'analyse")
        print("   3. ✅ Documenter les limitations du score actuel")
        print("   4. ✅ Ajouter au moins 20 exemples de questions similaires")
    else:
        print("\n   1. ✅ Le score de 75/100 est fiable")
        print("   2. ✅ Continuer à utiliser ce Golden Set")
        print("   3. ✅ Monitorer les nouvelles interactions")
        print("   4. ✅ Mettre à jour le Golden Set régulièrement")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()

