#!/usr/bin/env python3
"""Script pour corriger complètement prepare_node.py"""

# Lire le fichier
with open('nodes/prepare_node.py', 'r') as f:
    content = f.read()

# Supprimer toutes les initialisations incorrectes de ai_messages
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
        if i > 0 and "logger.info" in lines[i-1] and "Préparation de l'environnement" in lines[i-1]:
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
with open('nodes/prepare_node.py', 'w') as f:
    f.write(content)

print("✅ prepare_node.py corrigé")
