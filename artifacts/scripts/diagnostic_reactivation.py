#!/usr/bin/env python3
"""
Script de diagnostic pour identifier pourquoi la réactivation ne fonctionne pas.
"""

import asyncio
import os
import sys
import requests
from datetime import datetime
from services.database_persistence_service import db_persistence
from utils.logger import get_logger

logger = get_logger(__name__)


async def check_1_fastapi_running():
    """Vérifie si FastAPI est en cours d'exécution"""
    print("\n" + "="*80)
    print("CHECK 1: FastAPI est-il démarré ?")
    print("="*80)
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=3)
        if response.status_code == 200:
            data = response.json()
            print("✅ FastAPI est démarré")
            print(f"   Status: {data.get('status')}")
            print(f"   Celery workers: {data.get('celery_workers', 0)}")
            return True
        else:
            print(f"❌ FastAPI répond mais avec erreur: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ FastAPI ne répond pas sur http://localhost:8000")
        print("   → Démarrez FastAPI: uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


async def check_2_completed_tasks():
    """Vérifie s'il existe des tâches terminées pouvant être réactivées"""
    print("\n" + "="*80)
    print("CHECK 2: Y a-t-il des tâches terminées (réactivables) ?")
    print("="*80)
    
    try:
        await db_persistence.initialize()
        
        async with db_persistence.db_manager.get_connection() as conn:
            tasks = await conn.fetch("""
                SELECT 
                    tasks_id,
                    monday_item_id,
                    title,
                    internal_status,
                    monday_status,
                    reactivation_count
                FROM tasks
                WHERE internal_status IN ('completed', 'failed', 'quality_check')
                ORDER BY updated_at DESC
                LIMIT 5
            """)
            
            if tasks:
                print(f"✅ {len(tasks)} tâche(s) réactivable(s) trouvée(s):")
                for task in tasks:
                    print(f"\n   📋 Task ID: {task['tasks_id']}")
                    print(f"      Monday Item ID: {task['monday_item_id']}")
                    print(f"      Titre: {task['title'][:50]}...")
                    print(f"      Statut: {task['internal_status']}")
                    print(f"      Réactivations: {task['reactivation_count']}/10")
                return True
            else:
                print("❌ Aucune tâche terminée trouvée")
                print("   → Marquez une tâche comme 'Done' dans Monday.com d'abord")
                return False
                
    except Exception as e:
        print(f"❌ Erreur accès BDD: {e}")
        return False


async def check_3_recent_webhooks():
    """Vérifie si des webhooks ont été reçus récemment"""
    print("\n" + "="*80)
    print("CHECK 3: Des webhooks Monday.com ont-ils été reçus ?")
    print("="*80)
    
    try:
        async with db_persistence.db_manager.get_connection() as conn:
            webhooks = await conn.fetch("""
                SELECT 
                    id,
                    event_type,
                    payload,
                    received_at,
                    processed
                FROM webhook_events
                WHERE source = 'monday'
                ORDER BY received_at DESC
                LIMIT 10
            """)
            
            if webhooks:
                print(f"✅ {len(webhooks)} webhook(s) reçu(s) récemment:")
                
                update_webhooks = [w for w in webhooks if w['event_type'] in ('create_update', 'create_reply')]
                
                for webhook in webhooks[:5]:
                    event_type = webhook['event_type']
                    received = webhook['received_at'].strftime('%Y-%m-%d %H:%M:%S')
                    processed = "✅" if webhook['processed'] else "❌"
                    
                    marker = "🔔" if event_type in ('create_update', 'create_reply') else "📝"
                    print(f"\n   {marker} Type: {event_type}")
                    print(f"      Reçu: {received}")
                    print(f"      Traité: {processed}")
                
                if update_webhooks:
                    print(f"\n   ✅ {len(update_webhooks)} webhook(s) de type update/reply (réactivation possible)")
                else:
                    print("\n   ⚠️  Aucun webhook 'create_update' ou 'create_reply' détecté")
                    print("      → Vérifiez la configuration des webhooks Monday.com")
                
                return bool(update_webhooks)
            else:
                print("❌ Aucun webhook reçu")
                print("   → Vérifiez la configuration des webhooks dans Monday.com")
                print("   → URL webhook: http://votre-domaine.com/webhook/monday")
                return False
                
    except Exception as e:
        print(f"❌ Erreur accès BDD: {e}")
        return False


async def check_4_log_files():
    """Vérifie les fichiers de logs"""
    print("\n" + "="*80)
    print("CHECK 4: Où sont les logs ?")
    print("="*80)
    
    log_locations = [
        "logs/fastapi.log",
        "logs/celery.log",
        "logs/logs.txt",
        "logs/application.log"
    ]
    
    found_logs = []
    
    for log_path in log_locations:
        if os.path.exists(log_path):
            size = os.path.getsize(log_path)
            if size > 0:
                # Lire les dernières lignes
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                    last_10 = lines[-10:] if len(lines) >= 10 else lines
                    
                    # Chercher des mentions de réactivation
                    reactivation_lines = [l for l in last_10 if 'réactiv' in l.lower() or 'reactivat' in l.lower()]
                    
                    print(f"\n✅ {log_path}")
                    print(f"   Taille: {size/1024:.1f} KB")
                    print(f"   Lignes: {len(lines)}")
                    
                    if reactivation_lines:
                        print(f"   🔔 {len(reactivation_lines)} mention(s) de réactivation dans les 10 dernières lignes")
                    else:
                        print(f"   ⚠️  Pas de mention de réactivation dans les 10 dernières lignes")
                    
                    found_logs.append(log_path)
            else:
                print(f"\n⚠️  {log_path} existe mais est vide")
        else:
            print(f"\n❌ {log_path} n'existe pas")
    
    if found_logs:
        print(f"\n📝 Pour voir les logs en temps réel, utilisez:")
        for log_path in found_logs:
            print(f"   tail -f {log_path} | grep -i reactivat")
        return True
    else:
        print("\n❌ Aucun fichier de log trouvé")
        return False


async def check_5_test_webhook():
    """Teste l'envoi d'un webhook de réactivation"""
    print("\n" + "="*80)
    print("CHECK 5: Test d'envoi d'un webhook de réactivation")
    print("="*80)
    
    # Trouver une tâche terminée
    try:
        async with db_persistence.db_manager.get_connection() as conn:
            task = await conn.fetchrow("""
                SELECT monday_item_id, title
                FROM tasks
                WHERE internal_status = 'completed'
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            
            if not task:
                print("❌ Aucune tâche 'completed' trouvée pour tester")
                return False
            
            pulse_id = task['monday_item_id']
            print(f"📌 Tâche de test trouvée: {pulse_id} - {task['title'][:50]}...")
            
            # Créer un payload de test
            payload = {
                "event": {
                    "pulseId": pulse_id,
                    "type": "create_update",
                    "textBody": "Test de réactivation - diagnostic",
                    "updateId": f"test_{int(datetime.now().timestamp())}"
                },
                "type": "create_update"
            }
            
            print("\n📤 Envoi du webhook de test...")
            response = requests.post(
                "http://localhost:8000/webhook/monday",
                json=payload,
                timeout=10
            )
            
            print(f"\n📊 Réponse HTTP: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Webhook accepté")
                print(f"   Réponse: {data}")
                
                if data.get('is_reactivation'):
                    print("\n🎉 RÉACTIVATION DÉTECTÉE !")
                    print("   → Les logs devraient apparaître dans les fichiers de logs")
                    return True
                else:
                    print("\n⚠️  Webhook traité mais pas de réactivation détectée")
                    print(f"   Raison: {data.get('message', 'N/A')}")
                    return False
            else:
                print(f"❌ Erreur: {response.text}")
                return False
                
    except requests.exceptions.ConnectionError:
        print("❌ Impossible de se connecter à FastAPI")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Exécute tous les diagnostics"""
    print("\n" + "="*80)
    print("🔍 DIAGNOSTIC DE RÉACTIVATION")
    print("="*80)
    print("\nCe script va identifier pourquoi la réactivation ne fonctionne pas\n")
    
    results = {}
    
    # Check 1: FastAPI
    results['fastapi'] = await check_1_fastapi_running()
    
    if not results['fastapi']:
        print("\n" + "="*80)
        print("⛔ ARRÊT DU DIAGNOSTIC")
        print("="*80)
        print("\n❌ FastAPI n'est pas démarré. Démarrez-le d'abord:")
        print("   cd '/Users/stagiaire_vycode/Stage Smartelia/AI-Agent '")
        print("   source venv/bin/activate")
        print("   uvicorn main:app --reload")
        return
    
    # Check 2: Tâches terminées
    results['tasks'] = await check_2_completed_tasks()
    
    # Check 3: Webhooks reçus
    results['webhooks'] = await check_3_recent_webhooks()
    
    # Check 4: Fichiers de logs
    results['logs'] = await check_4_log_files()
    
    # Check 5: Test webhook
    if results['tasks']:
        results['test'] = await check_5_test_webhook()
    
    # Résumé
    print("\n" + "="*80)
    print("📊 RÉSUMÉ DU DIAGNOSTIC")
    print("="*80)
    
    for check, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
    
    # Recommandations
    print("\n" + "="*80)
    print("💡 RECOMMANDATIONS")
    print("="*80)
    
    if not results.get('webhooks'):
        print("\n⚠️  PROBLÈME PRINCIPAL: Aucun webhook 'create_update/create_reply' reçu")
        print("\n📝 Actions à faire:")
        print("   1. Allez sur Monday.com → Integrations → Webhooks")
        print("   2. Vérifiez que les événements suivants sont cochés:")
        print("      ✅ create_update")
        print("      ✅ create_reply")
        print("   3. Postez un commentaire sur une tâche 'Done'")
        print("   4. Relancez ce script pour voir si le webhook arrive")
    
    elif results.get('test'):
        print("\n✅ LE SYSTÈME FONCTIONNE !")
        print("\n📝 Pour voir les logs en temps réel:")
        print("   tail -f logs/fastapi.log | grep -E '(🔔|RÉACTIVATION|réactiv)'")
        print("\n📝 Pour tester avec Monday.com:")
        print("   1. Ouvrez une tâche marquée 'Done'")
        print("   2. Postez: 'Peux-tu ajouter un export CSV ?'")
        print("   3. Surveillez les logs (commande ci-dessus)")


if __name__ == "__main__":
    asyncio.run(main())

