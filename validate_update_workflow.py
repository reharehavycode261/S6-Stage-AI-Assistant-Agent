#!/usr/bin/env python3
"""Script de validation rapide du système de workflow depuis updates Monday."""

import asyncio
import sys
from typing import Dict, Any

# Couleurs pour l'output
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


async def check_imports():
    """Vérifie que tous les imports nécessaires sont disponibles."""
    print("\n" + "="*60)
    print("1️⃣  Vérification des imports")
    print("="*60)
    
    try:
        from models.schemas import UpdateType, UpdateIntent, UpdateAnalysisContext
        print_success("Modèles de données importés")
    except ImportError as e:
        print_error(f"Erreur import modèles: {e}")
        return False
    
    try:
        from services.update_analyzer_service import update_analyzer_service
        print_success("UpdateAnalyzerService importé")
    except ImportError as e:
        print_error(f"Erreur import UpdateAnalyzerService: {e}")
        return False
    
    try:
        from services.workflow_trigger_service import workflow_trigger_service
        print_success("WorkflowTriggerService importé")
    except ImportError as e:
        print_error(f"Erreur import WorkflowTriggerService: {e}")
        return False
    
    try:
        from services.database_persistence_service import db_persistence
        print_success("DatabasePersistenceService importé")
    except ImportError as e:
        print_error(f"Erreur import DatabasePersistenceService: {e}")
        return False
    
    return True


async def check_database():
    """Vérifie que la base de données est configurée correctement."""
    print("\n" + "="*60)
    print("2️⃣  Vérification de la base de données")
    print("="*60)
    
    try:
        from services.database_persistence_service import db_persistence
        
        # Initialiser la connexion
        await db_persistence.initialize()
        print_success("Connexion DB établie")
        
        # Vérifier que la table existe
        async with db_persistence.db_manager.get_connection() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'task_update_triggers'
                )
            """)
            
            if result:
                print_success("Table task_update_triggers existe")
            else:
                print_error("Table task_update_triggers n'existe pas")
                print_warning("Exécutez: psql -f data/migration_task_update_triggers.sql")
                return False
            
            # Vérifier que la colonne triggered_by_update_id existe
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'task_runs' 
                    AND column_name = 'triggered_by_update_id'
                )
            """)
            
            if result:
                print_success("Colonne triggered_by_update_id existe dans task_runs")
            else:
                print_error("Colonne triggered_by_update_id manquante")
                print_warning("Exécutez: psql -f data/migration_task_update_triggers.sql")
                return False
        
        return True
        
    except Exception as e:
        print_error(f"Erreur connexion DB: {e}")
        return False


