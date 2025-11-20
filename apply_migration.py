#!/usr/bin/env python3
"""Applique la migration SQL pour task_update_triggers."""

import asyncio
import sys


async def apply_migration():
    """Applique la migration SQL directement via asyncpg."""
    from services.database_persistence_service import db_persistence
    
    print("📋 Lecture du fichier de migration...")
    
    try:
        with open('data/migration_task_update_triggers.sql', 'r') as f:
            migration_sql = f.read()
        
        print(f"✅ Migration chargée: {len(migration_sql)} caractères")
        print()
        
        print("🔌 Connexion à la base de données...")
        await db_persistence.initialize()
        print("✅ Connexion établie")
        print()
        
        print("⚙️  Application de la migration...")
        async with db_persistence.db_manager.get_connection() as conn:
            # Exécuter la migration en une transaction
            async with conn.transaction():
                await conn.execute(migration_sql)
        
        print("✅ Migration appliquée avec succès!")
        print()
        
        # Vérifier
        print("🔍 Vérification...")
        async with db_persistence.db_manager.get_connection() as conn:
            # Vérifier table
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'task_update_triggers'
                )
            """)
            
            if table_exists:
                print("✅ Table task_update_triggers créée")
                
                # Vérifier structure
                columns = await conn.fetch("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'task_update_triggers'
                    ORDER BY ordinal_position
                """)
                
                print(f"\n📊 Structure de la table ({len(columns)} colonnes):")
                for col in columns:
                    print(f"  - {col['column_name']}: {col['data_type']}")
            else:
                print("❌ Erreur: table non créée")
                return False
            
            # Vérifier colonne dans task_runs
            col_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'task_runs' 
                    AND column_name = 'triggered_by_update_id'
                )
            """)
            
            if col_exists:
                print("\n✅ Colonne triggered_by_update_id ajoutée à task_runs")
            else:
                print("\n❌ Erreur: colonne non ajoutée")
                return False
        
        print("\n" + "="*70)
        print("🎉 MIGRATION RÉUSSIE!")
        print("="*70)
        print()
        print("Vous pouvez maintenant:")
        print("  1. Redémarrer FastAPI (si nécessaire)")
        print("  2. Tester avec: python3 test_update_manual.py")
        print("  3. Ou poster un commentaire dans Monday.com")
        print()
        
        return True
        
    except FileNotFoundError:
        print("❌ Fichier de migration non trouvé: data/migration_task_update_triggers.sql")
        return False
    except Exception as e:
        print(f"❌ Erreur lors de l'application: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(apply_migration())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Migration interrompue")
        sys.exit(1)

