#!/usr/bin/env python3
"""
Script de diagnostic pour identifier pourquoi la réactivation échoue silencieusement
"""

import asyncio
import asyncpg
from datetime import datetime

async def diagnose():
    """Diagnostique l'état du système pour la réactivation."""
    
    print("="*80)
    print("🔍 DIAGNOSTIC DE RÉACTIVATION")
    print("="*80)
    print()
    
    # Connexion à la base de données
    try:
        # Utiliser la même config que l'application
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        database_url = os.getenv("DATABASE_URL", "postgresql://admin:admin@localhost:5432/ai_agent_admin")
        conn = await asyncpg.connect(database_url)
        print("✅ Connecté à la base de données\n")
        
        # 1. Lister les tâches
        print("📋 TÂCHES EXISTANTES:")
        print("-" * 80)
        tasks = await conn.fetch("""
            SELECT 
                tasks_id,
                monday_item_id,
                title,
                internal_status,
                monday_status,
                reactivation_count,
                repository_url,
                created_at,
                updated_at
            FROM tasks
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        if not tasks:
            print("❌ ERREUR #1: Aucune tâche trouvée en base !")
            print("   CAUSE: Vous devez d'abord créer une tâche sur Monday.com")
            print("   SOLUTION: Créez un item sur Monday.com qui sera synchronisé\n")
        else:
            for task in tasks:
                print(f"\n🆔 Task ID: {task['tasks_id']}")
                print(f"   Monday Item ID: {task['monday_item_id']}")
                print(f"   Titre: {task['title']}")
                print(f"   Statut interne: {task['internal_status']}")
                print(f"   Statut Monday: {task['monday_status']}")
                print(f"   Réactivations: {task['reactivation_count']}")
                print(f"   Repository: {task['repository_url']}")
                
                # ✅ VÉRIFICATION CRITIQUE: La tâche est-elle réactivable ?
                can_reactivate = task['internal_status'] in ['completed', 'failed', 'quality_check']
                if can_reactivate:
                    print(f"   ✅ PEUT ÊTRE RÉACTIVÉE")
                else:
                    print(f"   ❌ ERREUR #2: NE PEUT PAS ÊTRE RÉACTIVÉE")
                    print(f"      CAUSE: Statut '{task['internal_status']}' n'est pas terminal")
                    print(f"      SOLUTION: La tâche doit être 'completed', 'failed' ou 'quality_check'")
        
        # 2. Vérifier les task_runs
        print("\n" + "-" * 80)
        print("🔄 TASK RUNS:")
        print("-" * 80)
        runs = await conn.fetch("""
            SELECT 
                tasks_runs_id,
                task_id,
                status,
                is_reactivation,
                parent_run_id,
                started_at,
                completed_at
            FROM task_runs
            ORDER BY started_at DESC
            LIMIT 10
        """)
        
        if not runs:
            print("⚠️  Aucun workflow run trouvé")
        else:
            for run in runs:
                reactivation_marker = "🔄" if run['is_reactivation'] else "🆕"
                print(f"\n{reactivation_marker} Run ID: {run['tasks_runs_id']}")
                print(f"   Task ID: {run['task_id']}")
                print(f"   Statut: {run['status']}")
                print(f"   Est réactivation: {run['is_reactivation']}")
                print(f"   Parent Run: {run['parent_run_id']}")
                
        # 3. Vérifier les webhooks reçus
        print("\n" + "-" * 80)
        print("📨 WEBHOOKS REÇUS (derniers 5):")
        print("-" * 80)
        webhooks = await conn.fetch("""
            SELECT 
                webhook_events_id,
                source,
                event_type,
                processed,
                processed_at,
                (payload->'event'->>'pulseId') as pulse_id,
                (payload->'event'->>'type') as event_subtype,
                received_at
            FROM webhook_events
            ORDER BY received_at DESC
            LIMIT 5
        """)
        
        if not webhooks:
            print("❌ ERREUR #3: Aucun webhook reçu !")
            print("   CAUSE: Monday.com n'envoie pas de webhooks OU l'URL webhook est incorrecte")
            print("   SOLUTION:")
            print("      1. Vérifiez l'URL webhook dans Monday.com")
            print("      2. Vérifiez que ngrok/tunnel est actif")
            print("      3. Testez avec: ./test_reactivation_webhook.py\n")
        else:
            for webhook in webhooks:
                processed_marker = "✅" if webhook['processed'] else "⏳"
                print(f"\n{processed_marker} Webhook ID: {webhook['webhook_events_id']}")
                print(f"   Type: {webhook['event_type']} / {webhook['event_subtype']}")
                print(f"   Pulse ID: {webhook['pulse_id']}")
                print(f"   Traité: {webhook['processed']}")
                print(f"   Reçu: {webhook['received_at']}")
        
        # 4. Vérifier les réactivations
        print("\n" + "-" * 80)
        print("🔄 TENTATIVES DE RÉACTIVATION:")
        print("-" * 80)
        reactivations = await conn.fetch("""
            SELECT 
                id,
                workflow_id,
                trigger_type,
                status,
                reactivated_at,
                update_data
            FROM workflow_reactivations
            ORDER BY reactivated_at DESC
            LIMIT 5
        """)
        
        if not reactivations:
            print("⚠️  Aucune tentative de réactivation enregistrée")
            print("   CAUSE POSSIBLE:")
            print("      - L'analyse LLM rejette les updates")
            print("      - La confidence est < 0.2")
            print("      - Les updates sont détectés comme venant de l'agent\n")
        else:
            for reac in reactivations:
                print(f"\n🔄 Réactivation ID: {reac['id']}")
                print(f"   Workflow ID: {reac['workflow_id']}")
                print(f"   Type: {reac['trigger_type']}")
                print(f"   Statut: {reac['status']}")
                print(f"   Date: {reac['reactivated_at']}")
        
        await conn.close()
        
        print("\n" + "=" * 80)
        print("✅ DIAGNOSTIC TERMINÉ")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ ERREUR DE CONNEXION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(diagnose())

