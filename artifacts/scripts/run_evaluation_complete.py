#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script complet pour exécuter une évaluation de l'agent VyData.

Workflow:
1. Charger les tests du Golden Set (CSV)
2. Exécuter l'agent sur chaque test
3. Évaluer avec le LLM Judge (VyDataEvaluator)
4. Sauvegarder les résultats
5. Poster dans Monday (optionnel)
6. Mettre à jour les métriques de performance

Usage:
    python scripts/run_evaluation_complete.py --test-type analysis --limit 5
    python scripts/run_evaluation_complete.py --test-ids GS_A001 GS_A002
    python scripts/run_evaluation_complete.py --all
"""

import asyncio
import argparse
from pathlib import Path
import sys
from datetime import datetime

# Ajouter le projet au PATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.evaluation.golden_dataset_manager import GoldenDatasetManager
from services.evaluation.vydata_evaluator import VyDataEvaluator
from services.evaluation.monday_evaluation_feedback_service import MondayEvaluationFeedbackService
from utils.logger import get_logger

logger = get_logger(__name__)


class EvaluationRunner:
    """Orchestrateur pour exécuter les évaluations complètes."""
    
    def __init__(self, post_to_monday: bool = False):
        """
        Initialise le runner.
        
        Args:
            post_to_monday: Si True, poste les résultats dans Monday.
        """
        self.manager = GoldenDatasetManager()
        self.evaluator = VyDataEvaluator()
        self.feedback = MondayEvaluationFeedbackService() if post_to_monday else None
        self.post_to_monday = post_to_monday
        
        logger.info("✅ EvaluationRunner initialisé")
    
    async def run_evaluation(
        self,
        test_type: str = None,
        test_ids: list = None,
        limit: int = None,
        monday_item_id: str = None
    ):
        """
        Lance l'évaluation complète.
        
        Args:
            test_type: Type de tests ('analysis' ou 'pr').
            test_ids: Liste d'IDs spécifiques.
            limit: Limiter le nombre de tests.
            monday_item_id: ID de l'item Monday pour poster les résultats.
        """
        logger.info("=" * 80)
        logger.info("🚀 LANCEMENT DE L'ÉVALUATION")
        logger.info("=" * 80)
        
        # 1. Charger les tests
        logger.info(f"\n📂 Chargement des tests (type={test_type}, ids={test_ids}, limit={limit})...")
        tests = self.manager.load_golden_sets(
            test_type=test_type,
            active_only=True,
            test_ids=test_ids
        )
        
        if limit:
            tests = tests.head(limit)
        
        if tests.empty:
            logger.warning("⚠️ Aucun test à exécuter")
            return
        
        logger.info(f"✅ {len(tests)} tests chargés\n")
        
        # 2. Exécuter les tests
        results = []
        
        for idx, (_, test) in enumerate(tests.iterrows(), 1):
            test_id = test['test_id']
            input_text = test['input_monday_update']
            expected_output = test['expected_output']
            test_type_val = test['test_type']
            
            logger.info(f"\n{'=' * 80}")
            logger.info(f"🧪 TEST {idx}/{len(tests)}: {test_id}")
            logger.info(f"{'=' * 80}")
            logger.info(f"📝 Type: {test_type_val}")
            logger.info(f"📥 Input: {input_text[:80]}...")
            
            # 3. Simuler l'exécution de l'agent (à remplacer par votre vraie logique)
            agent_response = await self._simulate_agent_execution(
                input_text,
                test_type_val
            )
            
            logger.info(f"🤖 Agent output: {agent_response[:80]}...")
            
            # 4. Évaluer avec LLM Judge
            logger.info("🔍 Évaluation par LLM Judge...")
            
            eval_result = self.evaluator.evaluate_response(
                reference_input=input_text,
                reference_output=expected_output,
                agent_response=agent_response,
                test_id=test_id,
                monday_update_id=f"auto_{test_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            # 5. Afficher le résultat
            self._print_evaluation_result(eval_result)
            
            # 6. Sauvegarder
            self.manager.save_evaluation_result(eval_result)
            logger.info(f"💾 Résultat sauvegardé: {eval_result['eval_id']}")
            
            # 7. Poster dans Monday (optionnel)
            if self.post_to_monday and monday_item_id:
                logger.info("📤 Envoi vers Monday...")
                await self.feedback.post_llm_evaluation_result(
                    item_id=monday_item_id,
                    evaluation_result=eval_result
                )
            
            results.append(eval_result)
        
        # 8. Mettre à jour les métriques
        logger.info(f"\n{'=' * 80}")
        logger.info("📊 MISE À JOUR DES MÉTRIQUES")
        logger.info("=" * 80)
        
        self.manager.update_performance_metrics()
        
        # 9. Afficher le résumé
        self._print_summary(results)
        
        # 10. Poster le résumé dans Monday (optionnel)
        if self.post_to_monday and monday_item_id:
            metrics = self.manager.get_performance_metrics(days=1).iloc[0].to_dict()
            await self.feedback.post_performance_summary(
                item_id=monday_item_id,
                metrics=metrics
            )
        
        logger.info("\n✅ ÉVALUATION COMPLÉTÉE!")
    
    async def _simulate_agent_execution(self, input_text: str, test_type: str) -> str:
        """
        Simule l'exécution de l'agent.
        
        À REMPLACER PAR VOTRE VRAIE LOGIQUE D'AGENT.
        
        Args:
            input_text: Input de l'utilisateur.
            test_type: Type de test.
            
        Returns:
            Réponse de l'agent simulée.
        """
        # TODO: Remplacer par l'appel réel à votre agent
        # from services.agent_response_service import AgentResponseService
        # agent = AgentResponseService()
        # return await agent.generate_and_post_response(input_text, ...)
        
        if test_type == "analysis":
            return f"Analyse de '{input_text}': Le système comprend plusieurs modules interconnectés..."
        else:
            return f"PR créée pour '{input_text}': Implémentation complète avec tests unitaires et documentation."
    
    def _print_evaluation_result(self, result: dict):
        """Affiche un résultat d'évaluation de façon formatée."""
        
        score = result['llm_score']
        status = result['status']
        
        status_emoji = "✅" if status == "PASS" else "❌"
        score_emoji = self._get_score_emoji(score)
        
        print(f"\n{score_emoji} {status_emoji} SCORE: {score}/100 ({status})")
        print(f"⏱️  Durée: {result['duration_seconds']}s")
        
        if result.get('criteria_scores'):
            print(f"\n📋 Scores par critère:")
            for criterion, crit_score in result['criteria_scores'].items():
                crit_emoji = self._get_score_emoji(crit_score)
                print(f"   {crit_emoji} {criterion.capitalize()}: {crit_score}/100")
        
        print(f"\n💬 Justification:")
        reasoning = result['llm_reasoning']
        for line in reasoning.split('\n'):
            if line.strip():
                print(f"   {line.strip()}")
    
    def _print_summary(self, results: list):
        """Affiche un résumé des résultats."""
        
        total = len(results)
        passed = sum(1 for r in results if r['status'] == 'PASS')
        failed = total - passed
        avg_score = sum(r['llm_score'] for r in results) / total if total > 0 else 0
        avg_duration = sum(r['duration_seconds'] for r in results) / total if total > 0 else 0
        
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\n{'=' * 80}")
        print("📊 RÉSUMÉ DE L'ÉVALUATION")
        print("=" * 80)
        print(f"🧪 Total tests: {total}")
        print(f"✅ Tests réussis: {passed}")
        print(f"❌ Tests échoués: {failed}")
        print(f"📈 Taux de réussite: {pass_rate:.1f}%")
        print(f"🎯 Score moyen: {avg_score:.1f}/100")
        print(f"⏱️  Durée moyenne: {avg_duration:.2f}s")
        print("=" * 80)
        
        # Statut de fiabilité
        if avg_score >= 85:
            reliability = "🟢 EXCELLENT"
        elif avg_score >= 70:
            reliability = "🟡 BON"
        else:
            reliability = "🔴 À AMÉLIORER"
        
        print(f"\n🎯 Statut de fiabilité: {reliability}\n")
    
    @staticmethod
    def _get_score_emoji(score: int) -> str:
        """Retourne un emoji selon le score."""
        if score >= 90:
            return "🌟"
        elif score >= 80:
            return "✅"
        elif score >= 70:
            return "👍"
        elif score >= 50:
            return "⚠️"
        else:
            return "❌"


async def main():
    """Point d'entrée principal."""
    
    parser = argparse.ArgumentParser(
        description="Évaluation complète de l'agent VyData avec Golden Sets"
    )
    
    parser.add_argument(
        '--test-type',
        choices=['analysis', 'pr'],
        help="Type de tests à exécuter"
    )
    
    parser.add_argument(
        '--test-ids',
        nargs='+',
        help="IDs spécifiques de tests à exécuter (ex: GS_A001 GS_A002)"
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help="Limiter le nombre de tests"
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help="Exécuter tous les tests actifs"
    )
    
    parser.add_argument(
        '--post-monday',
        action='store_true',
        help="Poster les résultats dans Monday"
    )
    
    parser.add_argument(
        '--monday-item-id',
        help="ID de l'item Monday pour poster les résultats"
    )
    
    args = parser.parse_args()
    
    # Initialiser le runner
    runner = EvaluationRunner(post_to_monday=args.post_monday)
    
    # Lancer l'évaluation
    await runner.run_evaluation(
        test_type=args.test_type if not args.all else None,
        test_ids=args.test_ids,
        limit=args.limit,
        monday_item_id=args.monday_item_id
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Évaluation interrompue par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

