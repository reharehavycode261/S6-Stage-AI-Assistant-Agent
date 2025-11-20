#!/usr/bin/env python3
"""
Script pour diagnostiquer et corriger la configuration Monday.com
après un changement de board ou de compte.
"""

import os
import sys
import asyncio
import httpx
from typing import Dict, Any, Optional
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings


class MondayConfigFixer:
    """Outil pour diagnostiquer et corriger la configuration Monday.com."""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_token = self.settings.monday_api_token
        self.base_url = "https://api.monday.com/v2"
        self.errors = []
        self.warnings = []
        self.success_messages = []
        
    async def check_api_token(self) -> bool:
        """Vérifie si le token API Monday.com est valide."""
        print("\n" + "="*60)
        print("🔑 ÉTAPE 1: Vérification du token API Monday.com")
        print("="*60)
        
        if not self.api_token or self.api_token == "your-monday-api-token-here":
            self.errors.append("❌ MONDAY_API_TOKEN n'est pas configuré ou utilise la valeur par défaut")
            print("❌ Token API non configuré")
            return False
        
        # Tester le token avec une requête simple
        query = """
        query {
            me {
                id
                name
                email
            }
        }
        """
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    json={"query": query},
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and "me" in data["data"]:
                        user_info = data["data"]["me"]
                        print(f"✅ Token valide - Connecté en tant que: {user_info.get('name')} ({user_info.get('email')})")
                        self.success_messages.append(f"Token valide pour {user_info.get('email')}")
                        return True
                    elif "errors" in data:
                        error_msg = data["errors"][0].get("message", "Erreur inconnue")
                        self.errors.append(f"❌ Erreur API Monday.com: {error_msg}")
                        print(f"❌ Erreur API: {error_msg}")
                        return False
                else:
                    self.errors.append(f"❌ Erreur HTTP {response.status_code}")
                    print(f"❌ Erreur HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            self.errors.append(f"❌ Erreur de connexion: {str(e)}")
            print(f"❌ Erreur de connexion: {str(e)}")
            return False
    
    async def check_board_access(self) -> Optional[Dict[str, Any]]:
        """Vérifie si le board configuré est accessible."""
        print("\n" + "="*60)
        print("📋 ÉTAPE 2: Vérification du board Monday.com")
        print("="*60)
        
        board_id = self.settings.monday_board_id
        print(f"Board ID configuré: {board_id}")
        
        if not board_id or board_id == "your-board-id":
            self.errors.append("❌ MONDAY_BOARD_ID n'est pas configuré")
            print("❌ Board ID non configuré")
            return None
        
        query = """
        query ($boardId: [ID!]) {
            boards(ids: $boardId) {
                id
                name
                description
                state
                columns {
                    id
                    title
                    type
                }
            }
        }
        """
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    json={
                        "query": query,
                        "variables": {"boardId": [int(board_id)]}
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "errors" in data:
                        error_msg = data["errors"][0].get("message", "Erreur inconnue")
                        self.errors.append(f"❌ Erreur API: {error_msg}")
                        print(f"❌ Erreur API: {error_msg}")
                        return None
                    
                    boards = data.get("data", {}).get("boards", [])
                    
                    if not boards:
                        self.errors.append(f"❌ Board {board_id} non trouvé ou inaccessible")
                        print(f"❌ Board {board_id} non trouvé")
                        print("\n💡 SOLUTION: Vérifiez que:")
                        print("   1. Le board existe dans votre compte Monday.com")
                        print("   2. Le token API a accès à ce board")
                        print("   3. Le board ID est correct dans votre fichier .env")
                        return None
                    
                    board = boards[0]
                    print(f"✅ Board trouvé: {board['name']} (ID: {board['id']})")
                    print(f"   État: {board['state']}")
                    print(f"   Nombre de colonnes: {len(board['columns'])}")
                    
                    self.success_messages.append(f"Board '{board['name']}' accessible")
                    return board
                    
        except Exception as e:
            self.errors.append(f"❌ Erreur lors de la vérification du board: {str(e)}")
            print(f"❌ Erreur: {str(e)}")
            return None
    
    def check_column_ids(self, board: Dict[str, Any]) -> Dict[str, str]:
        """Vérifie les IDs de colonnes configurés vs réels."""
        print("\n" + "="*60)
        print("📊 ÉTAPE 3: Vérification des IDs de colonnes")
        print("="*60)
        
        columns = board.get("columns", [])
        column_mapping = {}
        
        print("\n📋 Colonnes disponibles dans le board:\n")
        for col in columns:
            print(f"   • {col['title']:<30} (ID: {col['id']:<20} Type: {col['type']})")
            column_mapping[col['title'].lower()] = col['id']
        
        # Vérifier les colonnes requises
        print("\n🔍 Vérification des colonnes requises:\n")
        
        required_columns = {
            "status": {
                "env_var": "MONDAY_STATUS_COLUMN_ID",
                "configured": self.settings.monday_status_column_id,
                "search_terms": ["status", "statut", "état"],
                "type": "status"
            },
            "repository_url": {
                "env_var": "MONDAY_REPOSITORY_URL_COLUMN_ID",
                "configured": self.settings.monday_repository_url_column_id,
                "search_terms": ["repository url", "repo url", "github", "git"],
                "type": "link"
            }
        }
        
        recommendations = {}
        
        for col_name, info in required_columns.items():
            print(f"\n🔹 {col_name.upper()}:")
            print(f"   Variable env: {info['env_var']}")
            print(f"   Valeur configurée: {info['configured'] or 'Non configuré'}")
            
            # Chercher la colonne correspondante
            found_col = None
            for col in columns:
                if col['type'] == info['type']:
                    for term in info['search_terms']:
                        if term in col['title'].lower():
                            found_col = col
                            break
                    if found_col:
                        break
            
            if found_col:
                if info['configured'] == found_col['id']:
                    print(f"   ✅ Correct: '{found_col['title']}' (ID: {found_col['id']})")
                    self.success_messages.append(f"Colonne {col_name} correctement configurée")
                else:
                    print(f"   ⚠️  Trouvé: '{found_col['title']}' (ID: {found_col['id']})")
                    print(f"   ❌ Différent de la configuration: {info['configured']}")
                    self.warnings.append(f"Colonne {col_name}: ID incorrect dans .env")
                    recommendations[info['env_var']] = found_col['id']
            else:
                print(f"   ⚠️  Aucune colonne de type '{info['type']}' trouvée")
                self.warnings.append(f"Colonne {col_name} non trouvée dans le board")
        
        return recommendations
    
    async def check_database_tasks(self):
        """Vérifie les tâches en base de données."""
        print("\n" + "="*60)
        print("🗄️  ÉTAPE 4: Vérification des tâches en base de données")
        print("="*60)
        
        try:
            import psycopg2
            from urllib.parse import urlparse
            
            # Parser l'URL de la base de données
            db_url = self.settings.database_url
            parsed = urlparse(db_url)
            
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password
            )
            
            cursor = conn.cursor()
            
            # Compter les tâches par statut
            cursor.execute("""
                SELECT internal_status, COUNT(*) 
                FROM tasks 
                GROUP BY internal_status
                ORDER BY COUNT(*) DESC
            """)
            
            tasks_by_status = cursor.fetchall()
            
            if tasks_by_status:
                print("\n📊 Tâches en base de données:\n")
                total_tasks = sum(count for _, count in tasks_by_status)
                for status, count in tasks_by_status:
                    print(f"   • {status:<20} : {count:>5} tâches")
                print(f"\n   TOTAL: {total_tasks} tâches")
                
                # Compter les tâches pending/failed
                pending_count = sum(count for status, count in tasks_by_status if status in ['pending', 'failed', 'error'])
                
                if pending_count > 0:
                    self.warnings.append(f"{pending_count} tâches en attente/erreur dans la DB")
                    print(f"\n⚠️  {pending_count} tâches nécessitent une attention")
            else:
                print("✅ Aucune tâche en base de données")
                self.success_messages.append("Base de données propre")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            self.errors.append(f"❌ Erreur lors de la vérification DB: {str(e)}")
            print(f"❌ Erreur DB: {str(e)}")
    
    def generate_env_updates(self, recommendations: Dict[str, str]):
        """Génère les mises à jour recommandées pour le fichier .env."""
        print("\n" + "="*60)
        print("📝 ÉTAPE 5: Recommandations de configuration")
        print("="*60)
        
        if recommendations:
            print("\n⚠️  Mises à jour recommandées pour votre fichier .env:\n")
            for env_var, new_value in recommendations.items():
                print(f"{env_var}={new_value}")
            
            print("\n💡 ACTIONS À EFFECTUER:")
            print("   1. Ouvrez votre fichier .env")
            print("   2. Mettez à jour les variables ci-dessus")
            print("   3. Redémarrez Celery et l'application")
        else:
            print("✅ Aucune mise à jour nécessaire dans le fichier .env")
    
    def print_summary(self):
        """Affiche un résumé du diagnostic."""
        print("\n" + "="*60)
        print("📋 RÉSUMÉ DU DIAGNOSTIC")
        print("="*60)
        
        if self.success_messages:
            print("\n✅ SUCCÈS:")
            for msg in self.success_messages:
                print(f"   • {msg}")
        
        if self.warnings:
            print("\n⚠️  AVERTISSEMENTS:")
            for msg in self.warnings:
                print(f"   • {msg}")
        
        if self.errors:
            print("\n❌ ERREURS:")
            for msg in self.errors:
                print(f"   • {msg}")
        
        print("\n" + "="*60)
        
        if not self.errors and not self.warnings:
            print("✅ Tout est correctement configuré!")
        elif not self.errors:
            print("⚠️  Configuration fonctionnelle mais des améliorations sont recommandées")
        else:
            print("❌ Des erreurs doivent être corrigées")
        
        print("="*60 + "\n")
    
    async def run_full_diagnostic(self):
        """Lance le diagnostic complet."""
        print("\n" + "="*60)
        print("🔍 DIAGNOSTIC DE CONFIGURATION MONDAY.COM")
        print("="*60)
        print("\nCe script va vérifier:")
        print("  1. Token API Monday.com")
        print("  2. Accès au board")
        print("  3. IDs des colonnes")
        print("  4. État de la base de données")
        
        # Étape 1: Vérifier le token
        token_valid = await self.check_api_token()
        
        if not token_valid:
            print("\n❌ Impossible de continuer sans un token API valide")
            self.print_summary()
            return
        
        # Étape 2: Vérifier le board
        board = await self.check_board_access()
        
        if not board:
            print("\n❌ Impossible de continuer sans accès au board")
            self.print_summary()
            return
        
        # Étape 3: Vérifier les colonnes
        recommendations = self.check_column_ids(board)
        
        # Étape 4: Vérifier la base de données
        await self.check_database_tasks()
        
        # Étape 5: Générer les recommandations
        self.generate_env_updates(recommendations)
        
        # Résumé
        self.print_summary()


async def main():
    """Point d'entrée principal."""
    fixer = MondayConfigFixer()
    await fixer.run_full_diagnostic()


if __name__ == "__main__":
    asyncio.run(main())

