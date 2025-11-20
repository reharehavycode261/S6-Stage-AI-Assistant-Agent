#!/usr/bin/env python3
"""
Script pour mettre à jour automatiquement le fichier .env avec la nouvelle configuration.
"""

import os
from pathlib import Path

def update_env_file():
    """Met à jour le fichier .env avec les nouvelles valeurs."""
    env_path = Path(__file__).parent.parent / ".env"
    
    if not env_path.exists():
        print(f"❌ Fichier .env non trouvé: {env_path}")
        print("\n💡 Créez d'abord un fichier .env à partir de env_template.txt")
        return False
    
    print("📝 Mise à jour du fichier .env...")
    print(f"   Chemin: {env_path}\n")
    
    # Lire le contenu actuel
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Nouvelles valeurs
    new_values = {
        'MONDAY_BOARD_ID': '5037922237',
        'MONDAY_STATUS_COLUMN_ID': 'task_status',
        'MONDAY_REPOSITORY_URL_COLUMN_ID': 'link'
    }
    
    # Mettre à jour les lignes
    updated_lines = []
    updated_keys = set()
    
    for line in lines:
        updated = False
        for key, value in new_values.items():
            if line.startswith(f'{key}='):
                old_value = line.split('=', 1)[1].strip()
                if old_value != value:
                    print(f"🔄 {key}")
                    print(f"   Ancien: {old_value}")
                    print(f"   Nouveau: {value}")
                    updated_lines.append(f'{key}={value}\n')
                    updated_keys.add(key)
                    updated = True
                else:
                    print(f"✅ {key}={value} (déjà correct)")
                    updated_lines.append(line)
                    updated_keys.add(key)
                    updated = True
                break
        
        if not updated:
            updated_lines.append(line)
    
    # Ajouter les clés manquantes
    for key, value in new_values.items():
        if key not in updated_keys:
            print(f"➕ Ajout de {key}={value}")
            updated_lines.append(f'{key}={value}\n')
    
    # Écrire le fichier mis à jour
    with open(env_path, 'w') as f:
        f.writelines(updated_lines)
    
    print("\n✅ Fichier .env mis à jour avec succès!")
    return True


def main():
    """Point d'entrée principal."""
    print("\n" + "="*60)
    print("🔧 MISE À JOUR DE LA CONFIGURATION .env")
    print("="*60)
    print("\nNouvelle configuration pour le board 5037922237:")
    print("   • Board ID: 5037922237")
    print("   • Statut Column: task_status")
    print("   • Repository URL Column: link")
    print()
    
    if update_env_file():
        print("\n" + "="*60)
        print("✅ Configuration mise à jour!")
        print("="*60)
        print("\n📋 Prochaines étapes:")
        print("   1. Vérifier: python3 scripts/fix_monday_config.py")
        print("   2. Redémarrer Celery pour appliquer les changements")
    else:
        print("\n❌ Échec de la mise à jour")


if __name__ == "__main__":
    main()

