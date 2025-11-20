from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ai.llm.llm_factory import get_llm_with_fallback
from utils.logger import get_logger

logger = get_logger(__name__)


class IntentClassification(BaseModel):
    
    intent_type: str = Field(
        description="Type d'intention détecté: 'QUESTION' ou 'COMMAND'"
    )
    
    confidence: float = Field(
        description="Score de confiance de la classification (0.0 à 1.0)",
        ge=0.0,
        le=1.0
    )
    
    reasoning: str = Field(
        description="Explication courte de la décision de classification"
    )
    
    keywords_detected: list[str] = Field(
        default_factory=list,
        description="Mots-clés détectés qui ont influencé la classification"
    )


def create_intent_classification_chain(
    provider: str = "anthropic",
    model: Optional[str] = None,
    temperature: float = 0.0,  
    max_tokens: int = 500,
    fallback_to_openai: bool = True
):
    """
    Crée une chain LangChain pour classifier l'intention d'un message @vydata.
    
    Args:
        provider: Provider LLM principal ("anthropic" ou "openai")
        model: Modèle spécifique (optionnel)
        temperature: Température du modèle (0.0-1.0)
        max_tokens: Nombre maximum de tokens
        fallback_to_openai: Si True, utilise OpenAI en fallback si Anthropic échoue
        
    Returns:
        Chain LangChain configurée pour la classification d'intention
    """
    logger.info(f"🔗 Création chain classification d'intention (provider: {provider})")

    parser = PydanticOutputParser(pydantic_object=IntentClassification)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """Tu es un expert en classification d'intentions pour un agent IA de développement.

Ton rôle est de classifier les messages adressés à @vydata en deux catégories:

**QUESTION**: Demandes d'information, d'explication, sans modification de code
Exemples:
- "Pourquoi ce projet utilise Java?"
- "Comment fonctionne l'authentification?"  
- "Explique-moi l'architecture"
- "Qu'est-ce que fait cette fonction?"

Indicateurs: pourquoi, comment, qu'est-ce que, explique, décris, ?, interrogation

**COMMAND**: Demandes d'action, de modification de code
Exemples:
- "Ajoute un fichier README.md"
- "Crée une fonction update()"
- "Corrige le bug dans l'auth"
- "Modifie la configuration"

Indicateurs: ajoute, crée, modifie, supprime, implémente, corrige, update, impératif

{format_instructions}

Analyse le message et réponds UNIQUEMENT avec le JSON demandé."""),
        ("human", """Message à classifier:
"{message_text}"

Contexte de la tâche:
- Titre: {task_title}
- Description: {task_description}
- Statut: {task_status}

Classifie ce message.""")
    ])

    if fallback_to_openai and provider == "anthropic":
        llm = get_llm_with_fallback(
            primary_provider="anthropic",
            fallback_providers=["openai"],
            primary_model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
    else:
        from ai.llm.llm_factory import get_llm
        llm = get_llm(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

    chain = prompt | llm | parser
    
    logger.info(f"✅ Chain classification d'intention créée")
    
    return chain


async def classify_vydata_intent(
    message_text: str,
    task_context: Optional[Dict[str, Any]] = None,
    provider: str = "anthropic",
    fallback_to_openai: bool = True,
    model: Optional[str] = None
) -> IntentClassification:
    """
    Classifie l'intention d'un message @vydata.
    
    Args:
        message_text: Texte du message (sans le @vydata)
        task_context: Contexte optionnel de la tâche
        provider: Provider LLM à utiliser
        fallback_to_openai: Si True, utilise OpenAI en fallback
        model: Modèle spécifique (optionnel)
        
    Returns:
        IntentClassification avec le type, confiance et raisonnement
    """
    logger.info(f"🔍 Classification intention pour: '{message_text[:50]}...'")
    
    if task_context is None:
        task_context = {}
    
    task_title = task_context.get("title", "N/A")
    task_description = task_context.get("description", "N/A")[:200]
    task_status = task_context.get("internal_status", "N/A")
    
    chain = create_intent_classification_chain(
        provider=provider,
        model=model,
        fallback_to_openai=fallback_to_openai
    )
    
    parser = PydanticOutputParser(pydantic_object=IntentClassification)
    
    try:
        result = await chain.ainvoke({
            "message_text": message_text,
            "task_title": task_title,
            "task_description": task_description,
            "task_status": task_status,
            "format_instructions": parser.get_format_instructions()
        })
        
        logger.info(
            f"✅ Classification terminée: {result.intent_type} "
            f"(confiance: {result.confidence:.2f})"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur classification: {e}", exc_info=True)
        
        logger.warning("⚠️ Fallback sur classification par mots-clés")
        
        message_lower = message_text.lower()
        
        question_keywords = ["pourquoi", "comment", "qu'est-ce", "explique", "décris", "?"]
        question_count = sum(1 for kw in question_keywords if kw in message_lower)
        
        command_keywords = ["ajoute", "crée", "modifie", "supprime", "implémente", "corrige"]
        command_count = sum(1 for kw in command_keywords if kw in message_lower)
        
        if question_count > command_count or "?" in message_text:
            return IntentClassification(
                intent_type="QUESTION",
                confidence=0.6,
                reasoning=f"Fallback mots-clés: question détectée ({question_count} indicateurs)",
                keywords_detected=[kw for kw in question_keywords if kw in message_lower]
            )
        elif command_count > question_count:
            return IntentClassification(
                intent_type="COMMAND",
                confidence=0.6,
                reasoning=f"Fallback mots-clés: commande détectée ({command_count} indicateurs)",
                keywords_detected=[kw for kw in command_keywords if kw in message_lower]
            )
        else:
            return IntentClassification(
                intent_type="UNKNOWN",
                confidence=0.3,
                reasoning="Fallback mots-clés: intention incertaine",
                keywords_detected=[]
            )


def extract_classification_metrics(classification: IntentClassification) -> Dict[str, Any]:

    return {
        "intent_type": classification.intent_type,
        "confidence": classification.confidence,
        "keywords_count": len(classification.keywords_detected),
        "has_high_confidence": classification.confidence >= 0.7,
        "has_medium_confidence": 0.5 <= classification.confidence < 0.7,
        "has_low_confidence": classification.confidence < 0.5
    }
