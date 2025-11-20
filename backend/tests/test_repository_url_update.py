#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests pour la mise a jour automatique de la colonne Repository URL."""

import asyncio
import sys
import os
from datetime import datetime

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.github_pr_service import github_pr_service
from tools.monday_tool import MondayTool
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


async def test_github_pr_service():
    """Teste le service de recuperation de la derniere PR fusionnee."""
    logger.info("Test 1: Service de recuperation de la derniere PR fusionnee")
    
    # URL de test (repository public pour les tests)
    test_repo_url = "https://github.com/python/cpython"
    
    try:
        result = await github_pr_service.get_last_merged_pr(test_repo_url)
        
        if result and isinstance(result, dict) and result.get("success"):
            logger.info("Test reussi: Derniere PR fusionnee recuperee")
            logger.info(f"   PR #{result['pr_number']}: {result['pr_title']}")
            logger.info(f"   URL: {result['pr_url']}")
            logger.info(f"   Fusionnee le: {result['merged_at']}")
            return True
        else:
            error = result.get("error", "Erreur inconnue") if result and isinstance(result, dict) else "Resultat vide"
            logger.error(f"Test echoue: {error}")
            return False
    
    except Exception as e:
        logger.error(f"Exception lors du test: {e}", exc_info=True)
        return False


async def test_monday_column_existence():
    """Teste l'existence de la colonne Repository URL dans Monday.com."""
    logger.info("Test 2: Verification de la colonne Repository URL dans Monday")
    
    try:
        settings = get_settings()
        monday_tool = MondayTool()
        
        # Verifier que la configuration existe
        if not settings.monday_repository_url_column_id:
            logger.warning("MONDAY_REPOSITORY_URL_COLUMN_ID non configure dans .env")
            logger.info("Executez: python scripts/ensure_repository_url_column.py")
            return False
        
        logger.info(f"Colonne Repository URL configuree: {settings.monday_repository_url_column_id}")
        
        # Tester la recuperation des colonnes du board
        query = """
        query GetBoardColumns($boardId: [ID!]) {
            boards(ids: $boardId) {
                id
                columns {
                    id
                    title
                    type
                }
            }
        }
        """
        
        variables = {"boardId": [settings.monday_board_id]}
        result = await monday_tool._make_request(query, variables)
        
        if result.get("success") and result.get("data", {}).get("boards"):
            columns = result["data"]["boards"][0]["columns"]
            
            # Chercher notre colonne
            found = False
            for column in columns:
                if column["id"] == settings.monday_repository_url_column_id:
                    logger.info(f"Colonne trouvee: '{column['title']}' (Type: {column['type']})")
                    found = True
                    break
            
            if found:
                return True
            else:
                logger.error(f"Colonne avec ID {settings.monday_repository_url_column_id} non trouvee")
                return False
        else:
            error = result.get("error", "Erreur inconnue")
            logger.error(f"Erreur recuperation colonnes: {error}")
            return False
    
    except Exception as e:
        logger.error(f"Exception lors du test: {e}", exc_info=True)
        return False


async def test_repository_url_update_simulation():
    """Simule une mise a jour de la colonne Repository URL."""
    logger.info("Test 3: Simulation de mise a jour de la colonne Repository URL")
    
    try:
        settings = get_settings()
        
        if not settings.monday_repository_url_column_id:
            logger.warning("Test ignore: MONDAY_REPOSITORY_URL_COLUMN_ID non configure")
            return False
        
        # Pour ce test, nous simulons simplement la logique sans modifier reellement Monday
        # afin de ne pas polluer les donnees de production
        
        test_repo_url = "https://github.com/python/cpython"
        
        logger.info(f"Recuperation de la derniere PR pour: {test_repo_url}")
        last_pr_result = await github_pr_service.get_last_merged_pr(test_repo_url)
        
        if last_pr_result and last_pr_result.get("success"):
            pr_url = last_pr_result.get("pr_url")
            pr_number = last_pr_result.get("pr_number")
            
            logger.info("Simulation reussie:")
            logger.info(f"   URL a mettre a jour: {pr_url}")
            logger.info(f"   PR #{pr_number}")
            logger.info(f"   Colonne cible: {settings.monday_repository_url_column_id}")
            
            # Dans un vrai workflow, on ferait:
            # await monday_tool._arun(
            #     action="update_column_value",
            #     item_id=monday_item_id,
            #     column_id=settings.monday_repository_url_column_id,
            #     value=pr_url
            # )
            
            return True
        else:
            error = last_pr_result.get("error", "Erreur inconnue") if last_pr_result else "Resultat vide"
            logger.error(f"Echec simulation: {error}")
            return False
    
    except Exception as e:
        logger.error(f"Exception lors du test: {e}", exc_info=True)
        return False


async def test_full_integration():
    """Test d'integration complet."""
    logger.info("=" * 60)
    logger.info("TESTS DE L'INTEGRATION REPOSITORY URL")
    logger.info("=" * 60)
    logger.info("")
    
    results = []
    
    # Test 1: Service GitHub PR
    test1 = await test_github_pr_service()
    results.append(("Service GitHub PR", test1))
    logger.info("")
    
    # Test 2: Existence de la colonne Monday
    test2 = await test_monday_column_existence()
    results.append(("Colonne Monday.com", test2))
    logger.info("")
    
    # Test 3: Simulation de mise a jour
    test3 = await test_repository_url_update_simulation()
    results.append(("Simulation mise a jour", test3))
    logger.info("")
    
    # Resume
    logger.info("=" * 60)
    logger.info("RESUME DES TESTS")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "PASSE" if passed else "ECHOUE"
        logger.info(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    logger.info("")
    
    if all_passed:
        logger.info("Tous les tests sont passes avec succes!")
        logger.info("")
        logger.info("Prochaines etapes:")
        logger.info("   1. Configurez MONDAY_REPOSITORY_URL_COLUMN_ID dans .env si ce n'est pas deja fait")
        logger.info("   2. Lancez un workflow pour tester la mise a jour automatique")
        logger.info("   3. Verifiez que la colonne Repository URL est mise a jour apres le workflow")
        return True
    else:
        logger.info("Certains tests ont echoue")
        logger.info("")
        logger.info("Actions correctives:")
        logger.info("   1. Verifiez vos variables d'environnement dans .env")
        logger.info("   2. Executez: python scripts/ensure_repository_url_column.py")
        logger.info("   3. Verifiez vos tokens GitHub et Monday.com")
        return False


async def main():
    """Fonction principale."""
    try:
        success = await test_full_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
