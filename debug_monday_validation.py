#!/usr/bin/env python3
"""Script de debug pour tester la validation humaine Monday.com."""

import asyncio
import json
from datetime import datetime, timedelta
from tools.monday_tool import MondayTool
from services.monday_validation_service import MondayValidationService
from utils.logger import get_logger

logger = get_logger(__name__)

async def debug_monday_replies():
    """Debug de la détection des replies Monday.com."""
    
    # ID de l'item qui contient la réponse "debug"
    test_item_id = "5010214993"
    
    print(f"🧪 Test de détection des replies pour item {test_item_id}")
    
    # Initialiser les services
    monday_tool = MondayTool()
    validation_service = MondayValidationService()
    
    try:
        # 1. Récupérer toutes les updates de l'item
        print(f"\n📥 Récupération des updates pour {test_item_id}...")
        updates_result = await monday_tool._get_item_updates(test_item_id)
        
        print(f"✅ Succès: {updates_result.get('success', False)}")
        print(f"📊 Nombre d'updates: {len(updates_result.get('updates', []))}")
        
        # 2. Debug spécifique du parsing de timestamp
        updates = updates_result.get('updates', [])
        print(f"\n🕒 DEBUG PARSING TIMESTAMPS:")
        
        for update in updates:
            update_time_str = update.get("created_at")
            print(f"\nUpdate {update.get('id')}:")
            print(f"  Raw timestamp: {repr(update_time_str)}")
            
            if update_time_str:
                # Test 1: Parsing direct
                try:
                    time1 = datetime.fromisoformat(update_time_str.replace('Z', '+00:00'))
                    print(f"  ✅ Parsing standard: {time1}")
                except Exception as e:
                    print(f"  ❌ Parsing standard failed: {e}")
        
        # 3. Test la logique _find_human_reply avec parsing fixé
        validation_update_id = None
        debug_reply = None
        
        print(f"\n🔍 RECHERCHE DE L'UPDATE DE VALIDATION ET DE LA REPLY DEBUG:")
        
        for update in updates:
            body = update.get('body', '')
            print(f"\nUpdate {update.get('id')}:")
            print(f"  Body contient 'VALIDATION HUMAINE REQUISE': {'VALIDATION HUMAINE REQUISE' in body}")
            print(f"  Body strip lower: {repr(body.strip().lower())}")
            
            # ✅ CORRECTION: Nettoyer le body pour ignorer les caractères invisibles
            import re
            cleaned_body = body.replace('\ufeff', '').replace('\u200b', '').replace('\u00a0', '')
            cleaned_body = re.sub(r'<[^>]+>', '', cleaned_body).strip().lower()
            
            print(f"  Body nettoyé: {repr(cleaned_body)}")
            print(f"  Body nettoyé == 'debug': {cleaned_body == 'debug'}")
            
            if "VALIDATION HUMAINE REQUISE" in body:
                validation_update_id = update.get('id')
                print(f"  ⭐ VALIDATION UPDATE FOUND: {validation_update_id}")
                
            if cleaned_body == 'debug':
                debug_reply = update
                print(f"  ⭐ DEBUG REPLY FOUND: {update.get('id')}")
        
        print(f"\n📋 RÉSULTAT DE LA RECHERCHE:")
        print(f"  Validation update ID: {validation_update_id}")
        print(f"  Debug reply: {debug_reply.get('id') if debug_reply else 'None'}")
        
        if validation_update_id and debug_reply:
            print(f"\n🎯 TEST LOGIQUE _find_human_reply AVEC PARSING FIXÉ")
            print(f"Validation update: {validation_update_id}")
            print(f"Debug reply: {debug_reply.get('id')} -> parent: {debug_reply.get('parent_id')}")
            
            # Tester avec un timestamp "since" approprié (avant la reply)
            debug_time_str = debug_reply.get('created_at')
            
            # Essayer plusieurs méthodes de parsing
            debug_time = None
            try:
                debug_time = datetime.fromisoformat(debug_time_str.replace('Z', '+00:00'))
                print(f"✅ Debug time parsed: {debug_time}")
            except:
                try:
                    debug_time = datetime.strptime(debug_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                    print(f"✅ Debug time parsed (strptime): {debug_time}")
                except Exception as e:
                    print(f"❌ Impossible de parser debug time: {e}")
            
            if debug_time:
                since_time = debug_time - timedelta(minutes=5)  # 5 minutes avant
                print(f"Using since time: {since_time}")
                
                # Simuler manuellement la logique _find_human_reply
                print(f"\n🔍 SIMULATION MANUELLE DE _find_human_reply:")
                
                for update in updates:
                    update_time_str = update.get("created_at")
                    if not update_time_str:
                        print(f"  Update {update.get('id')}: pas de timestamp")
                        continue
                    
                    # Essayer de parser le timestamp
                    update_time = None
                    try:
                        update_time = datetime.fromisoformat(update_time_str.replace('Z', '+00:00'))
                    except:
                        try:
                            update_time = datetime.strptime(update_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                        except Exception as e:
                            print(f"  Update {update.get('id')}: parsing timestamp failed: {e}")
                            continue
                    
                    # Vérifier les conditions
                    is_after_since = update_time > since_time
                    reply_to_match = (update.get("reply_to_id") == validation_update_id or 
                                    update.get("parent_id") == validation_update_id)
                    is_validation_reply = validation_service._is_validation_reply(update.get('body', '').strip().lower())
                    
                    print(f"  Update {update.get('id')}:")
                    print(f"    Time: {update_time} (after {since_time}: {is_after_since})")
                    print(f"    Reply to: {update.get('reply_to_id')}, Parent: {update.get('parent_id')} -> Match: {reply_to_match}")
                    print(f"    Is validation reply: {is_validation_reply}")
                    print(f"    Body: {repr(update.get('body', ''))[:50]}")
                    
                    if is_after_since and reply_to_match and is_validation_reply:
                        print(f"    ✅ CETTE REPLY DEVRAIT ÊTRE TROUVÉE!")
                        
                        # Analyser la reply
                        from services.intelligent_reply_analyzer import intelligent_reply_analyzer
                        analysis = await intelligent_reply_analyzer.analyze_human_intention(update.get('body', ''))
                        print(f"    🧠 Analyse: {analysis.decision.value} (confiance: {analysis.confidence})")
                        break
                    else:
                        missing_conditions = []
                        if not is_after_since:
                            missing_conditions.append("timestamp trop ancien")
                        if not reply_to_match:
                            missing_conditions.append("pas une reply à l'update de validation")
                        if not is_validation_reply:
                            missing_conditions.append("pas un pattern de validation")
                        print(f"    ❌ Conditions manquantes: {', '.join(missing_conditions)}")
        else:
            if not validation_update_id:
                print(f"❌ Aucun update de validation trouvé!")
            if not debug_reply:
                print(f"❌ Aucune reply 'debug' trouvée!")
        
    except Exception as e:
        logger.error(f"❌ Erreur durant les tests: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_monday_replies()) 