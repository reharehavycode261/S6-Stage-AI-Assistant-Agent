#!/usr/bin/env python3
"""
Script de migration de l'ancien schéma vers le nouveau schéma sans failles
Version: 2.0
Date: 2025-11-17

Ce script migre les données de l'ancien schéma (database_schema_final.sql)
vers le nouveau schéma refondu (database_schema_refonte_complete.sql)

Usage:
    python scripts/migrate_to_refonte_complete.py --old-db ai_agent_admin --new-db ai_agent_new
"""

import asyncpg
import asyncio
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Optional
import json


class DatabaseMigration:
    """Gestionnaire de migration de base de données"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "",
        old_db: str = "ai_agent_admin",
        new_db: str = "ai_agent_new",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.old_db = old_db
        self.new_db = new_db
        
        self.old_conn: Optional[asyncpg.Connection] = None
        self.new_conn: Optional[asyncpg.Connection] = None
        
        self.stats = {
            "users": 0,
            "projects": 0,
            "tasks": 0,
            "task_statuses": 0,
            "validations": 0,
            "workflows": 0,
            "ai_usage": 0,
            "webhooks": 0,
            "errors": [],
        }
    
    async def connect(self):
        """Connecter aux deux bases de données"""
        print("🔌 Connexion aux bases de données...")
        
        try:
            self.old_conn = await asyncpg.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.old_db,
            )
            print(f"  ✅ Connecté à l'ancienne base: {self.old_db}")
        except Exception as e:
            print(f"  ❌ Erreur connexion ancienne base: {e}")
            sys.exit(1)
        
        try:
            self.new_conn = await asyncpg.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.new_db,
            )
            print(f"  ✅ Connecté à la nouvelle base: {self.new_db}")
        except Exception as e:
            print(f"  ❌ Erreur connexion nouvelle base: {e}")
            await self.old_conn.close()
            sys.exit(1)
    
    async def disconnect(self):
        """Déconnecter des bases de données"""
        if self.old_conn:
            await self.old_conn.close()
        if self.new_conn:
            await self.new_conn.close()
        print("🔌 Déconnecté des bases de données")
    
    async def verify_old_schema(self) -> bool:
        """Vérifier que l'ancien schéma existe"""
        print("\n🔍 Vérification de l'ancien schéma...")
        
        required_tables = ["users", "projects", "tasks", "human_validations"]
        
        for table in required_tables:
            result = await self.old_conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = $1
                )
                """,
                table,
            )
            
            if not result:
                print(f"  ❌ Table manquante: {table}")
                return False
            print(f"  ✅ Table trouvée: {table}")
        
        return True
    
    async def verify_new_schema(self) -> bool:
        """Vérifier que le nouveau schéma est créé"""
        print("\n🔍 Vérification du nouveau schéma...")
        
        required_schemas = ["core", "reference", "security", "audit"]
        
        for schema in required_schemas:
            result = await self.new_conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.schemata 
                    WHERE schema_name = $1
                )
                """,
                schema,
            )
            
            if not result:
                print(f"  ❌ Schéma manquant: {schema}")
                print(f"\n⚠️  Veuillez d'abord exécuter le script de création:")
                print(f"     psql -d {self.new_db} -f data/database_schema_refonte_complete.sql")
                return False
            print(f"  ✅ Schéma trouvé: {schema}")
        
        return True
    
    async def get_old_counts(self) -> Dict[str, int]:
        """Récupérer le nombre d'enregistrements dans l'ancienne base"""
        print("\n📊 Comptage des enregistrements dans l'ancienne base...")
        
        counts = {}
        tables = ["users", "projects", "tasks", "human_validations", "workflows"]
        
        for table in tables:
            try:
                count = await self.old_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                counts[table] = count
                print(f"  📌 {table}: {count:,}")
            except Exception as e:
                print(f"  ⚠️  {table}: Erreur - {e}")
                counts[table] = 0
        
        return counts
    
    async def migrate_users(self):
        """Migrer les utilisateurs"""
        print("\n👥 Migration des utilisateurs...")
        
        try:
            # Récupérer les utilisateurs de l'ancienne base
            old_users = await self.old_conn.fetch(
                """
                SELECT 
                    id,
                    username,
                    email,
                    password,
                    COALESCE(created_at, NOW()) as created_at,
                    first_name,
                    last_name
                FROM users
                WHERE deleted_at IS NULL OR deleted_at IS NOT NULL
                """
            )
            
            print(f"  📥 {len(old_users)} utilisateurs trouvés")
            
            # Mapping ancien ID -> nouveau UUID
            user_mapping = {}
            
            for user in old_users:
                try:
                    # Insérer dans la nouvelle base
                    new_uuid = await self.new_conn.fetchval(
                        """
                        INSERT INTO security.users (
                            username,
                            email,
                            password_hash,
                            first_name,
                            last_name,
                            is_active,
                            created_at
                        ) VALUES ($1, $2, $3, $4, $5, TRUE, $6)
                        ON CONFLICT (username) DO UPDATE 
                        SET email = EXCLUDED.email
                        RETURNING id
                        """,
                        user["username"],
                        user["email"],
                        user["password"],
                        user.get("first_name"),
                        user.get("last_name"),
                        user["created_at"],
                    )
                    
                    user_mapping[user["id"]] = new_uuid
                    self.stats["users"] += 1
                    
                except Exception as e:
                    self.stats["errors"].append(f"User {user['username']}: {e}")
                    print(f"  ⚠️  Erreur user {user['username']}: {e}")
            
            print(f"  ✅ {self.stats['users']} utilisateurs migrés")
            return user_mapping
            
        except Exception as e:
            print(f"  ❌ Erreur migration users: {e}")
            raise
    
    async def migrate_projects(self):
        """Migrer les projets"""
        print("\n📁 Migration des projets...")
        
        try:
            old_projects = await self.old_conn.fetch(
                """
                SELECT 
                    id,
                    name,
                    description,
                    monday_board_id,
                    repository_url,
                    COALESCE(created_at, NOW()) as created_at,
                    config
                FROM projects
                WHERE deleted_at IS NULL OR deleted_at IS NOT NULL
                """
            )
            
            print(f"  📥 {len(old_projects)} projets trouvés")
            
            project_mapping = {}
            
            for project in old_projects:
                try:
                    new_uuid = await self.new_conn.fetchval(
                        """
                        INSERT INTO core.projects (
                            name,
                            description,
                            monday_board_id,
                            repository_url,
                            is_active,
                            config,
                            created_at
                        ) VALUES ($1, $2, $3, $4, TRUE, $5, $6)
                        ON CONFLICT (monday_board_id) DO UPDATE
                        SET name = EXCLUDED.name
                        RETURNING id
                        """,
                        project["name"],
                        project.get("description"),
                        project.get("monday_board_id"),
                        project.get("repository_url"),
                        project.get("config"),
                        project["created_at"],
                    )
                    
                    project_mapping[project["id"]] = new_uuid
                    self.stats["projects"] += 1
                    
                except Exception as e:
                    self.stats["errors"].append(f"Project {project['name']}: {e}")
                    print(f"  ⚠️  Erreur projet {project['name']}: {e}")
            
            print(f"  ✅ {self.stats['projects']} projets migrés")
            return project_mapping
            
        except Exception as e:
            print(f"  ❌ Erreur migration projects: {e}")
            raise
    
    async def migrate_tasks(self, project_mapping: Dict):
        """Migrer les tâches avec leurs statuts"""
        print("\n📋 Migration des tâches...")
        
        try:
            old_tasks = await self.old_conn.fetch(
                """
                SELECT 
                    id,
                    project_id,
                    title,
                    description,
                    status,
                    monday_item_id,
                    priority,
                    metadata,
                    COALESCE(created_at, NOW()) as created_at
                FROM tasks
                WHERE deleted_at IS NULL OR deleted_at IS NOT NULL
                """
            )
            
            print(f"  📥 {len(old_tasks)} tâches trouvées")
            
            task_mapping = {}
            
            for task in old_tasks:
                try:
                    # Mapper l'ancien project_id au nouveau UUID
                    new_project_id = project_mapping.get(task["project_id"])
                    if not new_project_id:
                        print(f"  ⚠️  Projet non trouvé pour task {task['id']}")
                        continue
                    
                    # Insérer la tâche
                    new_uuid = await self.new_conn.fetchval(
                        """
                        INSERT INTO core.tasks (
                            project_id,
                            title,
                            description,
                            monday_item_id,
                            priority,
                            metadata,
                            created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        RETURNING id
                        """,
                        new_project_id,
                        task["title"],
                        task.get("description"),
                        task.get("monday_item_id"),
                        task.get("priority", 0),
                        task.get("metadata"),
                        task["created_at"],
                    )
                    
                    task_mapping[task["id"]] = new_uuid
                    self.stats["tasks"] += 1
                    
                    # Migrer le statut
                    await self.migrate_task_status(new_uuid, task["status"], task["created_at"])
                    
                except Exception as e:
                    self.stats["errors"].append(f"Task {task['id']}: {e}")
                    print(f"  ⚠️  Erreur task {task['id']}: {e}")
            
            print(f"  ✅ {self.stats['tasks']} tâches migrées")
            return task_mapping
            
        except Exception as e:
            print(f"  ❌ Erreur migration tasks: {e}")
            raise
    
    async def migrate_task_status(self, task_id: str, old_status: str, created_at):
        """Migrer le statut d'une tâche"""
        try:
            # Mapper l'ancien statut au nouveau code
            status_mapping = {
                "pending": "task_pending",
                "in_progress": "task_in_progress",
                "in progress": "task_in_progress",
                "completed": "task_completed",
                "failed": "task_failed",
                "cancelled": "task_cancelled",
            }
            
            status_code = status_mapping.get(old_status.lower(), "task_pending")
            
            # Récupérer l'ID du status_type
            status_id = await self.new_conn.fetchval(
                """
                SELECT id FROM reference.status_types
                WHERE code = $1 AND category = 'task'
                """,
                status_code,
            )
            
            if status_id:
                await self.new_conn.execute(
                    """
                    INSERT INTO core.task_statuses (
                        task_id,
                        status_id,
                        is_current,
                        created_at
                    ) VALUES ($1, $2, TRUE, $3)
                    """,
                    task_id,
                    status_id,
                    created_at,
                )
                self.stats["task_statuses"] += 1
        
        except Exception as e:
            print(f"    ⚠️  Erreur status pour task {task_id}: {e}")
    
    async def migrate_validations(self, task_mapping: Dict):
        """Migrer les validations humaines"""
        print("\n✅ Migration des validations...")
        
        try:
            old_validations = await self.old_conn.fetch(
                """
                SELECT 
                    id,
                    task_id,
                    question,
                    context,
                    response_status,
                    response_text,
                    response_at,
                    rejection_count,
                    COALESCE(created_at, NOW()) as created_at
                FROM human_validations
                WHERE deleted_at IS NULL OR deleted_at IS NOT NULL
                """
            )
            
            print(f"  📥 {len(old_validations)} validations trouvées")
            
            for validation in old_validations:
                try:
                    new_task_id = task_mapping.get(validation["task_id"])
                    if not new_task_id:
                        continue
                    
                    await self.new_conn.execute(
                        """
                        INSERT INTO core.human_validations (
                            task_id,
                            question,
                            context,
                            response_status,
                            response_text,
                            response_at,
                            rejection_count,
                            created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        new_task_id,
                        validation["question"],
                        validation.get("context"),
                        validation.get("response_status", "pending"),
                        validation.get("response_text"),
                        validation.get("response_at"),
                        validation.get("rejection_count", 0),
                        validation["created_at"],
                    )
                    
                    self.stats["validations"] += 1
                    
                except Exception as e:
                    self.stats["errors"].append(f"Validation {validation['id']}: {e}")
            
            print(f"  ✅ {self.stats['validations']} validations migrées")
            
        except Exception as e:
            print(f"  ❌ Erreur migration validations: {e}")
    
    async def print_summary(self, old_counts: Dict):
        """Afficher le résumé de la migration"""
        print("\n" + "=" * 80)
        print("📊 RÉSUMÉ DE LA MIGRATION")
        print("=" * 80)
        
        print("\n📈 Statistiques:")
        print(f"  👥 Utilisateurs:  {old_counts.get('users', 0):,} → {self.stats['users']:,}")
        print(f"  📁 Projets:       {old_counts.get('projects', 0):,} → {self.stats['projects']:,}")
        print(f"  📋 Tâches:        {old_counts.get('tasks', 0):,} → {self.stats['tasks']:,}")
        print(f"  🔄 Statuts:       - → {self.stats['task_statuses']:,}")
        print(f"  ✅ Validations:   {old_counts.get('human_validations', 0):,} → {self.stats['validations']:,}")
        
        if self.stats["errors"]:
            print(f"\n⚠️  Erreurs: {len(self.stats['errors'])}")
            for i, error in enumerate(self.stats["errors"][:10], 1):
                print(f"  {i}. {error}")
            if len(self.stats["errors"]) > 10:
                print(f"  ... et {len(self.stats['errors']) - 10} autres")
        else:
            print("\n✅ Aucune erreur !")
        
        print("\n" + "=" * 80)
    
    async def run(self):
        """Exécuter la migration complète"""
        start_time = datetime.now()
        
        print("=" * 80)
        print("🚀 MIGRATION VERS LE NOUVEAU SCHÉMA SANS FAILLES")
        print("=" * 80)
        print(f"  Ancienne base: {self.old_db}")
        print(f"  Nouvelle base: {self.new_db}")
        print(f"  Date: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        try:
            # Connexion
            await self.connect()
            
            # Vérifications
            if not await self.verify_old_schema():
                print("\n❌ Schéma ancien invalide")
                return False
            
            if not await self.verify_new_schema():
                print("\n❌ Nouveau schéma non créé")
                return False
            
            # Comptages
            old_counts = await self.get_old_counts()
            
            # Migration
            user_mapping = await self.migrate_users()
            project_mapping = await self.migrate_projects()
            task_mapping = await self.migrate_tasks(project_mapping)
            await self.migrate_validations(task_mapping)
            
            # Résumé
            await self.print_summary(old_counts)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n⏱️  Durée totale: {duration:.2f} secondes")
            print("\n✅ Migration terminée avec succès !")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Erreur fatale: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            await self.disconnect()


async def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Migrer l'ancienne base vers le nouveau schéma sans failles"
    )
    parser.add_argument("--host", default="localhost", help="Hôte PostgreSQL")
    parser.add_argument("--port", type=int, default=5432, help="Port PostgreSQL")
    parser.add_argument("--user", default="postgres", help="Utilisateur PostgreSQL")
    parser.add_argument("--password", default="", help="Mot de passe PostgreSQL")
    parser.add_argument("--old-db", default="ai_agent_admin", help="Ancienne base")
    parser.add_argument("--new-db", default="ai_agent_new", help="Nouvelle base")
    
    args = parser.parse_args()
    
    migration = DatabaseMigration(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        old_db=args.old_db,
        new_db=args.new_db,
    )
    
    success = await migration.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())



