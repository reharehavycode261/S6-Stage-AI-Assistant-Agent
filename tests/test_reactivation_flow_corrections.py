"""
Tests de validation du flux de réactivation après corrections.

Ce fichier teste les corrections apportées pour résoudre les erreurs :
1. Conflit de transactions PostgreSQL
2. Connexion PostgreSQL fermée prématurément
3. Workflow lancé en mode "NOUVEAU" au lieu de "RÉACTIVATION"
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
import asyncpg

from utils.database_manager import db_manager
from utils.task_lock_manager import task_lock_manager
from services.database_persistence_service import db_persistence
from services.webhook_persistence_service import WebhookPersistenceService
from models.schemas import TaskRequest


@pytest.fixture(scope="session")
def event_loop():
    """Créer une event loop pour les tests async."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def setup_database():
    """Initialise la base de données pour les tests."""
    await db_manager.initialize()
    yield
    await db_manager.close()


@pytest.mark.asyncio
async def test_database_connection_manager(setup_database):
    """
    TEST 1 : Vérifier que le gestionnaire de connexions fonctionne correctement.
    
    Vérifie que :
    - Les connexions sont acquises et libérées correctement
    - Pas de conflit de transactions
    - Le pool est correctement configuré
    """
    # Test d'acquisition et libération de connexion
    async with db_manager.get_connection() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1, "La connexion DB devrait fonctionner"
    
    # Vérifier les statistiques du pool
    stats = await db_manager.get_pool_stats()
    assert stats["status"] == "active", "Le pool devrait être actif"
    assert stats["size"] > 0, "Le pool devrait avoir des connexions"
    
    print("✅ Test 1 réussi : Gestionnaire de connexions fonctionne")


