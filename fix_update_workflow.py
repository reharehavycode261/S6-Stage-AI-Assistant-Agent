#!/usr/bin/env python3
"""Script de correction automatique pour le système de workflow depuis updates."""

import asyncio
import sys

# Couleurs
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")


async def correction_1_verifier_migration():
    """CORRECTION 1: Vérifier si la migration SQL est appliquée."""
    print("\n" + "="*70)
    print("CORRECTION 1: Vérification Migration SQL")
    print("="*70)
    
    try:
        from services.database_persistence_service import db_persistence
        
        await db_persistence.initialize()
        print_success("Connexion DB établie")
        
        async with db_persistence.db_manager.get_connection() as conn:
            # Vérifier table task_update_triggers
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'task_update_triggers'
                )
            """)
            
            if exists:
                print_success("Table task_update_triggers existe")
                
                # Compter les triggers
                count = await conn.fetchval("SELECT COUNT(*) FROM task_update_triggers")
                print_info(f"Triggers enregistrés: {count}")
            else:
                print_error("Table task_update_triggers MANQUANTE")
                print_warning("Action requise: Appliquer data/migration_task_update_triggers.sql")
                print_info("Via pgAdmin, psql ou autre client SQL")
                return False
            
            # Vérifier colonne triggered_by_update_id
            col_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'task_runs' 
                    AND column_name = 'triggered_by_update_id'
                )
            """)
            
            if col_exists:
                print_success("Colonne triggered_by_update_id existe")
            else:
                print_error("Colonne triggered_by_update_id MANQUANTE")
                return False
        
        return True
        
    except Exception as e:
        print_error(f"Erreur vérification migration: {e}")
        return False


async def correction_2_verifier_code():
    """CORRECTION 2: Vérifier que le code est en place."""
    print("\n" + "="*70)
    print("CORRECTION 2: Vérification Code")
    print("="*70)
    
    try:
        # Vérifier imports
        from services.update_analyzer_service import update_analyzer_service
        from services.workflow_trigger_service import workflow_trigger_service
        print_success("Services importés correctement")
        
        # Vérifier webhook_persistence_service
        import services.webhook_persistence_service as wps
        import inspect
        
        source = inspect.getsource(wps.WebhookPersistenceService._handle_update_event)
        
        if 'update_analyzer_service' in source:
            print_success("Import update_analyzer_service présent dans webhook")
        else:
            print_error("Import update_analyzer_service MANQUANT")
            return False
        
        if 'analyze_update_intent' in source:
            print_success("Appel analyze_update_intent présent")
        else:
            print_error("Appel analyze_update_intent MANQUANT")
            return False
        
        if 'trigger_workflow_from_update' in source:
            print_success("Appel trigger_workflow_from_update présent")
        else:
            print_error("Appel trigger_workflow_from_update MANQUANT")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Erreur vérification code: {e}")
        return False


async def correction_3_tester_analyse():
    """CORRECTION 3: Tester l'analyse LLM."""
    print("\n" + "="*70)
    print("CORRECTION 3: Test Analyse LLM")
    print("="*70)
    
    try:
        from services.update_analyzer_service import update_analyzer_service
        
        print_info("Test 1: Nouvelle demande")
        context = {
            'task_title': 'Test',
            'task_status': 'completed',
            'original_description': 'Test'
        }
        
        result = await update_analyzer_service.analyze_update_intent(
            'Bonjour, pouvez-vous ajouter un export CSV ?',
            context
        )
        
        print(f"  Type détecté: {result.type}")
        print(f"  Confiance: {result.confidence}")
        print(f"  Requires workflow: {result.requires_workflow}")
        
        if result.requires_workflow and result.confidence > 0.7:
            print_success("Analyse fonctionne correctement")
        else:
            print_warning(f"Analyse retourne confidence faible: {result.confidence}")
        
        return True
        
    except Exception as e:
        print_error(f"Erreur test analyse: {e}")
        import traceback
        traceback.print_exc()
        return False


