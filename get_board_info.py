#!/usr/bin/env python3
"""Script pour récupérer les informations d'un board Monday.com spécifique."""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.monday_tool import MondayTool


async def get_board_info(board_id: str):
    """Récupère les colonnes d'un board spécifique."""
    print(f"\n🔍 Récupération des informations du board {board_id}...\n")
    
    monday_tool = MondayTool()
    
    query = """
    query GetBoardColumns($boardId: [ID!]) {
        boards(ids: $boardId) {
            id
            name
            description
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
            board = result["data"]["boards"][0]
            
            print("=" * 80)
            print(f"📊 Board: {board['name']}")
            print(f"📋 Board ID: {board['id']}")
            if board.get('description'):
                print(f"📝 Description: {board['description']}")
            print("=" * 80)
            
            print(f"\n📄 {len(board['columns'])} colonne(s) disponible(s):\n")
            
            # Identifier automatiquement les colonnes importantes
            status_col = None
            task_col = None
            repo_col = None
            
            for i, column in enumerate(board['columns'], 1):
                col_type = column['type']
                col_title = column['title']
                col_id = column['id']
                col_title_lower = col_title.lower()
                
                marker = "  "
                
                # Identifier la colonne de statut
                if col_type in ["color", "status"] and any(k in col_title_lower for k in ["status", "statut", "état"]):
                    marker = "✅ STATUS"
                    status_col = col_id
                
                # Identifier la colonne de tâche/nom
                elif col_type == "name":
                    marker = "✅ TASK/NAME"
                    task_col = col_id
                
                # Identifier la colonne Repository URL
                elif col_type in ["text", "long_text", "link"] and any(k in col_title_lower for k in ["repository", "repo", "url", "git"]):
                    marker = "✅ REPO URL"
                    repo_col = col_id
                
                print(f"{i}. [{marker}] {col_title}")
                print(f"   Type: {col_type}")
                print(f"   ID: {col_id}")
                print()
            
            print("=" * 80)
            print("\n🎯 CONFIGURATION SUGGÉRÉE POUR .env:\n")
            print(f"MONDAY_BOARD_ID={board['id']}")
            
            if task_col:
                print(f"MONDAY_TASK_COLUMN_ID={task_col}")
            else:
                print("MONDAY_TASK_COLUMN_ID=<À_DÉFINIR_MANUELLEMENT>")
            
            if status_col:
                print(f"MONDAY_STATUS_COLUMN_ID={status_col}")
            else:
                print("MONDAY_STATUS_COLUMN_ID=<À_DÉFINIR_MANUELLEMENT>")
            
            if repo_col:
                print(f"MONDAY_REPOSITORY_URL_COLUMN_ID={repo_col}")
            else:
                print("# MONDAY_REPOSITORY_URL_COLUMN_ID=<OPTIONNEL>")
            
            print("\n" + "=" * 80)
            
            return {
                "board_id": board['id'],
                "task_column_id": task_col,
                "status_column_id": status_col,
                "repository_url_column_id": repo_col
            }
        else:
            print(f"❌ Board {board_id} introuvable")
            print(f"Résultat: {result}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Fonction principale."""
    if len(sys.argv) < 2:
        print("Usage: python get_board_info.py <BOARD_ID>")
        print("\nExemple: python get_board_info.py 1234567890")
        print("\nPour voir la liste des boards disponibles, exécutez:")
        print("  python list_boards.py")
        sys.exit(1)
    
    board_id = sys.argv[1]
    result = await get_board_info(board_id)
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

