"""
LLM Judge Service avec RAG - Version Enrichie Multilingue.

Cette classe ÉTEND le LLMJudgeServiceSimplified avec les capacités RAG:
- Recherche d'examples similaires dans le golden dataset
- Évaluation enrichie avec contexte
- Support multilingue automatique
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from ai.llm.llm_factory import get_llm_with_fallback
from utils.logger import get_logger
from datetime import datetime
from services.evaluation.golden_dataset_rag_extension import golden_dataset_rag_extension
from services.evaluation.llm_judge_service_simplified import LLMJudgeServiceSimplified, EvaluationResult

logger = get_logger(__name__)


class LLMJudgeRAGEnriched(LLMJudgeServiceSimplified):
    """
    LLM Judge enrichi avec RAG multilingue.
    
    Hérite de LLMJudgeServiceSimplified et ajoute:
    - Recherche d'examples similaires
    - Contexte enrichi pour l'évaluation
    - Détection de langue
    - Métriques de similarité
    """
    
    def __init__(
        self,
        provider: str = "anthropic",
        model_name: str = None,
        temperature: float = 0,
        use_rag: bool = True,
        rag_top_k: int = 3,
        rag_threshold: float = 0.6
    ):
        """
        Initialise le LLM Judge enrichi avec RAG.
        
        Args:
            provider: Provider LLM (anthropic, openai, google)
            model_name: Nom du modèle LLM
            temperature: Température pour la génération
            use_rag: Activer l'enrichissement RAG
            rag_top_k: Nombre d'examples similaires à récupérer
            rag_threshold: Seuil de similarité (0.0-1.0)
        """
        super().__init__(provider, model_name, temperature)
        
        self.use_rag = use_rag
        self.rag_top_k = rag_top_k
        self.rag_threshold = rag_threshold
        
        logger.info(f"✅ LLMJudgeRAGEnriched initialisé (RAG: {use_rag}, top_k: {rag_top_k})")
    
    def _create_evaluation_prompt_with_rag(self) -> ChatPromptTemplate:
        """
        Crée le prompt d'évaluation enrichi avec contexte RAG.
        
        Returns:
            ChatPromptTemplate configuré avec RAG
        """
        system_message = """You are an expert evaluator for an AI agent that performs various technical tasks.

Your task is to evaluate the agent's response against a reference output.

**IMPORTANT: You have access to similar reference examples from the Golden Dataset.**
Use these examples to understand the expected quality and format of responses.

Evaluation Criteria:
1. Accuracy: Does the response correctly address the user's question?
2. Completeness: Does it cover all aspects mentioned in the reference?
3. Clarity: Is the response clear and well-structured?
4. Technical Quality: Is the technical content accurate?
5. Consistency: Is it consistent with the reference examples?

Score from 0-100:
- 90-100: Excellent - Meets or exceeds all criteria
- 70-89: Good - Meets most criteria with minor issues
- 50-69: Adequate - Meets some criteria but has notable gaps
- 30-49: Poor - Significant issues or missing key information
- 0-29: Very Poor - Fails to address the question appropriately

Be objective and provide specific reasoning for your score.

You MUST respond with a valid JSON object in the following format:
{{
  "score": <number from 0-100>,
  "reasoning": "<detailed explanation of the score>"
}}"""
        
        user_message = """**User Question/Command:**
{reference_input}

**Expected Response (Reference):**
{reference_output}

**SIMILAR REFERENCE EXAMPLES FROM GOLDEN DATASET:**
{similar_examples}

**Agent's Actual Response:**
{agent_response}

**Language Detected:** {detected_language}