async def correction_4_ajouter_logs():
    """CORRECTION 4: Suggérer l'ajout de logs."""
    print("\n" + "="*70)
    print("CORRECTION 4: Ajout de Logs de Debugging")
    print("="*70)
    
    print_info("Pour mieux diagnostiquer, ajoutez ce log au début de _handle_update_event:")
    print()
    print("Dans services/webhook_persistence_service.py, ligne ~186:")
    print()
    print("=" * 60)
    print("""
logger.info(f"🔔 WEBHOOK UPDATE REÇU: pulse_id={pulse_id}, "
           f"text='{update_text[:50]}...', webhook_id={webhook_id}")
""")
    print("=" * 60)
    print()
    print_warning("Ajoutez ce log manuellement puis redémarrez FastAPI")
    
    return None  # Pas de validation auto


async def correction_5_creer_test():
    """CORRECTION 5: Créer un script de test."""
    print("\n" + "="*70)
    print("CORRECTION 5: Création Script de Test")
    print("="*70)
    
    test_script = """#!/usr/bin/env python3
import asyncio
from services.webhook_persistence_service import webhook_persistence
from services.database_persistence_service import db_persistence

async def test_update_event():
    await db_persistence.initialize()
    
    # Simuler un webhook create_update
    payload = {
        "event": {
            "type": "create_update",
            "pulseId": 5039108740,  # REMPLACER par votre item ID
            "textBody": "Bonjour, pouvez-vous ajouter un export CSV ?",
            "updateId": "test_update_manual_001"
        }
    }
    
    print("🧪 Test simulation webhook update...")
    result = await webhook_persistence.process_monday_webhook(payload)
    
    print(f"\\n✅ Résultat: {result}")

if __name__ == "__main__":
    asyncio.run(test_update_event())
"""
    
    try:
        with open('test_update_manual.py', 'w') as f:
            f.write(test_script)
        
        print_success("Script de test créé: test_update_manual.py")
        print_info("Exécutez: python3 test_update_manual.py")
        return True
        
    except Exception as e:
        print_error(f"Erreur création script: {e}")
        return False


async def main():
    """Exécute toutes les corrections."""
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "CORRECTIONS SYSTÈME UPDATE WORKFLOW" + " "*19 + "║")
    print("╚" + "="*68 + "╝")
    
    results = []
    
    # Correction 1: Migration SQL
    result = await correction_1_verifier_migration()
    results.append(("Migration SQL", result))
    
    if result is False:
        print_error("\n⛔ Migration SQL manquante - ARRÊT")
        print_info("Appliquez d'abord: psql -f data/migration_task_update_triggers.sql")
        sys.exit(1)
    
    # Correction 2: Code
    result = await correction_2_verifier_code()
    results.append(("Code en place", result))
    
    if result is False:
        print_error("\n⛔ Code incomplet - Vérifiez l'implémentation")
        sys.exit(1)
    
    # Correction 3: Test analyse
    result = await correction_3_tester_analyse()
    results.append(("Analyse LLM", result))
    
    # Correction 4: Logs (suggestion)
    await correction_4_ajouter_logs()
    results.append(("Logs debugging", None))
    
    # Correction 5: Script test
    result = await correction_5_creer_test()
    results.append(("Script de test", result))
    
    # Résumé
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*26 + "RÉSUMÉ FINAL" + " "*30 + "║")
    print("╚" + "="*68 + "╝")
    print()
    
    for name, result in results:
        if result is True:
            print_success(f"{name}")
        elif result is False:
            print_error(f"{name}")
        else:
            print_info(f"{name} - Action manuelle requise")
    
    print()
    print("╔" + "="*68 + "╗")
    print("║" + " "*20 + "ACTIONS SUIVANTES REQUISES" + " "*22 + "║")
    print("╚" + "="*68 + "╝")
    print()
    print("1. Vérifier configuration webhook Monday.com:")
    print("   - Aller sur Monday.com → Integrations → Webhooks")
    print("   - Cocher: create_update et create_reply")
    print()
    print("2. Redémarrer FastAPI:")
    print("   - Ctrl+C sur le processus actuel")
    print("   - Relancer: uvicorn main:app --reload")
    print()
    print("3. Tester manuellement:")
    print("   - python3 test_update_manual.py")
    print("   - OU poster un commentaire dans Monday")
    print()
    print("4. Surveiller les logs:")
    print("   - tail -f logs/application.log | grep -E '(🔔|analyse|trigger)'")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Correction interrompue")
        sys.exit(1)
    except Exception as e:
        print_error(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

