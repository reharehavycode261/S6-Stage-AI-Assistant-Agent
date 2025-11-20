#!/usr/bin/env python3
"""
Trouver tous les boards accessibles avec le token API actuel
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tools.monday_tool import MondayTool
from config.settings import get_settings

async def get_all_boards(monday_tool: MondayTool):
    """Récupérer tous les boards accessibles."""
    
    query = """
    query {
        boards(limit: 50) {
            id
            name
            description
            state
            columns {
                id
                title
                type
            }
        }
    }
    """
    
    result = await monday_tool._make_request(query, {})
    
    if result.get("success") and result.get("data", {}).get("boards"):
        return {"success": True, "boards": result["data"]["boards"]}
    else:
        return {"success": False, "error": result.get("error", "Erreur")}


async def main():
    print("\n" + "="*80)
    print("🔍 RECHERCHE DES BOARDS MONDAY.COM ACCESSIBLES")
    print("="*80)
    print()
    
    try:
        settings = get_settings()
        print(f"📋 Board ID configuré: {settings.monday_board_id}")
        print()
        
        monday_tool = MondayTool()
        
        print("🔍 Récupération de tous les boards accessibles...")
        result = await get_all_boards(monday_tool)
        
        if not result.get("success"):
            print(f"❌ Erreur: {result.get('error')}")
            return 1
        
        boards = result["boards"]
        print(f"✅ {len(boards)} boards trouvés")
        print()
        
        print("="*80)
        print("📋 BOARDS ACCESSIBLES")
        print("="*80)
        print()
        
        for i, board in enumerate(boards, 1):
            print(f"{i}. {board['name']}")
            print(f"   • ID: {board['id']}")
            print(f"   • État: {board['state']}")
            if board.get('description'):
                print(f"   • Description: {board['description']}")
            
            # Afficher les colonnes
            status_columns = [col for col in board['columns'] if col['type'] == 'status']
            if status_columns:
                print(f"   • Colonnes de statut:")
                for col in status_columns:
                    print(f"      - {col['title']} (ID: {col['id']})")
            
            link_columns = [col for col in board['columns'] if col['type'] == 'link']
            if link_columns:
                print(f"   • Colonnes de lien:")
                for col in link_columns:
                    print(f"      - {col['title']} (ID: {col['id']})")
            
            print()
        
        # Suggérer le board à utiliser
        if boards:
            print("="*80)
            print("💡 RECOMMANDATION")
            print("="*80)
            print()
            print(f"Utilisez un de ces boards dans votre fichier .env:")
            print()
            for board in boards[:3]:  # Top 3
                print(f"MONDAY_BOARD_ID={board['id']}  # {board['name']}")
                
                # Trouver le status column
                status_cols = [col for col in board['columns'] if col['type'] == 'status']
                if status_cols:
                    print(f"MONDAY_STATUS_COLUMN_ID={status_cols[0]['id']}  # {status_cols[0]['title']}")
                
                # Trouver le link column
                link_cols = [col for col in board['columns'] if col['type'] == 'link']
                if link_cols:
                    print(f"MONDAY_REPOSITORY_URL_COLUMN_ID={link_cols[0]['id']}  # {link_cols[0]['title']}")
                
                print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

