#!/usr/bin/env python3
"""Script de vérification complète du workflow."""

import asyncio
import sys
import os
import asyncpg

# Ajouter le chemin du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


async def verify_workflow():
    """Vérifie tous les composants critiques du workflow."""
    
    print('=' * 60)
    print('VERIFICATION COMPLETE DU WORKFLOW')
    print('=' * 60)
    print()
    
    errors = []
    warnings = []
    
    # 1. Vérifier les énumérations
    print('1. Vérification des énumérations...')
    try:
        from models.schemas import WorkflowStatus
        print(f'   Statuts workflow disponibles: {[s.value for s in WorkflowStatus]}')
        print()
    except Exception as e:
        errors.append(f'WorkflowStatus: {e}')
        print(f'   Erreur: {e}')
        print()
    
    # 2. Vérifier la base de données
    print('2. Vérification de la base de données...')
    try:
        settings = get_settings()
        conn = await asyncpg.connect(settings.database_url)
        
        # Vérifier les colonnes task_runs
        result = await conn.fetch('''
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'task_runs'
            AND column_name IN ('pull_request_url', 'last_merged_pr_url')
            ORDER BY column_name
        ''')
        
        print('   Colonnes task_runs:')
        found_cols = []
        for row in result:
            print(f'      {row["column_name"]}')
            found_cols.append(row["column_name"])
        
        if 'pull_request_url' not in found_cols:
            errors.append('Colonne pull_request_url manquante')
        
        if 'last_merged_pr_url' not in found_cols:
            errors.append('Colonne last_merged_pr_url manquante')
        
        await conn.close()
        print()
    except Exception as e:
        errors.append(f'Base de données: {e}')
        print(f'   Erreur: {e}')
        print()
    
    # 3. Vérifier les nodes
    print('3. Vérification des nodes...')
    try:
        from nodes.update_node import update_monday, _update_repository_url_column, _save_last_merged_pr_to_database
        print('   update_monday')
        print('   _update_repository_url_column')
        print('   _save_last_merged_pr_to_database')
        print()
    except Exception as e:
        errors.append(f'Nodes: {e}')
        print(f'   Erreur: {e}')
        print()
    
    # 4. Vérifier les services
    print('4. Vérification des services...')
    try:
        from services.github_pr_service import github_pr_service
        print('   github_pr_service')
        
        from services.database_persistence_service import db_persistence
        print('   db_persistence')
        
        if hasattr(db_persistence, 'update_last_merged_pr_url'):
            print('   db_persistence.update_last_merged_pr_url')
        else:
            errors.append('Méthode update_last_merged_pr_url manquante')
            print('   ERREUR: update_last_merged_pr_url manquante')
        
        print()
    except Exception as e:
        errors.append(f'Services: {e}')
        print(f'   Erreur: {e}')
        print()
    
    # 5. Vérifier la configuration
    print('5. Vérification de la configuration...')
    try:
        settings = get_settings()
        
        if settings.monday_repository_url_column_id:
            print(f'   MONDAY_REPOSITORY_URL_COLUMN_ID: {settings.monday_repository_url_column_id}')
        else:
            warnings.append('MONDAY_REPOSITORY_URL_COLUMN_ID non configuré')
            print('   AVERTISSEMENT: MONDAY_REPOSITORY_URL_COLUMN_ID non configuré')
        
        print()
    except Exception as e:
        errors.append(f'Configuration: {e}')
        print(f'   Erreur: {e}')
        print()
    
    # 6. Vérifier le graphe
    print('6. Vérification du graphe workflow...')
    try:
        from graph.workflow_graph import create_workflow_graph
        workflow = create_workflow_graph()
        print('   Graphe créé avec succès')
        
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        compiled_graph = workflow.compile(checkpointer=checkpointer)
        print('   Graphe compilé avec succès')
        print()
    except Exception as e:
        errors.append(f'Graphe workflow: {e}')
        print(f'   Erreur: {e}')
        print()
    
    # Résumé
    print('=' * 60)
    print('RESUME DE LA VERIFICATION')
    print('=' * 60)
    print()
    
    if errors:
        print(f'ERREURS CRITIQUES ({len(errors)}):')
        for error in errors:
            print(f'   {error}')
        print()
    
    if warnings:
        print(f'AVERTISSEMENTS ({len(warnings)}):')
        for warning in warnings:
            print(f'   {warning}')
        print()
    
    if not errors and not warnings:
        print('TOUS LES TESTS ONT REUSSI')
        print()
        print('Le workflow est pret a fonctionner:')
        print('   1. Base de donnees configuree')
        print('   2. Colonnes PR URLs presentes')
        print('   3. Services disponibles')
        print('   4. Nodes fonctionnels')
        print('   5. Graphe compilable')
        print()
        return True
    elif not errors:
        print('VERIFICATION REUSSIE AVEC AVERTISSEMENTS')
        print('Le workflow peut fonctionner mais certains parametres ne sont pas optimaux')
        print()
        return True
    else:
        print('VERIFICATION ECHOUEE')
        print('Corrigez les erreurs critiques avant de lancer le workflow')
        print()
        return False


async def main():
    """Fonction principale."""
    try:
        success = await verify_workflow()
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f'Erreur fatale: {e}', exc_info=True)
        exit(1)


if __name__ == '__main__':
    asyncio.run(main())

