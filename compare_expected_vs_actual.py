#!/usr/bin/env python3
"""
Comparer les tables attendues (sans scriptfinal.sql) avec les tables en DB
"""

import asyncio
import asyncpg
from pathlib import Path
import re

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'admin',
    'password': 'password',
    'database': 'ai_agent_admin',
}

def extract_tables_from_sql(sql_content: str) -> set:
    """Extraire les noms de tables d'un fichier SQL."""
    tables = set()
    for match in re.finditer(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)', sql_content, re.IGNORECASE):
        table_name = match.group(1).lower()
        tables.add(table_name)
    return tables

async def main():
    print("\n" + "="*80)
    print("📊 COMPARAISON: TABLES ATTENDUES vs TABLES EN DB")
    print("="*80)
    print()
    
    # 1. Tables attendues (sans scriptfinal.sql)
    data_dir = Path('data')
    sql_files = [
        f for f in data_dir.glob('*.sql') 
        if f.name not in [
            'scriptfinal.sql',
            'delete.sql', 
            'drop_all_except_ai_cost.sql', 
            'insert.sql'
        ]
    ]
    
    expected_tables = set()
    for sql_file in sql_files:
        content = sql_file.read_text()
        tables = extract_tables_from_sql(content)
        expected_tables.update(tables)
    
    print(f"📋 Tables attendues (sans scriptfinal.sql): {len(expected_tables)}")
    
    # 2. Tables en DB
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        rows = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        actual_tables = {row['tablename'].lower() for row in rows}
        
        print(f"📋 Tables en base de données:           {len(actual_tables)}")
        print()
        
        # 3. Comparaison
        print("="*80)
        print("📊 ANALYSE")
        print("="*80)
        print()
        
        missing = expected_tables - actual_tables
        extra = actual_tables - expected_tables
        present = expected_tables & actual_tables
        
        print(f"✅ Tables présentes:     {len(present)}/{len(expected_tables)} ({len(present)*100//len(expected_tables)}%)")
        print(f"⚠️  Tables manquantes:    {len(missing)}")
        print(f"ℹ️  Tables supplémentaires: {len(extra)}")
        print()
        
        if missing:
            print("="*80)
            print(f"⚠️  TABLES MANQUANTES ({len(missing)})")
            print("="*80)
            print()
            for table in sorted(missing):
                print(f"  ❌ {table}")
            print()
        
        if extra:
            print("="*80)
            print(f"ℹ️  TABLES SUPPLÉMENTAIRES EN DB ({len(extra)})")
            print("="*80)
            print()
            for table in sorted(extra):
                # Vérifier si c'est une partition pg_partman
                if 'webhook_events_p' in table:
                    print(f"  ✅ {table:40s} (partition pg_partman)")
                elif 'celery' in table:
                    print(f"  ✅ {table:40s} (Celery)")
                else:
                    print(f"  ℹ️  {table}")
            print()
        
        # 4. Résumé final
        print("="*80)
        print("📊 RÉSUMÉ FINAL")
        print("="*80)
        print()
        
        print(f"Tables attendues:        {len(expected_tables)}")
        print(f"Tables créées:           {len(present)}")
        print(f"Tables manquantes:       {len(missing)}")
        print(f"Taux de complétion:      {len(present)*100//len(expected_tables)}%")
        print()
        
        if len(missing) == 0:
            print("="*80)
            print("✅ TOUTES LES TABLES SONT CRÉÉES !")
            print("="*80)
            return 0
        else:
            print("="*80)
            print("⚠️  CERTAINES TABLES SONT MANQUANTES")
            print("="*80)
            print()
            print("💡 Actions recommandées:")
            print("   1. Appliquer les migrations manquantes")
            print("   2. Vérifier les erreurs dans les logs")
            return 1
            
    finally:
        await conn.close()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

