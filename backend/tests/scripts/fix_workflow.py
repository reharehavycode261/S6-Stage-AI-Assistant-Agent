#!/usr/bin/env python3
"""Script pour corriger l'erreur dans workflow_graph.py"""


# Lire le fichier
with open('graph/workflow_graph.py', 'r') as f:
    content = f.read()

# Remplacer la logique d'accès à l'état
old_code = '''        async for state in app.astream(initial_state, config=config):
            node_count += 1
            current_node = list(state.keys())[0] if state else "unknown"
            
            logger.info(f"📍 Nœud {node_count}: {current_node}")
            
            # Mettre à jour l'état final
            if state:
                final_state = list(state.values())[0]'''

new_code = '''        async for state in app.astream(initial_state, config=config):
            node_count += 1
            # L'état est directement un WorkflowState, pas un dict
            current_node = state.current_node if hasattr(state, 'current_node') else "unknown"
            
            logger.info(f"📍 Nœud {node_count}: {current_node}")
            
            # Mettre à jour l'état final
            if state:
                final_state = state'''

# Appliquer la correction
content = content.replace(old_code, new_code)

# Écrire le fichier corrigé
with open('graph/workflow_graph.py', 'w') as f:
    f.write(content)

print("✅ Correction appliquée dans workflow_graph.py")