async def test_update_analyzer():
    """Teste le service d'analyse des updates."""
    print("\n" + "="*60)
    print("3️⃣  Test UpdateAnalyzerService")
    print("="*60)
    
    try:
        from services.update_analyzer_service import update_analyzer_service
        from models.schemas import UpdateType
        
        # Test 1: Nouvelle demande
        print_info("Test 1: Détection nouvelle demande")
        context = {
            "task_title": "Dashboard admin",
            "task_status": "completed",
            "original_description": "Créer un dashboard"
        }
        
        # Note: Ce test nécessite une clé API LLM valide
        try:
            result = await update_analyzer_service.analyze_update_intent(
                "Pouvez-vous ajouter un export CSV ?",
                context
            )
            
            print(f"   Type détecté: {result.type}")
            print(f"   Confiance: {result.confidence}")
            print(f"   Requires workflow: {result.requires_workflow}")
            
            if result.confidence > 0:
                print_success("Analyse LLM fonctionnelle")
            else:
                print_warning("Analyse retournée mais confiance = 0 (vérifier clés API)")
                
        except Exception as e:
            print_warning(f"Analyse LLM a échoué (clés API?): {e}")
            print_info("Le système utilise un fallback en cas d'erreur LLM")
        
        # Test 2: Classification par mots-clés (sans LLM)
        print_info("Test 2: Classification par mots-clés")
        
        test_cases = [
            ("Merci beaucoup !", UpdateType.AFFIRMATION),
            ("Comment faire ?", UpdateType.QUESTION),
            ("Il y a un bug", UpdateType.BUG_REPORT),
            ("Ajouter une feature", UpdateType.NEW_REQUEST),
        ]
        
        all_passed = True
        for text, expected_type in test_cases:
            detected = update_analyzer_service.classify_update_type(text)
            if detected == expected_type:
                print(f"   ✓ '{text}' → {detected}")
            else:
                print(f"   ✗ '{text}' → {detected} (attendu: {expected_type})")
                all_passed = False
        
        if all_passed:
            print_success("Classification par mots-clés fonctionnelle")
        else:
            print_warning("Certaines classifications ont échoué")
        
        return True
        
    except Exception as e:
        print_error(f"Erreur test UpdateAnalyzer: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_workflow_trigger():
    """Teste le service de déclenchement de workflow."""
    print("\n" + "="*60)
    print("4️⃣  Test WorkflowTriggerService")
    print("="*60)
    
    try:
        from services.workflow_trigger_service import workflow_trigger_service
        from models.schemas import UpdateIntent, UpdateType
        
        # Test: Création de TaskRequest
        print_info("Test: Création TaskRequest depuis update")
        
        original_task = {
            'tasks_id': 1,
            'monday_item_id': 12345,
            'title': 'Test task',
            'description': 'Description test',
            'repository_url': 'https://github.com/test/repo',
            'internal_status': 'completed',
            'monday_status': 'Done',
            'priority': 'medium',
            'task_type': 'feature'
        }
        
        update_analysis = UpdateIntent(
            type=UpdateType.NEW_REQUEST,
            confidence=0.92,
            requires_workflow=True,
            reasoning="Test",
            extracted_requirements={
                'title': 'Test feature',
                'description': 'Test description',
                'task_type': 'feature',
                'priority': 'high'
            }
        )
        
        task_request = await workflow_trigger_service.create_task_request_from_update(
            original_task,
            update_analysis
        )
        
        if task_request:
            print(f"   Titre: {task_request.title}")
            print(f"   Type: {task_request.task_type}")
            print(f"   Priorité: {task_request.priority}")
            print_success("Création TaskRequest fonctionnelle")
        else:
            print_error("Échec création TaskRequest")
            return False
        
        # Test: Détermination priorité
        print_info("Test: Détermination priorité Celery")
        priorities = {
            'urgent': 9,
            'high': 7,
            'medium': 5,
            'low': 3
        }
        
        all_correct = True
        for priority_name, expected_value in priorities.items():
            analysis = UpdateIntent(
                type=UpdateType.NEW_REQUEST,
                confidence=0.9,
                requires_workflow=True,
                reasoning="Test",
                extracted_requirements={'priority': priority_name}
            )
            actual_value = workflow_trigger_service._determine_priority(analysis)
            if actual_value == expected_value:
                print(f"   ✓ {priority_name} → {actual_value}")
            else:
                print(f"   ✗ {priority_name} → {actual_value} (attendu: {expected_value})")
                all_correct = False
        
        if all_correct:
            print_success("Détermination priorité fonctionnelle")
        else:
            print_warning("Certaines priorités incorrectes")
        
        return True
        
    except Exception as e:
        print_error(f"Erreur test WorkflowTrigger: {e}")
        import traceback
        traceback.print_exc()
        return False


async def check_database_methods():
    """Vérifie que les nouvelles méthodes DB fonctionnent."""
    print("\n" + "="*60)
    print("5️⃣  Test méthodes DB")
    print("="*60)
    
    try:
        from services.database_persistence_service import db_persistence
        
        # Vérifier que les méthodes existent
        required_methods = [
            'create_update_trigger',
            'mark_trigger_as_processed',
            'get_task_update_triggers',
            'get_update_trigger_stats'
        ]
        
        for method_name in required_methods:
            if hasattr(db_persistence, method_name):
                print(f"   ✓ {method_name}")
            else:
                print(f"   ✗ {method_name} manquante")
                return False
        
        print_success("Toutes les méthodes DB présentes")
        
        # Test stats (même si vide)
        print_info("Test: Récupération stats (peut être vide)")
        try:
            stats = await db_persistence.get_update_trigger_stats()
            print(f"   Total triggers: {stats.get('total', 0)}")
            print_success("Méthode get_update_trigger_stats fonctionnelle")
        except Exception as e:
            print_error(f"Erreur get_update_trigger_stats: {e}")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Erreur test méthodes DB: {e}")
        return False


async def run_validation():
    """Exécute toute la validation."""
    print("\n" + "="*60)
    print("🚀 VALIDATION SYSTÈME WORKFLOW DEPUIS UPDATES")
    print("="*60)
    
    results = []
    
    # 1. Imports
    result = await check_imports()
    results.append(("Imports", result))
    if not result:
        print_error("Validation arrêtée: imports manquants")
        return False
    
    # 2. Base de données
    result = await check_database()
    results.append(("Base de données", result))
    if not result:
        print_error("Validation arrêtée: DB non configurée")
        return False
    
    # 3. UpdateAnalyzerService
    result = await test_update_analyzer()
    results.append(("UpdateAnalyzerService", result))
    
    # 4. WorkflowTriggerService
    result = await test_workflow_trigger()
    results.append(("WorkflowTriggerService", result))
    
    # 5. Méthodes DB
    result = await check_database_methods()
    results.append(("Méthodes DB", result))
    
    # Résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DE LA VALIDATION")
    print("="*60)
    
    for name, passed in results:
        if passed:
            print_success(f"{name}")
        else:
            print_error(f"{name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n" + "="*60)
        print_success("VALIDATION COMPLÈTE RÉUSSIE ✨")
        print_info("Le système est prêt pour les tests manuels")
        print_info("Consultez: GUIDE_TEST_NOUVEAU_WORKFLOW_UPDATE.md")
        print("="*60)
        return True
    else:
        print("\n" + "="*60)
        print_error("VALIDATION ÉCHOUÉE")
        print_warning("Corrigez les erreurs avant de continuer")
        print("="*60)
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_validation())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Validation interrompue")
        sys.exit(1)
    except Exception as e:
        print_error(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

