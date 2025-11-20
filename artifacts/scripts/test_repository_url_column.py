#!/usr/bin/env python3
"""
Script pour tester que la colonne Repository URL est bien définie et accessible.
"""

import sys
import asyncio
import httpx
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings


async def test_repository_url_column():
    """Teste l'accès à la colonne Repository URL."""
    print("\n" + "="*60)
    print("🔍 TEST DE LA COLONNE REPOSITORY URL")
    print("="*60)
    
    settings = get_settings()
    
    print("\n📋 Configuration actuelle:")
    print(f"   Board ID: {settings.monday_board_id}")
    print(f"   Repository URL Column ID: {settings.monday_repository_url_column_id}")
    
    # Vérifier que la colonne est définie
    if not settings.monday_repository_url_column_id:
        print("\n❌ ERREUR: MONDAY_REPOSITORY_URL_COLUMN_ID n'est pas définie!")
        return False
    
    # Requête pour récupérer les colonnes du board
    query = """
    query ($boardId: [ID!]) {
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
    
    headers = {
        "Authorization": f"Bearer {settings.monday_api_token}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.monday.com/v2",
                json={
                    "query": query,
                    "variables": {"boardId": [int(settings.monday_board_id)]}
                },
                headers=headers
            )
            
            if response.status_code != 200:
                print(f"\n❌ Erreur HTTP {response.status_code}")
                return False
            
            data = response.json()
            
            if "errors" in data:
                print(f"\n❌ Erreur API: {data['errors'][0].get('message')}")
                return False
            
            boards = data.get("data", {}).get("boards", [])
            
            if not boards:
                print(f"\n❌ Board {settings.monday_board_id} non trouvé")
                return False
            
            board = boards[0]
            columns = board.get("columns", [])
            
            print(f"\n✅ Board trouvé: {board['name']}")
            print(f"   Nombre de colonnes: {len(columns)}")
            
            # Chercher la colonne Repository URL
            repo_column = None
            for col in columns:
                if col['id'] == settings.monday_repository_url_column_id:
                    repo_column = col
                    break
            
            print(f"\n🔍 Recherche de la colonne '{settings.monday_repository_url_column_id}'...")
            
            if repo_column:
                print(f"\n✅ COLONNE TROUVÉE!")
                print(f"   ID: {repo_column['id']}")
                print(f"   Titre: {repo_column['title']}")
                print(f"   Type: {repo_column['type']}")
                
                # Vérifier le type
                if repo_column['type'] == 'link':
                    print(f"\n✅ Type correct: 'link'")
                else:
                    print(f"\n⚠️  Type inattendu: '{repo_column['type']}' (attendu: 'link')")
                
                return True
            else:
                print(f"\n❌ COLONNE NON TROUVÉE!")
                print(f"\n📋 Colonnes disponibles dans le board:\n")
                
                link_columns = []
                for col in columns:
                    if col['type'] == 'link':
                        link_columns.append(col)
                    print(f"   • {col['title']:<30} (ID: {col['id']:<20} Type: {col['type']})")
                
                if link_columns:
                    print(f"\n💡 Colonnes de type 'link' disponibles:")
                    for col in link_columns:
                        print(f"   • {col['title']} (ID: {col['id']})")
                    
                    print(f"\n🔧 Pour utiliser une de ces colonnes, mettez à jour votre .env:")
                    print(f"   MONDAY_REPOSITORY_URL_COLUMN_ID={link_columns[0]['id']}")
                else:
                    print(f"\n⚠️  Aucune colonne de type 'link' trouvée dans le board")
                
                return False
                
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_extraction_logic():
    """Teste la logique d'extraction de l'URL du repository."""
    print("\n" + "="*60)
    print("🔧 TEST DE LA LOGIQUE D'EXTRACTION")
    print("="*60)
    
    settings = get_settings()
    
    # Exemple de données comme Monday.com les renvoie
    example_column_value = {
        "id": "link",
        "title": "Repository URL",
        "type": "link",
        "value": '{"url": "https://github.com/user/repo", "text": "https://github.com/user/repo"}'
    }
    
    print("\n📋 Exemple de valeur de colonne link:")
    print(f"   {example_column_value}")
    
    # Tester l'extraction
    import json
    try:
        value_data = json.loads(example_column_value['value'])
        url = value_data.get('url', '')
        
        print(f"\n✅ URL extraite: {url}")
        
        if url and url.startswith('https://github.com'):
            print(f"✅ Format GitHub valide")
            return True
        else:
            print(f"⚠️  URL non valide ou vide")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur d'extraction: {e}")
        return False


async def main():
    """Point d'entrée principal."""
    print("\n" + "="*60)
    print("🧪 TEST COMPLET DE LA COLONNE REPOSITORY URL")
    print("="*60)
    
    # Test 1: Vérifier que la colonne existe dans Monday.com
    test1 = await test_repository_url_column()
    
    # Test 2: Vérifier la logique d'extraction
    test2 = await test_extraction_logic()
    
    # Résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*60)
    
    print(f"\n1. Colonne existe dans Monday.com: {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"2. Logique d'extraction fonctionne: {'✅ PASS' if test2 else '❌ FAIL'}")
    
    if test1 and test2:
        print("\n" + "="*60)
        print("✅ TOUS LES TESTS RÉUSSIS!")
        print("="*60)
        print("\nLa colonne Repository URL est correctement configurée.")
    else:
        print("\n" + "="*60)
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("="*60)
        print("\nVeuillez corriger les problèmes identifiés ci-dessus.")


if __name__ == "__main__":
    asyncio.run(main())

