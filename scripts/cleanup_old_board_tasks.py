#!/usr/bin/env python3
"""
Script pour nettoyer les tâches de l'ancien board Monday.com.
"""

import sys
import asyncio
import psycopg2
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings


class TaskCleanup:
    """Nettoyeur de tâches obsolètes."""
    
    def __init__(self):
        self.settings = get_settings()
        self.current_board_id = int(self.settings.monday_board_id)
        self.conn = None
        
    def connect_db(self):
        """Se connecte à la base de données."""
        db_url = self.settings.database_url
        parsed = urlparse(db_url)
        
        self.conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
        
    def analyze_tasks(self):
        """Analyse les tâches en base de données."""
        print("\n" + "="*60)
        print("📊 ANALYSE DES TÂCHES EN BASE DE DONNÉES")
        print("="*60)
        print(f"\nBoard actuel configuré: {self.current_board_id}\n")
        
        cursor = self.conn.cursor()
        
        # Récupérer toutes les tâches
        cursor.execute("""
            SELECT 
                tasks_id,
                monday_item_id,
                monday_board_id,
                title,
                internal_status,
                repository_url,
                created_at,
                updated_at
            FROM tasks
            ORDER BY created_at DESC
        """)
        
        tasks = cursor.fetchall()
        
        if not tasks:
            print("✅ Aucune tâche en base de données")
            cursor.close()
            return [], []
        
        print(f"Total de tâches: {len(tasks)}\n")
        
        old_board_tasks = []
        current_board_tasks = []
        
        for task in tasks:
            task_id, monday_item_id, monday_board_id, title, status, repo_url, created_at, updated_at = task
            
            if monday_board_id != self.current_board_id:
                old_board_tasks.append(task)
                print(f"⚠️  [ANCIEN BOARD] ID: {task_id}")
                print(f"   • Monday Item: {monday_item_id}")
                print(f"   • Board ID: {monday_board_id}")
                print(f"   • Titre: {title}")
                print(f"   • Statut: {status}")
                print(f"   • Créée: {created_at}")
                print()
            else:
                current_board_tasks.append(task)
        
        if old_board_tasks:
            print(f"\n⚠️  {len(old_board_tasks)} tâche(s) de l'ancien board trouvée(s)")
        else:
            print("\n✅ Toutes les tâches sont du board actuel")
        
        if current_board_tasks:
            print(f"✅ {len(current_board_tasks)} tâche(s) du board actuel")
        
        cursor.close()
        return old_board_tasks, current_board_tasks
    
    def get_task_dependencies(self, task_ids: list):
        """Récupère les dépendances des tâches (runs, steps, etc.)."""
        if not task_ids:
            return {}
        
        cursor = self.conn.cursor()
        dependencies = {}
        
        for task_id in task_ids:
            deps = {
                "runs": 0,
                "steps": 0,
                "ai_interactions": 0,
                "human_validations": 0
            }
            
            # Compter les runs
            cursor.execute("""
                SELECT COUNT(*) FROM task_runs WHERE task_id = %s
            """, (task_id,))
            deps["runs"] = cursor.fetchone()[0]
            
            # Compter les steps
            cursor.execute("""
                SELECT COUNT(*) FROM run_steps rs
                JOIN task_runs tr ON rs.task_run_id = tr.tasks_runs_id
                WHERE tr.task_id = %s
            """, (task_id,))
            deps["steps"] = cursor.fetchone()[0]
            
            # Compter les interactions IA
            cursor.execute("""
                SELECT COUNT(*) FROM ai_interactions ai
                JOIN run_steps rs ON ai.run_step_id = rs.run_steps_id
                JOIN task_runs tr ON rs.task_run_id = tr.tasks_runs_id
                WHERE tr.task_id = %s
            """, (task_id,))
            deps["ai_interactions"] = cursor.fetchone()[0]
            
            # Compter les validations humaines
            cursor.execute("""
                SELECT COUNT(*) FROM human_validations
                WHERE task_id = %s
            """, (task_id,))
            deps["human_validations"] = cursor.fetchone()[0]
            
            dependencies[task_id] = deps
        
        cursor.close()
        return dependencies
    
    def delete_task(self, task_id: int):
        """Supprime une tâche et toutes ses dépendances."""
        cursor = self.conn.cursor()
        
        try:
            # Les contraintes ON DELETE CASCADE s'occupent de la suppression en cascade
            cursor.execute("DELETE FROM tasks WHERE tasks_id = %s", (task_id,))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Erreur lors de la suppression: {e}")
            return False
        finally:
            cursor.close()
    
    def cleanup_old_board_tasks(self, old_board_tasks: list, dry_run: bool = True, auto_confirm: bool = False):
        """Supprime les tâches de l'ancien board."""
        if not old_board_tasks:
            print("\n✅ Aucune tâche à nettoyer")
            return
        
        print("\n" + "="*60)
        print("🧹 NETTOYAGE DES TÂCHES DE L'ANCIEN BOARD")
        print("="*60)
        
        task_ids = [task[0] for task in old_board_tasks]
        
        # Récupérer les dépendances
        print("\n📊 Analyse des dépendances...\n")
        dependencies = self.get_task_dependencies(task_ids)
        
        for task in old_board_tasks:
            task_id = task[0]
            title = task[3]
            deps = dependencies.get(task_id, {})
            
            print(f"Tâche ID {task_id}: {title}")
            print(f"   • {deps['runs']} run(s)")
            print(f"   • {deps['steps']} step(s)")
            print(f"   • {deps['ai_interactions']} interaction(s) IA")
            print(f"   • {deps['human_validations']} validation(s) humaine(s)")
            print()
        
        if dry_run:
            print("\n⚠️  MODE DRY-RUN: Aucune suppression effectuée")
            print("\nPour supprimer réellement ces tâches, exécutez:")
            print(f"   python3 {__file__} --delete --yes")
        else:
            if not auto_confirm:
                print(f"\n❓ Voulez-vous supprimer ces {len(old_board_tasks)} tâche(s) ? (y/N): ", end='')
                response = input().strip().lower()
                confirmed = response == 'y'
            else:
                print(f"\n✅ Suppression automatique confirmée (--yes)")
                confirmed = True
            
            if confirmed:
                print("\n🗑️  Suppression en cours...\n")
                
                for task in old_board_tasks:
                    task_id = task[0]
                    title = task[3]
                    
                    if self.delete_task(task_id):
                        print(f"✅ Tâche {task_id} supprimée: {title}")
                    else:
                        print(f"❌ Échec suppression tâche {task_id}")
                
                print("\n✅ Nettoyage terminé!")
            else:
                print("\n❌ Nettoyage annulé")
    
    def run(self, dry_run: bool = True, auto_confirm: bool = False):
        """Lance l'analyse et le nettoyage."""
        print("\n" + "="*60)
        print("🧹 NETTOYAGE DES TÂCHES DE L'ANCIEN BOARD MONDAY.COM")
        print("="*60)
        
        try:
            self.connect_db()
            print("✅ Connexion à la base de données établie")
            
            old_board_tasks, current_board_tasks = self.analyze_tasks()
            
            if old_board_tasks:
                self.cleanup_old_board_tasks(old_board_tasks, dry_run, auto_confirm)
            else:
                print("\n✅ Aucune tâche de l'ancien board à nettoyer")
            
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.conn:
                self.conn.close()
                print("\n✅ Connexion fermée")


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Nettoie les tâches de l'ancien board Monday.com"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Supprime réellement les tâches (sinon mode dry-run)"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Confirme automatiquement la suppression (pas de prompt)"
    )
    
    args = parser.parse_args()
    
    cleaner = TaskCleanup()
    cleaner.run(dry_run=not args.delete, auto_confirm=args.yes)


if __name__ == "__main__":
    main()

