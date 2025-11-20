from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ErrorCategory(str, Enum):
    IMPORT_ERROR = "import_error"
    SYNTAX_ERROR = "syntax_error"
    TYPE_ERROR = "type_error"
    ATTRIBUTE_ERROR = "attribute_error"
    NAME_ERROR = "name_error"
    ASSERTION_ERROR = "assertion_error"
    VALUE_ERROR = "value_error"
    KEY_ERROR = "key_error"
    INDEX_ERROR = "index_error"
    RUNTIME_ERROR = "runtime_error"
    LOGIC_ERROR = "logic_error"
    STYLE_ERROR = "style_error"
    CONFIGURATION_ERROR = "configuration_error"
    DEPENDENCY_ERROR = "dependency_error"
    OTHER = "other"


class ErrorPriority(int, Enum):
    CRITICAL = 5  
    HIGH = 4      
    MEDIUM = 3    
    LOW = 2       
    TRIVIAL = 1   


class FixStrategy(str, Enum):
    ADD_IMPORT = "add_import"
    FIX_SYNTAX = "fix_syntax"
    ADD_ATTRIBUTE = "add_attribute"
    UPDATE_TYPE = "update_type"
    ADD_DEPENDENCY = "add_dependency"
    REFACTOR_LOGIC = "refactor_logic"
    UPDATE_CONFIG = "update_config"
    FIX_TEST = "fix_test"
    ADD_ERROR_HANDLING = "add_error_handling"
    MULTIPLE_ACTIONS = "multiple_actions"


class ErrorInstance(BaseModel):
    error_message: str = Field(description="Message d'erreur complet")
    file_path: Optional[str] = Field(default=None, description="Chemin du fichier concerné")
    line_number: Optional[int] = Field(default=None, description="Numéro de ligne")
    test_name: Optional[str] = Field(default=None, description="Nom du test en échec")


class ErrorGroup(BaseModel):
    category: ErrorCategory = Field(description="Catégorie d'erreur")
    
    group_summary: str = Field(
        description="Résumé du groupe d'erreurs"
    )
    
    files_involved: List[str] = Field(
        default_factory=list,
        description="Fichiers impliqués dans ce groupe d'erreurs"
    )
    
    probable_root_cause: str = Field(
        description="Cause racine probable du groupe d'erreurs"
    )
    
    priority: ErrorPriority = Field(
        description="Priorité de correction (1-5, 5=critique)"
    )
    
    suggested_fix_strategy: FixStrategy = Field(
        description="Stratégie de correction suggérée"
    )
    
    fix_description: str = Field(
        description="Description détaillée de la correction à appliquer"
    )
    
    error_instances: List[ErrorInstance] = Field(
        default_factory=list,
        description="Instances d'erreurs individuelles dans ce groupe"
    )
    
    estimated_fix_time_minutes: int = Field(
        ge=1,
        description="Temps estimé pour corriger en minutes"
    )
    
    dependencies: List[str] = Field(
        default_factory=list,
        description="Dépendances à ce groupe (autres groupes à corriger d'abord)"
    )
    
    impact_scope: str = Field(
        description="Étendue de l'impact (local, module, global)"
    )


class ErrorClassification(BaseModel):
    """Modèle Pydantic pour la classification complète des erreurs."""
    
    total_errors: int = Field(description="Nombre total d'erreurs détectées")
    
    groups: List[ErrorGroup] = Field(
        min_length=1,
        description="Groupes d'erreurs identifiés"
    )
    
    reduction_percentage: float = Field(
        ge=0.0,
        le=100.0,
        description="Pourcentage de réduction du nombre d'actions"
    )
    
    recommended_fix_order: List[int] = Field(
        description="Ordre recommandé de correction (indices des groupes)"
    )
    
    critical_blockers: List[str] = Field(
        default_factory=list,
        description="Bloqueurs critiques identifiés"
    )
    
    estimated_total_fix_time: int = Field(
        description="Temps total estimé pour toutes les corrections en minutes"
    )
    
    overall_complexity: str = Field(
        description="Complexité globale des corrections (simple, moderate, complex)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_errors": 5,
                "groups": [
                    {
                        "category": "import_error",
                        "group_summary": "Imports manquants dans 3 fichiers",
                        "files_involved": ["test_api.py", "api/routes.py"],
                        "probable_root_cause": "Module 'fastapi' non importé",
                        "priority": 5,
                        "suggested_fix_strategy": "add_import",
                        "fix_description": "Ajouter 'from fastapi import FastAPI' en tête de fichier",
                        "error_instances": [
                            {
                                "error_message": "NameError: name 'FastAPI' is not defined",
                                "file_path": "api/routes.py",
                                "line_number": 10
                            }
                        ],
                        "estimated_fix_time_minutes": 2,
                        "dependencies": [],
                        "impact_scope": "module"
                    }
                ],
                "reduction_percentage": 40.0,
                "recommended_fix_order": [0, 1],
                "critical_blockers": ["Import manquant bloque l'exécution"],
                "estimated_total_fix_time": 10,
                "overall_complexity": "simple"
            }
        }


