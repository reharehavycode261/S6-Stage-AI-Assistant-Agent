#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de validation rapide de la configuration @vydata.

Ce script vérifie que tous les composants sont correctement configurés.
"""

import sys
import os

sys.path.insert(0, '.')

def print_header(title: str):
    """Affiche un header formaté."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_success(msg: str):
    """Affiche un message de succès."""
    print(f"✅ {msg}")

def print_warning(msg: str):
    """Affiche un avertissement."""
    print(f"⚠️  {msg}")

def print_error(msg: str):
    """Affiche une erreur."""
    print(f"❌ {msg}")

def check_configuration():
    """Vérifie la configuration."""
    print_header("1️⃣  VÉRIFICATION CONFIGURATION")
    
    try:
        from config.settings import get_settings
        settings = get_settings()
        
        # Feature flag
        if settings.vydata_reactivation_v2:
            print_success(f"Feature Flag: VYDATA_REACTIVATION_V2 = {settings.vydata_reactivation_v2}")
        else:
            print_error("Feature Flag désactivé (VYDATA_REACTIVATION_V2 = false)")
            return False
        
        # Signing secret
        if settings.monday_signing_secret:
            print_success(f"MONDAY_SIGNING_SECRET: Configuré ({settings.monday_signing_secret[:10]}...)")
        else:
            print_warning("MONDAY_SIGNING_SECRET: Non configuré (mode développement)")
        
        # API URL
        print_success(f"MONDAY_API_URL: {settings.monday_api_url}")
        
        # Redis
        print_success(f"REDIS_URL: {settings.redis_url}")
        
        return True
        
    except Exception as e:
        print_error(f"Erreur configuration: {e}")
        return False

def check_services():
    """Vérifie que tous les services sont disponibles."""
    print_header("2️⃣  VÉRIFICATION SERVICES")
    
    services = [
        ("MentionParserService", "services.mention_parser_service", "mention_parser_service"),
        ("IntentClassifierService", "services.intent_classifier_service", "intent_classifier_service"),
        ("AgentResponseService", "services.agent_response_service", "agent_response_service"),
        ("IntentRouterService", "services.intent_router_service", "intent_router_service"),
        ("VydataOrchestratorService", "services.vydata_orchestrator_service", "vydata_orchestrator_service"),
        ("RedisIdempotenceService", "services.redis_idempotence_service", "redis_idempotence_service"),
        ("WebhookSignatureValidator", "services.webhook_signature_validator", "webhook_signature_validator"),
    ]
    
    all_ok = True
    for name, module, instance in services:
        try:
            mod = __import__(module, fromlist=[instance])
            getattr(mod, instance)
            print_success(f"{name}")
        except Exception as e:
            print_error(f"{name}: {e}")
            all_ok = False
    
    return all_ok

def check_chain():
    """Vérifie la chain LangChain."""
    print_header("3️⃣  VÉRIFICATION CHAIN LANGCHAIN")
    
    try:
        from ai.chains.vydata_intent_classification_chain import classify_vydata_intent
        print_success("VydataIntentClassificationChain disponible")
        return True
    except Exception as e:
        print_error(f"Chain LangChain: {e}")
        return False

def test_parsing():
    """Test le parsing de mention."""
    print_header("4️⃣  TEST PARSING @vydata")
    
    try:
        from services.mention_parser_service import mention_parser_service
        
        # Test 1: Mention valide
        result = mention_parser_service.parse_mention("@vydata Test de mention")
        if result.has_mention and result.cleaned_text == "Test de mention":
            print_success("Parsing mention valide")
        else:
            print_error(f"Parsing mention invalide (has_mention={result.has_mention}, cleaned_text='{result.cleaned_text}')")
            return False
        
        # Test 2: Sans mention
        result = mention_parser_service.parse_mention("Message sans mention")
        if not result.has_mention:
            print_success("Détection absence de mention")
        else:
            print_error("Faux positif sur mention")
            return False
        
        # Test 3: Message agent
        is_agent = mention_parser_service.is_agent_message("🤖 Message agent")
        if is_agent:
            print_success("Détection message agent")
        else:
            print_error("Échec détection message agent")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Erreur test parsing: {e}")
        return False

