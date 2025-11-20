#!/usr/bin/env python3
"""
Script de vérification complète de la base de données.
Vérifie toutes les tables, leur structure et identifie les problèmes.
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from typing import List, Dict, Set

# Configuration de la base de données
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'user': os.getenv('DB_USER', 'admin'),
    'password': os.getenv('DB_PASSWORD', 'password'),  # Mot de passe du docker-compose
    'database': os.getenv('DB_NAME', 'ai_agent_admin'),  # Nom réel de la base
}


# Tables attendues dans la base
EXPECTED_TABLES = {
    # Tables principales de workflow
    'tasks': 'Tâches/workflows Monday.com',
    'task_runs': 'Exécutions des tâches',
    'run_steps': 'Étapes détaillées des exécutions',
    
    # Tables de résultats
    'test_results': 'Résultats des tests',
    'pull_requests': 'Pull requests GitHub',
    
    # Tables IA et coût (À PRÉSERVER)
    'ai_interactions': 'Interactions avec les modèles IA',
    'ai_code_generations': 'Code généré par IA',
    'ai_usage_logs': 'Logs d\'usage et coûts IA',
    'ai_cost_tracking': 'Tracking détaillé des coûts IA',
    'ai_prompt_templates': 'Templates de prompts',
    'ai_prompt_usage': 'Usage des prompts',
    
    # Tables de réactivation (NOUVELLES)
    'workflow_reactivations': 'Historique des réactivations de workflow',
    
    # Tables système
    'webhook_events': 'Événements webhook (partitionnée)',
    'application_logs': 'Logs de l\'application',
    'performance_metrics': 'Métriques de performance',
    'system_config': 'Configuration système',
}

# Tables de coût IA à absolument préserver
AI_COST_TABLES = {
    'ai_usage_logs',
    'ai_cost_tracking',
    'ai_interactions',
    'ai_code_generations',
    'ai_prompt_templates',
    'ai_prompt_usage',
}


async def check_database_connection() -> asyncpg.Connection:
    """Vérifier la connexion à la base de données."""
    print("="*80)
    print("🔌 VÉRIFICATION DE LA CONNEXION À LA BASE DE DONNÉES")
    print("="*80)
    print()
    
    try:
        conn = await asyncpg.connect(**DB_CONFIG)
        print(f"✅ Connexion réussie à la base de données '{DB_CONFIG['database']}'")
        print(f"   • Host: {DB_CONFIG['host']}")
        print(f"   • Port: {DB_CONFIG['port']}")
        print(f"   • User: {DB_CONFIG['user']}")
        
        # Vérifier la version PostgreSQL
        version = await conn.fetchval('SELECT version()')
        print(f"   • Version: {version.split(',')[0]}")
        
        return conn
        
    except Exception as e:
        print(f"❌ Erreur de connexion à la base de données:")
        print(f"   {e}")
        print()
        print("💡 Vérifications à faire:")
        print("   1. Le conteneur PostgreSQL est-il démarré ?")
        print("      → docker ps | grep postgres")
        print("   2. Les credentials sont-ils corrects ?")
        print("      → Vérifier les variables d'environnement")
        print("   3. Le port 5432 est-il accessible ?")
        print("      → netstat -an | grep 5432")
        return None


async def get_existing_tables(conn: asyncpg.Connection) -> List[Dict]:
    """Récupérer toutes les tables existantes."""
    query = """
        SELECT 
            tablename as table_name,
            schemaname as schema_name
        FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename
    """
    
    tables = await conn.fetch(query)
    return [dict(row) for row in tables]


async def get_table_info(conn: asyncpg.Connection, table_name: str) -> Dict:
    """Récupérer les informations détaillées d'une table."""
    # Compter les lignes
    try:
        count = await conn.fetchval(f'SELECT COUNT(*) FROM {table_name}')
    except Exception as e:
        count = f"Erreur: {e}"
    
    # Récupérer les colonnes
    query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' 
        AND table_name = $1
        ORDER BY ordinal_position
    """
    
    columns = await conn.fetch(query, table_name)
    
    return {
        'name': table_name,
        'row_count': count,
        'columns': [dict(col) for col in columns],
        'column_count': len(columns)
    }


async def check_partitioned_tables(conn: asyncpg.Connection) -> List[str]:
    """Vérifier les tables partitionnées."""
    query = """
        SELECT 
            parent.relname as parent_table,
            child.relname as partition_name
        FROM pg_inherits
        JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
        JOIN pg_class child ON pg_inherits.inhrelid = child.oid
        JOIN pg_namespace nmsp_parent ON nmsp_parent.oid = parent.relnamespace
        WHERE nmsp_parent.nspname = 'public'
        ORDER BY parent.relname, child.relname
    """
    
    partitions = await conn.fetch(query)
    return [dict(row) for row in partitions]


async def get_ai_cost_summary(conn: asyncpg.Connection) -> Dict:
    """Récupérer un résumé des coûts IA."""
    summary = {}
    
    # Vérifier ai_usage_logs
    if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'ai_usage_logs')"):
        try:
            result = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_calls,
                    COALESCE(SUM(estimated_cost), 0) as total_cost,
                    COALESCE(SUM(total_tokens), 0) as total_tokens
                FROM ai_usage_logs
            """)
            summary['ai_usage_logs'] = dict(result)
        except Exception as e:
            summary['ai_usage_logs'] = {'error': str(e)}
    
    # Vérifier ai_cost_tracking
    if await conn.fetchval("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'ai_cost_tracking')"):
        try:
            result = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_calls,
                    COALESCE(SUM(cost_usd), 0) as total_cost,
                    COALESCE(SUM(total_tokens), 0) as total_tokens
                FROM ai_cost_tracking
            """)
            summary['ai_cost_tracking'] = dict(result)
        except Exception as e:
            summary['ai_cost_tracking'] = {'error': str(e)}
    
    return summary


async def main():
    """Fonction principale de vérification."""
    print("\n" + "="*80)
    print("🔍 VÉRIFICATION COMPLÈTE DE LA BASE DE DONNÉES")
    print("="*80)
    print()
    
    # Étape 1: Connexion
    conn = await check_database_connection()
    if not conn:
        return 1
    
    print()
    
    try:
        # Étape 2: Lister les tables existantes
        print("="*80)
        print("📋 TABLES EXISTANTES DANS LA BASE DE DONNÉES")
        print("="*80)
        print()
        
        existing_tables = await get_existing_tables(conn)
        existing_table_names = {table['table_name'] for table in existing_tables}
        
        if not existing_tables:
            print("⚠️  Aucune table trouvée dans la base de données !")
            print()
            print("💡 La base semble vide. Vous devez créer les tables avec:")
            print("   docker exec -i ai-agent-postgres psql -U admin -d ai_agent < data/base2.sql")
            return 1
        
        print(f"✅ {len(existing_tables)} table(s) trouvée(s):")
        print()
        
        for table in existing_tables:
            info = await get_table_info(conn, table['table_name'])
            is_ai_cost = table['table_name'] in AI_COST_TABLES
            marker = "💰" if is_ai_cost else "📊"
            print(f"{marker} {table['table_name']}")
            print(f"   • Lignes: {info['row_count']}")
            print(f"   • Colonnes: {info['column_count']}")
            if is_ai_cost:
                print(f"   • ⭐ TABLE DE COÛT IA - À PRÉSERVER")
            print()
        
        # Étape 3: Identifier les tables manquantes
        print("="*80)
        print("🔍 VÉRIFICATION DES TABLES ATTENDUES")
        print("="*80)
        print()
        
        missing_tables = set(EXPECTED_TABLES.keys()) - existing_table_names
        
        if missing_tables:
            print(f"⚠️  {len(missing_tables)} table(s) manquante(s):")
            print()
            
            for table in sorted(missing_tables):
                description = EXPECTED_TABLES.get(table, 'Pas de description')
                is_critical = table in ['tasks', 'webhook_events', 'workflow_reactivations']
                marker = "❌" if is_critical else "⚠️ "
                print(f"{marker} {table}")
                print(f"   • Description: {description}")
                if is_critical:
                    print(f"   • ⚠️  CRITIQUE - Nécessaire pour le fonctionnement")
                print()
        else:
            print("✅ Toutes les tables attendues sont présentes !")
            print()
        
        # Étape 4: Vérifier les tables partitionnées
        print("="*80)
        print("📂 TABLES PARTITIONNÉES")
        print("="*80)
        print()
        
        partitions = await check_partitioned_tables(conn)
        
        if partitions:
            print(f"✅ {len(partitions)} partition(s) trouvée(s):")
            print()
            
            current_parent = None
            for partition in partitions:
                if partition['parent_table'] != current_parent:
                    current_parent = partition['parent_table']
                    print(f"📋 {current_parent} (table partitionnée):")
                print(f"   • {partition['partition_name']}")
            print()
        else:
            print("⚠️  Aucune table partitionnée trouvée")
            print()
            if 'webhook_events' in missing_tables:
                print("❌ La table webhook_events devrait être partitionnée mais n'existe pas !")
                print()
        
        # Étape 5: Résumé des coûts IA
        print("="*80)
        print("💰 RÉSUMÉ DES COÛTS IA ENREGISTRÉS")
        print("="*80)
        print()
        
        ai_summary = await get_ai_cost_summary(conn)
        
        if ai_summary:
            for table_name, data in ai_summary.items():
                print(f"📊 {table_name}:")
                if 'error' in data:
                    print(f"   ❌ Erreur: {data['error']}")
                else:
                    print(f"   • Appels IA: {data.get('total_calls', 0)}")
                    print(f"   • Coût total: ${data.get('total_cost', 0):.4f}")
                    print(f"   • Tokens totaux: {data.get('total_tokens', 0):,}")
                print()
        else:
            print("⚠️  Aucune table de coût IA trouvée")
            print()
        
        # Étape 6: Recommandations
        print("="*80)
        print("💡 RECOMMANDATIONS")
        print("="*80)
        print()
        
        if missing_tables:
            print("🔧 Actions recommandées:")
            print()
            
            if 'webhook_events' in missing_tables:
                print("1. ⚠️  URGENT - Créer la table webhook_events:")
                print("   ./fix_webhook_events_table.sh")
                print("   OU")
                print("   docker exec -i ai-agent-postgres psql -U admin -d ai_agent < data/create_webhook_events_table.sql")
                print()
            
            if 'workflow_reactivations' in missing_tables:
                print("2. Créer la table workflow_reactivations:")
                print("   docker exec -i ai-agent-postgres psql -U admin -d ai_agent < data/migration_workflow_reactivations_table.sql")
                print()
            
            if 'tasks' in missing_tables or len(missing_tables) > 5:
                print("3. Recréer toute la structure de base:")
                print("   docker exec -i ai-agent-postgres psql -U admin -d ai_agent < data/base2.sql")
                print()
            
            print("💰 IMPORTANT: Les tables de coût IA seront PRÉSERVÉES:")
            for table in sorted(AI_COST_TABLES & existing_table_names):
                count = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
                print(f"   ✅ {table}: {count} enregistrements")
            print()
        else:
            print("✅ La base de données est complète et fonctionnelle !")
            print()
        
        # Étape 7: Résumé final
        print("="*80)
        print("📊 RÉSUMÉ FINAL")
        print("="*80)
        print()
        
        print(f"✅ Tables existantes: {len(existing_tables)}")
        print(f"❌ Tables manquantes: {len(missing_tables)}")
        print(f"💰 Tables de coût IA: {len(AI_COST_TABLES & existing_table_names)}/{len(AI_COST_TABLES)}")
        print()
        
        if missing_tables:
            print("⚠️  STATUS: Base de données INCOMPLÈTE")
            print()
            print("Tables manquantes critiques:")
            for table in sorted(missing_tables):
                if table in ['tasks', 'webhook_events', 'workflow_reactivations']:
                    print(f"   ❌ {table}")
            return 1
        else:
            print("✅ STATUS: Base de données COMPLÈTE et OPÉRATIONNELLE")
            return 0
        
    finally:
        await conn.close()
        print()
        print("="*80)
        print("✅ Vérification terminée")
        print("="*80)
        print()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Vérification interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

