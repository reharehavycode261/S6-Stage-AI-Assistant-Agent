"""
LLM Judge Service - Service d'évaluation via LLM as Judge.

Responsabilités:
    - Comparer output agent vs expected output
    - Attribuer un score /100
    - Fournir un raisonnement détaillé
"""

from typing import Dict, Any, List
from models.evaluation_models import (
    GoldenDatasetItem,
    EvaluationResult,
    AgentEvaluationConfig
)
from ai.chains.llm_judge_chain import evaluate_with_llm_judge
from utils.logger import get_logger
from datetime import datetime
import time

logger = get_logger(__name__)


class LLMJudgeService:
    """
    Service d'évaluation utilisant un LLM as Judge.
    """
    
    def __init__(self, config: AgentEvaluationConfig):
        """
        Initialise le service LLM Judge.
        
        Args:
            config: Configuration de l'évaluation
        """
        self.config = config
        logger.info(f"✅ LLMJudgeService initialisé (provider: {config.judge_provider})")
    
    async def evaluate_single_test(
        self,
        item: GoldenDatasetItem,
        agent_output: str,
        agent_output_metadata: Dict[str, Any]
    ) -> EvaluationResult:
        """
        Évalue un test individuel.
        
        Args:
            item: Item du Golden Dataset
            agent_output: Output généré par l'agent
            agent_output_metadata: Métadonnées de l'output
            
        Returns:
            EvaluationResult avec score et raisonnement
        """
        logger.info(f"⚖️ Évaluation test: {item.id}")
        
        start_time = time.time()
        
        try:
            criteria = self._get_evaluation_criteria(item)
            
            judgment = await evaluate_with_llm_judge(
                test_type=item.type.value,
                input_text=item.input_text,
                input_context=item.input_context,
                agent_output=agent_output,
                expected_output=item.expected_output,
                criteria=criteria,
                provider=self.config.judge_provider,
                fallback_to_openai=True
            )
            
            duration = time.time() - start_time
            
            result = EvaluationResult(
                item_id=item.id,
                item_type=item.type,
                agent_output=agent_output,
                agent_output_metadata=agent_output_metadata,
                expected_output=item.expected_output,
                score=judgment.score,
                reasoning=judgment.reasoning,
                criteria_scores=judgment.criteria_scores,
                passed=judgment.score >= self.config.pass_threshold,
                threshold=self.config.pass_threshold,
                evaluated_at=datetime.utcnow(),
                evaluation_duration_seconds=round(duration, 2)
            )
            
            status = "✅ RÉUSSI" if result.passed else "❌ ÉCHOUÉ"
            logger.info(
                f"{status} Test {item.id}: {result.score:.1f}/100 "
                f"(seuil: {self.config.pass_threshold})"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Erreur évaluation test {item.id}: {e}", exc_info=True)
            
            duration = time.time() - start_time
            
            return EvaluationResult(
                item_id=item.id,
                item_type=item.type,
                agent_output=agent_output,
                agent_output_metadata=agent_output_metadata,
                expected_output=item.expected_output,
                score=0.0,
                reasoning=f"Erreur lors de l'évaluation: {str(e)}",
                criteria_scores={},
                passed=False,
                threshold=self.config.pass_threshold,
                evaluated_at=datetime.utcnow(),
                evaluation_duration_seconds=round(duration, 2),
                error=str(e)
            )
    
    def _get_evaluation_criteria(self, item: GoldenDatasetItem) -> List[str]:
        """
        Récupère les critères d'évaluation pour un item.
        
        Args:
            item: Item du Golden Dataset
            
        Returns:
            Liste des critères d'évaluation
        """
        if item.evaluation_criteria and len(item.evaluation_criteria) > 0:
            return item.evaluation_criteria
        
        if item.type == DatasetType.QUESTIONS:
            return self.config.default_criteria_questions
        else:  # COMMANDS
            return self.config.default_criteria_commands
    
    async def batch_evaluate(
        self,
        items_with_outputs: List[tuple[GoldenDatasetItem, str, Dict[str, Any]]]
    ) -> List[EvaluationResult]:
        """
        Évalue plusieurs tests en batch.
        
        Args:
            items_with_outputs: Liste de (item, agent_output, metadata)
            
        Returns:
            Liste de EvaluationResult
        """
        logger.info(f"📊 Évaluation batch de {len(items_with_outputs)} tests")
        
        results = []
        
        for item, agent_output, metadata in items_with_outputs:
            result = await self.evaluate_single_test(item, agent_output, metadata)
            results.append(result)
        
        logger.info(f"✅ {len(results)} tests évalués")
        
        return results

