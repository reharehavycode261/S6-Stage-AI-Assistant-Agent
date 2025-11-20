#!/usr/bin/env python3
"""Script pour appliquer automatiquement une configuration Monday.com au fichier .env."""

import sys
import os
import re
from datetime import datetime


def update_env_file(board_id: str, task_column_id: str, status_column_id: str, 
                   repository_url_column_id: str = None, env_file_path: str = ".env") -> bool:
    """
    Met à jour le fichier .env avec les nouvelles configurations.
    Préserve MONDAY_API_TOKEN et autres variables existantes.
    
    Args:
        board_id: ID du nouveau board
        task_column_id: ID de la colonne task
        status_column_id: ID de la colonne status
        repository_url_column_id: ID de la colonne repository URL (optionnel)
        env_file_path: Chemin vers le fichier .env
        
    Returns:
        True si succès, False sinon
    """
    if not os.path.exists(env_file_path):
        print(f"❌ Fichier {env_file_path} introuvable")
        return False
    
    try:
        # Lire le fichier .env actuel
        with open(env_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Créer une sauvegarde avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{env_file_path}.backup_{timestamp}"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"💾 Sauvegarde créée: {backup_path}")
        
        # Mettre à jour les lignes
        updated_lines = []
        keys_found = set()
        
        for line in lines:
            line_stripped = line.strip()
            
            # Ignorer les commentaires et lignes vides
            if not line_stripped or line_stripped.startswith('#'):
                updated_lines.append(line)
                continue
            
            # Vérifier si c'est une ligne de configuration à mettre à jour
            if '=' in line:
                key = line.split('=')[0].strip()
                
                # Mettre à jour MONDAY_BOARD_ID
                if key == "MONDAY_BOARD_ID":
                    updated_lines.append(f"MONDAY_BOARD_ID={board_id}\n")
                    keys_found.add("MONDAY_BOARD_ID")
                    print(f"✅ MONDAY_BOARD_ID mis à jour: {board_id}")
                
                # Mettre à jour MONDAY_STATUS_COLUMN_ID
                elif key == "MONDAY_STATUS_COLUMN_ID":
                    updated_lines.append(f"MONDAY_STATUS_COLUMN_ID={status_column_id}\n")
                    keys_found.add("MONDAY_STATUS_COLUMN_ID")
                    print(f"✅ MONDAY_STATUS_COLUMN_ID mis à jour: {status_column_id}")
                
                # Mettre à jour MONDAY_TASK_COLUMN_ID
                elif key == "MONDAY_TASK_COLUMN_ID":
                    updated_lines.append(f"MONDAY_TASK_COLUMN_ID={task_column_id}\n")
                    keys_found.add("MONDAY_TASK_COLUMN_ID")
                    print(f"✅ MONDAY_TASK_COLUMN_ID mis à jour: {task_column_id}")
                
                # Mettre à jour MONDAY_REPOSITORY_URL_COLUMN_ID
                elif key == "MONDAY_REPOSITORY_URL_COLUMN_ID":
                    if repository_url_column_id:
                        updated_lines.append(f"MONDAY_REPOSITORY_URL_COLUMN_ID={repository_url_column_id}\n")
                        keys_found.add("MONDAY_REPOSITORY_URL_COLUMN_ID")
                        print(f"✅ MONDAY_REPOSITORY_URL_COLUMN_ID mis à jour: {repository_url_column_id}")
                    else:
                        updated_lines.append(line)
                
                else:
                    # Garder la ligne telle quelle (préserve MONDAY_API_TOKEN et autres)
                    updated_lines.append(line)
            else:
                updated_lines.append(line)
        
        # Ajouter MONDAY_REPOSITORY_URL_COLUMN_ID si pas présent et fourni
        if "MONDAY_REPOSITORY_URL_COLUMN_ID" not in keys_found and repository_url_column_id:
            # Trouver où l'insérer (après la section Monday.com)
            inserted = False
            for i in range(len(updated_lines)):
                if "MONDAY_BOARD_ID" in updated_lines[i] or "MONDAY_TASK_COLUMN_ID" in updated_lines[i]:
                    # Trouver la fin de la section Monday.com
                    insert_index = i + 1
                    while insert_index < len(updated_lines):
                        line = updated_lines[insert_index].strip()
                        if line.startswith('#') and "=" not in line:
                            break
                        if not line or line.startswith('#'):
                            insert_index += 1
                        else:
                            insert_index += 1
                    
                    updated_lines.insert(insert_index, f"MONDAY_REPOSITORY_URL_COLUMN_ID={repository_url_column_id}\n")
                    print(f"✅ MONDAY_REPOSITORY_URL_COLUMN_ID ajouté: {repository_url_column_id}")
                    inserted = True
                    break
            
            if not inserted:
                # Ajouter à la fin de la section Monday.com
                updated_lines.append(f"MONDAY_REPOSITORY_URL_COLUMN_ID={repository_url_column_id}\n")
                print(f"✅ MONDAY_REPOSITORY_URL_COLUMN_ID ajouté: {repository_url_column_id}")
        
        # Écrire le fichier .env mis à jour
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        print(f"\n✅ Fichier {env_file_path} mis à jour avec succès")
        return True
        
    except Exception as e:
        print(f"❌ Erreur mise à jour {env_file_path}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Fonction principale."""
    if len(sys.argv) < 4:
        print("Usage: python apply_board_config.py <BOARD_ID> <TASK_COLUMN_ID> <STATUS_COLUMN_ID> [REPO_URL_COLUMN_ID]")
        print("\nExemple:")
        print("  python apply_board_config.py 1234567890 name status__1 text__1")
        print("\nPour obtenir ces informations, exécutez d'abord:")
        print("  python get_board_info.py <BOARD_ID>")
        sys.exit(1)
    
    board_id = sys.argv[1]
    task_column_id = sys.argv[2]
    status_column_id = sys.argv[3]
    repository_url_column_id = sys.argv[4] if len(sys.argv) > 4 else None
    
    print("\n" + "="*60)
    print("📝 APPLICATION DE LA CONFIGURATION MONDAY.COM")
    print("="*60)
    print(f"\nBoard ID: {board_id}")
    print(f"Task Column ID: {task_column_id}")
    print(f"Status Column ID: {status_column_id}")
    print(f"Repository URL Column ID: {repository_url_column_id or 'Non fourni'}")
    print("\n" + "="*60 + "\n")
    
    success = update_env_file(board_id, task_column_id, status_column_id, repository_url_column_id)
    
    if success:
        print("\n" + "="*60)
        print("🎉 CONFIGURATION TERMINÉE!")
        print("="*60)
        print("\n⚠️ IMPORTANT:")
        print("  • Le MONDAY_API_TOKEN a été préservé")
        print("  • Une sauvegarde a été créée")
        print("  • Redémarrez l'application pour appliquer les changements:")
        print("\n    cd '/Users/stagiaire_vycode/Stage Smartelia/AI-Agent '")
        print("    docker-compose down && docker-compose up -d")
        print("    # ou")
        print("    ./restart_celery_clean.sh")
        print("\n" + "="*60 + "\n")
        sys.exit(0)
    else:
        print("\n❌ Échec de la configuration")
        sys.exit(1)


if __name__ == "__main__":
    main()

