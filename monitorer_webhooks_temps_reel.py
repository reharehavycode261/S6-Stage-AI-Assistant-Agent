#!/usr/bin/env python3
"""
Moniteur en temps réel des webhooks Monday.com.
Affiche TOUT ce qui arrive du serveur pour diagnostiquer.
"""

import asyncio
import signal
import sys
from datetime import datetime
from services.database_persistence_service import db_persistence
from utils.logger import get_logger

logger = get_logger(__name__)

# Flag pour arrêter proprement
running = True

def signal_handler(sig, frame):
    global running
    print('\n\n⏹️  Arrêt du monitoring...')
    running = False

signal.signal(signal.SIGINT, signal_handler)


async def monitor_webhooks():
    """Surveille les webhooks en temps réel"""
    
    print("\n" + "="*80)
    print("📡 MONITORING TEMPS RÉEL DES WEBHOOKS MONDAY.COM")
    print("="*80)
    print("\n🔍 En attente de webhooks...")
    print("   (Postez un commentaire dans Monday.com pour tester)")
    print("   (Appuyez sur Ctrl+C pour arrêter)")
    print("\n" + "="*80 + "\n")
    
    await db_persistence.initialize()
    
    # Garder trace du dernier webhook vu
    last_webhook_id = None
    
    # Récupérer l'ID du dernier webhook au démarrage
    async with db_persistence.db_manager.get_connection() as conn:
        result = await conn.fetchval("""
            SELECT MAX(webhook_events_id)
            FROM webhook_events
            WHERE source = 'monday'
        """)
        last_webhook_id = result or 0
    
    print(f"📌 Dernier webhook ID: {last_webhook_id}")
    print(f"🔄 Surveillance des nouveaux webhooks...\n")
    
    check_count = 0
    
    while running:
        try:
            async with db_persistence.db_manager.get_connection() as conn:
                # Chercher les nouveaux webhooks
                new_webhooks = await conn.fetch("""
                    SELECT 
                        webhook_events_id,
                        event_type,
                        payload,
                        received_at,
                        processed
                    FROM webhook_events
                    WHERE source = 'monday'
                      AND webhook_events_id > $1
                    ORDER BY webhook_events_id ASC
                """, last_webhook_id)
                
                if new_webhooks:
                    for webhook in new_webhooks:
                        webhook_id = webhook['webhook_events_id']
                        event_type = webhook['event_type']
                        received_at = webhook['received_at'].strftime('%H:%M:%S')
                        processed = "✅" if webhook['processed'] else "⏳"
                        payload = webhook['payload']
                        
                        # Extraire les infos importantes
                        event = payload.get('event', {})
                        pulse_id = event.get('pulseId', 'N/A')
                        pulse_name = event.get('pulseName', 'N/A')
                        text_body = event.get('textBody', '')
                        
                        # Affichage selon le type
                        if event_type in ('create_update', 'create_reply'):
                            print("🔔" + "="*79)
                            print(f"🎉 WEBHOOK DE RÉACTIVATION REÇU !")
                            print("="*80)
                        else:
                            print("📝" + "="*79)
                            print(f"📨 Nouveau webhook")
                            print("="*80)
                        
                        print(f"⏰ Heure: {received_at}")
                        print(f"🆔 ID: {webhook_id}")
                        print(f"📋 Type: {event_type}")
                        print(f"📌 Item Monday: {pulse_id}")
                        print(f"📝 Titre: {pulse_name[:50]}...")
                        print(f"{processed} Traité: {'Oui' if webhook['processed'] else 'Non'}")
                        
                        if text_body:
                            print(f"💬 Texte: {text_body[:100]}...")
                        
                        print("\n📦 PAYLOAD COMPLET:")
                        print("-" * 80)
                        import json
                        print(json.dumps(payload, indent=2, ensure_ascii=False)[:500] + "...")
                        print("-" * 80)
                        
                        if event_type in ('create_update', 'create_reply'):
                            print("\n✅ CE WEBHOOK DEVRAIT DÉCLENCHER UNE RÉACTIVATION !")
                            print("📝 Vérifiez les logs pour voir si la réactivation se lance:")
                            print("   tail -f logs/fastapi.log | grep -i reactivat")
                        
                        print("="*80 + "\n")
                        
                        last_webhook_id = webhook_id
                
                # Afficher un point tous les 10 checks pour montrer que ça tourne
                check_count += 1
                if check_count % 10 == 0:
                    print(f"⏳ En attente... (check #{check_count})", end='\r')
            
            # Attendre 2 secondes avant le prochain check
            await asyncio.sleep(2)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            await asyncio.sleep(5)
    
    print("\n✅ Monitoring arrêté")


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                 MONITEUR TEMPS RÉEL - WEBHOOKS MONDAY.COM                  ║
╚════════════════════════════════════════════════════════════════════════════╝

Ce script affiche TOUS les webhooks Monday.com dès qu'ils arrivent.

📝 COMMENT TESTER :
   1. Laissez ce script tourner
   2. Ouvrez Monday.com
   3. Postez un commentaire sur une tâche "Done"
   4. Le webhook devrait apparaître ICI dans les 2-3 secondes

🔍 SI RIEN N'APPARAÎT :
   → Monday.com n'envoie pas les webhooks
   → Il faut configurer les événements create_update/create_reply
   → Voir GUIDE_CONFIGURER_MONDAY.md

🎯 SI UN WEBHOOK APPARAÎT :
   → Le système fonctionne !
   → Vérifiez si la réactivation se lance dans les logs
    """)
    
    try:
        asyncio.run(monitor_webhooks())
    except KeyboardInterrupt:
        print("\n\n✅ Arrêt du monitoring")
        sys.exit(0)

