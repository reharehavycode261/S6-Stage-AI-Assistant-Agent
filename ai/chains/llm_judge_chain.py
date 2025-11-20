from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableSequence
from ai.llm.llm_factory import get_llm_with_fallback
from utils.logger import get_logger

logger = get_logger(__name__)


class LLMJudgment(BaseModel):
    
    score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Score global /100"
    )
    
    reasoning: str = Field(
        ...,
        description="Raisonnement détaillé de l'évaluation"
    )
    
    criteria_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Scores par critère /100"
    )
    
    strengths: List[str] = Field(
        default_factory=list,
        description="Points forts de l'output de l'agent"
    )
    
    weaknesses: List[str] = Field(
        default_factory=list,
        description="Points faibles de l'output de l'agent"
    )
    
    suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions d'amélioration"
    )


def create_llm_judge_chain(
    provider: str = "anthropic",
    fallback_to_openai: bool = True
) -> RunnableSequence:
    """
    Crée une chaîne LangChain pour évaluer les outputs de l'agent.
    
    Args:
        provider: Provider LLM principal (anthropic ou openai)
        fallback_to_openai: Utiliser OpenAI en fallback si provider principal échoue
        
    Returns:
        RunnableSequence configurée
    """
    logger.info(f"🔗 Création LLM Judge chain (provider: {provider})")
    
    parser = PydanticOutputParser(pydantic_object=LLMJudgment)
    
    system_prompt = """Tu es un **évaluateur expert** chargé de juger la qualité des outputs d'un agent IA de développement.

Ton rôle est de comparer:
1. **L'output généré par l'agent** (réponse ou Pull Request)
2. **L'output attendu** (réponse de référence ou PR de référence)

Tu dois évaluer selon des **critères spécifiques** et attribuer:
- Un **score global /100**
- Des **scores par critère /100**
- Un **raisonnement détaillé**

## Principes d'évaluation:

### Pour les QUESTIONS (Dataset 1):
- **Pertinence** (25%): La réponse répond-elle à la question?
- **Précision technique** (30%): Les informations sont-elles correctes?
- **Clarté** (20%): La réponse est-elle compréhensible?
- **Utilisation du contexte** (25%): L'agent a-t-il bien utilisé le contexte du projet?

### Pour les COMMANDES (Dataset 2):
- **Implémentation** (35%): La fonctionnalité est-elle correctement implémentée?
- **Qualité du code** (30%): Le code est-il propre, maintenable, bien structuré?
- **Tests** (20%): Des tests appropriés sont-ils présents?
- **Documentation** (15%): Le PR est-il bien documenté?

## Barème de notation:
- **90-100**: Excellent - Dépasse les attentes
- **75-89**: Très bon - Répond aux attentes
- **60-74**: Acceptable - Répond partiellement aux attentes
- **40-59**: Insuffisant - Nécessite des améliorations importantes
- **0-39**: Très insuffisant - Ne répond pas aux attentes

## Instructions:
1. Analyse l'output de l'agent avec attention
2. Compare avec l'output attendu
3. Évalue selon les critères fournis
4. Sois **objectif** mais **constructif**
5. Fournis des suggestions d'amélioration concrètes

{format_instructions}
"""
    
    user_prompt = """## 📋 ÉVALUATION À EFFECTUER

### Type de test:
{test_type}

### Input de l'agent:
```
{input_text}
```

### Contexte additionnel:
{input_context}

### Output généré par l'agent:
```
{agent_output}
```

### Output attendu (référence):
```
{expected_output}
```

### Critères d'évaluation à utiliser:
{criteria}

---

**Effectue maintenant ton évaluation détaillée en remplissant tous les champs demandés.**
"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_prompt)
    ])
    
    llm = get_llm_with_fallback(
        primary_provider=provider,
        fallback_providers=["openai"] if fallback_to_openai and provider != "openai" else None
    )
    
    chain = prompt | llm | parser
    
    logger.info("✅ LLM Judge chain créée avec succès")
    
    return chain


async def evaluate_with_llm_judge(
    test_type: str,
    input_text: str,
    input_context: Dict[str, Any],
    agent_output: str,
    expected_output: str,
    criteria: List[str],
    provider: str = "anthropic",
    fallback_to_openai: bool = True
) -> LLMJudgment:
    """
    Évalue un output de l'agent en utilisant le LLM Judge.
    
    Args:
        test_type: Type de test (question ou commande)
        input_text: Input donné à l'agent
        input_context: Contexte de l'input
        agent_output: Output généré par l'agent
        expected_output: Output attendu
        criteria: Critères d'évaluation
        provider: Provider LLM
        fallback_to_openai: Utiliser fallback
        
    Returns:
        LLMJudgment avec score et raisonnement
    """
    logger.info("⚖️ Évaluation avec LLM Judge...")
    logger.info(f"   Test type: {test_type}")
    logger.info(f"   Critères: {len(criteria)}")
    
    try:
        chain = create_llm_judge_chain(provider, fallback_to_openai)
        
        criteria_str = "\n".join([f"- {c}" for c in criteria])
        context_str = "\n".join([f"- {k}: {v}" for k, v in input_context.items()])
        
        parser = PydanticOutputParser(pydantic_object=LLMJudgment)
        
        judgment = await chain.ainvoke({
            "test_type": test_type,
            "input_text": input_text,
            "input_context": context_str if context_str else "Aucun contexte additionnel",
            "agent_output": agent_output,
            "expected_output": expected_output,
            "criteria": criteria_str,
            "format_instructions": parser.get_format_instructions()
        })
        
        logger.info(f"✅ Évaluation terminée: Score {judgment.score}/100")
        logger.info(f"   Reasoning: {judgment.reasoning[:100]}...")
        
        return judgment
    
    except Exception as e:
        logger.error(f"❌ Erreur évaluation LLM Judge: {e}", exc_info=True)
        raise

