#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour convertir les fichiers CSV en un seul fichier Excel avec 3 feuilles.
Usage: python scripts/csv_to_excel.py
"""

import pandas as pd
from pathlib import Path
import sys

def csv_to_excel():
    """Convertit les 3 CSV en un fichier Excel avec 3 feuilles."""
    
    # Chemins
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "golden_datasets"
    
    # Fichiers CSV
    golden_sets_csv = data_dir / "golden_sets.csv"
    evaluation_results_csv = data_dir / "evaluation_results.csv"
    performance_metrics_csv = data_dir / "performance_metrics.csv"
    
    # Fichier Excel de sortie
    excel_output = data_dir / "golden_datasets.xlsx"
    
    # Vérifier que les CSV existent
    if not all([golden_sets_csv.exists(), evaluation_results_csv.exists(), performance_metrics_csv.exists()]):
        print("❌ Erreur: Un ou plusieurs fichiers CSV sont manquants")
        print(f"   Vérifiez que ces fichiers existent dans {data_dir}:")
        print(f"   - golden_sets.csv")
        print(f"   - evaluation_results.csv")
        print(f"   - performance_metrics.csv")
        sys.exit(1)
    
    try:
        print("📂 Lecture des fichiers CSV...")
        
        # Lire les CSV
        df_golden_sets = pd.read_csv(golden_sets_csv)
        df_evaluation_results = pd.read_csv(evaluation_results_csv)
        df_performance_metrics = pd.read_csv(performance_metrics_csv)
        
        print(f"   ✅ Golden Sets: {len(df_golden_sets)} lignes")
        print(f"   ✅ Evaluation Results: {len(df_evaluation_results)} lignes")
        print(f"   ✅ Performance Metrics: {len(df_performance_metrics)} lignes")
        
        print(f"\n📝 Création du fichier Excel: {excel_output}")
        
        # Créer le fichier Excel avec 3 feuilles
        with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
            df_golden_sets.to_excel(writer, sheet_name='Golden_Sets', index=False)
            df_evaluation_results.to_excel(writer, sheet_name='Evaluation_Results', index=False)
            df_performance_metrics.to_excel(writer, sheet_name='Performance_Metrics', index=False)
        
        print(f"✅ Fichier Excel créé avec succès!")
        print(f"\n📊 Contenu:")
        print(f"   • Feuille 1: Golden_Sets ({len(df_golden_sets)} tests)")
        print(f"   • Feuille 2: Evaluation_Results ({len(df_evaluation_results)} évaluations)")
        print(f"   • Feuille 3: Performance_Metrics ({len(df_performance_metrics)} jours)")
        print(f"\n🎯 Vous pouvez maintenant ouvrir {excel_output} dans Excel")
        
    except Exception as e:
        print(f"❌ Erreur lors de la conversion: {e}")
        sys.exit(1)


if __name__ == "__main__":
    csv_to_excel()

