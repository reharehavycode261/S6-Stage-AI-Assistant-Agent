#!/usr/bin/env python3
"""Script pour corriger tous les nœuds en supprimant les initialisations incorrectes"""

import os

def fix_file(filepath):
    """Supprime toutes les initialisations incorrectes de ai_messages"""
    print(f"🔧 Correction de {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Supprimer les lignes d'initialisation incorrectes
    lines = content.split('\n')
    new_lines = []
    skip_next = False
    
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        
        # Supprimer les lignes d'initialisation incorrectes
        if "if 'ai_messages' not in state.results:" in line:
            # Vérifier si c'est dans le bon contexte (après logger.info principal)
            if i > 0 and "logger.info" in lines[i-1] and ("Préparation" in lines[i-1] or "Analyse" in lines[i-1] or "Implémentation" in lines[i-1] or "Test" in lines[i-1] or "Debug" in lines[i-1] or "QA" in lines[i-1] or "Finalisation" in lines[i-1] or "Mise à jour" in lines[i-1]):
                # Garder cette initialisation
                new_lines.append(line)
                continue
            else:
                # Supprimer cette initialisation incorrecte
                skip_next = True
                continue
        
        if "state.results['ai_messages'] = []" in line and skip_next:
            continue
        
        new_lines.append(line)
    
    # Rejoindre les lignes
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
    print("🎉 Tous les nœuds ont été corrigés!")
