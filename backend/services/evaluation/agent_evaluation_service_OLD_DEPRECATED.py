# -*- coding: utf-8 -*-
"""
Agent Evaluation Service - Orchestrateur de l'évaluation de l'agent IA.

Responsabilités:
    - Charger les Golden Datasets
    - Exécuter l'agent sur chaque test
    - Coordonner l'évaluation via LLM Judge
    - Générer le rapport d'évaluation
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
import time

from models.evaluation_models import (
    GoldenDataset,
    GoldenDatasetItem,
    EvaluationResult,
    EvaluationReport,
    AgentEvaluationConfig
)
from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from services.evaluation.llm_judge_service import LLMJudgeService
from services.agent_response_service import AgentResponseService
from services.intent_router_service import IntentRouterService
from utils.logger import get_logger

logger = get_logger(__name__)


class AgentEvaluationService:
    """
    Service principal d'évaluation de l'agent IA.
    
    Orchestre:
    1. Chargement des Golden Datasets
    2. Exécution de l'agent sur chaque test
    3. Évaluation via LLM Judge
    4. Génération du rapport
    """
    
    def __init__(
        self,
        config: Optional[AgentEvaluationConfig] = None,
        dataset_manager: Optional[GoldenDatasetManager] = None
    ):
        """
        Initialise le service d'évaluation.
        
        Args:
            config: Configuration de l'évaluation
            dataset_manager: Gestionnaire de datasets (créé si None)
        """
        self.config = config or AgentEvaluationConfig()
        self.dataset_manager = dataset_manager or GoldenDatasetManager()
        self.judge_service = LLMJudgeService(self.config)
        
        # Services pour exécuter l'agent
        self.agent_response_service = AgentResponseService()
        self.intent_router_service = IntentRouterService()
        
        logger.info("✅ AgentEvaluationService initialisé")
    
    async def evaluate_dataset(
        self,
        dataset_type: str = "golden",
        save_report: bool = True
    ) -> EvaluationReport:
        """
        Évalue l'agent sur un dataset complet.
        
        Args:
            dataset_type: Type de dataset à évaluer
            save_report: Sauvegarder le rapport en JSON
            
        Returns:
            EvaluationReport complet
        """
        logger.info("=" * 80)
        logger.info(f"🎯 DÉBUT ÉVALUATION AGENT - Dataset: {dataset_type.value}")
        logger.info("=" * 80)
        
        start_time = time.time()
        
        try:
            dataset = self.dataset_manager.load_dataset(dataset_type)
        except FileNotFoundError as e:
            logger.error(f"❌ Dataset {dataset_type.value} non trouvé: {e}")
            raise
        
        logger.info(f"✅ Dataset chargé: {dataset.name} ({dataset.total_items} tests)")
        
        report = EvaluationReport(
            report_id=str(uuid4()),
            dataset_name=dataset.name,
            dataset_type=dataset_type,
            evaluation_started_at=datetime.utcnow()
        )
        
        logger.info("🚀 Exécution des tests...")
        
        if self.config.run_in_parallel:
            results = await self._execute_tests_parallel(dataset)
        else:
            results = await self._execute_tests_sequential(dataset)
        
        report.results = results

        report.compute_statistics()
        
        report.generate_recommendations()
        
        report.evaluation_completed_at = datetime.utcnow()
        report.total_duration_seconds = round(time.time() - start_time, 2)
        
        self._display_report_summary(report)
        
        if save_report:
            await self._save_report(report)
        
        logger.info("=" * 80)
        logger.info(f"✅ ÉVALUATION TERMINÉE - Score: {report.reliability_score}/100")
        logger.info("=" * 80)
        
        return report
    
    async def _execute_tests_sequential(
        self,
        dataset: GoldenDataset
    ) -> list[EvaluationResult]:
        """Exécute les tests de manière séquentielle."""
        logger.info("📋 Exécution séquentielle des tests")
        
        results = []
        
        for i, item in enumerate(dataset.items, 1):
            logger.info(f"🧪 Test {i}/{dataset.total_items}: {item.id}")
            
            result = await self._execute_single_test(item)
            results.append(result)
        
        return results
    
    async def _execute_tests_parallel(
        self,
        dataset: GoldenDataset
    ) -> list[EvaluationResult]:
        """Exécute les tests en parallèle (avec limite)."""
        logger.info(
            f"⚡ Exécution parallèle des tests "
            f"(max: {self.config.max_parallel_tests} simultanés)"
        )
        
        semaphore = asyncio.Semaphore(self.config.max_parallel_tests)
        
        async def execute_with_semaphore(item: GoldenDatasetItem):
            async with semaphore:
                return await self._execute_single_test(item)
        
        tasks = [execute_with_semaphore(item) for item in dataset.items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Erreur test {dataset.items[i].id}: {result}")
                final_results.append(
                    self._create_error_result(dataset.items[i], str(result))
                )
            else:
                final_results.append(result)
        
        return final_results
    
    async def _execute_single_test(
        self,
        item: GoldenDatasetItem
    ) -> EvaluationResult:
        """
        Exécute un test individuel.
        
        1. Exécuter l'agent avec l'input du test
        2. Récupérer l'output de l'agent
        3. Évaluer via LLM Judge
        
        Args:
            item: Item du Golden Dataset
            
        Returns:
            EvaluationResult
        """
        logger.info(f"🧪 Exécution test: {item.id}")
        logger.info(f"   Type: {item.type.value}")
        logger.info(f"   Input: {item.input_text[:50]}...")
        
        try:
            simulated_task = self._create_simulated_task(item)
            
            agent_output, metadata = await self._execute_question_test(
                item,
                simulated_task
            )
            
            logger.info(f"✅ Agent output récupéré: {len(agent_output)} caractères")
            
            result = await self.judge_service.evaluate_single_test(
                item=item,
                agent_output=agent_output,
                agent_output_metadata=metadata
            )
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Erreur exécution test {item.id}: {e}", exc_info=True)
            return self._create_error_result(item, str(e))
    
    def _create_simulated_task(self, item: GoldenDatasetItem) -> Dict[str, Any]:
        """
        Crée une tâche Monday.com simulée pour le test.
        
        Args:
            item: Item du Golden Dataset
            
        Returns:
            Dictionnaire représentant une tâche
        """
        task = {
            "tasks_id": 999999,  # ID factice
            "monday_item_id": 999999,
            "title": f"Test Évaluation: {item.id}",
            "description": item.input_text,
            "repository_url": item.input_context.get("repository_url", "https://github.com/test/test"),
            "repository_name": item.input_context.get("repository_name", "test/test"),
            "default_branch": item.input_context.get("default_branch", "main"),
            "priority": "medium",
            "internal_status": "pending",
            "monday_status": "Working on it",
            "monday_board_id": 123456
        }
        
        return task
    
    async def _execute_question_test(
        self,
        item: GoldenDatasetItem,
        simulated_task: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """
        Exécute un test de type QUESTION.
        
        Args:
            item: Item du Golden Dataset
            simulated_task: Tâche simulée
            
        Returns:
            (agent_output, metadata)
        """
        logger.info("💬 Exécution test QUESTION")
        
        from types import SimpleNamespace
        task_obj = SimpleNamespace(**simulated_task)
        
        task_context = {
            "repository_url": simulated_task["repository_url"],
            "title": simulated_task["title"],
            "description": simulated_task["description"],
            "repository_name": simulated_task["repository_name"],
            "default_branch": simulated_task["default_branch"]
        }
        
        project_context = {
            "repository_url": simulated_task["repository_url"],
            "repository_name": simulated_task["repository_name"],
            "default_branch": simulated_task["default_branch"],
            "exploration_successful": True,  
            "technologies": ["Java", "JDBC", "DAO"],  
            "file_structure": [],
            "dependencies": [],
            "analysis_summary": f"Projet {simulated_task['repository_name']} - Test d'évaluation"
        }
        
        logger.info(f"🧪 Contexte évaluation créé avec exploration_successful=True")
        
        response_text = await self.agent_response_service._generate_response(
            question=item.input_text,
            task_context=task_context,
            project_context=project_context
        )
        
        metadata = {
            "test_type": "question",
            "repository_url": simulated_task["repository_url"]
        }
        
        return response_text, metadata
    
    async def _execute_command_test(
        self,
        item: GoldenDatasetItem,
        simulated_task: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """
        Exécute un test de type COMMANDE.
        
        Args:
            item: Item du Golden Dataset
            simulated_task: Tâche simulée
            
        Returns:
            (agent_output, metadata)
        """
        logger.info("⚙️ Exécution test COMMANDE")
        
        logger.warning("⚠️ Exécution workflow COMMANDE non implémentée pour évaluation")
        logger.warning("   → Utiliser l'expected_output comme agent_output pour le test")
        
        metadata = {
            "test_type": "command",
            "repository_url": simulated_task["repository_url"],
            "note": "Workflow execution not implemented in evaluation mode"
        }
        
        return item.expected_output, metadata
    
    def _create_error_result(
        self,
        item: GoldenDatasetItem,
        error_message: str
    ) -> EvaluationResult:
        """Crée un EvaluationResult pour une erreur."""
        return EvaluationResult(
            item_id=item.id,
            item_type=item.type,
            agent_output="",
            expected_output=item.expected_output,
            score=0.0,
            reasoning=f"Erreur d'exécution: {error_message}",
            passed=False,
            threshold=self.config.pass_threshold,
            error=error_message
        )
    
    def _display_report_summary(self, report: EvaluationReport):
        """Affiche un résumé du rapport dans les logs."""
        logger.info("=" * 80)
        logger.info("📊 RÉSUMÉ DU RAPPORT D'ÉVALUATION")
        logger.info("=" * 80)
        logger.info(f"📋 Dataset: {report.dataset_name} ({report.dataset_type.value})")
        logger.info(f"🧪 Tests: {report.total_tests}")
        logger.info(f"✅ Réussis: {report.tests_passed}")
        logger.info(f"❌ Échoués: {report.tests_failed}")
        logger.info(f"📊 Score moyen: {report.average_score:.1f}/100")
        logger.info(f"🎯 Score de fiabilité: {report.reliability_score:.1f}/100")
        logger.info(f"🏆 Statut: {report.reliability_status.upper()}")
        logger.info(f"⏱️  Durée: {report.total_duration_seconds:.1f}s")
        
        if report.recommendations:
            logger.info("\n📌 Recommandations:")
            for rec in report.recommendations:
                logger.info(f"   {rec}")
        
        logger.info("=" * 80)
    
    async def _save_report(self, report: EvaluationReport):
        """Sauvegarde le rapport d'évaluation en JSON."""
        try:
            import json
            from pathlib import Path
            
            reports_dir = Path(__file__).parent.parent.parent / "data" / "evaluation_reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_{report.dataset_type.value}_{timestamp}.json"
            filepath = reports_dir / filename
            
            report_data = report.model_dump(mode="json")
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Rapport sauvegardé: {filepath}")
        
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde rapport: {e}", exc_info=True)

