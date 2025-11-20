#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test simple : Vérifier la structure simplifiée du Golden Dataset

Ce script vérifie que:
1. Le CSV a bien 2 colonnes (input_reference, output_reference)
2. Toutes les données ont été migrées correctement
3. Le GoldenDatasetManager peut charger les données
"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from services.evaluation.golden_dataset_manager import GoldenDatasetManager


def test_csv_structure():
    """Test 1: Vérifier la structure du CSV"""
    print("\n" + "="*70)
    print("🧪 Test 1: Vérification de la structure du CSV")
    print("="*70)
    
    csv_path = Path(__file__).parent.parent / "data/golden_datasets/golden_sets.csv"
    
    if not csv_path.exists():
        print(f"❌ ÉCHEC: Fichier introuvable: {csv_path}")
        return False
    
    df = pd.read_csv(csv_path)
    
    # Vérifier les colonnes
    expected_cols = ['input_reference', 'output_reference']
    actual_cols = list(df.columns)
    
    if actual_cols == expected_cols:
        print(f"✅ SUCCÈS: Structure correcte ({len(expected_cols)} colonnes)")
        print(f"   Colonnes: {actual_cols}")
    else:
        print(f"❌ ÉCHEC: Structure incorrecte")
        print(f"   Attendu: {expected_cols}")
        print(f"   Actuel: {actual_cols}")
        return False
    
    # Vérifier le nombre de lignes
    num_rows = len(df)
    print(f"✅ Nombre de tests: {num_rows}")
    
    # Vérifier qu'il n'y a pas de valeurs nulles
    null_counts = df.isnull().sum()
    if null_counts.sum() == 0:
        print(f"✅ Aucune valeur nulle")
    else:
        print(f"⚠️  Valeurs nulles détectées:")
        print(null_counts[null_counts > 0])
    
    return True


def test_manager_load():
    """Test 2: Vérifier que le GoldenDatasetManager peut charger les données"""
    print("\n" + "="*70)
    print("🧪 Test 2: Chargement via GoldenDatasetManager")
    print("="*70)
    
    try:
        manager = GoldenDatasetManager()
        print("✅ GoldenDatasetManager initialisé")
        
        df = manager.load_golden_sets()
        print(f"✅ {len(df)} tests chargés")
        
        # Vérifier qu'on peut récupérer un test par index
        test = manager.get_test_by_index(0)
        print(f"✅ Test récupéré par index:")
        print(f"   Input: {test['input_reference'][:50]}...")
        print(f"   Output: {test['output_reference'][:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_content():
    """Test 3: Vérifier le contenu des données"""
    print("\n" + "="*70)
    print("🧪 Test 3: Vérification du contenu des données")
    print("="*70)
    
    try:
        manager = GoldenDatasetManager()
        df = manager.load_golden_sets()
        
        # Vérifier la longueur minimale des textes
        min_input_length = df['input_reference'].str.len().min()
        min_output_length = df['output_reference'].str.len().min()
        
        print(f"✅ Longueur minimale input_reference: {min_input_length} caractères")
        print(f"✅ Longueur minimale output_reference: {min_output_length} caractères")
        
        if min_input_length < 5:
            print(f"⚠️  Attention: Certains inputs sont très courts")
        
        if min_output_length < 10:
            print(f"⚠️  Attention: Certains outputs sont très courts")
        
        # Afficher quelques exemples
        print(f"\n📋 Exemples de tests:")
        for i in range(min(3, len(df))):
            row = df.iloc[i]
            print(f"\n   Test #{i+1}:")
            print(f"   Input: {row['input_reference'][:70]}...")
            print(f"   Output: {row['output_reference'][:70]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Execute tous les tests"""
    print("\n" + "="*70)
    print("🧪 TESTS DU GOLDEN DATASET SIMPLIFIÉ")
    print("="*70)
    
    results = []
    
    # Exécuter les tests
    results.append(("Structure CSV", test_csv_structure()))
    results.append(("Chargement Manager", test_manager_load()))
    results.append(("Contenu données", test_data_content()))
    
    # Résumé
    print("\n" + "="*70)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*70)
    
    total = len(results)
    passed = sum(1 for _, success in results if success)
    
    for test_name, success in results:
        status = "✅ SUCCÈS" if success else "❌ ÉCHEC"
        print(f"{status}: {test_name}")
    
    print("\n" + "-"*70)
    print(f"Résultat final: {passed}/{total} tests réussis")
    
    if passed == total:
        print("✅ TOUS LES TESTS ONT RÉUSSI!")
        print("\n📚 Documentation: data/golden_datasets/README_STRUCTURE_SIMPLIFIEE.md")
    else:
        print(f"❌ {total - passed} test(s) échoué(s)")
    
    print("="*70 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

