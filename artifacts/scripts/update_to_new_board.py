#!/usr/bin/env python3
"""
Script pour mettre à jour la configuration vers le nouveau board Monday.com.
"""

import sys
import asyncio
import httpx
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings


async def check_board_info(board_id: str, api_token: str):
    """Récupère les informations du board."""
    print(f"\n🔍 Vérification du board {board_id}...")
    
    query = """
    query ($boardId: [ID!]) {
        boards(ids: $boardId) {
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
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.monday.com/v2",
                json={
                    "query": query,
                    "variables": {"boardId": [int(board_id)]}
                },
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "errors" in data:
                    print(f"❌ Erreur API: {data['errors'][0].get('message')}")
                    return None
                
                boards = data.get("data", {}).get("boards", [])
                
                if not boards:
                    print(f"❌ Board {board_id} non trouvé")
                    return None
                
                board = boards[0]
                print(f"✅ Board trouvé: {board['name']}")
                print(f"   État: {board['state']}")
                print(f"   Workspace: {board.get('workspace', {}).get('name', 'N/A')}")
                print(f"   Colonnes: {len(board['columns'])}")
                
                return board
                
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None


def generate_env_config(board_id: str, board_data: dict):
    """Génère la configuration .env pour le nouveau board."""
    print("\n" + "="*60)
    print("📝 CONFIGURATION À METTRE À JOUR")
    print("="*60)
    
    print(f"\n🔹 Board ID: {board_id}")
    print(f"🔹 Board Name: {board_data['name']}")
    print(f"\n📋 Colonnes disponibles:\n")
    
    status_col = None
    repo_col = None
    
    for col in board_data['columns']:
        print(f"   • {col['title']:<30} (ID: {col['id']:<20} Type: {col['type']})")
        
        # Identifier automatiquement les colonnes importantes
        if col['type'] == 'status':
            status_col = col['id']
        elif col['type'] == 'link' and 'repo' in col['title'].lower():
            repo_col = col['id']
    
    print("\n" + "="*60)
    print("📝 VARIABLES À METTRE À JOUR DANS VOTRE .env")
    print("="*60)
    
    print(f"\nMONDAY_BOARD_ID={board_id}")
    
    if status_col:
        print(f"MONDAY_STATUS_COLUMN_ID={status_col}")
    else:
        print("# MONDAY_STATUS_COLUMN_ID=<ID de votre colonne status>")
    
    if repo_col:
        print(f"MONDAY_REPOSITORY_URL_COLUMN_ID={repo_col}")
    else:
        print("# MONDAY_REPOSITORY_URL_COLUMN_ID=<ID de votre colonne repository URL>")
    
    print("\n" + "="*60)
    print("✅ Copiez ces lignes dans votre fichier .env")
    print("="*60)


async def main():
    """Point d'entrée principal."""
    print("\n" + "="*60)
    print("🔄 MISE À JOUR VERS LE NOUVEAU BOARD MONDAY.COM")
    print("="*60)
    
    # Récupérer le nouveau board ID depuis l'argument ou l'URL
    if len(sys.argv) > 1:
        new_board_id = sys.argv[1]
    else:
        print("\n❌ Veuillez fournir le Board ID")
        print("\nUsage: python3 update_to_new_board.py <BOARD_ID>")
        print("\nExemple: python3 update_to_new_board.py 5037922237")
        return
    
    settings = get_settings()
    
    # Vérifier le board
    board_data = await check_board_info(new_board_id, settings.monday_api_token)
    
    if board_data:
        generate_env_config(new_board_id, board_data)
    else:
        print("\n❌ Impossible de récupérer les informations du board")
        print("\n💡 Vérifiez que:")
        print("   1. Le Board ID est correct")
        print("   2. Votre token API a accès à ce board")
        print("   3. Le board n'est pas archivé")


if __name__ == "__main__":
    asyncio.run(main())

