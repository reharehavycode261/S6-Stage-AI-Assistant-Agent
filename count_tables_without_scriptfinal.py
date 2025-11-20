#!/usr/bin/env python3
"""
Compter toutes les tables uniques déclarées dans les fichiers SQL
SANS scriptfinal.sql
"""

from pathlib import Path
import re

def extract_tables_from_sql(sql_content: str) -> set:
    """Extraire les noms de tables d'un fichier SQL."""
    tables = set()
    
    # Pattern pour CREATE TABLE
    for match in re.finditer(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)', sql_content, re.IGNORECASE):
        table_name = match.group(1).lower()
        tables.add(table_name)
    
    return tables

def main():
    print("\n" + "="*80)
    print("📊 COMPTAGE DES TABLES (SANS scriptfinal.sql)")
    print("="*80)
    print()
    
    data_dir = Path('data')
    
    # Lister tous les fichiers SQL SAUF scriptfinal.sql et les fichiers non-migration
    sql_files = sorted([
        f for f in data_dir.glob('*.sql') 
        if f.name not in [
            'scriptfinal.sql',  # EXCLU
            'delete.sql', 
            'drop_all_except_ai_cost.sql', 
            'insert.sql'
        ]
    ])
    
    print(f"📋 Analyse de {len(sql_files)} fichiers SQL")
    print()
    
    all_tables = set()
    file_details = []
    
    for sql_file in sql_files:
        content = sql_file.read_text()
        tables = extract_tables_from_sql(content)
        
        if tables:
            file_details.append((sql_file.name, tables))
            all_tables.update(tables)
    
    # Afficher les détails par fichier
    print("="*80)
    print("📄 TABLES PAR FICHIER")
    print("="*80)
    print()
    
    for filename, tables in sorted(file_details, key=lambda x: len(x[1]), reverse=True):
        if tables:
            print(f"📄 {filename:50s} {len(tables):2d} tables")
            for table in sorted(tables):
                print(f"   • {table}")
            print()
    
    # Résumé
    print("="*80)
    print("📊 RÉSUMÉ FINAL")
    print("="*80)
    print()
    
    print(f"Fichiers analysés:     {len(sql_files)}")
    print(f"Tables uniques:        {len(all_tables)}")
    print()
    
    print("="*80)
    print("📋 LISTE COMPLÈTE DES TABLES UNIQUES")
    print("="*80)
    print()
    
    for i, table in enumerate(sorted(all_tables), 1):
        print(f"{i:2d}. {table}")
    
    print()
    print("="*80)
    print(f"✅ TOTAL: {len(all_tables)} TABLES UNIQUES")
    print("="*80)
    print()

if __name__ == "__main__":
    main()

