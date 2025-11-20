#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour peupler automatiquement les IDs Slack dans Monday.com.

Ce script :
1. Récupère tous les utilisateurs qui ont créé des items dans Monday.com
2. Pour chaque email trouvé, cherche l'ID Slack correspondant
3. Met à jour Monday.com avec l'ID Slack trouvé

Usage:
    python scripts/populate_slack_ids.py
"""

import asyncio
import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.monday_tool import MondayTool
from services.slack_notification_service import slack_notification_service
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


async def get_all_board_items():
    """Récupère tous les items du board Monday.com avec leurs créateurs."""
    monday_tool = MondayTool()
    
    query = """
    query ($boardId: [ID!]) {
        boards(ids: $boardId) {
            items_page(limit: 500) {
                items {
                    id
                    name
                    creator {
                        id
                        email
                        name
                    }
                }
            }
        }
    }
    """
    
    try:
        result = await monday_tool._make_request(query, {
            "boardId": [int(settings.monday_board_id)]
        })
        
        if result and result.get("data", {}).get("boards"):
            items = result["data"]["boards"][0]["items_page"]["items"]
            logger.info(f"✅ {len(items)} items récupérés depuis Monday.com")
            return items
        else:
            logger.error("❌ Impossible de récupérer les items")
            return []
            
    except Exception as e:
        logger.error(f"❌ Erreur récupération items: {e}")
        return []


async def update_slack_id_in_monday(item_id: str, slack_id: str):
    """Met à jour l'ID Slack dans Monday.com."""
    monday_tool = MondayTool()
    slack_column_id = settings.monday_slack_user_id_column_id
    
    if not slack_column_id:
        logger.error("❌ MONDAY_SLACK_USER_ID_COLUMN_ID non configuré dans .env")
        return False
    
    mutation = """
    mutation ($itemId: ID!, $columnId: String!, $value: String!) {
        change_simple_column_value(
            item_id: $itemId,
            column_id: $columnId,
            value: $value
        ) {
            id
        }
    }
    """
    
    try:
        result = await monday_tool._make_request(mutation, {
            "itemId": item_id,
            "columnId": slack_column_id,
            "value": slack_id
        })
        
        if result and result.get("data"):
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour Monday.com: {e}")
        return False


async def populate_slack_ids():
    """
    Fonction principale pour peupler les IDs Slack dans Monday.com.
    """
    logger.info("🚀 Démarrage du script de population des IDs Slack")
    logger.info("=" * 70)
    
    # Vérifier la configuration
    if not settings.slack_enabled:
        logger.error("❌ Slack est désactivé (SLACK_ENABLED=false)")
        return
    
    if not settings.slack_bot_token:
        logger.error("❌ SLACK_BOT_TOKEN non configuré")
        return
    
    if not settings.monday_slack_user_id_column_id:
        logger.error("❌ MONDAY_SLACK_USER_ID_COLUMN_ID non configuré")
        logger.info("ℹ️  Veuillez créer une colonne 'Slack User ID' dans Monday.com")
        logger.info("ℹ️  et ajouter son ID dans .env: MONDAY_SLACK_USER_ID_COLUMN_ID=text9__1")
        return
    
    # 1. Récupérer tous les items
    logger.info("\n📋 Étape 1: Récupération des items Monday.com...")
    items = await get_all_board_items()
    
    if not items:
        logger.error("❌ Aucun item trouvé")
        return
    
    # 2. Créer un dictionnaire email → items
    logger.info("\n👥 Étape 2: Collecte des emails uniques...")
    email_to_items = {}
    
    for item in items:
        creator = item.get("creator", {})
        email = creator.get("email")
        name = creator.get("name", "Unknown")
        
        if email:
            if email not in email_to_items:
                email_to_items[email] = {
                    "name": name,
                    "items": []
                }
            email_to_items[email]["items"].append(item["id"])
    
    logger.info(f"✅ {len(email_to_items)} emails uniques trouvés")
    
    # 3. Pour chaque email, trouver l'ID Slack
    logger.info("\n💬 Étape 3: Recherche des IDs Slack...")
    logger.info("=" * 70)
    
    stats = {
        "found": 0,
        "not_found": 0,
        "updated": 0,
        "errors": 0
    }
    
    for email, data in email_to_items.items():
        name = data["name"]
        item_ids = data["items"]
        
        logger.info(f"\n👤 {name} ({email})")
        logger.info(f"   └─> {len(item_ids)} item(s) à mettre à jour")
        
        # Chercher l'ID Slack
        slack_id = await slack_notification_service.get_user_id_by_email(email)
        
        if slack_id:
            logger.info(f"   ✅ ID Slack trouvé: {slack_id}")
            stats["found"] += 1
            
            # Mettre à jour tous les items de cet utilisateur
            for item_id in item_ids:
                success = await update_slack_id_in_monday(item_id, slack_id)
                
                if success:
                    stats["updated"] += 1
                    logger.info(f"      ✅ Item {item_id} mis à jour")
                else:
                    stats["errors"] += 1
                    logger.error(f"      ❌ Échec mise à jour item {item_id}")
                
                # Petit délai pour ne pas surcharger l'API
                await asyncio.sleep(0.5)
        else:
            logger.warning(f"   ⚠️  Aucun compte Slack trouvé")
            stats["not_found"] += 1
    
    # 4. Résumé
    logger.info("\n" + "=" * 70)
    logger.info("📊 RÉSUMÉ")
    logger.info("=" * 70)
    logger.info(f"✅ IDs Slack trouvés:        {stats['found']}")
    logger.info(f"⚠️  Utilisateurs sans Slack:  {stats['not_found']}")
    logger.info(f"✅ Items mis à jour:         {stats['updated']}")
    logger.info(f"❌ Erreurs:                  {stats['errors']}")
    logger.info("=" * 70)
    
    if stats["not_found"] > 0:
        logger.info("\n💡 CONSEIL:")
        logger.info("Les utilisateurs sans compte Slack doivent:")
        logger.info("1. S'assurer d'utiliser le même email dans Monday.com et Slack")
        logger.info("2. Être membres du workspace Slack où le bot est installé")
    
    logger.info("\n✅ Script terminé")


async def list_slack_users():
    """Liste tous les utilisateurs Slack disponibles (pour debug)."""
    logger.info("📋 Liste des utilisateurs Slack disponibles:")
    logger.info("=" * 70)
    
    try:
        from slack_sdk.web.async_client import AsyncWebClient
        client = AsyncWebClient(token=settings.slack_bot_token)
        
        response = await client.users_list()
        
        if response["ok"]:
            members = response["members"]
            
            for member in members:
                if not member.get("deleted") and not member.get("is_bot"):
                    name = member.get("name")
                    real_name = member.get("real_name", "")
                    email = member.get("profile", {}).get("email", "")
                    user_id = member.get("id")
                    
                    logger.info(f"👤 {name} ({real_name})")
                    logger.info(f"   Email: {email}")
                    logger.info(f"   ID: {user_id}")
                    logger.info("")
        else:
            logger.error(f"❌ Erreur API Slack: {response.get('error')}")
            
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Peupler les IDs Slack dans Monday.com"
    )
    parser.add_argument(
        "--list-slack-users",
        action="store_true",
        help="Lister tous les utilisateurs Slack disponibles"
    )
    
    args = parser.parse_args()
    
    if args.list_slack_users:
        asyncio.run(list_slack_users())
    else:
        asyncio.run(populate_slack_ids())

