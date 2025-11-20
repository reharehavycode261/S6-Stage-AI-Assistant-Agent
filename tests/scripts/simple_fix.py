#!/usr/bin/env python3
"""Script simple pour corriger les accès à state"""

import os

def fix_file(filepath):
    """Corrige un fichier en remplaçant state['key'] par state.results['key']"""
    print(f"🔧 Correction simple de {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remplacer state['key'] par state.results['key']
    content = content.replace("state['", "state.results['")
    
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
    print("🎉 Correction simple terminée!")
