#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test de sauvegarde des deux URLs de PR en base de donnees."""

import asyncio
import sys
import os

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database_persistence_service import db_persistence
from services.github_pr_service import github_pr_service
from utils.logger import get_logger

logger = get_logger(__name__)


async def test_save_both_pr_urls():
    """Test complet de sauvegarde des deux URLs de PR."""
    
    logger.info("=" * 60)
    logger.info("TEST DE SAUVEGARDE DES DEUX URLs DE PR")
    logger.info("=" * 60)
    logger.info("")
    
    try:
        # Initialiser la base de donnees
        await db_persistence.initialize()
        logger.info("DB initialisee")
        logger.info("")
        
        # Simuler un workflow avec creation de task et task_run
        logger.info("1. Creation d'une tache de test...")
        
        # Creer une tache de test
        monday_payload = {
            "pulseId": 999999999,  # Utiliser un entier
            "pulseName": "Test - Sauvegarde deux URLs PR",
            "boardId": 2135637353,  # Utiliser un entier aussi
            "columnValues": {
                "repository_url": {
                    "text": "https://github.com/python/cpython"
                }
            }
        }
        
        task_id = await db_persistence.create_task_from_monday(monday_payload)
        logger.info(f"   Tache creee: task_id={task_id}")
        logger.info("")
        
        # Creer un task_run
        logger.info("2. Creation d'un task_run de test...")
        task_run_id = await db_persistence.start_task_run(
            task_id,
            "test_workflow_123",
            "test_run_456"
        )
        logger.info(f"   Task run cree: task_run_id={task_run_id}")
        logger.info("")
        
        # Simuler la creation d'une PR par le workflow
        logger.info("3. Sauvegarde de la PR creee par le workflow...")
        created_pr_url = "https://github.com/python/cpython/pull/12345"
        
        pr_id = await db_persistence.create_pull_request(
            task_id=task_id,
            task_run_id=task_run_id,
            github_pr_number=12345,
            github_pr_url=created_pr_url,
            pr_title="Test PR creee par workflow",
            pr_description="Test description",
            head_sha="abc123",
            base_branch="main",
            feature_branch="feature/test"
        )
        logger.info(f"   PR creee sauvegardee: {created_pr_url}")
        logger.info(f"   PR ID en base: {pr_id}")
        logger.info("")
        
        # Recuperer la derniere PR fusionnee depuis GitHub
        logger.info("4. Recuperation de la derniere PR fusionnee depuis GitHub...")
        repo_url = "https://github.com/python/cpython"
        last_pr_result = await github_pr_service.get_last_merged_pr(repo_url)
        
        if last_pr_result and last_pr_result.get("success"):
            last_merged_pr_url = last_pr_result.get("pr_url")
            pr_number = last_pr_result.get("pr_number")
            logger.info(f"   Derniere PR fusionnee: #{pr_number}")
            logger.info(f"   URL: {last_merged_pr_url}")
            logger.info("")
            
            # Sauvegarder l'URL de la derniere PR fusionnee
            logger.info("5. Sauvegarde de la derniere PR fusionnee en base...")
            success = await db_persistence.update_last_merged_pr_url(
                task_run_id,
                last_merged_pr_url
            )
            
            if success:
                logger.info("   Sauvegarde reussie")
                logger.info("")
                
                # Verifier que les deux URLs sont bien en base
                logger.info("6. Verification des donnees en base...")
                
                async with db_persistence.db_manager.get_connection() as conn:
                    result = await conn.fetchrow("""
                        SELECT 
                            pull_request_url,
                            last_merged_pr_url
                        FROM task_runs
                        WHERE tasks_runs_id = $1
                    """, task_run_id)
                    
                    logger.info("")
                    logger.info("=== RESULTATS ===")
                    logger.info("")
                    logger.info(f"  PR creee par workflow:")
                    logger.info(f"    {result['pull_request_url']}")
                    logger.info("")
                    logger.info(f"  Derniere PR fusionnee GitHub:")
                    logger.info(f"    {result['last_merged_pr_url']}")
                    logger.info("")
                    
                    if result['pull_request_url'] and result['last_merged_pr_url']:
                        logger.info("SUCCES - Les deux URLs sont stockees en base")
                        logger.info("")
                        logger.info("Details:")
                        logger.info(f"  1. pull_request_url = {result['pull_request_url']}")
                        logger.info(f"  2. last_merged_pr_url = {result['last_merged_pr_url']}")
                        
                        # Nettoyer les donnees de test
                        logger.info("")
                        logger.info("7. Nettoyage des donnees de test...")
                        await conn.execute("DELETE FROM tasks WHERE tasks_id = $1", task_id)
                        logger.info("   Donnees de test supprimees")
                        
                        return True
                    else:
                        logger.error("ECHEC - Une ou plusieurs URLs manquantes")
                        return False
            else:
                logger.error("ECHEC - Sauvegarde de last_merged_pr_url echouee")
                return False
        else:
            logger.error("ECHEC - Impossible de recuperer la derniere PR fusionnee")
            return False
    
    except Exception as e:
        logger.error(f"ERREUR: {e}", exc_info=True)
        return False
    
    finally:
        await db_persistence.close()


async def main():
    """Fonction principale."""
    try:
        success = await test_save_both_pr_urls()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

