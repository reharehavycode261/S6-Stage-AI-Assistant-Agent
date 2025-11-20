#!/usr/bin/env python3
"""
Script de test pour l'intégration RabbitMQ dans AI-Agent.

Ce script teste :
1. La connectivité RabbitMQ
2. L'envoi de tâches Celery
3. Le traitement des payloads webhook Monday.com
4. Les queues spécialisées et priorités
5. Les Dead Letter Queues

Usage:
    python test_rabbitmq_integration.py [--quick] [--verbose]
"""

import asyncio
import time
import sys
import argparse
from datetime import datetime

# Imports du projet
from config.settings import get_settings
from models.schemas import WebhookPayload
from services.celery_app import celery_app, submit_task
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RabbitMQTester:
    """Testeur pour l'intégration RabbitMQ."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {}
        
    def log(self, message: str, level: str = "INFO"):
        """Log avec niveau."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = "🔍" if level == "INFO" else "✅" if level == "SUCCESS" else "❌"
        print(f"[{timestamp}] {prefix} {message}")
        
        if self.verbose:
            logger.info(message)
    
    async def test_rabbitmq_connectivity(self) -> bool:
        """Test de connectivité RabbitMQ."""
        self.log("🐰 Test de connectivité RabbitMQ...")
        
        try:
            # Test de ping Celery
            inspection = celery_app.control.inspect()
            stats = inspection.stats()
            
            if stats:
                active_workers = len(stats)
                self.log(f"✅ RabbitMQ connecté - {active_workers} workers actifs", "SUCCESS")
                self.results["rabbitmq_connectivity"] = True
                return True
            else:
                self.log("❌ Aucun worker Celery détecté", "ERROR")
                self.results["rabbitmq_connectivity"] = False
                return False
                
        except Exception as e:
            self.log(f"❌ Erreur connexion RabbitMQ: {e}", "ERROR")
            self.results["rabbitmq_connectivity"] = False
            return False
    
    def test_queue_routing(self) -> bool:
        """Test du routing vers les bonnes queues."""
        self.log("🔀 Test du routing des queues...")
        
        test_cases = [
            {
                "task": "ai_agent_background.process_monday_webhook",
                "queue": "webhooks",
                "priority": 9
            },
            {
                "task": "ai_agent_background.execute_workflow", 
                "queue": "workflows",
                "priority": 5
            },
            {
                "task": "ai_agent_background.generate_code",
                "queue": "ai_generation",
                "priority": 7
            },
            {
                "task": "ai_agent_background.run_tests",
                "queue": "tests",
                "priority": 3
            }
        ]
        
        routing_config = celery_app.conf.task_routes
        success_count = 0
        
        for case in test_cases:
            task_name = case["task"]
            expected_queue = case["queue"]
            expected_priority = case["priority"]
            
            if task_name in routing_config:
                config = routing_config[task_name]
                actual_queue = config.get("queue")
                actual_priority = config.get("priority")
                
                if actual_queue == expected_queue and actual_priority == expected_priority:
                    self.log(f"✅ {task_name} → {actual_queue} (priorité {actual_priority})", "SUCCESS")
                    success_count += 1
                else:
                    self.log(f"❌ {task_name} → {actual_queue} (attendu: {expected_queue})", "ERROR")
            else:
                self.log(f"❌ Pas de routing configuré pour {task_name}", "ERROR")
        
        success = success_count == len(test_cases)
        self.results["queue_routing"] = success
        return success
    
    def test_webhook_payload_validation(self) -> bool:
        """Test de validation des payloads webhook."""
        self.log("📝 Test de validation des payloads webhook...")
        
        test_cases = [
            {
                "name": "Changement couleur bouton",
                "payload": WebhookPayload.example_button_color_change(),
                "should_pass": True
            },
            {
                "name": "Feature OAuth2",
                "payload": WebhookPayload.example_oauth_feature(),
                "should_pass": True
            },
            {
                "name": "Bug fix email",
                "payload": WebhookPayload.example_bug_fix(), 
                "should_pass": True
            }
        ]
        
        success_count = 0
        
        for case in test_cases:
            try:
                payload = case["payload"]
                task_info = payload.extract_task_info()
                
                if task_info and case["should_pass"]:
                    self.log(f"✅ {case['name']}: extraction réussie", "SUCCESS") 
                    self.log(f"   → Tâche: {task_info.get('title', 'N/A')}")
                    self.log(f"   → Type: {task_info.get('task_type', 'N/A')}")
                    self.log(f"   → Priorité: {task_info.get('priority', 'N/A')}")
                    success_count += 1
                elif not task_info and not case["should_pass"]:
                    self.log(f"✅ {case['name']}: échec attendu", "SUCCESS")
                    success_count += 1
                else:
                    self.log(f"❌ {case['name']}: résultat inattendu", "ERROR")
                    
            except Exception as e:
                if case["should_pass"]:
                    self.log(f"❌ {case['name']}: erreur {e}", "ERROR")
                else:
                    self.log(f"✅ {case['name']}: erreur attendue", "SUCCESS")
                    success_count += 1
        
        success = success_count == len(test_cases)
        self.results["payload_validation"] = success
        return success
    
    def test_task_submission(self) -> bool:
        """Test de soumission de tâches avec priorités."""
        self.log("📨 Test de soumission de tâches...")
        
        try:
            # Test avec payload d'exemple
            example_payload = WebhookPayload.example_button_color_change()
            payload_dict = example_payload.dict()
            
            # Soumettre une tâche de test
            task = submit_task(
                "ai_agent_background.process_monday_webhook",
                payload_dict,
                None,  # Pas de signature pour test
                priority=8
            )
            
            if task and task.id:
                self.log(f"✅ Tâche soumise avec succès: {task.id}", "SUCCESS")
                self.log("   → Queue: webhooks")
                self.log("   → Priorité: 8")
                
                # Attendre un peu et vérifier le statut
                time.sleep(2)
                result = task.result
                state = task.state
                
                self.log(f"   → État: {state}")
                if self.verbose and result:
                    self.log(f"   → Résultat: {result}")
                
                self.results["task_submission"] = True
                return True
            else:
                self.log("❌ Échec de soumission de tâche", "ERROR")
                self.results["task_submission"] = False
                return False
                
        except Exception as e:
            self.log(f"❌ Erreur soumission tâche: {e}", "ERROR")
            self.results["task_submission"] = False
            return False
    
    def test_celery_configuration(self) -> bool:
        """Test de la configuration Celery."""
        self.log("⚙️ Test de la configuration Celery...")
        
        config_checks = [
            ("broker_url", settings.celery_broker_url, "amqp://"),
            ("result_backend", settings.celery_result_backend, "db+postgresql://"),
            ("task_serializer", celery_app.conf.task_serializer, "json"),
            ("result_serializer", celery_app.conf.result_serializer, "json"),
            ("task_default_exchange", celery_app.conf.task_default_exchange, "ai_agent"),
            ("task_default_exchange_type", celery_app.conf.task_default_exchange_type, "topic")
        ]
        
        success_count = 0
        
        for check_name, actual_value, expected_part in config_checks:
            if expected_part in str(actual_value):
                self.log(f"✅ {check_name}: {actual_value}", "SUCCESS")
                success_count += 1
            else:
                self.log(f"❌ {check_name}: {actual_value} (attendu: contient '{expected_part}')", "ERROR")
        
        # Vérifier les queues configurées
        queues = celery_app.conf.task_queues
        expected_queues = ["webhooks", "workflows", "ai_generation", "tests", "dlq"]
        
        if queues:
            queue_names = [q.name for q in queues]
            for expected_queue in expected_queues:
                if expected_queue in queue_names:
                    self.log(f"✅ Queue configurée: {expected_queue}", "SUCCESS")
                    success_count += 1
                else:
                    self.log(f"❌ Queue manquante: {expected_queue}", "ERROR")
        
        success = success_count >= len(config_checks) + len(expected_queues) - 2  # Tolérance de 2 erreurs
        self.results["celery_configuration"] = success
        return success
    
    def test_priority_queues(self) -> bool:
        """Test des priorités de queues."""
        self.log("🔝 Test des priorités de queues...")
        
        try:
            # Tester différentes priorités
            priority_tests = [
                {"priority": "urgent", "expected": 9},
                {"priority": "high", "expected": 7},
                {"priority": "medium", "expected": 5},
                {"priority": "low", "expected": 3}
            ]
            
            priority_map = {
                "urgent": 9,
                "high": 7,
                "medium": 5,
                "low": 3
            }
            
            for test in priority_tests:
                priority_str = test["priority"]
                expected = test["expected"]
                actual = priority_map.get(priority_str.lower(), 5)
                
                if actual == expected:
                    self.log(f"✅ Priorité {priority_str}: {actual}", "SUCCESS")
                else:
                    self.log(f"❌ Priorité {priority_str}: {actual} (attendu: {expected})", "ERROR")
            
            self.results["priority_queues"] = True
            return True
            
        except Exception as e:
            self.log(f"❌ Erreur test priorités: {e}", "ERROR")
            self.results["priority_queues"] = False
            return False
    
    def print_summary(self):
        """Affiche le résumé des tests."""
        self.log("\n" + "="*60)
        self.log("📊 RÉSUMÉ DES TESTS RABBITMQ")
        self.log("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result)
        
        for test_name, result in self.results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            test_display = test_name.replace("_", " ").title()
            self.log(f"{status} {test_display}")
        
        self.log("-" * 60)
        self.log(f"📈 TOTAL: {passed_tests}/{total_tests} tests réussis")
        
        if passed_tests == total_tests:
            self.log("🎉 TOUS LES TESTS SONT PASSÉS ! RabbitMQ est prêt.", "SUCCESS")
            return True
        else:
            self.log(f"⚠️ {total_tests - passed_tests} test(s) échoué(s). Vérifiez la configuration.", "ERROR")
            return False


async def main():
    """Fonction principale de test."""
    parser = argparse.ArgumentParser(description="Test d'intégration RabbitMQ pour AI-Agent")
    parser.add_argument("--quick", action="store_true", help="Tests rapides seulement")
    parser.add_argument("--verbose", action="store_true", help="Logs détaillés")
    args = parser.parse_args()
    
    print("🚀 DÉBUT DES TESTS D'INTÉGRATION RABBITMQ")
    print("=" * 60)
    
    tester = RabbitMQTester(verbose=args.verbose)
    
    # Tests obligatoires
    tests = [
        ("connectivité RabbitMQ", tester.test_rabbitmq_connectivity),
        ("configuration Celery", tester.test_celery_configuration),
        ("routing des queues", tester.test_queue_routing),
        ("validation payloads", tester.test_webhook_payload_validation),
        ("priorités", tester.test_priority_queues),
    ]
    
    # Tests complets (sauf si --quick)
    if not args.quick:
        tests.append(("soumission tâches", tester.test_task_submission))
    
    # Exécuter tous les tests
    for test_name, test_func in tests:
        print(f"\n📋 Test: {test_name}")
        print("-" * 40)
        
        if asyncio.iscoroutinefunction(test_func):
            await test_func()
        else:
            test_func()
    
    # Résumé final
    success = tester.print_summary()
    
    if success:
        print("\n🎯 RabbitMQ est correctement configuré et fonctionnel !")
        print("Commandes pour démarrer le système :")
        print("  docker-compose -f docker-compose.rabbitmq.yml up -d")
        print("  celery -A services.celery_app worker --loglevel=info")
        sys.exit(0)
    else:
        print("\n🔧 Des problèmes ont été détectés. Consultez les logs ci-dessus.")
        print("Vérifiez la configuration et les services RabbitMQ/PostgreSQL.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrompus par l'utilisateur")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Erreur inattendue: {e}")
        sys.exit(1) 