def create_debug_error_classification_chain(
    provider: str = "anthropic",
    model: Optional[str] = None,
    temperature: float = 0.0,  
    max_tokens: int = 3000
):
    """
    Crée une chaîne LCEL pour classifier et regrouper les erreurs.
    
    Args:
        provider: Provider LLM à utiliser ("anthropic" ou "openai")
        model: Nom du modèle (optionnel, utilise le défaut du provider)
        temperature: Température du modèle (0.0-1.0)
        max_tokens: Nombre maximum de tokens
        
    Returns:
        Chaîne LCEL configurée (Prompt → LLM → Parser)
        
    Raises:
        ValueError: Si le provider n'est pas supporté
        Exception: Si les clés API sont manquantes
    """
    logger.info(f"🔗 Création debug_error_classification_chain avec provider={provider}")

    parser = PydanticOutputParser(pydantic_object=ErrorClassification)

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """Tu es un expert en analyse d'erreurs de code qui classifie et regroupe les erreurs pour optimiser les corrections.

Ton objectif est d'identifier les patterns d'erreurs, de les regrouper intelligemment, et de proposer une stratégie de correction efficace.

IMPORTANT: Tu DOIS retourner UNIQUEMENT du JSON valide, sans texte avant ou après.
Utilise le schéma suivant:

{format_instructions}

Principes de classification:
1. REGROUPE les erreurs similaires ou liées
2. IDENTIFIE la cause racine commune
3. PRIORISE selon l'impact (ImportError > AssertionError > Style)
4. ORDONNE les corrections par dépendances
5. ESTIME le temps de correction réaliste
6. PROPOSE une stratégie de correction claire"""),
        ("user", """Analyse et classifie ces erreurs:

## LOGS DE TESTS
```
{test_logs}
```

## STACK TRACES
```
{stack_traces}
```

## DIFF RÉCENT
```
{recent_diff}
```

## FICHIERS MODIFIÉS
{modified_files}

## CONTEXTE ADDITIONNEL
{additional_context}

Classe ces erreurs en groupes cohérents et propose une stratégie de correction optimisée.""")
    ])
    
    prompt = prompt_template.partial(format_instructions=parser.get_format_instructions())
    
    if provider.lower() == "anthropic":
        if not settings.anthropic_api_key:
            raise Exception("ANTHROPIC_API_KEY manquante dans la configuration")
        
        llm = ChatAnthropic(
            model=model or "claude-3-5-sonnet-20241022",
            anthropic_api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=max_tokens
        )
        logger.info(f"✅ LLM Anthropic initialisé: {model or 'claude-3-5-sonnet-20241022'}")
        
    elif provider.lower() == "openai":
        if not settings.openai_api_key:
            raise Exception("OPENAI_API_KEY manquante dans la configuration")
        
        llm = ChatOpenAI(
            model=model or "gpt-4",
            openai_api_key=settings.openai_api_key,
            temperature=temperature,
            max_tokens=max_tokens
        )
        logger.info(f"✅ LLM OpenAI initialisé: {model or 'gpt-4'}")
        
    else:
        raise ValueError(f"Provider non supporté: {provider}. Utilisez 'anthropic' ou 'openai'")
    
    chain = prompt | llm | parser
    
    logger.info("✅ Debug error classification chain créée avec succès")
    return chain


