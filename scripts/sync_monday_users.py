#!/usr/bin/env python3
"""
Script pour synchroniser les utilisateurs Monday.com dans la base de données.
Ce script :
1. Récupère les utilisateurs depuis Monday.com via l'API
2. Récupère les monday_item_id depuis la table tasks
3. Insert/Update les utilisateurs dans la table monday_users
"""

import asyncio
import asyncpg
import requests
import os
from datetime import datetime
from config.settings import get_settings

settings = get_settings()


async def get_monday_users_from_api():
    """Récupère les utilisateurs depuis Monday.com"""
    api_url = "https://api.monday.com/v2"
    headers = {
        "Authorization": settings.monday_api_token,
        "Content-Type": "application/json"
    }
    
    # Query GraphQL pour récupérer les users
    query = """
    query {
        users {
            id
            name
            email
            title
            teams {
                name
            }
        }
    }
    """
    
    try:
        response = requests.post(
            api_url,
            json={"query": query},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            print(f"❌ Erreur API Monday: {data['errors']}")
            return []
        
        return data.get("data", {}).get("users", [])
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des utilisateurs Monday: {e}")
        return []


async def sync_users_to_database(users):
    """Synchronise les utilisateurs dans la base de données"""
    conn = await asyncpg.connect(settings.database_url)
    
    try:
        # Créer la table si elle n'existe pas
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS monday_users (
                monday_user_id BIGINT PRIMARY KEY,
                monday_item_id BIGINT UNIQUE,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                role VARCHAR(100),
                team VARCHAR(100),
                access_status VARCHAR(20) DEFAULT 'authorized',
                satisfaction_score DECIMAL(2,1),
                satisfaction_comment TEXT,
                last_activity TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                monday_metadata JSONB DEFAULT '{}'
            );
        """)
        
        inserted = 0
        updated = 0
        
        for user in users:
            monday_user_id = int(user['id'])
            name = user.get('name', 'Unknown')
            email = user.get('email', f'user{monday_user_id}@monday.com')
            role = user.get('title', 'Utilisateur')
            team = ', '.join([t['name'] for t in user.get('teams', [])])[:100] if user.get('teams') else None
            
            # Chercher le monday_item_id correspondant dans tasks
            monday_item_id = await conn.fetchval("""
                SELECT DISTINCT monday_item_id 
                FROM tasks 
                WHERE created_by_user_id = $1 
                ORDER BY created_at DESC 
                LIMIT 1
            """, monday_user_id)
            
            # Récupérer la dernière activité
            last_activity = await conn.fetchval("""
                SELECT MAX(created_at)
                FROM tasks
                WHERE created_by_user_id = $1 OR monday_item_id = $2
            """, monday_user_id, monday_item_id)
            
            try:
                # Insert or update
                result = await conn.execute("""
                    INSERT INTO monday_users (
                        monday_user_id, monday_item_id, name, email, role, team, 
                        last_activity, monday_metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                    ON CONFLICT (monday_user_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        role = EXCLUDED.role,
                        team = EXCLUDED.team,
                        last_activity = EXCLUDED.last_activity,
                        monday_metadata = EXCLUDED.monday_metadata,
                        updated_at = NOW()
                """, monday_user_id, monday_item_id, name, email, role, team, 
                     last_activity, '{}')
                
                if "INSERT" in result:
                    inserted += 1
                else:
                    updated += 1
                    
                print(f"✅ Synchronisé: {name} ({email})")
            except Exception as e:
                print(f"❌ Erreur pour {name}: {e}")
        
        # Synchroniser aussi les utilisateurs depuis tasks qui ne sont pas encore dans monday_users
        await sync_users_from_tasks(conn)
        
        print(f"\n📊 Résumé:")
        print(f"  ✅ {inserted} utilisateurs insérés")
        print(f"  🔄 {updated} utilisateurs mis à jour")
        
    finally:
        await conn.close()


async def sync_users_from_tasks(conn):
    """Synchronise les utilisateurs depuis la table tasks"""
    print("\n🔄 Synchronisation des utilisateurs depuis tasks...")
    
    # Récupérer tous les monday_item_id uniques depuis tasks
    items = await conn.fetch("""
        SELECT DISTINCT 
            monday_item_id,
            MAX(created_at) as last_activity,
            COUNT(*) as total_tasks,
            COUNT(*) FILTER (WHERE internal_status = 'completed') as completed_tasks
        FROM tasks
        WHERE monday_item_id IS NOT NULL
        GROUP BY monday_item_id
    """)
    
    for item in items:
        monday_item_id = item['monday_item_id']
        
        # Vérifier si cet item existe déjà dans monday_users
        exists = await conn.fetchval("""
            SELECT EXISTS(SELECT 1 FROM monday_users WHERE monday_item_id = $1)
        """, monday_item_id)
        
        if not exists:
            # Créer un utilisateur basique depuis les données tasks
            email = f"user{monday_item_id}@example.com"
            name = f"Utilisateur {monday_item_id}"
            
            # Calculer un score de satisfaction basique (basé sur le taux de succès)
            total = item['total_tasks']
            completed = item['completed_tasks']
            satisfaction = round(3.0 + (completed / total * 2.0), 1) if total > 0 else 3.5
            
            await conn.execute("""
                INSERT INTO monday_users (
                    monday_user_id, monday_item_id, name, email, role, 
                    last_activity, satisfaction_score, access_status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (monday_item_id) DO NOTHING
            """, monday_item_id, monday_item_id, name, email, 'Développeur',
                 item['last_activity'], satisfaction, 'authorized')
            
            print(f"✅ Créé utilisateur depuis tasks: {name}")


async def main():
    """Fonction principale"""
    print("🚀 Démarrage de la synchronisation des utilisateurs Monday...")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. Récupérer les utilisateurs depuis Monday API
    print("1️⃣ Récupération des utilisateurs depuis Monday.com...")
    monday_users = await get_monday_users_from_api()
    print(f"   Trouvé {len(monday_users)} utilisateurs dans Monday\n")
    
    # 2. Synchroniser dans la base de données
    print("2️⃣ Synchronisation dans la base de données...")
    await sync_users_to_database(monday_users)
    
    print("\n✨ Synchronisation terminée!")


if __name__ == "__main__":
    asyncio.run(main())

