#!/usr/bin/env python3
"""Script pour récupérer et mettre à jour la configuration Monday.com avec un nouveau board."""

import asyncio
import sys
import os
import re
from typing import Dict, Any, List, Optional

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.monday_tool import MondayTool
from utils.logger import get_logger

logger = get_logger(__name__)


async def get_accessible_boards() -> List[Dict[str, Any]]:
    """
    Récupère la liste des boards accessibles.
    
    Returns:
        Liste des boards avec leur ID et nom
    """
    monday_tool = MondayTool()
    
    query = """
    query GetBoards {
        boards(limit: 100) {
            id
            name
            description
            state
        }
    }
    """
    
    try:
        result = await monday_tool._make_request(query, {})
        
        if result.get("data", {}).get("boards"):
            boards = result["data"]["boards"]
            # Filtrer les boards actifs
            active_boards = [b for b in boards if b.get("state") == "active"]
            return active_boards
        else:
            logger.error("❌ Impossible de récupérer les boards")
            return []
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la requête: {e}")
        return []


async def get_board_columns(board_id: str) -> Dict[str, Any]:
    """
    Récupère toutes les colonnes d'un board Monday.com.
    
    Args:
        board_id: ID du board Monday.com
        
    Returns:
        Dictionnaire avec les informations des colonnes
    """
    monday_tool = MondayTool()
    
    query = """
    query GetBoardColumns($boardId: [ID!]) {
        boards(ids: $boardId) {
            id
            name
            columns {
                id
                title
                type
                settings_str
            }
        }
    }
    """
    
    variables = {"boardId": [board_id]}
    
    try:
        result = await monday_tool._make_request(query, variables)
        
        if result.get("data", {}).get("boards"):
            board_data = result["data"]["boards"][0]
            return {
                "success": True,
                "board_id": board_data["id"],
                "board_name": board_data["name"],
                "columns": board_data["columns"]
            }
        else:
            return {
                "success": False,
                "error": f"Impossible de récupérer les colonnes du board {board_id}",
                "details": result
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Erreur lors de la requête: {str(e)}"
        }


def find_column_by_type_and_keywords(columns: List[Dict[str, Any]], 
                                     column_types: List[str], 
                                     keywords: List[str],
                                     priority_keywords: Optional[List[str]] = None) -> Optional[str]:
    """
    Trouve une colonne basée sur son type et des mots-clés dans son titre.
    
    Args:
        columns: Liste des colonnes
        column_types: Types de colonnes acceptés
        keywords: Mots-clés à rechercher dans le titre
        priority_keywords: Mots-clés prioritaires
        
    Returns:
        ID de la colonne trouvée ou None
    """
    # D'abord chercher avec les mots-clés prioritaires
    if priority_keywords:
        for column in columns:
            column_title = column["title"].lower()
            column_type = column["type"]
            if column_type in column_types:
                if any(keyword in column_title for keyword in priority_keywords):
                    return column["id"]
    
    # Ensuite chercher avec les mots-clés standards
    for column in columns:
        column_title = column["title"].lower()
        column_type = column["type"]
        if column_type in column_types:
            if any(keyword in column_title for keyword in keywords):
                return column["id"]
    
    return None


