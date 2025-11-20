#!/usr/bin/env python3
"""
Script de migration pour créer les tables d'authentification
Base de données: ai_agent_admin
Utilisateur: admin
"""
import asyncio
import asyncpg
import sys
import os
from pathlib import Path
from datetime import datetime
from getpass import getpass


async def migrate_auth_tables():
    """Crée les tables users et audit_logs dans la base de données"""
    
    print("=" * 70)
    print("🔐 Migration des tables d'authentification")
    print("=" * 70)
    print()
    
    # Configuration de la connexion
    print("📋 Configuration de la connexion à la base de données")
    print()
    
    db_user = input("Utilisateur PostgreSQL [admin]: ").strip() or "admin"
    db_password = getpass("Mot de passe PostgreSQL: ")
    db_name = input("Nom de la base de données [ai_agent_admin]: ").strip() or "ai_agent_admin"
    db_host = input("Host [localhost]: ").strip() or "localhost"
    db_port = input("Port [5432]: ").strip() or "5432"
    
    print()
    print(f"📊 Connexion à la base de données...")
    print(f"   Database: {db_name}")
    print(f"   User: {db_user}")
    print(f"   Host: {db_host}:{db_port}")
    print()
    
    try:
        # Connexion à la base de données
        conn = await asyncpg.connect(
            user=db_user,
            password=db_password,
            database=db_name,
            host=db_host,
            port=int(db_port)
        )
        print("✅ Connexion établie avec succès")
        print()
        
        # Vérifier si les tables existent déjà
        print("🔍 Vérification des tables existantes...")
        existing_tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('users', 'audit_logs')
        """)
        
        existing_table_names = [row['tablename'] for row in existing_tables]
        
        if existing_table_names:
            print(f"⚠️  Tables existantes trouvées: {', '.join(existing_table_names)}")
            print()
            
            # Demander confirmation
            response = input("   Voulez-vous recréer ces tables ? (o/n): ")
            if response.lower() != 'o':
                print("❌ Migration annulée")
                await conn.close()
                return
            
            # Supprimer les tables existantes
            print("🗑️  Suppression des tables existantes...")
            await conn.execute("DROP TABLE IF EXISTS audit_logs CASCADE;")
            await conn.execute("DROP TABLE IF EXISTS users CASCADE;")
            print("✅ Tables supprimées")
        else:
            print("✅ Aucune table existante, création en cours...")
        
        print()
        
        # Lire le fichier SQL
        sql_file = Path(__file__).parent / "sql" / "create_users_table.sql"
        
        if not sql_file.exists():
            print(f"❌ Fichier SQL introuvable: {sql_file}")
            await conn.close()
            sys.exit(1)
        
        print(f"📄 Lecture du fichier SQL: {sql_file.name}")
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print(f"   Taille: {len(sql_content)} caractères")
        print()
        
        # Exécuter le SQL
        print("⚙️  Exécution des commandes SQL...")
        try:
            await conn.execute(sql_content)
            print("✅ Commandes SQL exécutées avec succès")
        except Exception as e:
            print(f"❌ Erreur lors de l'exécution SQL: {e}")
            await conn.close()
            sys.exit(1)
        
        print()
        
        # Vérifier la création des tables
        print("🔍 Vérification de la création des tables...")
        created_tables = await conn.fetch("""
            SELECT tablename, schemaname
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('users', 'audit_logs')
            ORDER BY tablename
        """)
        
        if len(created_tables) == 2:
            print("✅ Tables créées avec succès:")
            for table in created_tables:
                print(f"   - {table['tablename']}")
        else:
            print(f"⚠️  Seulement {len(created_tables)} table(s) créée(s)")
        
        print()
        
        # Vérifier la structure de la table users
        print("📋 Structure de la table 'users':")
        users_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """)
        
        for col in users_columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"   - {col['column_name']:<20} {col['data_type']:<20} {nullable}")
        
        print()
        
        # Vérifier la structure de la table audit_logs
        print("📋 Structure de la table 'audit_logs':")
        audit_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'audit_logs'
            ORDER BY ordinal_position
        """)
        
        for col in audit_columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"   - {col['column_name']:<20} {col['data_type']:<20} {nullable}")
        
        print()
        
        # Vérifier les index
        print("🔑 Index créés:")
        indexes = await conn.fetch("""
            SELECT 
                tablename,
                indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename IN ('users', 'audit_logs')
            ORDER BY tablename, indexname
        """)
        
        current_table = None
        for idx in indexes:
            if idx['tablename'] != current_table:
                current_table = idx['tablename']
                print(f"   Table {current_table}:")
            print(f"      - {idx['indexname']}")
        
        print()
        
        # Vérifier les contraintes
        print("🔒 Contraintes créées:")
        constraints = await conn.fetch("""
            SELECT
                conname,
                contype,
                pg_get_constraintdef(oid) as definition
            FROM pg_constraint
            WHERE conrelid IN (
                SELECT oid FROM pg_class 
                WHERE relname IN ('users', 'audit_logs')
            )
            ORDER BY conname
        """)
        
        for const in constraints:
            const_type = {
                'p': 'PRIMARY KEY',
                'f': 'FOREIGN KEY',
                'c': 'CHECK',
                'u': 'UNIQUE'
            }.get(const['contype'], const['contype'])
            print(f"   - {const['conname']:<35} [{const_type}]")
        
        print()
        
        # Statistiques finales
        print("=" * 70)
        print("📊 Résumé de la migration")
        print("=" * 70)
        print(f"✅ Tables créées: 2 (users, audit_logs)")
        print(f"✅ Colonnes table users: {len(users_columns)}")
        print(f"✅ Colonnes table audit_logs: {len(audit_columns)}")
        print(f"✅ Index créés: {len(indexes)}")
        print(f"✅ Contraintes créées: {len(constraints)}")
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Compter les utilisateurs
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        print(f"👥 Utilisateurs dans la base: {user_count}")
        
        if user_count == 0:
            print()
            print("⚠️  ATTENTION: Aucun utilisateur dans la base!")
            print("   Vous devez créer un administrateur pour accéder à l'interface:")
            print()
            print("   python3 scripts/create_admin_user.py")
            print()
        else:
            print()
            print("✅ Utilisateurs existants:")
            users = await conn.fetch("""
                SELECT user_id, email, name, role, is_active
                FROM users
                ORDER BY user_id
            """)
            for user in users:
                status = "✅ Actif" if user['is_active'] else "❌ Inactif"
                print(f"   [{user['user_id']}] {user['email']:<30} {user['name']:<25} {user['role']:<12} {status}")
        
        print()
        print("=" * 70)
        print("🎉 Migration terminée avec succès!")
        print("=" * 70)
        print()
        
        # Fermer la connexion
        await conn.close()
        print("✅ Connexion fermée")
        
    except asyncpg.exceptions.InvalidPasswordError:
        print()
        print("❌ ERREUR: Mot de passe incorrect")
        print("   Vérifiez le mot de passe de l'utilisateur PostgreSQL")
        sys.exit(1)
        
    except asyncpg.exceptions.InvalidCatalogNameError:
        print()
        print(f"❌ ERREUR: Base de données '{db_name}' introuvable")
        print()
        print("   Créez d'abord la base de données:")
        print(f"   psql -U {db_user} -c 'CREATE DATABASE {db_name};'")
        print()
        sys.exit(1)
        
    except asyncpg.exceptions.ConnectionRefusedError:
        print()
        print("❌ ERREUR: Impossible de se connecter à PostgreSQL")
        print("   Vérifiez que PostgreSQL est démarré:")
        print("   brew services start postgresql  (macOS)")
        print("   ou")
        print("   sudo systemctl start postgresql  (Linux)")
        print()
        sys.exit(1)
        
    except Exception as e:
        print()
        print(f"❌ ERREUR: {type(e).__name__}")
        print(f"   {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(migrate_auth_tables())
