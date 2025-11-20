#!/usr/bin/env python3
"""Script pour vérifier/créer la colonne 'Repository URL' dans Monday.com."""

import asyncio
import sys
import os

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.monday_tool import MondayTool
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


async def check_repository_url_column(board_id: str) -> dict:
    """
    Vérifie si la colonne 'Repository URL' existe sur le board Monday.com.
    
    Args:
        board_id: ID du board Monday.com
        
    Returns:
        Dictionnaire avec les informations de la colonne
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
            }
        }
    }
    """
    
    variables = {"boardId": [board_id]}
    
    try:
        result = await monday_tool._make_request(query, variables)
        
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Erreur inconnue")
            }
        
        if not result.get("data", {}).get("boards"):
            return {
                "success": False,
                "error": f"Board {board_id} non trouvé"
            }
        
        board_data = result["data"]["boards"][0]
        columns = board_data["columns"]
        
        # Chercher une colonne pour l'URL du repository
        repository_column = None
        for column in columns:
            title_lower = column["title"].lower()
            column_id_lower = column["id"].lower()
            
            # Rechercher par titre ou ID
            if any(keyword in title_lower for keyword in ["repository url", "repo url", "github url", "repository", "repo"]):
                if column["type"] in ["text", "link"]:
                    repository_column = column
                    logger.info(f"✅ Colonne trouvée: '{column['title']}' (ID: {column['id']}, Type: {column['type']})")
                    break
            elif any(keyword in column_id_lower for keyword in ["repository_url", "repo_url", "github_url"]):
                repository_column = column
                logger.info(f"✅ Colonne trouvée par ID: '{column['title']}' (ID: {column['id']}, Type: {column['type']})")
                break
        
        if repository_column:
            return {
                "success": True,
                "exists": True,
                "column_id": repository_column["id"],
                "column_title": repository_column["title"],
                "column_type": repository_column["type"]
            }
        else:
            # Liste toutes les colonnes pour aider l'utilisateur
            logger.warning("⚠️ Colonne 'Repository URL' non trouvée")
            logger.info("📋 Colonnes disponibles:")
            for col in columns:
                logger.info(f"  • {col['title']} (ID: {col['id']}, Type: {col['type']})")
            
            return {
                "success": True,
                "exists": False,
                "message": "Colonne 'Repository URL' non trouvée",
                "available_columns": columns
            }
    
    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def create_repository_url_column(board_id: str) -> dict:
    """
    Crée une colonne 'Repository URL' sur le board Monday.com.
    
    Note: La création de colonnes via l'API Monday.com nécessite des permissions
    spéciales et n'est pas toujours disponible. Cette fonction tente de créer
    la colonne mais peut échouer selon les permissions du token.
    
    Args:
        board_id: ID du board Monday.com
        
    Returns:
        Dictionnaire avec le résultat de la création
    """
    monday_tool = MondayTool()
    
    # Mutation pour créer une colonne
    # Note: Cette mutation peut nécessiter des permissions administrateur
    mutation = """
    mutation CreateColumn($boardId: ID!, $title: String!, $columnType: ColumnType!) {
        create_column(
            board_id: $boardId,
            title: $title,
            column_type: $columnType
        ) {
            id
            title
            type
        }
    }
    """
    
    variables = {
        "boardId": board_id,
        "title": "Repository URL",
        "columnType": "text"
    }
    
    try:
        result = await monday_tool._make_request(mutation, variables)
        
        if result.get("success") and result.get("data", {}).get("create_column"):
            column_data = result["data"]["create_column"]
            logger.info(f"✅ Colonne créée: {column_data['title']} (ID: {column_data['id']})")
            return {
                "success": True,
                "created": True,
                "column_id": column_data["id"],
                "column_title": column_data["title"]
            }
        else:
            error_msg = result.get("error", "Erreur inconnue lors de la création")
            logger.error(f"❌ Échec création colonne: {error_msg}")
            return {
                "success": False,
                "created": False,
                "error": error_msg
            }
    
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création: {e}", exc_info=True)
        return {
            "success": False,
            "created": False,
            "error": str(e)
        }


