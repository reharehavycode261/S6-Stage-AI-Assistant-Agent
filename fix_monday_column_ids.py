#!/usr/bin/env python3
"""
Script pour récupérer et corriger automatiquement les Column IDs Monday.com
Correction de l'erreur: "This column ID doesn't exist for the board"
"""

import asyncio
import json
import os
from pathlib import Path
import aiohttp
from typing import Dict, List

# Configuration
MONDAY_API_URL = "https://api.monday.com/v2"

async def get_board_columns(board_id: str, api_token: str) -> Dict:
    """Récupérer toutes les colonnes d'un board Monday.com."""
    
    query = """
    query GetBoardColumns($boardId: ID!) {
        boards(ids: [$boardId]) {
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
    
    variables = {"boardId": board_id}
    
    headers = {
        "Authorization": api_token,
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            MONDAY_API_URL,
            json={"query": query, "variables": variables},
            headers=headers
        ) as response:
            data = await response.json()
            
            if "errors" in data:
                return {"success": False, "error": data["errors"]}
            
            if not data.get("data", {}).get("boards"):
                return {"success": False, "error": "Board non trouvé"}
            
            board = data["data"]["boards"][0]
            return {
                "success": True,
                "board_name": board["name"],
                "columns": board["columns"]
            }


def find_status_column(columns: List[Dict]) -> str:
    """Trouver le column ID du statut."""
    # Chercher une colonne de type 'status'
    for col in columns:
        if col["type"] == "status":
            print(f"✅ Colonne statut trouvée: '{col['title']}' (ID: {col['id']})")
            return col["id"]
    
    # Chercher par nom commun
    common_names = ["status", "statut", "état", "state"]
    for col in columns:
        if col["title"].lower() in common_names:
            print(f"✅ Colonne statut trouvée par nom: '{col['title']}' (ID: {col['id']})")
            return col["id"]
    
    return None


def find_link_column(columns: List[Dict]) -> str:
    """Trouver le column ID pour les liens (Repository URL)."""
    # Chercher une colonne de type 'link'
    for col in columns:
        if col["type"] == "link":
            print(f"✅ Colonne link trouvée: '{col['title']}' (ID: {col['id']})")
            return col["id"]
    
    # Chercher par nom
    link_names = ["link", "repository url", "repo url", "url", "lien"]
    for col in columns:
        if any(name in col["title"].lower() for name in link_names):
            print(f"✅ Colonne link trouvée par nom: '{col['title']}' (ID: {col['id']})")
            return col["id"]
    
    return None


def update_env_file(status_column_id: str, link_column_id: str) -> bool:
    """Mettre à jour le fichier .env avec les bons column IDs."""
    
    env_path = Path(".env")
    
    if not env_path.exists():
        print("❌ Fichier .env non trouvé")
        return False
    
    # Lire le fichier
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Mettre à jour les lignes
    updated_lines = []
    status_updated = False
    link_updated = False
    
    for line in lines:
        if line.startswith("MONDAY_STATUS_COLUMN_ID="):
            updated_lines.append(f"MONDAY_STATUS_COLUMN_ID={status_column_id}\n")
            status_updated = True
            print(f"🔄 MONDAY_STATUS_COLUMN_ID mis à jour: {status_column_id}")
        elif line.startswith("MONDAY_REPOSITORY_URL_COLUMN_ID="):
            updated_lines.append(f"MONDAY_REPOSITORY_URL_COLUMN_ID={link_column_id}\n")
            link_updated = True
            print(f"🔄 MONDAY_REPOSITORY_URL_COLUMN_ID mis à jour: {link_column_id}")
        else:
            updated_lines.append(line)
    
    # Ajouter si manquant
    if not status_updated:
        updated_lines.append(f"MONDAY_STATUS_COLUMN_ID={status_column_id}\n")
        print(f"➕ MONDAY_STATUS_COLUMN_ID ajouté: {status_column_id}")
    
    if not link_updated:
        updated_lines.append(f"MONDAY_REPOSITORY_URL_COLUMN_ID={link_column_id}\n")
        print(f"➕ MONDAY_REPOSITORY_URL_COLUMN_ID ajouté: {link_column_id}")
    
    # Écrire le fichier
    with open(env_path, 'w') as f:
        f.writelines(updated_lines)
    
    print("✅ Fichier .env mis à jour")
    return True


async def main():
    print("\n" + "="*80)
    print("🔧 CORRECTION DES COLUMN IDS MONDAY.COM")
    print("="*80)
    print()
    
    # Charger les variables d'environnement
    from dotenv import load_dotenv
    load_dotenv()
    
    api_token = os.getenv("MONDAY_API_TOKEN")
    board_id = os.getenv("MONDAY_BOARD_ID")
    
    if not api_token:
        print("❌ MONDAY_API_TOKEN non trouvé dans .env")
        return 1
    
    if not board_id:
        print("❌ MONDAY_BOARD_ID non trouvé dans .env")
        return 1
    
    print(f"📋 Board ID: {board_id}")
    print()
    
    # Récupérer les colonnes du board
    print("🔍 Récupération des colonnes du board...")
    result = await get_board_columns(board_id, api_token)
    
    if not result["success"]:
        print(f"❌ Erreur: {result['error']}")
        return 1
    
    print(f"✅ Board trouvé: {result['board_name']}")
    print(f"📊 {len(result['columns'])} colonnes disponibles")
    print()
    
    # Afficher toutes les colonnes
    print("="*80)
    print("📋 TOUTES LES COLONNES DISPONIBLES")
    print("="*80)
    print()
    
    for col in result['columns']:
        print(f"  • {col['title']:30s} Type: {col['type']:15s} ID: {col['id']}")
    
    print()
    print("="*80)
    print("🔍 IDENTIFICATION DES COLONNES CRITIQUES")
    print("="*80)
    print()
    
    # Identifier les colonnes
    status_column_id = find_status_column(result['columns'])
    link_column_id = find_link_column(result['columns'])
    
    if not status_column_id:
        print("❌ Colonne de statut non trouvée automatiquement")
        print("💡 Veuillez configurer manuellement MONDAY_STATUS_COLUMN_ID dans .env")
        return 1
    
    if not link_column_id:
        print("⚠️  Colonne de lien non trouvée (optionnel)")
        link_column_id = "link"  # Valeur par défaut
    
    print()
    print("="*80)
    print("📝 MISE À JOUR DU FICHIER .ENV")
    print("="*80)
    print()
    
    success = update_env_file(status_column_id, link_column_id)
    
    if success:
        print()
        print("="*80)
        print("✅ CORRECTION TERMINÉE")
        print("="*80)
        print()
        print("💡 Prochaines étapes:")
        print("   1. Redémarrer le serveur FastAPI")
        print("   2. Redémarrer Celery")
        print("   3. Tester un nouveau webhook Monday.com")
        print()
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

