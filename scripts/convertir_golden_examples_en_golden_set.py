#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convertit golden_sets_10_exemples.csv en golden_sets.csv utilisable

Ajoute les colonnes manquantes :
- input → transformé en updateMday_XXX
- output → gardé tel quel
- type → détecté automatiquement (analysis/pr)
"""

import pandas as pd
from pathlib import Path
import re
import csv


def detecter_type(input_text: str, output_text: str) -> str:
    """Détecte si c'est une analyse ou une PR"""
    
    # Mots-clés pour PR
    pr_keywords = ['pr #', 'pull request', 'branche', 'commit', 'merge', 'créée avec succès']
    
    input_lower = input_text.lower()
    output_lower = output_text.lower()
    
    # Si input demande création/implémentation ET output mentionne PR
    if any(keyword in output_lower for keyword in pr_keywords):
        return 'pr'
    
    # Si input demande création/implémentation mais output est explicatif
    creation_keywords = ['crée', 'implémente', 'ajoute', 'génère', 'développe']
    if any(keyword in input_lower for keyword in creation_keywords):
        # Si output explique comment faire → analysis
        # Si output dit qu'une PR a été créée → pr
        if 'pr #' in output_lower or 'créée' in output_lower:
            return 'pr'
        else:
            return 'analysis'  # C'est une explication de comment faire
    
    # Par défaut, c'est une analysis
    return 'analysis'


def main():
    print("\n" + "="*70)
    print("🔄 CONVERSION: golden_sets_10_exemples.csv → golden_sets.csv")
    print("="*70)
    
    # Chemins
    base_path = Path(__file__).parent.parent / "data/golden_datasets"
    input_file = base_path / "golden_sets_10_exemples.csv"
    output_file = base_path / "golden_sets.csv"
    
    # ÉTAPE 1: Compter le nombre total de lignes du fichier
    print(f"\n📊 Vérification du fichier source...")
    with open(input_file, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for line in f if line.strip())  # Ignorer les lignes complètement vides
    
    print(f"   Lignes totales (non vides): {total_lines}")
    
    # ÉTAPE 2: Lire le fichier source avec gestion d'erreurs
    print(f"\n📂 Lecture de {input_file.name}...")
    
    rows = []
    ignored_count = 0
    parse_errors = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        csv_reader = csv.reader(f, quotechar='"', doublequote=True)
        for line_num, row in enumerate(csv_reader, 1):
            try:
                if len(row) >= 2:
                    # Prendre les 2 premières colonnes
                    input_text = row[0].strip()
                    output_text = row[1].strip()
                    
                    # Vérifier que ce ne sont pas des lignes vides
                    if input_text and output_text:
                        rows.append({
                            'input_text': input_text, 
                            'output_reference': output_text,
                            'line_number': line_num
                        })
                    else:
                        ignored_count += 1
                elif len(row) == 1:
                    # Ligne incomplète
                    if row[0].strip():
                        parse_errors.append(f"Ligne {line_num}: incomplète - {row[0][:50]}...")
                    ignored_count += 1
                elif len(row) == 0:
                    # Ligne vide
                    ignored_count += 1
                # Les lignes complètement vides sont ignorées silencieusement
            except Exception as e:
                parse_errors.append(f"Ligne {line_num}: erreur de parsing - {str(e)}")
                ignored_count += 1
    
    df = pd.DataFrame(rows)
    loaded_count = len(df)
    
    # ÉTAPE 3: Vérifier la cohérence
    print(f"\n✅ {loaded_count} exemples chargés")
    
    if ignored_count > 0:
        print(f"   ⚠️  {ignored_count} lignes ignorées (incomplètes ou vides)")
    
    if parse_errors:
        print(f"\n⚠️  Erreurs de parsing détectées:")
        for error in parse_errors[:5]:  # Montrer les 5 premières
            print(f"   • {error}")
        if len(parse_errors) > 5:
            print(f"   ... et {len(parse_errors) - 5} autres erreurs")
    
    # ÉTAPE 4: Alerte si différence importante
    expected_valid = total_lines  # On s'attend à charger toutes les lignes non vides
    difference = expected_valid - loaded_count - ignored_count
    
    if difference > 5:  # Seuil de tolérance
        print(f"\n⚠️  ATTENTION: Différence importante détectée!")
        print(f"   Lignes totales: {total_lines}")
        print(f"   Lignes chargées: {loaded_count}")
        print(f"   Lignes ignorées: {ignored_count}")
        print(f"   Différence: {difference}")
        print(f"\n   → Vérifiez le format du CSV (guillemets, virgules, etc.)")
    else:
        print(f"\n✅ Vérification OK: {loaded_count} lignes valides sur {total_lines} total")
    
    # Transformer en format golden_sets
    print("\n🔄 Transformation en cours...")
    
    golden_rows = []
    for idx, row in df.iterrows():
        input_text = row['input_text']
        output_text = row['output_reference']
        
        # Créer un ID Monday fictif mais cohérent
        # Utiliser l'index + un préfixe
        monday_id = f"golden_{idx+1:04d}"
        input_id = f"updateMday_{monday_id}"
        
        # Détecter le type
        item_type = detecter_type(input_text, output_text)
        
        golden_rows.append({
            'input': input_id,
            'output': output_text,
            'type': item_type,
            'input_text_original': input_text  # Pour référence
        })
    
    # Créer le DataFrame final
    df_golden = pd.DataFrame(golden_rows)
    
    # Statistiques
    print(f"\n📊 Statistiques:")
    print(f"   Total: {len(df_golden)} entrées")
    
    type_counts = df_golden['type'].value_counts()
    for type_name, count in type_counts.items():
        percentage = (count / len(df_golden) * 100)
        print(f"   • {type_name}: {count} ({percentage:.1f}%)")
    
    # Aperçu
    print(f"\n📝 Aperçu des premières entrées:")
    for i in range(min(3, len(df_golden))):
        row = df_golden.iloc[i]
        print(f"\n   {i+1}. Input ID: {row['input']}")
        print(f"      Type: {row['type']}")
        print(f"      Question: {row['input_text_original'][:60]}...")
        print(f"      Output: {row['output'][:80]}...")
    
    # Sauvegarder
    print(f"\n💾 Sauvegarde...")
    
    # Version simple (input, output, type)
    df_golden_simple = df_golden[['input', 'output', 'type']]
    df_golden_simple.to_csv(output_file, index=False)
    print(f"✅ Golden Set sauvegardé: {output_file}")
    
    # Version détaillée
    output_file_detailed = base_path / "golden_sets_detailed.csv"
    df_golden.to_csv(output_file_detailed, index=False)
    print(f"✅ Version détaillée: {output_file_detailed}")
    
    print("\n" + "="*70)
    print("✅ Conversion terminée !")
    print("="*70)
    
    print("\n💡 Prochaines étapes:")
    print("   1. Le fichier golden_sets.csv contient maintenant vos 92 exemples")
    print("   2. Ces outputs sont les RÉFÉRENCES PARFAITES attendues")
    print("   3. Lancer l'évaluation pour comparer agent vs références")
    print("   4. python scripts/evaluation_finale_golden_set.py")
    
    print("\n⚠️  IMPORTANT:")
    print("   Les inputs ont des IDs fictifs (updateMday_golden_XXXX)")
    print("   Pour utiliser les vrais IDs Monday, vous devez les mapper manuellement")
    print("   dans golden_sets.csv")


if __name__ == "__main__":
    main()