async def update_env_with_column_id(column_id: str, env_file_path: str = ".env"):
    """
    Met à jour le fichier .env avec l'ID de la colonne Repository URL.
    
    Args:
        column_id: ID de la colonne Repository URL
        env_file_path: Chemin vers le fichier .env
    """
    try:
        if not os.path.exists(env_file_path):
            logger.error(f"❌ Fichier {env_file_path} introuvable")
            return False
        
        # Lire le fichier .env
        with open(env_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Chercher et mettre à jour la ligne MONDAY_REPOSITORY_URL_COLUMN_ID
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("MONDAY_REPOSITORY_URL_COLUMN_ID="):
                lines[i] = f"MONDAY_REPOSITORY_URL_COLUMN_ID={column_id}\n"
                updated = True
                break
        
        # Si la ligne n'existe pas, l'ajouter
        if not updated:
            lines.append(f"\n# Monday.com Repository URL Column\n")
            lines.append(f"MONDAY_REPOSITORY_URL_COLUMN_ID={column_id}\n")
        
        # Écrire le fichier .env mis à jour
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        logger.info(f"✅ Fichier .env mis à jour avec MONDAY_REPOSITORY_URL_COLUMN_ID={column_id}")
        return True
    
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour .env: {e}")
        return False


async def main():
    """Fonction principale."""
    logger.info("🚀 Vérification de la colonne 'Repository URL' dans Monday.com...")
    
    try:
        settings = get_settings()
        board_id = settings.monday_board_id
        
        if not board_id or board_id == "your_monday_board_id_here":
            logger.error("❌ MONDAY_BOARD_ID non configuré dans .env")
            return False
        
        # Vérifier si la colonne existe
        logger.info(f"📋 Vérification du board: {board_id}")
        result = await check_repository_url_column(board_id)
        
        if not result["success"]:
            logger.error(f"❌ Erreur: {result['error']}")
            return False
        
        if result["exists"]:
            logger.info(f"✅ La colonne 'Repository URL' existe déjà!")
            logger.info(f"   Titre: {result['column_title']}")
            logger.info(f"   ID: {result['column_id']}")
            logger.info(f"   Type: {result['column_type']}")
            
            # Mettre à jour le .env
            await update_env_with_column_id(result['column_id'])
            return True
        else:
            logger.warning("⚠️ La colonne 'Repository URL' n'existe pas")
            logger.info("💡 Vous devez créer manuellement une colonne de type 'Texte' ou 'Lien'")
            logger.info("   nommée 'Repository URL' dans votre board Monday.com")
            logger.info("")
            logger.info("🔧 Étapes pour créer la colonne:")
            logger.info("   1. Ouvrez votre board Monday.com")
            logger.info("   2. Cliquez sur le bouton '+' pour ajouter une colonne")
            logger.info("   3. Sélectionnez le type 'Texte' ou 'Lien'")
            logger.info("   4. Nommez la colonne 'Repository URL'")
            logger.info("   5. Relancez ce script pour configurer automatiquement l'ID")
            logger.info("")
            
            # Tentative de création automatique (peut échouer selon les permissions)
            logger.info("🔄 Tentative de création automatique...")
            create_result = await create_repository_url_column(board_id)
            
            if create_result.get("created"):
                logger.info("🎉 Colonne créée automatiquement avec succès!")
                await update_env_with_column_id(create_result['column_id'])
                return True
            else:
                logger.warning("⚠️ Création automatique impossible (permissions insuffisantes)")
                logger.info("   Veuillez créer la colonne manuellement comme indiqué ci-dessus")
                return False
    
    except Exception as e:
        logger.error(f"❌ Erreur: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

