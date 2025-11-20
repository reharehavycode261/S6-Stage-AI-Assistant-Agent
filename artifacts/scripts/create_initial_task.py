#!/usr/bin/env python3
"""Crée une tâche initiale pour tester la réactivation."""
import asyncio
import asyncpg
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

async def main():
    c = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Créer une tâche initiale
    task_id = await c.fetchval("""
        INSERT INTO tasks (
            title, description, priority, repository_url,
            internal_status, monday_item_id, monday_board_id, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING tasks_id
    """, 
        "Test Workflow - Fonctionnalité API",
        "Développer une API REST avec authentification",
        "medium",
        "https://github.com/test/api-project",  # Repository requis
        "completed",  # ✅ Status completed pour permettre réactivation
        5054186334,  # ✅ Bigint pas string
        8218506916,  # Board ID
        datetime.now(timezone.utc)
    )
    
    print(f"✅ Tâche créée: ID={task_id}, Monday Item=5054186334")
    
    # Créer un workflow run initial (utiliser la bonne colonne status)
    run_id = await c.fetchval("""
        INSERT INTO task_runs (
            task_id, status, created_at
        ) VALUES ($1, $2, $3)
        RETURNING tasks_runs_id
    """, task_id, "completed", datetime.now(timezone.utc))
    
    print(f"✅ Workflow run créé: run_id={run_id}")
    
    await c.close()
    
    return task_id, run_id

if __name__ == "__main__":
    task_id, run_id = asyncio.run(main())
    print(f"\n🎯 Tâche prête pour réactivation:")
    print(f"   - Task ID: {task_id}")
    print(f"   - Monday Item: 5054186334")
    print(f"   - Status: completed")
    print(f"\n✅ Vous pouvez maintenant poster un update sur Monday item 5054186334")

