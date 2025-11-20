#!/usr/bin/env python3
"""
Script pour lister tous les boards Monday.com accessibles avec le token actuel.
"""

import sys
import asyncio
import httpx
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings


async def list_boards():
    """Liste tous les boards accessibles."""
    print("\n" + "="*60)
    print("📋 LISTE DES BOARDS MONDAY.COM ACCESSIBLES")
    print("="*60)
    
    settings = get_settings()
    
    query = """
    query {
        me {
            id
            name
            email
            account {
                name
                id
            }
        }
        boards(limit: 50) {
            id
            name
            description
            state
            workspace {
                id
                name
            }
            columns {
                id
                title
                type
            }
        }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {settings.monday_api_token}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.monday.com/v2",
                json={"query": query},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "errors" in data:
                    print(f"❌ Erreur API: {data['errors'][0].get('message')}")
                    return
                
                # Informations utilisateur
                me = data.get("data", {}).get("me", {})
                print(f"\n👤 Connecté en tant que:")
                print(f"   • Nom: {me.get('name')}")
                print(f"   • Email: {me.get('email')}")
                print(f"   • Compte: {me.get('account', {}).get('name')}")
                
                # Liste des boards
                boards = data.get("data", {}).get("boards", [])
                
                if not boards:
                    print("\n❌ Aucun board accessible avec ce token")
                    return
                
                print(f"\n📋 {len(boards)} board(s) accessible(s):\n")
                print("="*60)
                
                for i, board in enumerate(boards, 1):
                    print(f"\n{i}. {board['name']}")
                    print(f"   • Board ID: {board['id']}")
                    print(f"   • État: {board['state']}")
                    
                    workspace = board.get('workspace')
                    if workspace:
                        print(f"   • Workspace: {workspace.get('name')}")
                    
                    print(f"   • Nombre de colonnes: {len(board['columns'])}")
                    
                    # Afficher les colonnes importantes
                    important_cols = []
                    for col in board['columns']:
                        if col['type'] in ['status', 'link', 'text']:
                            important_cols.append(f"{col['title']} ({col['type']})")
                    
                    if important_cols:
                        print(f"   • Colonnes: {', '.join(important_cols[:3])}")
                        if len(important_cols) > 3:
                            print(f"              ... et {len(important_cols) - 3} autre(s)")
                
                print("\n" + "="*60)
                print("\n💡 Pour utiliser un board, copiez son ID dans votre .env :")
                print("   MONDAY_BOARD_ID=<Board ID>")
                print("="*60)
                
            else:
                print(f"❌ Erreur HTTP {response.status_code}")
                
    except Exception as e:
        print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    asyncio.run(list_boards())