async def classify_debug_errors(
    test_logs: str,
    stack_traces: Optional[str] = None,
    recent_diff: Optional[str] = None,
    modified_files: Optional[List[str]] = None,
    additional_context: Optional[Dict[str, Any]] = None,
    provider: str = "anthropic",
    fallback_to_openai: bool = True
) -> ErrorClassification:
    """
    Classifie et regroupe les erreurs de debug pour optimiser les corrections.
    
    Args:
        test_logs: Logs des tests en échec
        stack_traces: Stack traces des erreurs (optionnel)
        recent_diff: Diff récent du code (optionnel)
        modified_files: Liste des fichiers récemment modifiés (optionnel)
        additional_context: Contexte additionnel (dict)
        provider: Provider principal ("anthropic" ou "openai")
        fallback_to_openai: Si True, fallback vers OpenAI si le provider principal échoue
        
    Returns:
        ErrorClassification validé par Pydantic
        
    Raises:
        Exception: Si tous les providers échouent
    """
    context_str = str(additional_context) if additional_context else "Aucun contexte additionnel"
    files_str = "\n".join(f"- {f}" for f in (modified_files or [])) if modified_files else "Non spécifiés"
    
    inputs = {
        "test_logs": test_logs or "Non disponibles",
        "stack_traces": stack_traces or "Non disponibles",
        "recent_diff": recent_diff or "Non disponible",
        "modified_files": files_str,
        "additional_context": context_str
    }
    
    try:
        logger.info(f"🚀 Classification des erreurs avec {provider}...")
        chain = create_debug_error_classification_chain(provider=provider)
        classification = await chain.ainvoke(inputs)
        
        logger.info(
            f"✅ Classification générée: "
            f"{classification.total_errors} erreurs → {len(classification.groups)} groupes "
            f"(réduction: {classification.reduction_percentage:.1f}%)"
        )
        return classification
        
    except Exception as e:
        logger.warning(f"⚠️ Échec classification avec {provider}: {e}")
        
        if fallback_to_openai and provider.lower() != "openai":
            try:
                logger.info("🔄 Fallback vers OpenAI...")
                chain_fallback = create_debug_error_classification_chain(provider="openai")
                classification = await chain_fallback.ainvoke(inputs)
                
                logger.info(f"✅ Classification générée avec succès (fallback OpenAI)")
                return classification
                
            except Exception as fallback_error:
                logger.error(f"❌ Fallback OpenAI échoué: {fallback_error}")
                raise Exception(
                    f"Tous les providers ont échoué. "
                    f"Principal: {e}, Fallback: {fallback_error}"
                )
        
        raise Exception(f"Classification échouée avec {provider}: {e}")


def extract_classification_metrics(classification: ErrorClassification) -> Dict[str, Any]:
    priority_distribution = {}
    for group in classification.groups:
        priority_name = f"priority_{group.priority}"
        priority_distribution[priority_name] = priority_distribution.get(priority_name, 0) + 1
    
    category_distribution = {}
    for group in classification.groups:
        category = group.category.value
        category_distribution[category] = category_distribution.get(category, 0) + 1
    
    total_instances = sum(len(g.error_instances) for g in classification.groups)
    
    return {
        "total_errors": classification.total_errors,
        "total_groups": len(classification.groups),
        "total_error_instances": total_instances,
        "reduction_percentage": classification.reduction_percentage,
        "actions_before": classification.total_errors,
        "actions_after": len(classification.groups),
        "priority_distribution": priority_distribution,
        "category_distribution": category_distribution,
        "critical_blockers_count": len(classification.critical_blockers),
        "estimated_total_fix_time": classification.estimated_total_fix_time,
        "average_fix_time_per_group": (
            classification.estimated_total_fix_time / len(classification.groups)
            if classification.groups else 0
        ),
        "overall_complexity": classification.overall_complexity,
        "has_critical_errors": any(
            g.priority == ErrorPriority.CRITICAL for g in classification.groups
        )
    }


def get_priority_ordered_groups(classification: ErrorClassification) -> List[ErrorGroup]:
    if classification.recommended_fix_order:
        try:
            return [classification.groups[i] for i in classification.recommended_fix_order]
        except IndexError:
            logger.warning("⚠️ Ordre recommandé invalide, tri par priorité")
    return sorted(classification.groups, key=lambda g: g.priority, reverse=True)

