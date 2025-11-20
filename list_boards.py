#!/usr/bin/env python3
"""Script simple pour lister tous les boards Monday.com accessibles."""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.monday_tool import MondayTool


async def main():
    """Liste tous les boards accessibles."""
    print("\n🔍 Récupération des boards Monday.com...\n")
    
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
            active_boards = [b for b in boards if b.get("state") == "active"]
            
            print(f"📊 {len(active_boards)} board(s) actif(s) trouvé(s):\n")
            print("=" * 80)
            
            for i, board in enumerate(active_boards, 1):
                print(f"\n{i}. {board['name']}")
                print(f"   📋 Board ID: {board['id']}")
                if board.get('description'):
                    print(f"   📝 Description: {board['description']}")
            
            print("\n" + "=" * 80)
        else:
            print("❌ Aucun board trouvé")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

