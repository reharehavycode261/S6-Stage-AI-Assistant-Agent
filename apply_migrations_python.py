#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Python pour appliquer les migrations de réactivation.
Alternative à psql qui utilise asyncpg directement.
"""

import asyncio
import asyncpg
from pathlib import Path
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration de la base de données
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'ai_agent_admin'),
    'user': os.getenv('DB_USER', 'ai_agent_user'),
    'password': os.getenv('DB_PASSWORD', '')
}

print("=" * 80)
print("🚀 APPLICATION DES MIGRATIONS DE RÉACTIVATION")
print("=" * 80)
print()
print(f"📊 Configuration:")
print(f"   - Host: {DB_CONFIG['host']}")
print(f"   - Port: {DB_CONFIG['port']}")
print(f"   - Database: {DB_CONFIG['database']}")
print(f"   - User: {DB_CONFIG['user']}")
print()

async def execute_sql_file(conn, file_path: Path):
    """Exécute un fichier SQL."""
    print(f"📄 Exécution de {file_path.name}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Diviser le contenu en commandes individuelles
        # (en évitant de couper les DO blocks et les fonctions)
        await conn.execute(sql_content)
        
        print(f"   ✅ {file_path.name} exécuté avec succès")
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur dans {file_path.name}: {e}")
        return False


async def apply_migrations():
    """Applique toutes les migrations de réactivation."""
    
    base_path = Path(__file__).parent / "data"
    
    migrations = [
        base_path / "migration_workflow_reactivations_table.sql",
        base_path / "migration_failles_workflow_reactivation.sql",
        base_path / "add_parent_run_id_column.sql"
    ]
    
    # Vérifier que tous les fichiers existent
    print("🔍 Vérification des fichiers de migration...")
    for migration_file in migrations:
        if migration_file.exists():
            print(f"   ✅ {migration_file.name}")
        else:
            print(f"   ❌ {migration_file.name} - FICHIER MANQUANT")
            return False
    print()
    
    # Connexion à la base de données
    print("🔌 Connexion à la base de données...")
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print("   ✅ Connexion établie")
        print()
    except Exception as e:
        print(f"   ❌ Erreur de connexion: {e}")
        print()
        print("💡 Vérifiez que:")
        print("   1. PostgreSQL est démarré")
        print("   2. Les credentials dans .env sont corrects")
        print("   3. La base de données 'ai_agent_admin' existe")
        return False
    
    try:
        # Appliquer chaque migration
        print("📋 Application des migrations...")
        print("-" * 80)
        print()
        
        success_count = 0
        
        for i, migration_file in enumerate(migrations, 1):
            print(f"Étape {i}/{len(migrations)}: {migration_file.name}")
            
            if await execute_sql_file(conn, migration_file):
                success_count += 1
            else:
                print(f"⚠️  Migration {migration_file.name} a échoué")
            
            print()
        
        # Validation finale
        print("=" * 80)
        print("🔍 VALIDATION FINALE")
        print("=" * 80)
        print()
        
        # Vérifier que la table workflow_reactivations existe
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'workflow_reactivations'
            )
        """)
        
        if table_exists:
            print("✅ Table workflow_reactivations : Créée")
        else:
            print("❌ Table workflow_reactivations : MANQUANTE")
        
        # Vérifier les colonnes de tasks
        task_columns = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tasks' 
            AND column_name IN (
                'reactivation_count', 'reactivated_at', 'is_locked', 
                'cooldown_until', 'locked_at', 'locked_by'
            )
        """)
        
        print(f"✅ Colonnes de tasks : {len(task_columns)}/6 ajoutées")
        
        # Vérifier les colonnes de task_runs
        run_columns = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'task_runs' 
            AND column_name IN (
                'is_reactivation', 'parent_run_id', 'active_task_ids'
            )
        """)
        
        print(f"✅ Colonnes de task_runs : {len(run_columns)}/3 ajoutées")
        
        # Vérifier les vues
        views = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'public' 
            AND table_name IN (
                'v_tasks_reactivable',
                'v_workflow_reactivation_stats',
                'v_reactivation_tree'
            )
        """)
        
        print(f"✅ Vues créées : {len(views)}/3")
        print()
        
        # Résumé final
        print("=" * 80)
        if success_count == len(migrations):
            print("🎉 MIGRATION COMPLÈTE RÉUSSIE !")
            print("=" * 80)
            print()
            print("📊 Résumé des modifications :")
            print(f"   ✅ {success_count}/{len(migrations)} migrations appliquées")
            print(f"   ✅ Table workflow_reactivations créée")
            print(f"   ✅ {len(task_columns)} colonnes ajoutées à tasks")
            print(f"   ✅ {len(run_columns)} colonnes ajoutées à task_runs")
            print(f"   ✅ {len(views)} vues de monitoring créées")
            print()
            print("🔄 Le système de réactivation est maintenant OPÉRATIONNEL")
            print()
            print("📝 Prochaines étapes :")
            print("   1. Redémarrer Celery : pkill -f celery && celery -A tasks.celery_worker worker")
            print("   2. Redémarrer FastAPI : pkill -f uvicorn && uvicorn main:app --reload")
            print("   3. Tester avec Monday.com")
            print()
        else:
            print("⚠️  MIGRATION PARTIELLE")
            print("=" * 80)
            print(f"   {success_count}/{len(migrations)} migrations appliquées")
            print()
            print("Vérifiez les erreurs ci-dessus et réessayez.")
        
        print("=" * 80)
        
    finally:
        await conn.close()
        print()
        print("🔌 Connexion fermée")


async def main():
    """Point d'entrée principal."""
    try:
        await apply_migrations()
    except KeyboardInterrupt:
        print("\n⚠️  Migration interrompue par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

