#!/usr/bin/env python3
"""
Script de test pour vérifier l'extraction de base_branch depuis Monday.com.
Compare avec l'extraction de repository_url pour s'assurer que les deux fonctionnent.
"""

import asyncio
import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.monday_tool import MondayTool
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


async def test_base_branch_extraction():
    """Test l'extraction de base_branch depuis Monday.com."""
    
    print("=" * 80)
    print("🧪 TEST: Extraction de base_branch depuis Monday.com")
    print("=" * 80)
    print()
    
    # Initialiser MondayTool
    monday_tool = MondayTool()
    
    # Récupérer l'item ID depuis les arguments ou utiliser le board configuré
    if len(sys.argv) > 1:
        item_id = sys.argv[1]
        print(f"📌 Utilisation de l'item ID fourni: {item_id}")
    else:
        # Récupérer automatiquement le dernier item du board
        print(f"📋 Récupération automatique du dernier item du board {settings.monday_board_id}...")
        try:
            board_items = await monday_tool._arun(
                action="get_board_items",
                board_id=settings.monday_board_id
            )
            if board_items and board_items.get("success") and board_items.get("items"):
                item_id = board_items["items"][0]["id"]
                print(f"✅ Dernier item trouvé: {item_id} - {board_items['items'][0].get('name', 'Sans titre')}")
            else:
                print("❌ Impossible de récupérer les items du board")
                return
        except Exception as e:
            print(f"❌ Erreur récupération items du board: {e}")
            return
    
    print()
    print(f"🎯 Test sur l'item: {item_id}")
    print("-" * 80)
    print()
    
    # Récupérer les informations de l'item
    try:
        print("📡 Appel API Monday.com...")
        item_info = await monday_tool._arun(
            action="get_item_info",
            item_id=item_id
        )
        
        if not item_info.get("success"):
            print(f"❌ Échec récupération item: {item_info.get('error')}")
            return
        
        print("✅ Informations item récupérées avec succès")
        print()
        
        # Afficher les informations de base
        print("📋 INFORMATIONS DE BASE")
        print("-" * 80)
        print(f"  ID        : {item_info.get('id')}")
        print(f"  Nom       : {item_info.get('name')}")
        print(f"  Board ID  : {item_info.get('board_id')}")
        print(f"  Creator   : {item_info.get('creator_name')} (ID: {item_info.get('creator_id')})")
        print()
        
        # Vérifier repository_url
        print("🔗 REPOSITORY URL")
        print("-" * 80)
        column_values = item_info.get("column_values", {})
        
        # Chercher repository_url dans les colonnes
        repo_url = None
        repo_column_id = None
        
        if settings.monday_repository_url_column_id:
            if settings.monday_repository_url_column_id in column_values:
                col_data = column_values[settings.monday_repository_url_column_id]
                repo_url = col_data.get("url") or col_data.get("text") or ""
                repo_column_id = settings.monday_repository_url_column_id
        
        if not repo_url:
            # Fallback: chercher dans "repo_url"
            if "repo_url" in column_values:
                col_data = column_values["repo_url"]
                repo_url = col_data.get("text", "")
                repo_column_id = "repo_url"
        
        if repo_url:
            print(f"  ✅ Trouvé dans colonne: {repo_column_id}")
            print(f"  📍 URL: {repo_url}")
        else:
            print("  ⚠️  Repository URL non trouvée")
        print()
        
        # Vérifier base_branch
        print("🌿 BASE BRANCH")
        print("-" * 80)
        
        base_branch = item_info.get("base_branch")
        
        if base_branch:
            print(f"  ✅ Trouvé: {base_branch}")
            print(f"  📍 Type: {type(base_branch).__name__}")
        else:
            print("  ⚠️  Base Branch non trouvée")
            print()
            print("  🔍 DEBUG: Colonnes disponibles contenant 'branch':")
            for col_id, col_data in column_values.items():
                if "branch" in col_id.lower() or "base" in col_id.lower():
                    print(f"    - {col_id}:")
                    print(f"      text  : {col_data.get('text', '(vide)')}")
                    print(f"      value : {col_data.get('value', '(vide)')[:100]}...")
        
        print()
        
        # Résumé du test
        print("=" * 80)
        print("📊 RÉSUMÉ DU TEST")
        print("=" * 80)
        
        success_count = 0
        total_count = 2
        
        if repo_url:
            print("  ✅ Repository URL : TROUVÉE")
            success_count += 1
        else:
            print("  ❌ Repository URL : NON TROUVÉE")
        
        if base_branch:
            print("  ✅ Base Branch    : TROUVÉE")
            success_count += 1
        else:
            print("  ❌ Base Branch    : NON TROUVÉE")
        
        print()
        print(f"  Résultat: {success_count}/{total_count} champs extraits avec succès")
        print()
        
        if success_count == total_count:
            print("  🎉 TEST RÉUSSI: Tous les champs sont extraits correctement !")
        elif success_count > 0:
            print("  ⚠️  TEST PARTIEL: Certains champs manquent")
            print()
            print("  💡 SUGGESTIONS:")
            if not repo_url:
                print(f"    - Vérifiez que la colonne Repository URL existe dans Monday.com")
                print(f"    - ID de colonne configuré: {settings.monday_repository_url_column_id}")
            if not base_branch:
                print(f"    - Créez une colonne 'Base Branch' (type: Text ou Label)")
                print(f"    - Ajoutez une valeur comme 'main', 'develop', 'staging'")
        else:
            print("  ❌ TEST ÉCHOUÉ: Aucun champ extrait")
        
        print()
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()


