#!/usr/bin/env python3
"""Script pour ajouter l'initialisation de ai_messages"""

# Lire le fichier
with open('nodes/prepare_node.py', 'r') as f:
    content = f.read()

# Ajouter l'initialisation après logger.info
old_section = '''    logger.info(f"🔧 Préparation de l'environnement pour la tâche: {state.task.title}")
    
    # Mettre à jour le statut'''

new_section = '''    logger.info(f"🔧 Préparation de l'environnement pour la tâche: {state.task.title}")
    
    # Initialiser ai_messages si nécessaire
    if 'ai_messages' not in state.results:
        state.results['ai_messages'] = []
    
    # Mettre à jour le statut'''

# Appliquer la correction
content = content.replace(old_section, new_section)

# Écrire le fichier corrigé
with open('nodes/prepare_node.py', 'w') as f:
    f.write(content)

print("✅ Initialisation de ai_messages ajoutée")