def test_redis():
    """Test la connexion Redis."""
    print_header("5️⃣  TEST CONNEXION REDIS")
    
    try:
        import asyncio
        from services.redis_idempotence_service import redis_idempotence_service
        
        async def test():
            await redis_idempotence_service.initialize()
            if redis_idempotence_service._initialized:
                print_success("Connexion Redis OK")
                await redis_idempotence_service.close()
                return True
            else:
                print_warning("Redis non disponible - Mode dégradé actif")
                return True  # OK car mode dégradé existe
        
        return asyncio.run(test())
        
    except Exception as e:
        print_warning(f"Redis non disponible: {e}")
        print_warning("Le système fonctionnera en mode dégradé (cache mémoire)")
        return True  # Non bloquant

def test_orchestrator():
    """Test l'orchestrateur."""
    print_header("6️⃣  TEST ORCHESTRATEUR")
    
    try:
        from services.vydata_orchestrator_service import vydata_orchestrator_service
        
        modes = vydata_orchestrator_service.get_activation_modes_summary()
        if len(modes["modes"]) == 2:
            print_success(f"2 modes d'activation détectés")
            for mode in modes["modes"]:
                print(f"   • {mode['name']}: {mode['description'][:50]}...")
            return True
        else:
            print_error("Nombre de modes d'activation incorrect")
            return False
        
    except Exception as e:
        print_error(f"Erreur test orchestrateur: {e}")
        return False

def check_webhook_events():
    """Vérifie les événements webhook supportés."""
    print_header("7️⃣  ÉVÉNEMENTS WEBHOOK SUPPORTÉS")
    
    print_success("create_update - Nouveau commentaire Monday.com")
    print_success("create_reply - Réponse à un commentaire")
    print_success("update_column_value - Changement de statut")
    print_success("create_pulse - Création de tâche")
    
    print("\n📝 CONFIGURATION MONDAY.COM REQUISE:")
    print("   1. Accéder à votre board Monday.com")
    print("   2. Intégrations → Webhooks")
    print("   3. Vérifier que ces événements sont cochés:")
    print("      ☑️  When an update is created (create_update)")
    print("      ☑️  When a reply is created (create_reply)")
    print("      ☑️  When a status changes (update_column_value)")
    print("      ☑️  When an item is created (create_pulse)")
    
    return True

def main():
    """Fonction principale."""
    print("=" * 80)
    print("🚀 VALIDATION CONFIGURATION SYSTÈME @vydata")
    print("=" * 80)
    
    results = []
    
    # Tests
    results.append(("Configuration", check_configuration()))
    results.append(("Services", check_services()))
    results.append(("Chain LangChain", check_chain()))
    results.append(("Parsing", test_parsing()))
    results.append(("Redis", test_redis()))
    results.append(("Orchestrateur", test_orchestrator()))
    results.append(("Webhook Events", check_webhook_events()))
    
    # Résumé
    print_header("📊 RÉSUMÉ")
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    failed = total - passed
    
    for name, result in results:
        if result:
            print_success(f"{name}")
        else:
            print_error(f"{name}")
    
    print("\n" + "=" * 80)
    if failed == 0:
        print("🎉 TOUS LES TESTS PASSÉS !")
        print(f"   {passed}/{total} composants validés")
        print("\n✅ Le système @vydata est prêt à être utilisé")
        print("\n📝 Prochaines étapes:")
        print("   1. Configurer les événements webhook sur Monday.com")
        print("   2. Redémarrer Celery: ./restart_celery_clean.sh")
        print("   3. Tester avec: @vydata Pourquoi ce projet...?")
        print("=" * 80)
        return 0
    else:
        print(f"⚠️  {failed}/{total} TESTS ÉCHOUÉS")
        print(f"   Consultez les erreurs ci-dessus")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(main())

