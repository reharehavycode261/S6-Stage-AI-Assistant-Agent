#!/usr/bin/env python3
"""Script pour corriger TOUS les accès à state dans tous les nœuds"""

import os
import re

def fix_file(filepath):
    """Corrige un fichier en remplaçant TOUS les accès state['key'] par state.key"""
    print(f"🔧 Correction complète de {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Compter les occurrences avant correction
    before_count = len(re.findall(r"state\['[^']+'\]", content))
    
    # Remplacer state['key'] par state.key (lecture)
    content = re.sub(r"state\['([^']+)'\]", r"state.\1", content)
    
    # Compter les occurrences après correction
    after_count = len(re.findall(r"state\['[^']+'\]", content))
    
    # Écrire le fichier corrigé
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✅ {filepath} corrigé ({before_count} → {after_count} occurrences)")

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
    print("🎉 Tous les accès à state ont été corrigés!")