Evaluate the agent's response and provide a score (0-100) with detailed reasoning in JSON format.
Consider the similar examples to understand the expected quality standard."""
        
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message)
        ])
    
    async def evaluate_response_with_rag(
        self,
        reference_input: str,
        reference_output: str,
        agent_response: str,
        use_rag: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Évalue la réponse de l'agent avec enrichissement RAG.
        
        Args:
            reference_input: Question/commande de test
            reference_output: Réponse attendue
            agent_response: Réponse générée par l'agent
            use_rag: Activer RAG pour cette évaluation (override)
            
        Returns:
            Résultat d'évaluation enrichi avec contexte RAG
        """
        use_rag_eval = use_rag if use_rag is not None else self.use_rag
        
        similar_examples = []
        rag_context = None
        detected_language = 'en'
        
        if use_rag_eval:
            try:
                similar_examples = await golden_dataset_rag_extension.find_similar_golden_examples(
                    query=reference_input,
                    top_k=self.rag_top_k,
                    match_threshold=self.rag_threshold
                )
                
                if similar_examples:
                    detected_language = similar_examples[0].get('language', 'en')
                
                logger.info(f"🔍 RAG: {len(similar_examples)} examples similaires trouvés (langue: {detected_language})")
                
            except Exception as e:
                logger.warning(f"⚠️ Erreur recherche RAG (non-bloquant): {e}")
                similar_examples = []
        
        similar_examples_text = ""
        if similar_examples:
            similar_examples_text = "\n"
            for i, ex in enumerate(similar_examples, 1):
                similar_examples_text += f"\nExample {i} (Similarity: {ex['similarity_score']:.2f}, Language: {ex['language']}):\n"
                similar_examples_text += f"  Input: {ex['input_reference']}\n"
                similar_examples_text += f"  Expected Output: {ex['output_reference'][:300]}...\n"
        else:
            similar_examples_text = "\nNo similar examples found in the Golden Dataset."
        
        if use_rag_eval and similar_examples:
            prompt = self._create_evaluation_prompt_with_rag()
            input_vars = {
                "reference_input": reference_input,
                "reference_output": reference_output,
                "agent_response": agent_response,
                "similar_examples": similar_examples_text,
                "detected_language": detected_language
            }
        else:
            prompt = self._create_evaluation_prompt()
            input_vars = {
                "reference_input": reference_input,
                "reference_output": reference_output,
                "adam_response": agent_response
            }
        
        try:
            llm = self._get_llm()
            parser = JsonOutputParser(pydantic_object=EvaluationResult)
            chain = prompt | llm | parser
            
            result = await chain.ainvoke(input_vars)
            
            result['timestamp'] = datetime.now().isoformat()
            result['rag_enabled'] = use_rag_eval
            result['rag_similar_count'] = len(similar_examples)
            result['rag_language_detected'] = detected_language
            
            if similar_examples:
                result['rag_max_similarity'] = max([ex['similarity_score'] for ex in similar_examples])
                result['rag_similar_examples'] = [
                    {
                        'input': ex['input_reference'][:100],
                        'similarity': ex['similarity_score'],
                        'language': ex['language']
                    }
                    for ex in similar_examples
                ]
            
            logger.info(f"✅ Évaluation terminée: score={result.get('score', 0):.1f}/100, RAG={use_rag_eval}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'évaluation: {e}", exc_info=True)
            raise
    
    async def evaluate_response(
        self,
        reference_input: str,
        reference_output: str,
        adam_response: str
    ) -> Dict[str, Any]:
        """
        Override de la méthode parent pour utiliser RAG par défaut.
        
        Maintient la compatibilité avec l'API existante.
        """
        return await self.evaluate_response_with_rag(
            reference_input=reference_input,
            reference_output=reference_output,
            agent_response=adam_response,
            use_rag=self.use_rag
        )
    
    async def compare_classic_vs_rag(
        self,
        reference_input: str,
        reference_output: str,
        agent_response: str
    ) -> Dict[str, Any]:
        """
        Compare l'évaluation classique vs RAG enrichie.
        
        Args:
            reference_input: Question/commande
            reference_output: Réponse attendue
            agent_response: Réponse de l'agent
            
        Returns:
            Comparaison des deux méthodes
        """
        logger.info("📊 Comparaison Classic vs RAG...")
        
        classic_result = await self.evaluate_response_with_rag(
            reference_input=reference_input,
            reference_output=reference_output,
            agent_response=agent_response,
            use_rag=False
        )

        rag_result = await self.evaluate_response_with_rag(
            reference_input=reference_input,
            reference_output=reference_output,
            agent_response=agent_response,
            use_rag=True
        )

        comparison = {
            "classic": {
                "score": classic_result.get('score', 0),
                "reasoning": classic_result.get('reasoning', ''),
                "method": "classic"
            },
            "rag_enriched": {
                "score": rag_result.get('score', 0),
                "reasoning": rag_result.get('reasoning', ''),
                "method": "rag_enriched",
                "similar_count": rag_result.get('rag_similar_count', 0),
                "language": rag_result.get('rag_language_detected', 'en'),
                "max_similarity": rag_result.get('rag_max_similarity', 0.0)
            },
            "difference": {
                "score_delta": rag_result.get('score', 0) - classic_result.get('score', 0),
                "rag_provides_context": rag_result.get('rag_similar_count', 0) > 0
            },
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"✅ Comparaison terminée:")
        logger.info(f"   • Classic: {classic_result.get('score', 0):.1f}/100")
        logger.info(f"   • RAG Enriched: {rag_result.get('score', 0):.1f}/100")
        logger.info(f"   • Delta: {comparison['difference']['score_delta']:.1f}")
        
        return comparison


llm_judge_rag_enriched = LLMJudgeRAGEnriched()

