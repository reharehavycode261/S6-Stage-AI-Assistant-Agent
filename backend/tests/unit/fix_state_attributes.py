#!/usr/bin/env python3
"""Script pour corriger les attributs inexistants dans WorkflowState"""

import os
import re

def fix_file(filepath):
    """Corrige un fichier en remplaçant les attributs inexistants par results"""
    print(f"🔧 Correction des attributs dans {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remplacer state.current_status par state.results["current_status"]
    content = re.sub(r"state\.current_status", r"state.results['current_status']", content)
    
    # Remplacer state.ai_messages par state.results["ai_messages"]
    content = re.sub(r"state\.ai_messages", r"state.results['ai_messages']", content)
    
    # Remplacer state.current_status = par state.results["current_status"] =
    content = re.sub(r"state\.current_status\s*=", r"state.results['current_status'] =", content)
    
    # Remplacer state.ai_messages = par state.results["ai_messages"] =
    content = re.sub(r"state\.ai_messages\s*=", r"state.results['ai_messages'] =", content)
    
    # S'assurer que ai_messages est initialisé comme une liste
    if "ai_messages" in content and "ai_messages" not in content[:200]:
        # Ajouter l'initialisation au début de la fonction
        content = re.sub(
            r"(def \w+\(state: WorkflowState\) -> WorkflowState:.*?\"\"\".*?\"\"\"\s*\n)",
            r"\1    # Initialiser ai_messages si nécessaire\n    if 'ai_messages' not in state.results:\n        state.results['ai_messages'] = []\n\n",
            content,
            flags=re.DOTALL
        )
    
    # Écrire le fichier corrigé
    with open(filepath, 'w') as f:
        f.write(content)
    
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
    print("🎉 Tous les attributs ont été corrigés!")
