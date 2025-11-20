#!/usr/bin/env python3
"""Script pour corriger l'accès aux attributs dans tous les nœuds"""

import os
import re

def fix_file(filepath):
    """Corrige un fichier en remplaçant state['key'] par state.key"""
    print(f"🔧 Correction de {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remplacer state['key'] par state.key
    # Pattern pour capturer state['quelque_chose']
    pattern = r"state\['([^']+)'\]"
    
    def replacement(match):
        key = match.group(1)
        return f"state.{key}"
    
    new_content = re.sub(pattern, replacement, content)
    
    # Écrire le fichier corrigé
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print(f"✅ {filepath} corrigé")

def main():
    """Corrige tous les fichiers de nœuds"""
    nodes_dir = "nodes"
    
    # Fichiers à corriger
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
        else:
            print(f"⚠️ Fichier non trouvé: {filepath}")

if __name__ == "__main__":
    main()
    print("🎉 Tous les nœuds ont été corrigés!")