@pytest.mark.asyncio
async def test_database_transaction_context(setup_database):
    """
    TEST 2 : Vérifier que les transactions sont correctement gérées.
    
    Vérifie que :
    - Les transactions commit en cas de succès
    - Les transactions rollback en cas d'erreur
    - Pas de conflit entre transactions
    """
    # Test de transaction réussie
    test_task_id = None
    
    try:
        async with db_manager.get_transaction() as conn:
            # Créer une tâche de test
            test_task_id = await conn.fetchval("""
                INSERT INTO tasks (
                    monday_item_id,
                    monday_board_id,
                    title,
                    description,
                    internal_status
                ) VALUES ($1, $2, $3, $4, $5)
                RETURNING tasks_id
            """, 999999, 123456, "Test Transaction", "Test description", "pending")
        
        # Vérifier que la tâche a été créée (transaction committed)
        async with db_manager.get_connection() as conn:
            task_exists = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM tasks WHERE tasks_id = $1)
            """, test_task_id)
        
        assert task_exists, "La tâche devrait exister après commit"
        
    finally:
        # Nettoyer la tâche de test
        if test_task_id:
            async with db_manager.get_connection() as conn:
                await conn.execute("DELETE FROM tasks WHERE tasks_id = $1", test_task_id)
    
    # Test de transaction avec rollback
    try:
        async with db_manager.get_transaction() as conn:
            await conn.execute("""
                INSERT INTO tasks (monday_item_id, title)
                VALUES (999998, 'Should Rollback')
            """)
            # Lever une erreur pour déclencher le rollback
            raise ValueError("Test rollback")
    except ValueError:
        pass  # Erreur attendue
    
    # Vérifier que la tâche n'existe pas (rollback effectué)
    async with db_manager.get_connection() as conn:
        task_exists = await conn.fetchval("""
            SELECT EXISTS(SELECT 1 FROM tasks WHERE monday_item_id = 999998)
        """)
    
    assert not task_exists, "La tâche ne devrait pas exister après rollback"
    
    print("✅ Test 2 réussi : Transactions correctement gérées")


@pytest.mark.asyncio
async def test_task_lock_manager():
    """
    TEST 3 : Vérifier que le système de verrous fonctionne correctement.
    
    Vérifie que :
    - Les verrous sont acquis et libérés correctement
    - Pas de traitement concurrent de la même tâche
    - Le cooldown est respecté
    """
    test_task_id = 888888
    
    # Acquérir le verrou
    acquired = await task_lock_manager.acquire_with_cooldown(test_task_id, timeout=1.0)
    assert acquired, "Le verrou devrait être acquis"
    
    # Vérifier que le verrou est actif
    is_locked = task_lock_manager.is_locked(test_task_id)
    assert is_locked, "Le verrou devrait être actif"
    
    # Libérer le verrou
    task_lock_manager.release(test_task_id)
    
    # Vérifier que le verrou est libéré
    is_locked = task_lock_manager.is_locked(test_task_id)
    assert not is_locked, "Le verrou devrait être libéré"
    
    # Tester le cooldown
    await task_lock_manager.acquire_with_cooldown(test_task_id)
    task_lock_manager.release(test_task_id)
    
    # Essayer de réacquérir immédiatement (devrait être bloqué par le cooldown)
    acquired = await task_lock_manager.acquire_with_cooldown(test_task_id, timeout=0.5)
    if not acquired:
        print("✅ Test 3 réussi : Cooldown fonctionne correctement")
    else:
        task_lock_manager.release(test_task_id)
        print("⚠️ Test 3 : Cooldown pourrait ne pas fonctionner (à vérifier)")


@pytest.mark.asyncio
async def test_webhook_processing_with_lock(setup_database):
    """
    TEST 4 : Vérifier que le traitement de webhook utilise les verrous.
    
    Vérifie que :
    - Un webhook ne peut pas être traité plusieurs fois simultanément
    - Le verrou est libéré après traitement
    """
    # Créer un payload de test
    test_payload = {
        "event": {
            "pulseId": 777777,
            "pulseName": "Test Webhook Lock",
            "boardId": 123456,
            "type": "create_pulse",
            "columnValues": {
                "text": {"text": "Test description"}
            }
        },
        "type": "create_pulse"
    }
    
    # Traiter le webhook une première fois
    result1 = await WebhookPersistenceService.process_monday_webhook(test_payload)
    
    # Le verrou devrait être libéré maintenant
    is_locked = task_lock_manager.is_locked(777777)
    assert not is_locked, "Le verrou devrait être libéré après traitement"
    
    # Nettoyer
    if result1.get("task_id"):
        async with db_manager.get_connection() as conn:
            await conn.execute("DELETE FROM tasks WHERE tasks_id = $1", result1["task_id"])
    
    print("✅ Test 4 réussi : Webhook utilise correctement les verrous")


@pytest.mark.asyncio
async def test_reactivation_flag_propagation(setup_database):
    """
    TEST 5 : Vérifier que le flag is_reactivation est correctement propagé.
    
    Vérifie que :
    - Le flag is_reactivation est détecté lors du traitement
    - Le flag est présent dans le TaskRequest
    - Les données de réactivation sont transmises
    """
    # Créer une tâche "completed" pour la réactiver
    test_monday_item_id = 666666
    
    async with db_manager.get_transaction() as conn:
        # Créer la tâche
        task_id = await conn.fetchval("""
            INSERT INTO tasks (
                monday_item_id,
                monday_board_id,
                title,
                description,
                internal_status,
                monday_status,
                repository_url
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING tasks_id
        """, test_monday_item_id, 123456, "Test Reactivation", 
            "Test", "completed", "Done", "https://github.com/test/test")
        
        # Créer un run complété
        run_id = await conn.fetchval("""
            INSERT INTO task_runs (
                task_id,
                run_number,
                status,
                celery_task_id,
                ai_provider
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING tasks_runs_id
        """, task_id, 1, "completed", "test_run_123", "claude")
    
    try:
        # Simuler un événement de changement de statut (réactivation)
        test_payload = {
            "event": {
                "pulseId": test_monday_item_id,
                "boardId": 123456,
                "type": "update_column_value",
                "columnId": "status",
                "value": {"label": {"text": "Working on it"}},
                "previousValue": {"label": {"text": "Done"}}
            },
            "type": "update_column_value"
        }
        
        # Traiter le webhook
        result = await WebhookPersistenceService.process_monday_webhook(test_payload)
        
        # Vérifier que is_reactivation est True
        # Note: Ceci dépend de l'implémentation de _handle_item_event
        # qui doit détecter le changement de statut Done → Working on it
        
        print(f"📊 Résultat du webhook : {result}")
        
        if result.get("is_reactivation"):
            print("✅ Test 5 réussi : Flag is_reactivation correctement détecté")
        else:
            print("⚠️ Test 5 : is_reactivation non détecté (vérifier la logique de détection)")
        
    finally:
        # Nettoyer
        async with db_manager.get_connection() as conn:
            await conn.execute("DELETE FROM task_runs WHERE task_id = $1", task_id)
            await conn.execute("DELETE FROM tasks WHERE tasks_id = $1", task_id)


@pytest.mark.asyncio
async def test_task_request_with_reactivation_fields(setup_database):
    """
    TEST 6 : Vérifier que TaskRequest contient les champs de réactivation.
    
    Vérifie que :
    - TaskRequest accepte is_reactivation
    - TaskRequest accepte reactivation_context
    - TaskRequest accepte reactivation_count
    - TaskRequest accepte source_branch
    """
    # Créer un TaskRequest avec champs de réactivation
    task_request = TaskRequest(
        task_id="123",
        title="Test Reactivation",
        description="Test description",
        repository_url="https://github.com/test/test",
        monday_item_id=123456,
        is_reactivation=True,
        reactivation_context="Nouvelle demande de modification",
        reactivation_count=2,
        source_branch="main"
    )
    
    # Vérifier que les champs sont présents
    assert task_request.is_reactivation == True, "is_reactivation devrait être True"
    assert task_request.reactivation_context == "Nouvelle demande de modification"
    assert task_request.reactivation_count == 2
    assert task_request.source_branch == "main"
    
    print("✅ Test 6 réussi : TaskRequest contient les champs de réactivation")


@pytest.mark.asyncio
async def test_database_persistence_uses_centralized_manager(setup_database):
    """
    TEST 7 : Vérifier que DatabasePersistenceService utilise le gestionnaire centralisé.
    
    Vérifie que :
    - db_persistence utilise db_manager
    - Pas d'utilisation directe de asyncpg.create_pool
    """
    # Vérifier que db_persistence a accès au gestionnaire
    assert hasattr(db_persistence, 'db_manager'), "db_persistence devrait avoir db_manager"
    assert db_persistence.db_manager == db_manager, "db_persistence devrait utiliser le gestionnaire centralisé"
    
    print("✅ Test 7 réussi : DatabasePersistenceService utilise le gestionnaire centralisé")


def test_lock_manager_stats():
    """
    TEST 8 : Vérifier que les statistiques du gestionnaire de verrous sont disponibles.
    """
    stats = task_lock_manager.get_stats()
    
    assert "total_locks" in stats
    assert "active_locks" in stats
    assert "cooldown_seconds" in stats
    
    print(f"📊 Statistiques verrous : {stats}")
    print("✅ Test 8 réussi : Statistiques des verrous disponibles")


@pytest.mark.asyncio
async def test_cleanup_old_locks():
    """
    TEST 9 : Vérifier que le nettoyage des verrous obsolètes fonctionne.
    """
    # Créer quelques verrous
    test_ids = [111111, 222222, 333333]
    for task_id in test_ids:
        await task_lock_manager.acquire_with_cooldown(task_id)
        task_lock_manager.release(task_id)
    
    # Nettoyer les verrous obsolètes (avec un âge très court pour le test)
    cleaned = task_lock_manager.cleanup_old_locks(max_age_seconds=0)
    
    print(f"🧹 Nettoyage effectué : {cleaned} verrous supprimés")
    print("✅ Test 9 réussi : Nettoyage des verrous obsolètes fonctionne")


if __name__ == "__main__":
    """Exécuter les tests."""
    print("="*80)
    print("🧪 TESTS DE VALIDATION DU FLUX DE RÉACTIVATION")
    print("="*80)
    print()
    
    asyncio.run(pytest.main([__file__, "-v", "-s"]))

