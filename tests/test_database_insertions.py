# -*- coding: utf-8 -*-
"""
Script de test pour valider les insertions dans toutes les tables de la base de données.
"""

from __future__ import annotations

import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import get_settings
from services.database_persistence_service import db_persistence
from services.human_validation_service import HumanValidationService
from services.system_config_service import system_config_service
from models.schemas import HumanValidationRequest, HumanValidationResponse, HumanValidationStatus
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseInsertionTester:
    """Testeur pour valider les insertions dans toutes les tables."""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_pool = None  # type: Optional[asyncpg.Pool]
        self.test_results = {}
        self.test_ids = {}  # Pour stocker les IDs créés pendant les tests
    
    async def initialize(self):
        """Initialise les connexions aux services."""
        logger.info("🔧 Initialisation des services...")
        
        # Initialiser le pool de base de données principal
        self.db_pool = await asyncpg.create_pool(
            self.settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        
        # Initialiser les services
        await db_persistence.initialize()
        
        logger.info("✅ Services initialisés")
    
    async def cleanup(self):
        """Nettoie les connexions."""
        if self.db_pool:
            await self.db_pool.close()
        await db_persistence.close()
        logger.info("🧹 Nettoyage terminé")
    
    async def test_tasks_table(self) -> bool:
        """Teste l'insertion dans la table tasks."""
        logger.info("📋 Test: table tasks")
        try:
            test_payload = {
                "pulseId": 999888777,
                "boardId": 123456,
                "pulseName": "Test Task - Database Insertion",
                "columnValues": {
                    "description": {"text": "Test de création de tâche"},
                    "priority": {"text": "high"},
                    "repository_url": {"text": "https://github.com/test/repo"}
                }
            }
            
            task_id = await db_persistence.create_task_from_monday(test_payload)
            self.test_ids['task_id'] = task_id
            
            if task_id:
                logger.info(f"✅ tasks: Task créée avec ID {task_id}")
                self.test_results['tasks'] = True
                return True
            else:
                logger.error("❌ tasks: Échec création task")
                self.test_results['tasks'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ tasks: Exception - {e}")
            self.test_results['tasks'] = False
            return False
    
    async def test_task_runs_table(self) -> bool:
        """Teste l'insertion dans la table task_runs."""
        logger.info("📋 Test: table task_runs")
        try:
            task_id = self.test_ids.get('task_id')
            if not task_id:
                logger.warning("⚠️ task_runs: Pas de task_id disponible, création d'une task")
                await self.test_tasks_table()
                task_id = self.test_ids.get('task_id')
            
            run_id = await db_persistence.start_task_run(
                task_id=task_id,
                celery_task_id=f"test_celery_{datetime.now().timestamp()}",
                ai_provider="claude"
            )
            self.test_ids['run_id'] = run_id
            
            if run_id:
                logger.info(f"✅ task_runs: Run créé avec ID {run_id}")
                self.test_results['task_runs'] = True
                return True
            else:
                logger.error("❌ task_runs: Échec création run")
                self.test_results['task_runs'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ task_runs: Exception - {e}")
            self.test_results['task_runs'] = False
            return False
    
    async def test_run_steps_table(self) -> bool:
        """Teste l'insertion dans la table run_steps."""
        logger.info("📋 Test: table run_steps")
        try:
            run_id = self.test_ids.get('run_id')
            if not run_id:
                logger.warning("⚠️ run_steps: Pas de run_id disponible, création d'un run")
                await self.test_task_runs_table()
                run_id = self.test_ids.get('run_id')
            
            step_id = await db_persistence.create_run_step(
                task_run_id=run_id,
                node_name="test_node",
                step_order=1,
                input_data={"test": "data"}
            )
            self.test_ids['step_id'] = step_id
            
            if step_id:
                # Compléter le step
                await db_persistence.complete_run_step(
                    step_id=step_id,
                    status="completed",
                    output_data={"result": "success"}
                )
                logger.info(f"✅ run_steps: Step créé et complété avec ID {step_id}")
                self.test_results['run_steps'] = True
                return True
            else:
                logger.error("❌ run_steps: Échec création step")
                self.test_results['run_steps'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ run_steps: Exception - {e}")
            self.test_results['run_steps'] = False
            return False
    
    async def test_ai_interactions_table(self) -> bool:
        """Teste l'insertion dans la table ai_interactions."""
        logger.info("📋 Test: table ai_interactions")
        try:
            step_id = self.test_ids.get('step_id')
            if not step_id:
                logger.warning("⚠️ ai_interactions: Pas de step_id disponible, création d'un step")
                await self.test_run_steps_table()
                step_id = self.test_ids.get('step_id')
            
            interaction_id = await db_persistence.log_ai_interaction(
                run_step_id=step_id,
                ai_provider="claude",
                model="claude-3-5-sonnet-20241022",
                prompt="Test prompt",
                response="Test response",
                token_usage={"prompt_tokens": 10, "completion_tokens": 20},
                latency_ms=1500
            )
            
            if interaction_id:
                logger.info(f"✅ ai_interactions: Interaction créée avec ID {interaction_id}")
                self.test_results['ai_interactions'] = True
                return True
            else:
                logger.error("❌ ai_interactions: Échec création interaction")
                self.test_results['ai_interactions'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ ai_interactions: Exception - {e}")
            self.test_results['ai_interactions'] = False
            return False
    
    async def test_ai_code_generations_table(self) -> bool:
        """Teste l'insertion dans la table ai_code_generations."""
        logger.info("📋 Test: table ai_code_generations")
        try:
            run_id = self.test_ids.get('run_id')
            if not run_id:
                logger.warning("⚠️ ai_code_generations: Pas de run_id disponible, création d'un run")
                await self.test_task_runs_table()
                run_id = self.test_ids.get('run_id')
            
            gen_id = await db_persistence.log_code_generation(
                task_run_id=run_id,
                provider="claude",
                model="claude-3-5-sonnet-20241022",
                generation_type="initial",
                prompt="Generate a hello world function",
                generated_code="def hello(): print('Hello World')",
                tokens_used=50,
                response_time_ms=2000,
                cost_estimate=0.002,
                files_modified=["test.py"]
            )
            
            if gen_id:
                logger.info(f"✅ ai_code_generations: Génération créée avec ID {gen_id}")
                self.test_results['ai_code_generations'] = True
                return True
            else:
                logger.error("❌ ai_code_generations: Échec création génération")
                self.test_results['ai_code_generations'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ ai_code_generations: Exception - {e}")
            self.test_results['ai_code_generations'] = False
            return False
    
    async def test_test_results_table(self) -> bool:
        """Teste l'insertion dans la table test_results."""
        logger.info("📋 Test: table test_results")
        try:
            run_id = self.test_ids.get('run_id')
            if not run_id:
                logger.warning("⚠️ test_results: Pas de run_id disponible, création d'un run")
                await self.test_task_runs_table()
                run_id = self.test_ids.get('run_id')
            
            test_id = await db_persistence.log_test_results(
                task_run_id=run_id,
                passed=True,
                status="passed",
                tests_total=10,
                tests_passed=10,
                tests_failed=0,
                tests_skipped=0,
                coverage_percentage=85.5,
                pytest_report={"summary": "All tests passed"},
                duration_seconds=30
            )
            
            if test_id:
                logger.info(f"✅ test_results: Résultats de tests créés avec ID {test_id}")
                self.test_results['test_results'] = True
                return True
            else:
                logger.error("❌ test_results: Échec création résultats tests")
                self.test_results['test_results'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ test_results: Exception - {e}")
            self.test_results['test_results'] = False
            return False
    
    async def test_pull_requests_table(self) -> bool:
        """Teste l'insertion dans la table pull_requests."""
        logger.info("📋 Test: table pull_requests")
        try:
            task_id = self.test_ids.get('task_id')
            run_id = self.test_ids.get('run_id')
            
            if not task_id or not run_id:
                logger.warning("⚠️ pull_requests: Pas de task_id ou run_id, création...")
                if not task_id:
                    await self.test_tasks_table()
                    task_id = self.test_ids.get('task_id')
                if not run_id:
                    await self.test_task_runs_table()
                    run_id = self.test_ids.get('run_id')
            
            pr_id = await db_persistence.create_pull_request(
                task_id=task_id,
                task_run_id=run_id,
                github_pr_number=123,
                github_pr_url="https://github.com/test/repo/pull/123",
                pr_title="Test PR",
                pr_description="Test description",
                head_sha="abc123def456",
                base_branch="main",
                feature_branch="test-branch"
            )
            
            if pr_id:
                logger.info(f"✅ pull_requests: PR créée avec ID {pr_id}")
                self.test_results['pull_requests'] = True
                return True
            else:
                logger.error("❌ pull_requests: Échec création PR")
                self.test_results['pull_requests'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ pull_requests: Exception - {e}")
            self.test_results['pull_requests'] = False
            return False
    
    async def test_performance_metrics_table(self) -> bool:
        """Teste l'insertion dans la table performance_metrics."""
        logger.info("📋 Test: table performance_metrics")
        try:
            task_id = self.test_ids.get('task_id')
            run_id = self.test_ids.get('run_id')
            
            if not task_id or not run_id:
                logger.warning("⚠️ performance_metrics: Pas de task_id ou run_id, création...")
                if not task_id:
                    await self.test_tasks_table()
                    task_id = self.test_ids.get('task_id')
                if not run_id:
                    await self.test_task_runs_table()
                    run_id = self.test_ids.get('run_id')
            
            await db_persistence.record_performance_metrics(
                task_id=task_id,
                task_run_id=run_id,
                total_duration_seconds=300,
                ai_processing_time_seconds=150,
                testing_time_seconds=50,
                total_ai_calls=5,
                total_tokens_used=2000,
                total_ai_cost=0.05,
                test_coverage_final=85.5,
                retry_attempts=0
            )
            
            # Vérifier l'insertion
            async with self.db_pool.acquire() as conn:
                count = await conn.fetchval("""
                    SELECT COUNT(*) FROM performance_metrics 
                    WHERE task_id = $1 AND task_run_id = $2
                """, task_id, run_id)
            
            if count > 0:
                logger.info(f"✅ performance_metrics: Métriques enregistrées ({count} entrée(s))")
                self.test_results['performance_metrics'] = True
                return True
            else:
                logger.error("❌ performance_metrics: Aucune métrique trouvée")
                self.test_results['performance_metrics'] = False
                return False
                
        except Exception as e:
            logger.error(f"❌ performance_metrics: Exception - {e}")
            self.test_results['performance_metrics'] = False
            return False
    
    async def test_human_validations_table(self) -> bool:
        """Teste l'insertion dans la table human_validations."""
        logger.info("📋 Test: table human_validations")
        try:
            task_id = self.test_ids.get('task_id')
            run_id = self.test_ids.get('run_id')
            step_id = self.test_ids.get('step_id')
            
            if not task_id:
                await self.test_tasks_table()
                task_id = self.test_ids.get('task_id')
            
            validation_service = HumanValidationService()
            await validation_service.init_db_pool()
            
            # Créer une demande de validation
            validation_request = HumanValidationRequest(
                validation_id=f"test_val_{int(datetime.now().timestamp())}",
                workflow_id="test_workflow",
                task_id=str(task_id),
                task_title="Test Validation",
                generated_code={"test.py": "print('hello')"},
                code_summary="Simple test code",
                files_modified=["test.py"],
                original_request="Create a test file",
                implementation_notes="Test implementation",
                test_results={"passed": True},
                pr_info=None,
                expires_at=datetime.now() + timedelta(hours=24),
                requested_by="test_script"
            )
            
            success = await validation_service.create_validation_request(
                validation_request,
                task_id=task_id,
                task_run_id=run_id,
                run_step_id=step_id
            )
            
            if success:
                self.test_ids['validation_id'] = validation_request.validation_id
                logger.info(f"✅ human_validations: Validation créée avec ID {validation_request.validation_id}")
                self.test_results['human_validations'] = True
                
                await validation_service.close_db_pool()
                return True
            else:
                logger.error("❌ human_validations: Échec création validation")
                self.test_results['human_validations'] = False
                await validation_service.close_db_pool()
                return False
                
        except Exception as e:
            logger.error(f"❌ human_validations: Exception - {e}")
            self.test_results['human_validations'] = False
            return False
    
    async def test_human_validation_responses_table(self) -> bool:
        """Teste l'insertion dans la table human_validation_responses."""
        logger.info("📋 Test: table human_validation_responses")
        try:
            validation_id = self.test_ids.get('validation_id')
            if not validation_id:
                logger.warning("⚠️ human_validation_responses: Pas de validation_id, création d'une validation")
                await self.test_human_validations_table()
                validation_id = self.test_ids.get('validation_id')
            
            validation_service = HumanValidationService()
            await validation_service.init_db_pool()
            
            # Créer une réponse de validation
            response = HumanValidationResponse(
                validation_id=validation_id,
                status=HumanValidationStatus.APPROVED,
                comments="Test approval",
                suggested_changes=None,
                approval_notes="Looks good",
                validated_by="test_validator",
                validated_at=datetime.now(),
                should_merge=True,
                should_continue_workflow=True
            )
            
            success = await validation_service.submit_validation_response(
                validation_id,
                response
            )
            
            if success:
                logger.info(f"✅ human_validation_responses: Réponse créée pour validation {validation_id}")
                self.test_results['human_validation_responses'] = True
                await validation_service.close_db_pool()
                return True
            else:
                logger.error("❌ human_validation_responses: Échec création réponse")
                self.test_results['human_validation_responses'] = False
                await validation_service.close_db_pool()
                return False
                
        except Exception as e:
            logger.error(f"❌ human_validation_responses: Exception - {e}")
            self.test_results['human_validation_responses'] = False
            return False
    
    async def test_validation_actions_table(self) -> bool:
        """Teste l'insertion dans la table validation_actions."""
        logger.info("📋 Test: table validation_actions")
        try:
            validation_id = self.test_ids.get('validation_id')
            if not validation_id:
                logger.warning("⚠️ validation_actions: Pas de validation_id, création d'une validation")
                await self.test_human_validations_table()
                validation_id = self.test_ids.get('validation_id')
            
            validation_service = HumanValidationService()
            await validation_service.init_db_pool()
            
            # Créer une action
            action_id = await validation_service.create_validation_action(
                validation_id=validation_id,
                action_type="merge_pr",
                action_data={"pr_number": 123, "branch": "test-branch"}
            )
            
            if action_id:
                # Mettre à jour l'action
                update_success = await validation_service.update_validation_action(
                    action_id=action_id,
                    status="completed",
                    result_data={"merge_success": True},
                    merge_commit_hash="abc123",
                    merge_commit_url="https://github.com/test/repo/commit/abc123"
                )
                
                if update_success:
                    logger.info(f"✅ validation_actions: Action créée et mise à jour avec ID {action_id}")
                    self.test_results['validation_actions'] = True
                    await validation_service.close_db_pool()
                    return True
                else:
                    logger.error("❌ validation_actions: Échec mise à jour action")
                    self.test_results['validation_actions'] = False
                    await validation_service.close_db_pool()
                    return False
            else:
                logger.error("❌ validation_actions: Échec création action")
                self.test_results['validation_actions'] = False
                await validation_service.close_db_pool()
                return False
                
        except Exception as e:
            logger.error(f"❌ validation_actions: Exception - {e}")
            self.test_results['validation_actions'] = False
            return False
    
    async def test_system_config_table(self) -> bool:
        """Teste l'insertion dans la table system_config."""
        logger.info("📋 Test: table system_config")
        try:
            await system_config_service.init_db_pool()
            
            # Test création de configuration
            success_create = await system_config_service.create_or_update_config(
                key="test.config.key",
                value={"test": "value", "number": 42},
                description="Test configuration",
                config_type="application",
                updated_by="test_script"
            )
            
            if not success_create:
                logger.error("❌ system_config: Échec création config")
                self.test_results['system_config'] = False
                await system_config_service.close_db_pool()
                return False
            
            # Test récupération
            config = await system_config_service.get_config("test.config.key")
            if not config:
                logger.error("❌ system_config: Config créée mais non récupérable")
                self.test_results['system_config'] = False
                await system_config_service.close_db_pool()
                return False
            
            # Test mise à jour
            success_update = await system_config_service.create_or_update_config(
                key="test.config.key",
                value={"test": "updated_value", "number": 100},
                description="Updated test configuration",
                config_type="application",
                updated_by="test_script"
            )
            
            if success_update:
                logger.info(f"✅ system_config: Configuration créée et mise à jour")
                self.test_results['system_config'] = True
                await system_config_service.close_db_pool()
                return True
            else:
                logger.error("❌ system_config: Échec mise à jour config")
                self.test_results['system_config'] = False
                await system_config_service.close_db_pool()
                return False
                
        except Exception as e:
            logger.error(f"❌ system_config: Exception - {e}")
            self.test_results['system_config'] = False
            return False
    
    async def run_all_tests(self):
        """Exécute tous les tests dans l'ordre."""
        logger.info("=" * 80)
        logger.info("🚀 DÉBUT DES TESTS D'INSERTION DANS LA BASE DE DONNÉES")
        logger.info("=" * 80)
        
        await self.initialize()
        
        # Exécuter les tests dans l'ordre des dépendances
        test_order = [
            ("tasks", self.test_tasks_table),
            ("task_runs", self.test_task_runs_table),
            ("run_steps", self.test_run_steps_table),
            ("ai_interactions", self.test_ai_interactions_table),
            ("ai_code_generations", self.test_ai_code_generations_table),
            ("test_results", self.test_test_results_table),
            ("pull_requests", self.test_pull_requests_table),
            ("performance_metrics", self.test_performance_metrics_table),
            ("human_validations", self.test_human_validations_table),
            ("human_validation_responses", self.test_human_validation_responses_table),
            ("validation_actions", self.test_validation_actions_table),
            ("system_config", self.test_system_config_table),
        ]
        
        for table_name, test_func in test_order:
            logger.info(f"\n{'=' * 80}")
            await test_func()
            await asyncio.sleep(0.5)  # Petit délai entre les tests
        
        # Afficher le résumé
        logger.info("\n" + "=" * 80)
        logger.info("📊 RÉSUMÉ DES TESTS")
        logger.info("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        failed_tests = total_tests - passed_tests
        
        for table, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{status} - {table}")
        
        logger.info("=" * 80)
        logger.info(f"Total: {total_tests} | Réussis: {passed_tests} | Échoués: {failed_tests}")
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        logger.info(f"Taux de réussite: {success_rate:.1f}%")
        logger.info("=" * 80)
        
        await self.cleanup()
        
        return passed_tests == total_tests


async def main():
    """Point d'entrée principal."""
    tester = DatabaseInsertionTester()
    
    try:
        all_passed = await tester.run_all_tests()
        
        if all_passed:
            logger.info("\n🎉 TOUS LES TESTS ONT RÉUSSI!")
            return 0
        else:
            logger.error("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
            return 1
            
    except Exception as e:
        logger.error(f"\n💥 ERREUR CRITIQUE: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
