"""
Tests d'intégration LangSmith pour le projet AI-Agent.
"""

import os
import asyncio
from datetime import datetime
from models.schemas import TaskRequest, TaskType
from models.state import GraphState
from config.langsmith_config import langsmith_config
from utils.langsmith_tracing import workflow_tracer
from utils.logger import get_logger

logger = get_logger(__name__)


async def test_langsmith_config():
    """Tester la configuration LangSmith."""
    print("🧪 TEST CONFIGURATION LANGSMITH")
    print("=" * 40)
    
    # Vérifier les variables d'environnement
    api_key = os.getenv("LANGSMITH_API_KEY")
    project = os.getenv("LANGSMITH_PROJECT", "ai-agent-production")
    
    print("📋 Configuration:")
    print(f"   API Key: {'✅ Configurée' if api_key else '❌ Manquante'}")
    print(f"   Project: {project}")
    print(f"   Tracing: {langsmith_config.tracing_enabled}")
    print(f"   Endpoint: {langsmith_config.endpoint}")
    
    # Tester l'initialisation du client
    print("\n🔧 Test client:")
    if langsmith_config.is_configured:
        client = langsmith_config.client
        if client:
            print("   ✅ Client LangSmith initialisé avec succès")
        else:
            print("   ❌ Erreur initialisation client")
    else:
        print("   ⚠️ LangSmith non configuré (normal si pas d'API key)")
    
    return langsmith_config.is_configured


async def test_workflow_tracing():
    """Tester le tracing d'un workflow simulé."""
    print("\n🚀 TEST TRACING WORKFLOW")
    print("=" * 40)
    
    # Créer un état de workflow de test
    test_state: GraphState = {
        "workflow_id": "test_langsmith_123",
        "status": "processing",
        "current_node": "test_node",
        "completed_nodes": [],
        "task": TaskRequest(
            task_id="test_123",
            title="Test LangSmith Integration",
            description="Test d'intégration LangSmith",
            task_type=TaskType.FEATURE,
            repository_url="https://github.com/test/repo.git"
        ),
        "results": {},
        "error": None,
        "started_at": datetime.now(),
        "langsmith_session": "test_session_123"
    }
    
    try:
        # Test trace workflow start
        print("📍 Test trace_workflow_start...")
        workflow_tracer.trace_workflow_start(test_state)
        print("   ✅ Trace workflow start réussie")
        
        # Test trace node execution
        print("📍 Test trace_node_execution...")
        workflow_tracer.trace_node_execution(
            test_state,
            "test_node",
            {"input": "test_input"},
            {"output": "test_output", "success": True}
        )
        print("   ✅ Trace node execution réussie")
        
        # Test trace business event
        print("📍 Test trace_business_event...")
        workflow_tracer.trace_business_event(
            test_state,
            "test_event",
            {"metric": "test_value", "count": 42}
        )
        print("   ✅ Trace business event réussie")
        
        # Test trace test execution
        print("📍 Test trace_test_execution...")
        workflow_tracer.trace_test_execution(test_state, {
            "test_type": "unit",
            "success": True,
            "tests_run": 10,
            "tests_passed": 8,
            "tests_failed": 2,
            "execution_time": 5.2
        })
        print("   ✅ Trace test execution réussie")
        
        # Test trace workflow completion
        print("📍 Test trace_workflow_completion...")
        test_state["completed_at"] = datetime.now()
        workflow_tracer.trace_workflow_completion(test_state, {
            "success": True,
            "files_modified": ["test1.py", "test2.py"],
            "pull_request_url": "https://github.com/test/repo/pull/123"
        })
        print("   ✅ Trace workflow completion réussie")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur tracing: {e}")
        return False


async def test_ai_tools_tracing():
    """Tester le tracing des outils IA (simulation)."""
    print("\n🤖 TEST TRACING OUTILS IA")
    print("=" * 40)
    
    try:
        # Simuler un appel Claude (sans vraiment appeler l'API)
        print("📍 Test simulation tracing Claude...")
        
        if langsmith_config.client:
            langsmith_config.client.create_run(
                name="test_claude_simulation",
                run_type="llm",
                inputs={
                    "prompt": "Test prompt for LangSmith integration",
                    "model": "claude-3-5-sonnet-20241022"
                },
                outputs={
                    "content": "Test response from Claude",
                    "tokens_used": 150,
                    "estimated_cost": 0.002
                },
                session_name="test_session_123",
                extra={
                    "provider": "claude",
                    "test_mode": True
                }
            )
            print("   ✅ Simulation tracing Claude réussie")
        else:
            print("   ⚠️ Client LangSmith non disponible (simulation skippée)")
        
        # Simuler un appel GitHub
        print("📍 Test simulation tracing GitHub...")
        
        if langsmith_config.client:
            langsmith_config.client.create_run(
                name="test_github_simulation",
                run_type="tool",
                inputs={
                    "operation": "create_pull_request",
                    "repo": "test/repo",
                    "title": "Test PR"
                },
                outputs={
                    "success": True,
                    "pr_number": 123,
                    "pr_url": "https://github.com/test/repo/pull/123"
                },
                session_name="test_session_123",
                extra={
                    "tool": "github",
                    "test_mode": True
                }
            )
            print("   ✅ Simulation tracing GitHub réussie")
        else:
            print("   ⚠️ Client LangSmith non disponible (simulation skippée)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erreur simulation tracing: {e}")
        return False


async def main():
    """Fonction principale de test."""
    print("🔬 TESTS D'INTÉGRATION LANGSMITH")
    print("=" * 50)
    
    # Setup environment
    langsmith_config.setup_environment()
    
    results = []
    
    # Test 1: Configuration
    config_ok = await test_langsmith_config()
    results.append(("Configuration", config_ok))
    
    # Test 2: Workflow tracing
    workflow_ok = await test_workflow_tracing()
    results.append(("Workflow Tracing", workflow_ok))
    
    # Test 3: AI tools tracing
    tools_ok = await test_ai_tools_tracing()
    results.append(("AI Tools Tracing", tools_ok))
    
    # Résumé
    print("\n📊 RÉSUMÉ DES TESTS")
    print("=" * 30)
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {test_name:20} {status}")
        if not success:
            all_passed = False
    
    print(f"\n🎯 RÉSULTAT GLOBAL: {'✅ TOUS LES TESTS PASSÉS' if all_passed else '❌ CERTAINS TESTS ÉCHOUÉS'}")
    
    if langsmith_config.is_configured:
        print(f"\n🔗 Consultez vos traces sur: https://smith.langchain.com/projects/{langsmith_config.project}")
    else:
        print("\n💡 Pour activer LangSmith:")
        print("   1. Obtenez une API key sur https://smith.langchain.com")
        print("   2. Ajoutez LANGSMITH_API_KEY=your_key dans votre .env")
        print("   3. Redémarrez l'application")
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(main()) 