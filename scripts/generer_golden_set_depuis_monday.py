#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère le Golden Set depuis les vraies données Monday.com

Structure finale :
- input: updateMday_ITEM_ID (ex: updateMday_5079505726)
- output: Contenu attendu (analyse ou PR JSON)
- type: "analysis" ou "pr"
"""

import sys
from pathlib import Path
import pandas as pd
import json
import re

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))


def extraire_pr_content(agent_output: str) -> dict:
    """
    Extrait le contenu structuré d'une PR depuis l'output de l'agent
    
    Args:
        agent_output: Texte de la réponse de l'agent
        
    Returns:
        Dict avec les infos de la PR
    """
    pr_info = {
        "type": "pull_request",
        "description": "",
        "files_modified": [],
        "branch": "",
        "pr_number": None,
        "summary": ""
    }
    
    # Extraire le numéro de PR
    pr_match = re.search(r'PR #(\d+)', agent_output)
    if pr_match:
        pr_info["pr_number"] = int(pr_match.group(1))
    
    # Extraire la branche
    branch_match = re.search(r'branche ([a-zA-Z0-9/_-]+)', agent_output)
    if branch_match:
        pr_info["branch"] = branch_match.group(1)
    
    # Extraire les fichiers
    files_match = re.search(r'Fichiers?:\s*([^\.]+)', agent_output)
    if files_match:
        files_text = files_match.group(1)
        # Séparer par virgules ou espaces
        files = re.split(r'[,\s]+', files_text.strip())
        pr_info["files_modified"] = [f.strip() for f in files if f.strip()]
    
    # Le reste comme description
    pr_info["description"] = agent_output.strip()
    pr_info["summary"] = agent_output[:200].strip() + "..." if len(agent_output) > 200 else agent_output.strip()
    
    return pr_info


def determiner_type_interaction(row) -> str:
    """
    Détermine si c'est une analyse ou une PR
    
    Args:
        row: Ligne du DataFrame
        
    Returns:
        "analysis" ou "pr"
    """
    interaction_type = row.get('interaction_type', '').lower()
    agent_output = str(row.get('agent_output', '')).lower()
    
    # Si le type est explicite
    if interaction_type == 'pr':
        return 'pr'
    elif interaction_type == 'analysis':
        return 'analysis'
    
    # Sinon, détecter depuis l'output
    if 'pr #' in agent_output or 'pull request' in agent_output or 'branche' in agent_output:
        return 'pr'
    else:
        return 'analysis'


def generer_golden_set():
    """
    Génère le Golden Set depuis agent_interactions_log.csv
    """
    print("\n" + "="*70)
    print("🎯 GÉNÉRATION DU GOLDEN SET DEPUIS DONNÉES MONDAY.COM")
    print("="*70)
    
    # 1. Charger les données réelles
    csv_path = Path(__file__).parent.parent / "data/golden_datasets/agent_interactions_log.csv"
    
    if not csv_path.exists():
        print(f"❌ Fichier introuvable: {csv_path}")
        return
    
    df = pd.read_csv(csv_path)
    print(f"\n📂 {len(df)} interactions chargées")
    
    # 2. Filtrer les interactions réussies
    df_success = df[df['success'] == True].copy()
    print(f"✅ {len(df_success)} interactions réussies")
    
    # 3. Transformer en Golden Set
    golden_rows = []
    
    for idx, row in df_success.iterrows():
        # Déterminer le type
        interaction_type = determiner_type_interaction(row)
        
        # Construire l'input au format updateMday_ITEM_ID
        monday_item_id = row.get('monday_item_id', 'unknown')
        input_id = f"updateMday_{monday_item_id}"
        
        # Construire l'output
        agent_output = str(row.get('agent_output', ''))
        
        # CORRECTION: Garder le format original de l'agent (texte brut)
        # pour que le Golden Set corresponde exactement à ce que l'agent produit
        output_content = agent_output
        
        golden_rows.append({
            'input': input_id,
            'output': output_content,
            'type': interaction_type,
            'input_text_original': row.get('input_text', ''),  # Pour référence
            'monday_update_id': row.get('monday_update_id', '')
        })
    
    # 4. Créer le DataFrame Golden Set
    df_golden = pd.DataFrame(golden_rows)
    
    # 5. Afficher un aperçu
    print(f"\n📊 Golden Set généré:")
    print(f"   Total: {len(df_golden)} entrées")
    print(f"   Analyses: {len(df_golden[df_golden['type'] == 'analysis'])}")
    print(f"   PR: {len(df_golden[df_golden['type'] == 'pr'])}")
    
    print("\n📝 Aperçu des premières entrées:")
    for i, row in df_golden.head(3).iterrows():
        print(f"\n   {i+1}. Input: {row['input']}")
        print(f"      Type: {row['type']}")
        print(f"      Output: {row['output'][:100]}...")
    
    # 6. Sauvegarder
    output_path = Path(__file__).parent.parent / "data/golden_datasets/golden_sets.csv"
    
    # Garder seulement les colonnes essentielles
    df_golden_final = df_golden[['input', 'output', 'type']]
    df_golden_final.to_csv(output_path, index=False)
    
    print(f"\n✅ Golden Set sauvegardé: {output_path}")
    
    # 7. Créer aussi une version détaillée avec tous les champs
    output_path_detailed = Path(__file__).parent.parent / "data/golden_datasets/golden_sets_detailed.csv"
    df_golden.to_csv(output_path_detailed, index=False)
    
    print(f"✅ Version détaillée: {output_path_detailed}")
    
    # 8. Statistiques
    print("\n" + "="*70)
    print("📈 STATISTIQUES")
    print("="*70)
    
    print(f"\n🔍 Répartition par type:")
    type_counts = df_golden['type'].value_counts()
    for type_name, count in type_counts.items():
        percentage = (count / len(df_golden) * 100)
        print(f"   • {type_name}: {count} ({percentage:.1f}%)")
    
    print(f"\n📏 Longueur moyenne des outputs:")
    for type_name in df_golden['type'].unique():
        avg_len = df_golden[df_golden['type'] == type_name]['output'].str.len().mean()
        print(f"   • {type_name}: {avg_len:.0f} caractères")
    
    print("\n" + "="*70)
    print("✅ Génération terminée !")
    print("="*70)
    
    print("\n💡 Prochaines étapes:")
    print("   1. Vérifier le fichier golden_sets.csv")
    print("   2. Ajuster manuellement si nécessaire")
    print("   3. Utiliser pour l'évaluation avec LLM-as-judge")


if __name__ == "__main__":
    generer_golden_set()

