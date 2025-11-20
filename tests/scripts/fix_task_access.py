#!/usr/bin/env python3
"""Script pour corriger l'accès à task et ajouter les imports manquants"""

import os

def fix_file(filepath):
    """Corrige l'accès à task et ajoute les imports manquants"""
    print(f"🔧 Correction de {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remplacer state.results["task"] par state.task
    content = content.replace('state.results["task"]', 'state.task')
    
    # Ajouter l'import GitOperationResult si nécessaire
    if 'GitOperationResult' in content and 'from models.schemas import' in content:
        # Remplacer l'import existant pour inclure GitOperationResult
        content = content.replace(
            'from models.schemas import',
            'from models.schemas import GitOperationResult,'
        )
    elif 'GitOperationResult' in content and 'from models.schemas import' not in content:
        # Ajouter l'import
        content = 'from models.schemas import GitOperationResult\n' + content
    
    # Écrire le fichier corrigé
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✅ {filepath} corrigé")

def main():
    """Corrige tous les fichiers de nœuds"""
    nodes_dir = "nodes"
    
    files_to_fix = [
        "prepare_node.py",
        "analyze_node.py", 
        "implement_node.py",
        "test_node.py",
        "debug_node.py",
        "qa_node.py",
        "finalize_node.py",
        "update_node.py"
    ]
    
    for filename in files_to_fix:
        filepath = os.path.join(nodes_dir, filename)
        if os.path.exists(filepath):
            fix_file(filepath)

if __name__ == "__main__":
    main()
    print("🎉 Accès à task et imports corrigés!")
