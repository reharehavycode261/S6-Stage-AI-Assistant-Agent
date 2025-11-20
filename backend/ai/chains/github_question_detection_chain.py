from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GitHubQuestionAnalysis(BaseModel):
    is_github_question: bool = Field(
        description="True si la question nécessite des informations depuis l'API GitHub (PRs, owner, issues, contributors, etc.)"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Score de confiance de la classification (0.0 à 1.0)"
    )
    reasoning: str = Field(
        description="Explication courte de pourquoi c'est (ou pas) une question GitHub"
    )


def create_github_question_detection_chain(provider: str = "anthropic"):
    logger.info(f"🔗 Création chain détection questions GitHub (provider: {provider})")
    
    if provider.lower() == "anthropic":
        llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            anthropic_api_key=settings.anthropic_api_key,
            temperature=0.1,  
            max_tokens=500
        )
        logger.info("✅ LLM Anthropic initialisé: claude-3-5-sonnet-20241022")
    else:
        llm = ChatOpenAI(
            model="gpt-4",
            openai_api_key=settings.openai_api_key,
            temperature=0.1,
            max_tokens=500
        )
        logger.info("✅ LLM OpenAI initialisé: gpt-4")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Tu es un assistant spécialisé dans la classification de questions.

Ta tâche est de déterminer si une question nécessite des informations depuis l'API GitHub pour y répondre.

**Questions GitHub** (is_github_question = True):
Ces questions nécessitent des informations que seule l'API GitHub peut fournir:
- Pull Requests: "De quoi parle le dernier PR?", "Quels fichiers ont changé dans le PR #66?", "Combien de PR ouvertes?"
- Owner/Repository: "Qui est l'owner?", "À qui appartient ce repo?", "Combien d'étoiles?"
- Issues: "Combien d'issues ouvertes?", "Quels bugs sont en cours?"
- Contributors: "Qui contribue?", "Qui a fait le plus de commits?"
- Activité: "Quand a eu lieu le dernier commit?", "Le projet est-il actif?"

**Questions NON-GitHub** (is_github_question = False):
Ces questions peuvent être répondues par l'analyse du code source du projet:
- Langages/Technologies: "Quel langage est utilisé?", "Quelles dépendances?"
- Architecture: "Comment est structuré le projet?", "Quelle architecture?"
- Code: "Comment fonctionne cette fonction?", "Où est définie la classe X?"
- Fonctionnalités: "Que fait ce projet?", "Comment utiliser ce module?"

RÈGLE SIMPLE:
- Si l'information vient des **métadonnées GitHub** (PRs, issues, stars, contributors) → True
- Si l'information vient du **code source analysé** → False"""),
        ("human", "Question: {question}")
    ])
    
    chain = prompt | llm.with_structured_output(GitHubQuestionAnalysis)
    
    logger.info("✅ Chain détection questions GitHub créée avec succès")
    return chain


async def detect_github_question(
    question: str,
    provider: str = "anthropic",
    fallback_to_openai: bool = True
) -> GitHubQuestionAnalysis:
    """
    Détecte si une question nécessite des informations GitHub via un LLM.
    
    Args:
        question: Question à analyser
        provider: Provider principal ("anthropic" ou "openai")
        fallback_to_openai: Si True, fallback vers OpenAI en cas d'échec
        
    Returns:
        Analyse structurée de la question
    """
    logger.info("🔍 Détection question GitHub via LLM...")
    logger.info(f"❓ Question: '{question[:100]}...'")
    
    try:
        chain = create_github_question_detection_chain(provider=provider)
        
        logger.info(f"🚀 Analyse avec {provider}...")
        analysis = await chain.ainvoke({"question": question})
        
        logger.info(f"✅ Détection terminée: is_github={analysis.is_github_question}, type={analysis.question_type}")
        logger.info(f"   Confiance: {analysis.confidence:.2f}")
        logger.info(f"   Raisonnement: {analysis.reasoning}")
        
        return analysis
    
    except Exception as e:
        logger.warning(f"⚠️ Échec détection avec {provider}: {e}")
        
        if fallback_to_openai and provider.lower() != "openai":
            try:
                logger.info("🔄 Fallback vers OpenAI...")
                chain_fallback = create_github_question_detection_chain(provider="openai")
                analysis = await chain_fallback.ainvoke({"question": question})
                
                logger.info(f"✅ Détection terminée (fallback): is_github={analysis.is_github_question}")
                return analysis
            
            except Exception as fallback_error:
                logger.error(f"❌ Fallback OpenAI échoué: {fallback_error}")
                return GitHubQuestionAnalysis(
                    is_github_question=False,
                    confidence=0.3,
                    reasoning="Erreur lors de la détection - défaut: pas une question GitHub"
                )
        
        logger.error(f"❌ Détection question GitHub échouée: {e}")
        return GitHubQuestionAnalysis(
            is_github_question=False,
            confidence=0.3,
            reasoning="Erreur lors de la détection - défaut: pas une question GitHub"
        )

