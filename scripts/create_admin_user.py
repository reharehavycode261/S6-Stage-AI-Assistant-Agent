#!/usr/bin/env python3
"""
Script pour créer le premier utilisateur admin
Ce script doit être exécuté après la création de la table users
"""
import asyncio
import os
import sys
from pathlib import Path
from getpass import getpass

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from passlib.context import CryptContext
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration du hashing de mot de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_admin_user(
    email: str,
    name: str,
    password: str,
    database_url: str
):
    """Crée un utilisateur admin dans la base de données"""
    
    # Hasher le mot de passe
    password_hash = pwd_context.hash(password)
    
    # Connexion à la base de données
    conn = await asyncpg.connect(database_url)
    
    try:
        # Vérifier si un admin existe déjà
        existing_admin = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE role = 'Admin'"
        )
        
        if existing_admin > 0:
            print(f"⚠️  Un administrateur existe déjà dans la base de données.")
            response = input("Voulez-vous créer un autre admin ? (o/n): ")
            if response.lower() != 'o':
                print("❌ Opération annulée.")
                return
        
        # Vérifier si l'email existe déjà
        existing_user = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE email = $1",
            email
        )
        
        if existing_user > 0:
            print(f"❌ Un utilisateur avec l'email {email} existe déjà.")
            return
        
        # Créer l'utilisateur admin
        user_id = await conn.fetchval(
            """
            INSERT INTO users (email, name, password_hash, role, is_active)
            VALUES ($1, $2, $3, 'Admin', TRUE)
            RETURNING user_id
            """,
            email, name, password_hash
        )
        
        print(f"✅ Utilisateur admin créé avec succès!")
        print(f"   ID: {user_id}")
        print(f"   Email: {email}")
        print(f"   Nom: {name}")
        print(f"   Rôle: Admin")
        print(f"\n🔐 Vous pouvez maintenant vous connecter à l'interface admin avec ces identifiants.")
        
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'utilisateur: {e}")
        raise
    finally:
        await conn.close()


async def check_tables_exist(database_url: str):
    """Vérifie que les tables users et audit_logs existent"""
    conn = await asyncpg.connect(database_url)
    
    try:
        # Vérifier l'existence des tables
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('users', 'audit_logs')
        """)
        
        if len(tables) == 2:
            print("✅ Tables users et audit_logs trouvées")
            return True
        else:
            print(f"❌ Tables manquantes. Trouvé: {[t['tablename'] for t in tables]}")
            print("   Exécutez d'abord: python3 migrate_auth_tables.py")
            return False
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification des tables: {e}")
        return False
    finally:
        await conn.close()


def validate_email(email: str) -> bool:
    """Valide le format de l'email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password: str) -> bool:
    """Valide le mot de passe (min 8 caractères)"""
    return len(password) >= 8


async def main():
    """Point d'entrée principal"""
    print("=" * 60)
    print("🔐 Création d'un utilisateur administrateur")
    print("=" * 60)
    print()
    
    # Récupérer l'URL de la base de données
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ Variable d'environnement DATABASE_URL non trouvée")
        print("   Assurez-vous que votre fichier .env est configuré correctement")
        return
    
    print(f"📊 Base de données: {database_url.split('@')[1] if '@' in database_url else 'configurée'}")
    print()
    
    # Vérifier que les tables existent
    print("📝 Vérification des tables...")
    tables_ok = await check_tables_exist(database_url)
    
    if not tables_ok:
        print("❌ Tables manquantes. Exécutez d'abord: python3 migrate_auth_tables.py")
        return
    
    print()
    print("=" * 60)
    print("Informations du nouvel administrateur")
    print("=" * 60)
    print()
    
    # Demander les informations de l'admin
    while True:
        email = input("📧 Email: ").strip()
        if validate_email(email):
            break
        print("❌ Format d'email invalide. Réessayez.")
    
    name = input("👤 Nom complet: ").strip()
    
    while True:
        password = getpass("🔒 Mot de passe (min 8 caractères): ")
        if validate_password(password):
            password_confirm = getpass("🔒 Confirmez le mot de passe: ")
            if password == password_confirm:
                break
            print("❌ Les mots de passe ne correspondent pas. Réessayez.")
        else:
            print("❌ Le mot de passe doit contenir au moins 8 caractères.")
    
    print()
    print("=" * 60)
    print("Résumé")
    print("=" * 60)
    print(f"Email: {email}")
    print(f"Nom: {name}")
    print(f"Rôle: Admin")
    print("=" * 60)
    print()
    
    # Confirmation
    response = input("Confirmer la création de cet administrateur ? (o/n): ")
    
    if response.lower() == 'o':
        await create_admin_user(email, name, password, database_url)
    else:
        print("❌ Opération annulée.")


if __name__ == "__main__":
    asyncio.run(main())

