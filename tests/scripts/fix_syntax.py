#!/usr/bin/env python3
"""Script pour corriger la syntaxe dans prepare_node.py"""

# Lire le fichier
with open('nodes/prepare_node.py', 'r') as f:
    content = f.read()

# Remplacer la section problématique
old_section = '''    logger.info(f"🔧 Préparation de l'environnement pour la tâche: {state.task.title}")
    
    # Mettre à jour le statut
    state.results["current_status"] = "IN_PROGRESS".lower()
    state.results["ai_messages"].append("Début de la préparation de l'environnement...")
    
    try:'''

new_section = '''    logger.info(f"🔧 Préparation de l'environnement pour la tâche: {state.task.title}")
    
    # Initialiser ai_messages si nécessaire
    if 'ai_messages' not in state.results:
        state.results['ai_messages'] = []
    
    # Mettre à jour le statut
    state.results["current_status"] = "IN_PROGRESS".lower()
    state.results["ai_messages"].append("Début de la préparation de l'environnement...")
    
    try:'''

# Appliquer la correction
content = content.replace(old_section, new_section)

# Écrire le fichier corrigé
with open('nodes/prepare_node.py', 'w') as f:
    f.write(content)

print("✅ Syntaxe corrigée dans prepare_node.py")