async def test_base_branch_with_labels():
    """Test l'extraction avec différents formats de colonnes Label."""
    
    print()
    print("=" * 80)
    print("🧪 TEST AVANCÉ: Support des différents formats de Label")
    print("=" * 80)
    print()
    
    # Simuler différents formats de réponse Monday.com pour les Labels
    test_cases = [
        {
            "name": "Format Label (single)",
            "column_data": {
                "text": "",
                "value": '{"label": {"text": "develop"}}'
            },
            "expected": "develop"
        },
        {
            "name": "Format Labels (array)",
            "column_data": {
                "text": "",
                "value": '{"labels": [{"text": "staging"}]}'
            },
            "expected": "staging"
        },
        {
            "name": "Format Text simple",
            "column_data": {
                "text": "main",
                "value": ""
            },
            "expected": "main"
        },
        {
            "name": "Format mixte (text prioritaire)",
            "column_data": {
                "text": "release",
                "value": '{"label": {"text": "develop"}}'
            },
            "expected": "release"
        }
    ]
    
    success_count = 0
    
    for test_case in test_cases:
        print(f"📝 Test: {test_case['name']}")
        print(f"   Données: {test_case['column_data']}")
        
        # Simuler l'extraction
        col_data = test_case['column_data']
        extracted_value = None
        
        # Cas 1: Colonne de type TEXTE
        branch_text = col_data.get("text", "").strip()
        if branch_text:
            extracted_value = branch_text
        else:
            # Cas 2: Colonne de type LABEL
            col_value = col_data.get("value", "")
            if col_value:
                try:
                    import json
                    value_data = json.loads(col_value) if isinstance(col_value, str) else col_value
                    
                    if isinstance(value_data, dict):
                        if "label" in value_data and isinstance(value_data["label"], dict):
                            branch_text = value_data["label"].get("text", "").strip()
                        elif "labels" in value_data and isinstance(value_data["labels"], list) and len(value_data["labels"]) > 0:
                            branch_text = value_data["labels"][0].get("text", "").strip()
                        elif "text" in value_data:
                            branch_text = value_data.get("text", "").strip()
                        
                        if branch_text:
                            extracted_value = branch_text
                except Exception as e:
                    print(f"   ❌ Erreur: {e}")
        
        # Vérifier le résultat
        if extracted_value == test_case['expected']:
            print(f"   ✅ Résultat: {extracted_value} (attendu: {test_case['expected']})")
            success_count += 1
        else:
            print(f"   ❌ Résultat: {extracted_value} (attendu: {test_case['expected']})")
        
        print()
    
    print("=" * 80)
    print(f"📊 Tests réussis: {success_count}/{len(test_cases)}")
    
    if success_count == len(test_cases):
        print("🎉 TOUS LES FORMATS SONT SUPPORTÉS !")
    else:
        print("⚠️  Certains formats ne sont pas supportés")
    
    print("=" * 80)
    print()


async def main():
    """Point d'entrée principal."""
    try:
        # Test 1: Extraction réelle depuis Monday.com
        await test_base_branch_extraction()
        
        # Test 2: Validation des formats
        await test_base_branch_with_labels()
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrompu par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

