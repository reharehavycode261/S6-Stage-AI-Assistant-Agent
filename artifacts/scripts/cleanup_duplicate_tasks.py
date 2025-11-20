#!/usr/bin/env python3
"""
Script de nettoyage des tâches dupliquées.

Ce script :
1. Identifie les tâches dupliquées par monday_item_id
2. Garde la tâche la plus récente
3. Supprime les doublons
4. Met à jour les références
"""

import asyncio
import sys
import os
from typing import List, Dict, Any

# Ajouter le répertoire racine au path
sys.path.insert(0, os.path.dirname(__file__))

async def cleanup_duplicate_tasks():
    """Nettoie les tâches dupliquées dans la base de données."""
    
    try:
        from services.database_persistence_service import DatabasePersistenceService
        
        db_service = DatabasePersistenceService()
        await db_service.initialize()
        
        print("🧹 Nettoyage des tâches dupliquées...")
        print("=" * 50)
        
        # 1. Trouver les tâches dupliquées
        async with db_service.pool.acquire() as conn:
            duplicate_query = """
            SELECT monday_item_id, COUNT(*) as count_duplicates
            FROM tasks 
            WHERE monday_item_id IS NOT NULL
            GROUP BY monday_item_id 
            HAVING COUNT(*) > 1
            ORDER BY count_duplicates DESC
            """
            
            duplicate_groups = await conn.fetch(duplicate_query)
            
            if not duplicate_groups:
                print("✅ Aucune tâche dupliquée trouvée")
                return True
            
            print(f"🔍 {len(duplicate_groups)} groupes de tâches dupliquées trouvées:")
            
            total_duplicates_removed = 0
            
            for group in duplicate_groups:
                monday_item_id = group['monday_item_id']
                count = group['count_duplicates']
                
                print(f"\n📋 Monday Item {monday_item_id}: {count} duplicatas")
                
                # 2. Récupérer toutes les tâches de ce groupe
                tasks_query = """
                SELECT tasks_id, monday_item_id, title, created_at, started_at, completed_at
                FROM tasks 
                WHERE monday_item_id = $1 
                ORDER BY created_at DESC
                """
                
                tasks = await conn.fetch(tasks_query, monday_item_id)
                
                if len(tasks) <= 1:
                    continue
                
                # 3. Garder la tâche la plus récente (première dans la liste triée)
                keep_task = tasks[0]
                remove_tasks = tasks[1:]
                
                print(f"   ✅ Garder: Task {keep_task['tasks_id']} (créée le {keep_task['created_at']})")
                
                for remove_task in remove_tasks:
                    print(f"   🗑️ Supprimer: Task {remove_task['tasks_id']} (créée le {remove_task['created_at']})")
                    
                    # 4. Supprimer les task_runs associées
                    await conn.execute("""
                        DELETE FROM task_runs WHERE task_id = $1
                    """, remove_task['tasks_id'])
                    
                    # 5. Supprimer la tâche dupliquée
                    await conn.execute("""
                        DELETE FROM tasks WHERE tasks_id = $1
                    """, remove_task['tasks_id'])
                    
                    total_duplicates_removed += 1
                    print(f"      ✅ Task {remove_task['tasks_id']} supprimée")
            
            print(f"\n🎯 Nettoyage terminé: {total_duplicates_removed} tâches dupliquées supprimées")
            return True
            
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage: {e}")
        return False

async def show_current_tasks():
    """Affiche l'état actuel des tâches."""
    
    try:
        from services.database_persistence_service import DatabasePersistenceService
        
        db_service = DatabasePersistenceService()
        await db_service.initialize()
        
        async with db_service.pool.acquire() as conn:
            # Statistiques générales
            total_tasks = await conn.fetchval("SELECT COUNT(*) FROM tasks")
            
            # Tâches par monday_item_id
            tasks_query = """
            SELECT monday_item_id, title, internal_status, created_at, COUNT(*) OVER (PARTITION BY monday_item_id) as duplicates
            FROM tasks 
            ORDER BY monday_item_id, created_at DESC
            """
            
            tasks = await conn.fetch(tasks_query)
            
            print("\n📊 État actuel des tâches:")
            print("=" * 60)
            print(f"📈 Total des tâches: {total_tasks}")
            
            if tasks:
                print("\n📋 Détail des tâches:")
                current_item_id = None
                
                for task in tasks:
                    item_id = task['monday_item_id']
                    if item_id != current_item_id:
                        if task['duplicates'] > 1:
                            print(f"\n⚠️ Monday Item {item_id} ({task['duplicates']} duplicatas):")
                        else:
                            print(f"\n✅ Monday Item {item_id}:")
                        current_item_id = item_id
                    
                    status_icon = "🔄" if task['internal_status'] == "processing" else "✅"
                    print(f"   {status_icon} {task['title'][:50]}... ({task['internal_status']}) - {task['created_at']}")
            
            return True
            
    except Exception as e:
        print(f"❌ Erreur lors de l'affichage: {e}")
        return False

async def main():
    """Fonction principale."""
    print("🧹 Utilitaire de nettoyage des tâches dupliquées")
    print("=" * 60)
    
    # Afficher l'état actuel
    await show_current_tasks()
    
    # Demander confirmation (simulée ici)
    print(f"\n⚠️ ATTENTION: Ce script va supprimer les tâches dupliquées.")
    print("💡 Les tâches les plus récentes seront conservées.")
    
    # Effectuer le nettoyage
    success = await cleanup_duplicate_tasks()
    
    if success:
        print("\n" + "=" * 60)
        # Afficher l'état après nettoyage
        await show_current_tasks()
        print("\n🎉 Nettoyage terminé avec succès!")
    else:
        print("\n❌ Nettoyage échoué")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 