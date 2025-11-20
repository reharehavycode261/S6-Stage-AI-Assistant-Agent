#!/usr/bin/env python3
"""Vérifie la structure de webhook_events."""

import asyncio


async def check_structure():
    from services.database_persistence_service import db_persistence
    
    await db_persistence.initialize()
    
    async with db_persistence.db_manager.get_connection() as conn:
        print("📋 Structure de webhook_events:")
        print("="*70)
        
        # Colonnes
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'webhook_events'
            ORDER BY ordinal_position
        """)
        
        print("\n📊 Colonnes:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
        
        # Contraintes
        constraints = await conn.fetch("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints 
            WHERE table_name = 'webhook_events'
        """)
        
        print("\n🔐 Contraintes:")
        for c in constraints:
            print(f"  - {c['constraint_name']}: {c['constraint_type']}")
        
        # Clés primaires
        pk = await conn.fetch("""
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE table_name = 'webhook_events'
            AND constraint_name LIKE '%_pkey'
        """)
        
        print("\n🔑 Clé primaire:")
        for p in pk:
            print(f"  - {p['column_name']}")


if __name__ == "__main__":
    asyncio.run(check_structure())

