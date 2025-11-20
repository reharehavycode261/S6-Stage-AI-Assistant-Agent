#!/usr/bin/env python3
"""Script pour récupérer automatiquement les column IDs Monday.com."""

import asyncio
import sys
import os
from typing import Dict, Any, List

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.monday_tool import MondayTool
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


async def get_board_columns(board_id: str) -> Dict[str, Any]:
    """
    Récupère toutes les colonnes d'un board Monday.com.
    
    Args:
        board_id: ID du board Monday.com
        
    Returns:
        Dictionnaire avec les informations des colonnes
    """
    monday_tool = MondayTool()
    
    # Requête GraphQL pour récupérer les colonnes du board
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


def find_relevant_columns(columns: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Identifie les colonnes pertinentes (status, task, etc.).
    
    Args:
        columns: Liste des colonnes du board
        
    Returns:
        Dictionnaire avec les IDs des colonnes importantes
    """
    column_mapping = {}
    
    for column in columns:
        column_id = column["id"]
        column_title = column["title"].lower()
        column_type = column["type"]
        
        # Identifier la colonne de statut
        if (column_type in ["color", "status"] and 
            any(keyword in column_title for keyword in ["status", "statut", "état"])) or column_type == "status":
            column_mapping["status_column_id"] = column_id
            logger.info(f"✅ Colonne Status trouvée: {column['title']} (ID: {column_id})")
        
        # Identifier la colonne de tâche/nom
        elif column_type == "name" or any(keyword in column_title for keyword in ["task", "tâche", "name", "nom"]):
            column_mapping["task_column_id"] = column_id
            logger.info(f"✅ Colonne Task trouvée: {column['title']} (ID: {column_id})")
        
        # Identifier d'autres colonnes utiles
        elif column_type == "date" and any(keyword in column_title for keyword in ["deadline", "échéance", "date"]):
            column_mapping["deadline_column_id"] = column_id
            logger.info(f"📅 Colonne Date trouvée: {column['title']} (ID: {column_id})")
        
        elif column_type == "text" and any(keyword in column_title for keyword in ["description", "details"]):
            column_mapping["description_column_id"] = column_id
            logger.info(f"📝 Colonne Description trouvée: {column['title']} (ID: {column_id})")
    
    return column_mapping


def update_env_file(column_mapping: Dict[str, str], env_file_path: str = ".env"):
    """
    Met à jour le fichier .env avec les column IDs trouvés.
    
    Args:
        column_mapping: Mapping des colonnes trouvées
        env_file_path: Chemin vers le fichier .env
    """
    if not os.path.exists(env_file_path):
        logger.error(f"❌ Fichier {env_file_path} introuvable")
        return False
    
    try:
        # Lire le fichier .env actuel
        with open(env_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remplacer les placeholders par les vraies valeurs
        if "status_column_id" in column_mapping:
            content = content.replace(
                "MONDAY_STATUS_COLUMN_ID=your_status_column_id_here",
                f"MONDAY_STATUS_COLUMN_ID={column_mapping['status_column_id']}"
            )
            logger.info(f"✅ MONDAY_STATUS_COLUMN_ID mis à jour: {column_mapping['status_column_id']}")
        
        if "task_column_id" in column_mapping:
            content = content.replace(
                "MONDAY_TASK_COLUMN_ID=your_task_column_id_here",
                f"MONDAY_TASK_COLUMN_ID={column_mapping['task_column_id']}"
            )
            logger.info(f"✅ MONDAY_TASK_COLUMN_ID mis à jour: {column_mapping['task_column_id']}")
        
        # Écrire le fichier .env mis à jour
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"✅ Fichier {env_file_path} mis à jour avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour {env_file_path}: {e}")
        return False


async def main():
    """Fonction principale pour récupérer et configurer les column IDs Monday.com."""
    logger.info("🚀 Récupération automatique des column IDs Monday.com...")
    
    try:
        # Charger les settings
        settings = get_settings()
        board_id = settings.monday_board_id
        
        if not board_id or board_id == "your_monday_board_id_here":
            logger.error("❌ MONDAY_BOARD_ID non configuré dans .env")
            logger.info("💡 Configurez d'abord votre MONDAY_BOARD_ID dans le fichier .env")
            return False
        
        logger.info(f"📋 Analyse du board Monday.com: {board_id}")
        
        # Récupérer les colonnes du board
        result = await get_board_columns(board_id)
        
        if not result["success"]:
            logger.error(f"❌ Échec récupération colonnes: {result['error']}")
            return False
        
        logger.info(f"📊 Board trouvé: {result['board_name']}")
        logger.info(f"📄 {len(result['columns'])} colonnes détectées")
        
        # Afficher toutes les colonnes pour information
        print("\n📋 COLONNES DISPONIBLES:")
        print("-" * 60)
        for column in result["columns"]:
            print(f"  • {column['title']} (Type: {column['type']}, ID: {column['id']})")
        
        # Identifier les colonnes pertinentes
        column_mapping = find_relevant_columns(result["columns"])
        
        if not column_mapping:
            logger.warning("⚠️ Aucune colonne pertinente automatiquement identifiée")
            logger.info("💡 Vérifiez manuellement les colonnes ci-dessus et configurez les IDs dans .env")
            return False
        
        print("\n🎯 MAPPING IDENTIFIÉ:")
        print("-" * 40)
        for key, value in column_mapping.items():
            print(f"  • {key}: {value}")
        
        # Mettre à jour le fichier .env
        success = update_env_file(column_mapping)
        
        if success:
            logger.info("🎉 Configuration Monday.com terminée avec succès !")
            logger.info("♻️ Redémarrez l'application pour prendre en compte les nouveaux IDs")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 