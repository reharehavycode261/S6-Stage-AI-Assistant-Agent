#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour prévisualiser le contenu des fichiers CSV Golden Datasets.
Usage: python scripts/preview_csv_data.py
"""

import pandas as pd
from pathlib import Path

def preview_csv_data():
    """Affiche un aperçu des données CSV."""
    
    # Chemins
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "golden_datasets"
    
    print("=" * 80)
    print("📊 APERÇU DES FICHIERS CSV - GOLDEN DATASETS")
    print("=" * 80)
    
    # 1. Golden Sets
    print("\n🧪 FEUILLE 1 : GOLDEN_SETS (Tests de référence)")
    print("-" * 80)
    
    try:
        df_golden = pd.read_csv(data_dir / "golden_sets.csv")
        print(f"✅ {len(df_golden)} tests chargés\n")
        
        # Statistiques
        print("📈 Statistiques :")
        print(f"   • Tests d'analyse (type=analysis) : {len(df_golden[df_golden['test_type'] == 'analysis'])}")
        print(f"   • Tests de PR (type=pr) : {len(df_golden[df_golden['test_type'] == 'pr'])}")
        print(f"   • Tests actifs : {len(df_golden[df_golden['active'] == True])}")
        print(f"   • Tests haute priorité : {len(df_golden[df_golden['priority'] == 'high'])}")
        
        # Aperçu des premiers tests
        print("\n📋 Premiers tests :")
        for idx, row in df_golden.head(3).iterrows():
            print(f"\n   [{row['test_id']}] {row['test_type'].upper()}")
            print(f"   Input: {row['input_monday_update'][:60]}...")
            print(f"   Expected: {row['expected_output'][:60]}...")
            print(f"   Critères: {row['evaluation_criteria']}")
            print(f"   Priorité: {row['priority']} | Actif: {row['active']}")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    # 2. Evaluation Results
    print("\n\n📈 FEUILLE 2 : EVALUATION_RESULTS (Résultats d'évaluation)")
    print("-" * 80)
    
    try:
        df_eval = pd.read_csv(data_dir / "evaluation_results.csv")
        print(f"✅ {len(df_eval)} évaluations chargées\n")
        
        # Statistiques
        print("📊 Statistiques :")
        print(f"   • Tests PASS (score ≥70) : {len(df_eval[df_eval['status'] == 'PASS'])}")
        print(f"   • Tests FAIL (score <70) : {len(df_eval[df_eval['status'] == 'FAIL'])}")
        print(f"   • Taux de réussite : {len(df_eval[df_eval['status'] == 'PASS']) / len(df_eval) * 100:.1f}%")
        print(f"   • Score LLM moyen : {df_eval['llm_score'].mean():.1f}/100")
        print(f"   • Score humain moyen : {df_eval['human_score'].dropna().mean():.1f}/100")
        print(f"   • Score final moyen : {df_eval['final_score'].mean():.1f}/100")
        print(f"   • Durée moyenne : {df_eval['duration_seconds'].mean():.1f}s")
        
        # Validations humaines
        print(f"\n🙋 Validation humaine :")
        print(f"   • Validées : {len(df_eval[df_eval['human_validation_status'] == 'validated'])}")
        print(f"   • En attente : {len(df_eval[df_eval['human_validation_status'] == 'pending'])}")
        print(f"   • À revoir : {len(df_eval[df_eval['human_validation_status'] == 'to_review'])}")
        
        # Top 3 meilleurs scores
        print("\n🏆 Top 3 meilleurs scores :")
        top3 = df_eval.nlargest(3, 'final_score')
        for idx, row in top3.iterrows():
            print(f"   • {row['test_id']} : {row['final_score']:.1f}/100 ({row['status']})")
        
        # Tests échoués
        failed = df_eval[df_eval['status'] == 'FAIL']
        if len(failed) > 0:
            print(f"\n⚠️ Tests échoués ({len(failed)}) :")
            for idx, row in failed.iterrows():
                print(f"   • {row['test_id']} : {row['final_score']:.1f}/100")
                print(f"     Raison: {row['llm_reasoning'][:80]}...")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    # 3. Performance Metrics
    print("\n\n📊 FEUILLE 3 : PERFORMANCE_METRICS (Métriques quotidiennes)")
    print("-" * 80)
    
    try:
        df_metrics = pd.read_csv(data_dir / "performance_metrics.csv")
        print(f"✅ {len(df_metrics)} jours de métriques chargés\n")
        
        # Dernière semaine
        print("📅 Dernière semaine (7 jours les plus récents) :")
        recent = df_metrics.head(7)
        
        for idx, row in recent.iterrows():
            status_icon = {
                'excellent': '🟢',
                'good': '🟡',
                'needs_improvement': '🔴'
            }.get(row['reliability_status'], '⚪')
            
            print(f"\n   {row['metric_date']} {status_icon} {row['reliability_status'].upper()}")
            print(f"   └─ Tests: {row['total_tests_run']} | Pass rate: {row['pass_rate_percent']}% | Score: {row['avg_final_score']:.1f}")
            if row['notes']:
                print(f"      Notes: {row['notes']}")
        
        # Tendances
        print("\n📈 Tendances :")
        print(f"   • Score final moyen (période) : {df_metrics['avg_final_score'].mean():.1f}/100")
        print(f"   • Taux de réussite moyen : {df_metrics['pass_rate_percent'].mean():.1f}%")
        print(f"   • Jours excellents (≥85) : {len(df_metrics[df_metrics['reliability_status'] == 'excellent'])}")
        print(f"   • Jours à améliorer (<70) : {len(df_metrics[df_metrics['reliability_status'] == 'needs_improvement'])}")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    print("\n" + "=" * 80)
    print("✅ Aperçu terminé !")
    print("=" * 80)
    print("\n💡 Pour convertir en Excel, lancez : python scripts/csv_to_excel.py")
    print("📖 Documentation complète : data/golden_datasets/README_CSV.md\n")


if __name__ == "__main__":
    preview_csv_data()











