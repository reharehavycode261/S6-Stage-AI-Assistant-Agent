"""
VyData Evaluator - LLM as Judge pour évaluer les réponses de l'agent VyData.

Implémentation du système d'évaluation automatique selon l'architecture:
Update Monday → Agent Coding → Output → LLM Judge → Score /100

Critères d'évaluation:
1. Accuracy - La réponse répond-elle correctement à la question ?
2. Completeness - Traite-t-elle tous les aspects demandés ?
3. Clarity - Est-elle claire et bien structurée ?
4. Data Quality - Les données fournies sont-elles exactes et pertinentes ?
5. Actionability - Fournit-elle des informations utiles ou des étapes suivantes ?
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import time
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from utils.logger import get_logger

logger = get_logger(__name__)


class EvaluationScore(BaseModel):
    """Modèle structuré pour le score d'évaluation."""
    score: int = Field(..., ge=0, le=100, description="Score global entre 0 et 100")
    reasoning: str = Field(..., description="Explication détaillée du score")
    criteria_scores: Dict[str, int] = Field(
        default_factory=dict,
        description="Scores par critère (accuracy, completeness, clarity, data_quality, actionability)"
    )


class VyDataEvaluator:
    """
    Évaluateur LLM pour l'agent VyData.
    
    Compare la sortie de l'agent (agent_response) avec la sortie attendue (reference_output)
    et attribue un score selon 5 critères.
    """
    
    def __init__(
        self,
        model_name: str = "claude-3-5-sonnet-20241022",
        provider: str = "anthropic",
        temperature: float = 0.0
    ):
        """
        Initialise l'évaluateur.
        
        Args:
            model_name: Nom du modèle LLM à utiliser.
            provider: Provider ('anthropic' ou 'openai').
            temperature: Température du modèle (0.0 = déterministe).
        """
        self.model_name = model_name
        self.provider = provider
        
        llm_initialized = False
        
        if provider == "anthropic":
            try:
                self.llm = ChatAnthropic(
                    model=model_name,
                    temperature=temperature
                )
                llm_initialized = True
                logger.info(f"✅ LLM Anthropic initialisé: {model_name}")
            except Exception as e:
                logger.warning(f"⚠️ Échec Anthropic: {e}")
                logger.info("🔄 Fallback vers OpenAI...")
        
        if not llm_initialized or provider == "openai":
            try:
                self.llm = ChatOpenAI(
                    model="gpt-4" if provider == "anthropic" else model_name,
                    temperature=temperature
                )
                self.provider = "openai"  
                self.model_name = "gpt-4" if provider == "anthropic" else model_name
                llm_initialized = True
                logger.info(f"✅ LLM OpenAI initialisé: {self.model_name}")
            except Exception as e:
                logger.error(f"❌ Échec OpenAI: {e}")
                raise ValueError(f"Impossible d'initialiser un LLM provider: {e}")
        
        if not llm_initialized:
            raise ValueError(f"Provider non supporté: {provider}")
        
        self.prompt = self._create_prompt()
        
        self.chain = self.prompt | self.llm.with_structured_output(EvaluationScore)
        
        logger.info(f"✅ VyDataEvaluator initialisé (model={self.model_name}, provider={self.provider})")
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """Crée le prompt système pour l'évaluation."""
        
        system_prompt = """Tu es un évaluateur expert pour un agent IA de coding appelé VyData.

**🎯 Ta mission:**
Évaluer la qualité des outputs de l'agent VyData en les comparant à des outputs de référence attendus.

**📊 Critères d'évaluation (5 critères):**

1. **Accuracy** (Exactitude) - 25%
   - La réponse répond-elle correctement à la question posée ?
   - Les informations fournies sont-elles exactes ?
   - L'agent a-t-il compris la demande ?

2. **Completeness** (Complétude) - 25%
   - Tous les aspects demandés sont-ils traités ?
   - La réponse couvre-t-elle tous les points importants ?
   - Manque-t-il des éléments essentiels ?

3. **Clarity** (Clarté) - 20%
   - La réponse est-elle claire et bien structurée ?
   - Le format est-il lisible et professionnel ?
   - La communication est-elle efficace ?

4. **Data Quality** (Qualité des données) - 15%
   - Les données/code fournis sont-ils exacts et pertinents ?
   - Les exemples sont-ils appropriés ?
   - Les références sont-elles correctes ?

5. **Actionability** (Caractère actionnable) - 15%
   - La réponse fournit-elle des informations utiles ?
   - Contient-elle des étapes suivantes claires si nécessaire ?
   - L'utilisateur peut-il agir sur la base de cette réponse ?

**🎯 Barème de notation (0-100):**

- **90-100**: Excellent - Respecte tous les critères, dépasse les attentes
- **80-89**: Bon - Quelques problèmes mineurs, répond globalement aux attentes
- **70-79**: Adéquat - Des manques notables mais réponse acceptable
- **50-69**: Pauvre - Erreurs significatives ou données manquantes
- **0-49**: Très mauvais - Ne répond pas correctement à la demande

**📋 Format de sortie attendu:**

Tu dois retourner un JSON avec:
- **score**: Score global (0-100)
- **reasoning**: Explication détaillée justifiant le score
- **criteria_scores**: Score pour chaque critère individuel

**⚠️ Important:**
- Sois objectif et constructif
- Compare toujours avec l'output de référence attendu
- Justifie précisément ton score
- Mentionne les points forts ET les points à améliorer
"""

        user_prompt = """**📝 Input (Question/Commande de l'utilisateur):**
{reference_input}

**✅ Output Attendu (Référence du Golden Set):**
{reference_output}

**🤖 Output Généré par l'Agent VyData:**
{agent_response}

---

**Instructions:**
Évalue l'output de l'agent en le comparant à l'output attendu. Attribue un score global et des scores par critère."""

        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt)
        ])
    
    def evaluate_response(
        self,
        reference_input: str,
        reference_output: str,
        agent_response: str,
        test_id: Optional[str] = None,
        monday_update_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Évalue la réponse de l'agent.
        
        Args:
            reference_input: La question/commande initiale (input Monday).
            reference_output: La réponse attendue (Golden Set).
            agent_response: La réponse générée par l'agent.
            test_id: ID du test (optionnel).
            monday_update_id: ID de l'update Monday (optionnel).
            
        Returns:
            Dictionnaire avec les résultats de l'évaluation complets.
        """
        start_time = time.time()
        
        try:
            logger.info(f"🔍 Évaluation en cours{f' pour {test_id}' if test_id else ''}...")
            result: EvaluationScore = self.chain.invoke({
                "reference_input": reference_input,
                "reference_output": reference_output,
                "agent_response": agent_response
            })
            
            duration = time.time() - start_time
            
            status = "PASS" if result.score >= 70 else "FAIL"
            
            evaluation_result = {
                "eval_id": f"EVAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "timestamp": datetime.now().isoformat(),
                "test_id": test_id or "N/A",
                "monday_update_id": monday_update_id or "N/A",
                "agent_output": agent_response,
                "llm_score": result.score,
                "llm_reasoning": result.reasoning,
                "criteria_scores": result.criteria_scores,
                "human_validation_status": "pending",
                "human_score": None,
                "human_feedback": None,
                "final_score": result.score,  
                "status": status,
                "duration_seconds": round(duration, 2),
                "error_message": None,
                "evaluator_model": self.model_name,
                "evaluator_provider": self.provider
            }
            
            logger.info(
                f"✅ Évaluation terminée: {result.score}/100 ({status}) "
                f"en {duration:.2f}s"
            )
            
            return evaluation_result
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'évaluation: {e}", exc_info=True)
            
            duration = time.time() - start_time
            
            return {
                "eval_id": f"EVAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "timestamp": datetime.now().isoformat(),
                "test_id": test_id or "N/A",
                "monday_update_id": monday_update_id or "N/A",
                "agent_output": agent_response,
                "llm_score": 0,
                "llm_reasoning": f"Error during evaluation: {str(e)}",
                "criteria_scores": {},
                "human_validation_status": "pending",
                "human_score": None,
                "human_feedback": None,
                "final_score": 0,
                "status": "FAIL",
                "duration_seconds": round(duration, 2),
                "error_message": str(e),
                "evaluator_model": self.model_name,
                "evaluator_provider": self.provider
            }
    
    def batch_evaluate(
        self,
        evaluations: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Évalue plusieurs réponses en batch.
        
        Args:
            evaluations: Liste de dict avec keys: reference_input, reference_output, agent_response
            
        Returns:
            Liste des résultats d'évaluation.
        """
        logger.info(f"📊 Évaluation batch de {len(evaluations)} réponses...")
        
        results = []
        for i, eval_data in enumerate(evaluations, 1):
            logger.info(f"   Évaluation {i}/{len(evaluations)}...")
            result = self.evaluate_response(**eval_data)
            results.append(result)
        
        avg_score = sum(r['llm_score'] for r in results) / len(results)
        passed = sum(1 for r in results if r['status'] == 'PASS')
        
        logger.info(
            f"✅ Batch terminé: {passed}/{len(results)} PASS "
            f"(score moyen: {avg_score:.1f}/100)"
        )
        
        return results
    
    def get_evaluation_summary(self, result: Dict[str, Any]) -> str:
        """
        Génère un résumé textuel de l'évaluation pour affichage.
        
        Args:
            result: Résultat d'évaluation.
            
        Returns:
            Texte formaté pour affichage.
        """
        summary = f"""
╔═══════════════════════════════════════════════════════════╗
║  📊 RÉSULTAT D'ÉVALUATION - {result['test_id']}
╠═══════════════════════════════════════════════════════════╣
║  🎯 Score Global: {result['llm_score']}/100 ({result['status']})
║  ⏱️  Durée: {result['duration_seconds']}s
╠═══════════════════════════════════════════════════════════╣
║  📋 Scores par Critère:
"""
        
        if result.get('criteria_scores'):
            for criterion, score in result['criteria_scores'].items():
                summary += f"║    • {criterion}: {score}/100\n"
        
        summary += f"""╠═══════════════════════════════════════════════════════════╣
║  💬 Justification:
║  {result['llm_reasoning'][:80]}...
╚═══════════════════════════════════════════════════════════╝
"""
        
        return summary

