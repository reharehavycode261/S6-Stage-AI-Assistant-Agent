"""
LLM Judge Service - Version simplifiée compatible avec le Golden Dataset simplifié.

Logique identique à celle de la capture d'écran:
- Compare input_reference, output_reference et agent_response
- Retourne un JSON simple: {"score": number, "reasoning": string}
- 5 critères d'évaluation standard
- Score de 0-100 avec barème détaillé
"""

from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from ai.llm.llm_factory import get_llm_with_fallback
from utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)


class EvaluationResult(BaseModel):
    """Résultat simplifié de l'évaluation (format JSON)."""
    
    score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Score de 0-100"
    )
    
    reasoning: str = Field(
        ...,
        description="Explication détaillée du score"
    )


class LLMJudgeServiceSimplified:
    """
    Service d'évaluation LLM-as-judge simplifié.
    
    Utilise la même logique que dans la capture d'écran:
    - 5 critères d'évaluation standard
    - Format JSON simple
    - Barème détaillé de 0-100
    """
    
    def __init__(self, provider: str = "anthropic", model_name: str = None, temperature: float = 0):
        """
        Initialise le service LLM Judge.
        
        Args:
            provider: Provider LLM (anthropic, openai, google)
            model_name: Nom du modèle LLM à utiliser (optionnel)
            temperature: Température pour la génération (0 = déterministe)
        """
        self.provider = provider
        if model_name is None:
            if provider == "anthropic":
                self.model_name = "claude-3-5-sonnet-20241022"  
            elif provider == "openai":
                self.model_name = "gpt-4o"  
            elif provider == "google":
                self.model_name = "gemini-1.5-pro"  
            else:
                self.model_name = "claude-3-5-sonnet-20241022"  
        else:
            self.model_name = model_name
        
        self.temperature = temperature
        self.llm = None
        logger.info(f"✅ LLMJudgeServiceSimplified initialisé (provider: {provider}, model: {self.model_name})")
    
    def _get_llm(self):
        """Récupère ou crée l'instance LLM."""
        if self.llm is None:
            self.llm = get_llm_with_fallback(
                primary_provider=self.provider,
                fallback_providers=["openai", "anthropic"],
                temperature=self.temperature,
                model_name=self.model_name
            )
        return self.llm
    
    def _create_evaluation_prompt(self) -> ChatPromptTemplate:
        """
        Crée le prompt d'évaluation (identique à la capture d'écran).
        
        Returns:
            ChatPromptTemplate configuré
        """
        system_message = """You are an expert evaluator for an AI agent called ADAM that analyzes advertising data.

Your task is to evaluate ADAM's response against a reference output or evaluation instruction.

Evaluation Criteria:
1. Accuracy: Does the response correctly address the user's question?
2. Completeness: Does it cover all aspects mentioned in the reference/instruction?
3. Clarity: Is the response clear and well-structured?
4. Data Quality: If data/tables are provided, are they accurate and relevant?
5. Actionability: Does it provide useful insights or next steps?

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
        
        user_message = """**Reference Input (User Question):**
{reference_input}

**Reference Output / Evaluation Instruction:**
{reference_output}

**ADAM's Actual Response:**
{adam_response}

Evaluate ADAM's response and provide a score (0-100) with detailed reasoning in JSON format."""
        
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", user_message)
        ])
    
    async def evaluate_response(
        self,
        reference_input: str,
        reference_output: str,
        adam_response: str
    ) -> Dict[str, Any]:
        """
        Évalue la réponse de l'agent ADAM.
        
        Args:
            reference_input: Question de l'utilisateur (input_reference)
            reference_output: Réponse attendue ou instruction d'évaluation (output_reference)
            adam_response: Réponse générée par l'agent
            
        Returns:
            Dict avec score, reasoning, passed, et métadonnées
        """
        logger.info("⚖️ Évaluation avec LLM-as-judge...")
        logger.info(f"   Input: {reference_input[:50]}...")
        logger.info(f"   Output attendu: {reference_output[:50]}...")
        
        try:
            prompt = self._create_evaluation_prompt()
            
            parser = JsonOutputParser()
            
            llm = self._get_llm()
            
            judge = prompt | llm | parser
            
            response = await judge.ainvoke({
                "reference_input": reference_input,
                "reference_output": reference_output,
                "adam_response": adam_response
            })
            
            if isinstance(response, dict):
                if "score" not in response or "reasoning" not in response:
                    raise ValueError(f"LLM response missing 'score' or 'reasoning': {response}")
                result = response
            else:
                import json
                import re
                
                response_text = str(response)
                json_match = re.search(r'\{[^}]*"score"[^}]*"reasoning"[^}]*\}', response_text, re.DOTALL)
                
                if json_match:
                    json_str = json_match.group(0)
                    result = json.loads(json_str)
                else:
                    raise ValueError(f"Could not parse JSON from response: {response_text[:200]}")
            
            score = float(result['score'])
            reasoning = result['reasoning']
            passed = score >= 70.0
            
            evaluation_result = {
                "timestamp": datetime.now().isoformat(),
                "input_reference": reference_input,
                "output_reference": reference_output,
                "agent_output": adam_response,
                "llm_score": score,
                "llm_reasoning": reasoning,
                "passed": passed,
                "duration_seconds": None  
            }
            
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"{status} Score: {score}/100 (seuil: 70)")
            logger.info(f"   Reasoning: {reasoning[:100]}...")
            
            return evaluation_result
        
        except Exception as e:
            logger.error(f"❌ Erreur évaluation LLM Judge: {e}", exc_info=True)
            
            return {
                "timestamp": datetime.now().isoformat(),
                "input_reference": reference_input,
                "output_reference": reference_output,
                "agent_output": adam_response,
                "llm_score": 0.0,
                "llm_reasoning": f"Erreur lors de l'évaluation: {str(e)}",
                "passed": False,
                "duration_seconds": None,
                "error": str(e)
            }

