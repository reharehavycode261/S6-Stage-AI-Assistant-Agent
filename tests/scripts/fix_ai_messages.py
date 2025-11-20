#!/usr/bin/env python3
"""Script pour initialiser ai_messages dans tous les nœuds"""

import os

def fix_file(filepath):
    """Ajoute l'initialisation de ai_messages"""
    print(f"🔧 Initialisation de ai_messages dans {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Ajouter l'initialisation après la ligne logger.info
    if "ai_messages" in content and "if 'ai_messages' not in state.results:" not in content:
        # Trouver la ligne logger.info et ajouter l'initialisation après
        lines = content.split('\n')
        new_lines = []
        
        for i, line in enumerate(lines):
            new_lines.append(line)
            if "logger.info" in line and "ai_messages" in content[i:]:
                # Ajouter l'initialisation après cette ligne
                new_lines.append("    # Initialiser ai_messages si nécessaire")
                new_lines.append("    if 'ai_messages' not in state.results:")
                new_lines.append("        state.results['ai_messages'] = []")
        
        content = '\n'.join(new_lines)
    
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
    print("🎉 Initialisation de ai_messages terminée!")