def find_relevant_columns(columns: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Identifie automatiquement les colonnes pertinentes.
    
    Args:
        columns: Liste des colonnes du board
        
    Returns:
        Dictionnaire avec les IDs des colonnes importantes
    """
    column_mapping = {}
    
    # Trouver la colonne de statut
    status_column_id = find_column_by_type_and_keywords(
        columns,
        ["color", "status"],
        ["status", "statut", "état", "state"],
        ["status", "statut"]
    )
    
    if status_column_id:
        column_mapping["status_column_id"] = status_column_id
        status_col = next((c for c in columns if c["id"] == status_column_id), None)
        if status_col:
            logger.info(f"✅ Colonne Status trouvée: '{status_col['title']}' (ID: {status_column_id})")
    
    # Trouver la colonne de tâche/nom
    task_column_id = None
    for column in columns:
        if column["type"] == "name":
            task_column_id = column["id"]
            column_mapping["task_column_id"] = task_column_id
            logger.info(f"✅ Colonne Task/Name trouvée: '{column['title']}' (ID: {task_column_id})")
            break
    
    # Si pas de colonne "name", chercher par mots-clés
    if not task_column_id:
        task_column_id = find_column_by_type_and_keywords(
            columns,
            ["text", "long_text"],
            ["task", "tâche", "name", "nom", "title", "titre"]
        )
        if task_column_id:
            column_mapping["task_column_id"] = task_column_id
            task_col = next((c for c in columns if c["id"] == task_column_id), None)
            if task_col:
                logger.info(f"✅ Colonne Task trouvée: '{task_col['title']}' (ID: {task_column_id})")
    
    # Trouver la colonne Repository URL
    repo_url_column_id = find_column_by_type_and_keywords(
        columns,
        ["text", "long_text", "link"],
        ["repository", "repo", "url", "git", "github"],
        ["repository_url", "repo_url", "repository url"]
    )
    
    if repo_url_column_id:
        column_mapping["repository_url_column_id"] = repo_url_column_id
        repo_col = next((c for c in columns if c["id"] == repo_url_column_id), None)
        if repo_col:
            logger.info(f"✅ Colonne Repository URL trouvée: '{repo_col['title']}' (ID: {repo_url_column_id})")
    
    return column_mapping


def update_env_file(board_id: str, column_mapping: Dict[str, str], env_file_path: str = ".env") -> bool:
    """
    Met à jour le fichier .env avec les nouvelles configurations.
    Préserve MONDAY_API_TOKEN et autres variables existantes.
    
    Args:
        board_id: ID du nouveau board
        column_mapping: Mapping des colonnes trouvées
        env_file_path: Chemin vers le fichier .env
        
    Returns:
        True si succès, False sinon
    """
    if not os.path.exists(env_file_path):
        logger.error(f"❌ Fichier {env_file_path} introuvable")
        return False
    
    try:
        # Lire le fichier .env actuel
        with open(env_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Créer une sauvegarde
        backup_path = f"{env_file_path}.backup"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        logger.info(f"💾 Sauvegarde créée: {backup_path}")
        
        # Mettre à jour les lignes
        updated_lines = []
        keys_updated = set()
        
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
                    keys_updated.add("MONDAY_BOARD_ID")
                    logger.info(f"✅ MONDAY_BOARD_ID mis à jour: {board_id}")
                
                # Mettre à jour MONDAY_STATUS_COLUMN_ID
                elif key == "MONDAY_STATUS_COLUMN_ID" and "status_column_id" in column_mapping:
                    updated_lines.append(f"MONDAY_STATUS_COLUMN_ID={column_mapping['status_column_id']}\n")
                    keys_updated.add("MONDAY_STATUS_COLUMN_ID")
                    logger.info(f"✅ MONDAY_STATUS_COLUMN_ID mis à jour: {column_mapping['status_column_id']}")
                
                # Mettre à jour MONDAY_TASK_COLUMN_ID
                elif key == "MONDAY_TASK_COLUMN_ID" and "task_column_id" in column_mapping:
                    updated_lines.append(f"MONDAY_TASK_COLUMN_ID={column_mapping['task_column_id']}\n")
                    keys_updated.add("MONDAY_TASK_COLUMN_ID")
                    logger.info(f"✅ MONDAY_TASK_COLUMN_ID mis à jour: {column_mapping['task_column_id']}")
                
                # Mettre à jour MONDAY_REPOSITORY_URL_COLUMN_ID
                elif key == "MONDAY_REPOSITORY_URL_COLUMN_ID" and "repository_url_column_id" in column_mapping:
                    updated_lines.append(f"MONDAY_REPOSITORY_URL_COLUMN_ID={column_mapping['repository_url_column_id']}\n")
                    keys_updated.add("MONDAY_REPOSITORY_URL_COLUMN_ID")
                    logger.info(f"✅ MONDAY_REPOSITORY_URL_COLUMN_ID mis à jour: {column_mapping['repository_url_column_id']}")
                
                else:
                    # Garder la ligne telle quelle (préserve MONDAY_API_TOKEN et autres)
                    updated_lines.append(line)
            else:
                updated_lines.append(line)
        
        # Ajouter les clés manquantes
        if "MONDAY_REPOSITORY_URL_COLUMN_ID" not in keys_updated and "repository_url_column_id" in column_mapping:
            # Ajouter après la section Monday.com
            for i, line in enumerate(updated_lines):
                if "MONDAY.COM CONFIGURATION" in line or "MONDAY_BOARD_ID" in line:
                    # Trouver la fin de la section Monday.com
                    insert_index = i + 1
                    while insert_index < len(updated_lines) and not updated_lines[insert_index].startswith('#'):
                        insert_index += 1
                    updated_lines.insert(insert_index, f"MONDAY_REPOSITORY_URL_COLUMN_ID={column_mapping['repository_url_column_id']}\n")
                    logger.info(f"✅ MONDAY_REPOSITORY_URL_COLUMN_ID ajouté: {column_mapping['repository_url_column_id']}")
                    break
        
        # Écrire le fichier .env mis à jour
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        logger.info(f"✅ Fichier {env_file_path} mis à jour avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour {env_file_path}: {e}")
        return False


async def main():
    """Fonction principale pour récupérer et configurer le nouveau board Monday.com."""
    print("\n" + "="*60)
    print("🚀 CONFIGURATION MONDAY.COM - NOUVEAU BOARD")
    print("="*60 + "\n")
    
    try:
        # Étape 1: Demander le Board ID ou lister les boards disponibles
        print("📋 Voulez-vous:")
        print("  1. Entrer manuellement l'ID du board")
        print("  2. Voir la liste des boards disponibles")
        
        choice = input("\nVotre choix (1/2): ").strip()
        
        board_id = None
        
        if choice == "2":
            print("\n🔍 Récupération de la liste des boards...\n")
            boards = await get_accessible_boards()
            
            if not boards:
                logger.error("❌ Aucun board trouvé ou erreur de connexion")
                return False
            
            print(f"📊 {len(boards)} board(s) disponible(s):\n")
            for i, board in enumerate(boards, 1):
                print(f"  {i}. {board['name']}")
                print(f"     ID: {board['id']}")
                if board.get('description'):
                    print(f"     Description: {board['description']}")
                print()
            
            # Demander de choisir un board
            board_choice = input("Entrez le numéro du board à utiliser: ").strip()
            try:
                board_index = int(board_choice) - 1
                if 0 <= board_index < len(boards):
                    board_id = boards[board_index]['id']
                    logger.info(f"✅ Board sélectionné: {boards[board_index]['name']} (ID: {board_id})")
                else:
                    logger.error("❌ Numéro invalide")
                    return False
            except ValueError:
                logger.error("❌ Entrée invalide")
                return False
        else:
            board_id = input("\nEntrez l'ID du board Monday.com: ").strip()
        
        if not board_id:
            logger.error("❌ Board ID requis")
            return False
        
        # Étape 2: Récupérer les colonnes du board
        print(f"\n🔍 Analyse du board {board_id}...\n")
        result = await get_board_columns(board_id)
        
        if not result["success"]:
            logger.error(f"❌ Échec récupération colonnes: {result['error']}")
            if 'details' in result:
                logger.error(f"Détails: {result['details']}")
            return False
        
        print(f"📊 Board trouvé: {result['board_name']}")
        print(f"📄 {len(result['columns'])} colonnes détectées\n")
        
        # Afficher toutes les colonnes
        print("📋 COLONNES DISPONIBLES:")
        print("-" * 60)
        for i, column in enumerate(result["columns"], 1):
            print(f"  {i}. {column['title']} (Type: {column['type']}, ID: {column['id']})")
        print()
        
        # Étape 3: Identifier automatiquement les colonnes pertinentes
        print("🎯 Identification automatique des colonnes...\n")
        column_mapping = find_relevant_columns(result["columns"])
        
        if not column_mapping:
            logger.warning("⚠️ Aucune colonne pertinente automatiquement identifiée")
            print("\n💡 Veuillez identifier manuellement les colonnes:")
            
            # Identification manuelle
            status_col = input("Entrez l'ID de la colonne STATUS: ").strip()
            if status_col:
                column_mapping["status_column_id"] = status_col
            
            task_col = input("Entrez l'ID de la colonne TASK/NAME: ").strip()
            if task_col:
                column_mapping["task_column_id"] = task_col
            
            repo_col = input("Entrez l'ID de la colonne REPOSITORY URL (optionnel): ").strip()
            if repo_col:
                column_mapping["repository_url_column_id"] = repo_col
        
        # Vérifier que les colonnes essentielles sont présentes
        if "status_column_id" not in column_mapping or "task_column_id" not in column_mapping:
            logger.error("❌ Les colonnes STATUS et TASK sont obligatoires")
            return False
        
        # Afficher le résumé
        print("\n" + "="*60)
        print("📝 RÉSUMÉ DE LA CONFIGURATION")
        print("="*60)
        print(f"Board ID: {board_id}")
        print(f"Board Name: {result['board_name']}")
        print(f"Status Column ID: {column_mapping.get('status_column_id', 'N/A')}")
        print(f"Task Column ID: {column_mapping.get('task_column_id', 'N/A')}")
        print(f"Repository URL Column ID: {column_mapping.get('repository_url_column_id', 'N/A')}")
        print("="*60 + "\n")
        
        # Demander confirmation
        confirm = input("Voulez-vous mettre à jour le fichier .env avec ces valeurs? (y/n): ").strip().lower()
        
        if confirm != 'y':
            logger.info("❌ Mise à jour annulée")
            return False
        
        # Étape 4: Mettre à jour le fichier .env
        print("\n📝 Mise à jour du fichier .env...\n")
        success = update_env_file(board_id, column_mapping)
        
        if success:
            print("\n" + "="*60)
            print("🎉 CONFIGURATION TERMINÉE AVEC SUCCÈS!")
            print("="*60)
            print("\n⚠️ IMPORTANT:")
            print("  • Le fichier .env a été mis à jour")
            print("  • Le MONDAY_API_TOKEN a été préservé")
            print("  • Une sauvegarde a été créée: .env.backup")
            print("  • Redémarrez l'application pour appliquer les changements")
            print("\n♻️ Pour redémarrer l'application:")
            print("  docker-compose down && docker-compose up -d")
            print("  # ou")
            print("  ./restart_celery_clean.sh")
            print("="*60 + "\n")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la configuration: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

