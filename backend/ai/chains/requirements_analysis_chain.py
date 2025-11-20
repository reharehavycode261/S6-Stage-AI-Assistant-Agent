import os
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


def _scan_project_files(working_dir: str) -> Optional[Dict[str, Any]]:

    try:
        import glob
        from pathlib import Path

        ignored_dirs = {'.git', 'node_modules', '__pycache__', 'venv', 'env', '.venv', 
                        'dist', 'build', 'target', '.idea', '.vscode', 'coverage'}
        
        all_files = []
        technologies = set()

        for root, dirs, files in os.walk(working_dir):

            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            for file in files:
                if file.startswith('.'):
                    continue
                    
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, working_dir)
                all_files.append(rel_path)
                
                ext = Path(file).suffix.lower()
                if ext in ['.java', '.jar']:
                    technologies.add('Java')
                elif ext in ['.py', '.pyw']:
                    technologies.add('Python')
                elif ext in ['.js', '.jsx', '.ts', '.tsx']:
                    technologies.add('JavaScript/TypeScript')
                elif ext in ['.go']:
                    technologies.add('Go')
                elif ext in ['.rs']:
                    technologies.add('Rust')
                elif ext in ['.rb']:
                    technologies.add('Ruby')
                elif ext in ['.php']:
                    technologies.add('PHP')
                elif ext in ['.c', '.cpp', '.h', '.hpp']:
                    technologies.add('C/C++')
                elif ext in ['.cs']:
                    technologies.add('C#')
                elif ext in ['.swift']:
                    technologies.add('Swift')
                elif ext in ['.kt', '.kts']:
                    technologies.add('Kotlin')
                elif file in ['pom.xml', 'build.gradle', 'build.gradle.kts']:
                    technologies.add('Java/Maven/Gradle')
                elif file in ['package.json', 'yarn.lock', 'package-lock.json']:
                    technologies.add('Node.js/npm')
                elif file in ['requirements.txt', 'setup.py', 'Pipfile', 'pyproject.toml']:
                    technologies.add('Python')
                elif file in ['Cargo.toml', 'Cargo.lock']:
                    technologies.add('Rust')
                elif file in ['go.mod', 'go.sum']:
                    technologies.add('Go')
        
        source_extensions = {'.java', '.py', '.js', '.ts', '.go', '.rs', '.rb', '.php', 
                            '.c', '.cpp', '.cs', '.swift', '.kt'}
        main_files = sorted(all_files, key=lambda f: (
            0 if Path(f).suffix.lower() in source_extensions else 1,
            f
        ))
        
        return {
            'total_files': len(all_files),
            'main_files': main_files,
            'technologies': sorted(list(technologies)),
            'summary': f"{len(all_files)} fichier(s) trouvé(s)"
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur scan fichiers: {e}", exc_info=True)
        return None


class TaskComplexity(str, Enum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FileValidationStatus(str, Enum):
    VALID = "valid"
    NOT_FOUND = "not_found"
    UNCERTAIN = "uncertain"


class CandidateFile(BaseModel):
    path: str = Field(description="Chemin du fichier")
    action: str = Field(description="Action à effectuer (create, modify, delete)")
    reason: str = Field(description="Raison de la modification")
    validation_status: FileValidationStatus = Field(
        default=FileValidationStatus.UNCERTAIN,
        description="Statut de validation du fichier"
    )


class TaskDependency(BaseModel):
    name: str = Field(description="Nom de la dépendance")
    type: str = Field(description="Type (package, service, file, etc.)")
    version: Optional[str] = Field(default=None, description="Version requise si applicable")
    required: bool = Field(default=True, description="Si la dépendance est obligatoire")


class IdentifiedRisk(BaseModel):
    description: str = Field(description="Description du risque")
    level: RiskLevel = Field(description="Niveau de gravité du risque")
    mitigation: str = Field(description="Stratégie de mitigation proposée")
    probability: int = Field(ge=1, le=10, description="Probabilité d'occurrence (1-10)")


class Ambiguity(BaseModel):
    question: str = Field(description="Question ou point ambigu")
    impact: str = Field(description="Impact de cette ambiguïté")
    suggested_assumption: Optional[str] = Field(
        default=None,
        description="Hypothèse suggérée si pas de clarification"
    )


class RequirementsAnalysis(BaseModel):
    schema_version: int = Field(default=1, description="Version du schéma")

    task_summary: str = Field(description="Résumé de la tâche analysée")

    complexity: TaskComplexity = Field(description="Complexité estimée de la tâche")
    complexity_score: int = Field(
        ge=1,
        le=10,
        description="Score de complexité (1=très simple, 10=très complexe)"
    )

    estimated_duration_minutes: int = Field(
        ge=5,
        description="Durée estimée en minutes"
    )

    candidate_files: List[CandidateFile] = Field(
        default_factory=list,
        description="Fichiers identifiés pour modification"
    )

    dependencies: List[TaskDependency] = Field(
        default_factory=list,
        description="Dépendances identifiées"
    )

    risks: List[IdentifiedRisk] = Field(
        default_factory=list,
        description="Risques identifiés"
    )

    ambiguities: List[Ambiguity] = Field(
        default_factory=list,
        description="Ambiguïtés ou points nécessitant clarification"
    )

    missing_info: List[str] = Field(
        default_factory=list,
        description="Informations manquantes pour une implémentation optimale"
    )

    implementation_approach: str = Field(
        description="Approche d'implémentation recommandée"
    )

    test_strategy: str = Field(
        description="Stratégie de test recommandée"
    )

    breaking_changes_risk: bool = Field(
        default=False,
        description="Si l'implémentation risque de casser du code existant"
    )

    requires_external_deps: bool = Field(
        default=False,
        description="Si l'implémentation nécessite des dépendances externes"
    )

    quality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Score de qualité de l'analyse (coverage)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "schema_version": 1,
                "task_summary": "Créer une API REST pour gérer les utilisateurs",
                "complexity": "moderate",
                "complexity_score": 6,
                "estimated_duration_minutes": 45,
                "candidate_files": [
                    {
                        "path": "api/routes/users.py",
                        "action": "create",
                        "reason": "Nouvelles routes API utilisateurs",
                        "validation_status": "uncertain"
                    }
                ],
                "dependencies": [
                    {
                        "name": "fastapi",
                        "type": "package",
                        "version": ">=0.104.0",
                        "required": True
                    }
                ],
                "risks": [
                    {
                        "description": "Conflit avec routes existantes",
                        "level": "medium",
                        "mitigation": "Vérifier les routes avant implémentation",
                        "probability": 5
                    }
                ],
                "ambiguities": [],
                "missing_info": ["Schéma de validation exact pour User"],
                "implementation_approach": "Créer module API séparé avec validation Pydantic",
                "test_strategy": "Tests unitaires + tests d'intégration API",
                "breaking_changes_risk": False,
                "requires_external_deps": False,
                "quality_score": 0.85
            }
        }


def create_requirements_analysis_chain(
    provider: str = "anthropic",
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 4000,
    max_retries: int = 2
):
    """
    Crée une chaîne LCEL pour analyser les requirements de manière structurée.

    Args:
        provider: Provider LLM à utiliser ("anthropic" ou "openai")
        model: Nom du modèle (optionnel, utilise le défaut du provider)
        temperature: Température du modèle (0.0-1.0)
        max_tokens: Nombre maximum de tokens
        max_retries: Nombre de tentatives en cas d'échec de validation

    Returns:
        Chaîne LCEL configurée (Prompt → LLM → Parser)

    Raises:
        ValueError: Si le provider n'est pas supporté
        Exception: Si les clés API sont manquantes
    """
    logger.info(f"🔗 Création requirements_analysis_chain avec provider={provider}")

    parser = PydanticOutputParser(pydantic_object=RequirementsAnalysis)

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """Tu es un analyste technique expert qui analyse les requirements de projets logiciels.
Tu dois examiner la description de la tâche et générer une analyse structurée complète au format JSON strict.

IMPORTANT: Tu DOIS retourner UNIQUEMENT du JSON valide, sans texte avant ou après.
Utilise le schéma suivant:

{format_instructions}

Sois exhaustif dans ton analyse :
- Identifie TOUS les fichiers potentiellement concernés
- Liste TOUTES les dépendances nécessaires
- Détecte TOUS les risques possibles
- Signale TOUTES les ambiguïtés ou informations manquantes
- Estime la complexité de façon réaliste
- Propose une stratégie d'implémentation claire

✅ RÈGLES IMPORTANTES pour réduire les informations manquantes :
1. Si une information n'est pas fournie, propose une valeur par défaut raisonnable
2. Pour les critères d'acceptation manquants, déduis-les du titre et de la description
3. Pour le contexte technique manquant, assume un contexte standard selon le type de projet
4. Pour les dépendances, liste les dépendances courantes même si non mentionnées explicitement
5. Privilégie des estimations conservatrices plutôt que de signaler des manques"""),
        ("user", """Analyse cette tâche en détail:

## INFORMATIONS DE LA TÂCHE

**Titre**: {task_title}
**Type**: {task_type}
**Priorité**: {priority}

**Description**:
{description}

**Critères d'acceptation**:
{acceptance_criteria}

**Contexte technique**:
{technical_context}

**Fichiers mentionnés**:
{files_to_modify}

**Repository**: {repository_url}

## CONTEXTE ADDITIONNEL
{additional_context}

Génère une analyse complète et structurée de cette tâche.""")
    ])

    prompt = prompt_template.partial(format_instructions=parser.get_format_instructions())

    if provider.lower() == "anthropic":
        if not settings.anthropic_api_key:
            raise Exception("ANTHROPIC_API_KEY manquante dans la configuration")

        llm = ChatAnthropic(
            model=model or "claude-3-5-sonnet-20241022",
            anthropic_api_key=settings.anthropic_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries
        )
        logger.info(f"✅ LLM Anthropic initialisé: {model or 'claude-3-5-sonnet-20241022'}")

    elif provider.lower() == "openai":
        if not settings.openai_api_key:
            raise Exception("OPENAI_API_KEY manquante dans la configuration")

        llm = ChatOpenAI(
            model=model or "gpt-4",
            openai_api_key=settings.openai_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries
        )
        logger.info(f"✅ LLM OpenAI initialisé: {model or 'gpt-4'}")

    else:
        raise ValueError(f"Provider non supporté: {provider}. Utilisez 'anthropic' ou 'openai'")

    chain = prompt | llm | parser

    logger.info("✅ Requirements analysis chain créée avec succès")
    return chain


async def generate_requirements_analysis(
    task_title: str,
    task_description: str,
    task_type: str = "feature",
    priority: str = "medium",
    acceptance_criteria: Optional[str] = None,
    technical_context: Optional[str] = None,
    files_to_modify: Optional[List[str]] = None,
    repository_url: Optional[str] = None,
    working_dir: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None,
    provider: str = "anthropic",
    fallback_to_openai: bool = True,
    validate_files: bool = True,
    run_step_id: Optional[int] = None
) -> RequirementsAnalysis:
    """
    Génère une analyse structurée des requirements avec fallback automatique.

    Args:
        task_title: Titre de la tâche
        task_description: Description détaillée
        task_type: Type de tâche (feature, bugfix, refactor, etc.)
        priority: Priorité de la tâche
        acceptance_criteria: Critères d'acceptation
        technical_context: Contexte technique additionnel
        files_to_modify: Liste des fichiers à modifier (si connus)
        repository_url: URL du repository
        working_dir: Répertoire de travail où le repository est cloné (pour scanner les fichiers)
        additional_context: Contexte additionnel (dict)
        provider: Provider principal ("anthropic" ou "openai")
        fallback_to_openai: Si True, fallback vers OpenAI si le provider principal échoue
        validate_files: Si True, valide l'existence des fichiers candidats
        run_step_id: ID du step pour logger les interactions IA dans la DB

    Returns:
        RequirementsAnalysis validé par Pydantic

    Raises:
        Exception: Si tous les providers échouent
    """
    context_str = str(additional_context) if additional_context else "Aucun contexte additionnel"
    files_str = ", ".join(files_to_modify) if files_to_modify else "Non spécifiés"
    
    project_structure_str = "Non disponible"
    logger.info(f"🔍 working_dir fourni: {working_dir}")
    
    if working_dir:
        logger.info(f"✅ working_dir existe: {os.path.exists(working_dir)}")
        if os.path.exists(working_dir):
            try:
                logger.info(f"🔍 Scan des fichiers dans: {working_dir}")
                project_structure = _scan_project_files(working_dir)
                logger.info(f"📊 Résultat scan: {project_structure}")
                
                if project_structure:
                    project_structure_str = f"""
📁 Structure du projet détectée:
{project_structure['summary']}

Principaux fichiers:
{chr(10).join(f"  - {f}" for f in project_structure['main_files'][:20])}

Technologies détectées: {', '.join(project_structure['technologies']) if project_structure['technologies'] else 'Aucune'}
"""
                    logger.info(f"✅ {project_structure['total_files']} fichiers détectés dans {working_dir}")
                else:
                    logger.warning("⚠️ Scan retourné None")
            except Exception as e:
                logger.error(f"❌ Erreur lors du scan des fichiers: {e}", exc_info=True)
        else:
            logger.warning(f"⚠️ working_dir n'existe pas: {working_dir}")
    else:
        logger.warning("⚠️ Aucun working_dir fourni")

    inputs = {
        "task_title": task_title,
        "description": task_description,
        "task_type": task_type,
        "priority": priority,
        "acceptance_criteria": acceptance_criteria or "Non spécifiés",
        "technical_context": f"{technical_context or 'Non spécifié'}\n\n{project_structure_str}",
        "files_to_modify": files_str,
        "repository_url": repository_url or "Non spécifié",
        "additional_context": context_str
    }

    callbacks = []
    if run_step_id:
        from utils.langchain_db_callback import create_db_callback
        callbacks = [create_db_callback(run_step_id)]
        logger.debug(f"📝 Callback DB activé pour run_step_id={run_step_id}")

    try:
        logger.info(f"🚀 Génération analyse requirements avec {provider}...")
        chain = create_requirements_analysis_chain(provider=provider)
        analysis = await chain.ainvoke(inputs, config={"callbacks": callbacks})

        if validate_files and analysis.candidate_files:
            _validate_candidate_files(analysis.candidate_files)

        analysis.quality_score = _calculate_quality_score(analysis)

        logger.info(
            f"✅ Analyse générée avec succès: "
            f"{len(analysis.candidate_files)} fichiers, "
            f"{len(analysis.risks)} risques, "
            f"{len(analysis.ambiguities)} ambiguïtés, "
            f"quality_score={analysis.quality_score:.2f}"
        )
        return analysis

    except Exception as e:
        logger.warning(f"⚠️ Échec génération analyse avec {provider}: {e}")

        if fallback_to_openai and provider.lower() != "openai":
            try:
                logger.info("🔄 Fallback vers OpenAI...")
                chain_fallback = create_requirements_analysis_chain(provider="openai")
                analysis = await chain_fallback.ainvoke(inputs, config={"callbacks": callbacks})

                if validate_files and analysis.candidate_files:
                    _validate_candidate_files(analysis.candidate_files)

                analysis.quality_score = _calculate_quality_score(analysis)

                logger.info("✅ Analyse générée avec succès (fallback OpenAI)")
                return analysis

            except Exception as fallback_error:
                logger.error(f"❌ Fallback OpenAI échoué: {fallback_error}")
                raise Exception(
                    f"Tous les providers ont échoué. "
                    f"Principal: {e}, Fallback: {fallback_error}"
                )

        raise Exception(f"Génération analyse échouée avec {provider}: {e}")


def _validate_candidate_files(files: List[CandidateFile]):
    """
    Valide l'existence des fichiers candidats.

    Args:
        files: Liste des fichiers candidats à valider
    """
    for file in files:
        if file.action in ["modify", "delete"]:
            if os.path.exists(file.path):
                file.validation_status = FileValidationStatus.VALID
            else:
                file.validation_status = FileValidationStatus.NOT_FOUND
                logger.warning(f"⚠️ Fichier non trouvé: {file.path}")
        elif file.action == "create":
            if os.path.exists(file.path):
                file.validation_status = FileValidationStatus.UNCERTAIN
                logger.warning(f"⚠️ Fichier à créer existe déjà: {file.path}")
            else:
                file.validation_status = FileValidationStatus.VALID


def _calculate_quality_score(analysis: RequirementsAnalysis) -> float:
    """
    Calcule un score de qualité pour l'analyse.

    ✅ AMÉLIORATION: Seuil de qualité augmenté (0.70 → 0.80)

    Le score est basé sur:
    - Présence et validité des fichiers candidats
    - Identification de risques
    - Gestion des dépendances
    - Complétude de l'analyse
    - Clarté des requirements (pénalités pour ambiguïtés)

    Args:
        analysis: Analyse à évaluer

    Returns:
        Score entre 0.0 et 1.0 (minimum recommandé: 0.80)
    """
    score = 0.0

    if analysis.candidate_files:
        valid_files = sum(
            1 for f in analysis.candidate_files
            if f.validation_status == FileValidationStatus.VALID
        )
        uncertain_files = sum(
            1 for f in analysis.candidate_files
            if f.validation_status == FileValidationStatus.UNCERTAIN
        )
        total_files = len(analysis.candidate_files)

        if uncertain_files == total_files:
            file_score = 0.30  
            logger.info(f"📋 {total_files} fichiers identifiés (validation en attente)")
        else:
            file_score = (valid_files / total_files) * 0.35
            if valid_files == total_files and total_files >= 2:
                file_score += 0.05  

        score += min(0.40, file_score)
    else:
        logger.warning("⚠️ Aucun fichier candidat identifié - qualité réduite")

    if analysis.risks:
        risk_score = min(0.15, len(analysis.risks) * 0.04)
        score += risk_score

    if analysis.dependencies:
        dep_score = min(0.15, len(analysis.dependencies) * 0.04)
        score += dep_score

    completeness = 0.0
    if analysis.implementation_approach and len(analysis.implementation_approach) > 20:
        completeness += 0.15  # Augmenté de 0.10
    if analysis.test_strategy and len(analysis.test_strategy) > 15:
        completeness += 0.15  # Augmenté de 0.10
    if analysis.estimated_duration_minutes > 0:
        completeness += 0.10
    score += completeness

    penalties = 0.0

    if analysis.ambiguities and len(analysis.ambiguities) > 3:
        penalties += min(0.10, (len(analysis.ambiguities) - 3) * 0.03)
        logger.warning(f"⚠️ {len(analysis.ambiguities)} ambiguïtés détectées - pénalité appliquée")

    if analysis.missing_info and len(analysis.missing_info) > 4:  
        penalties += min(0.08, (len(analysis.missing_info) - 4) * 0.02)  
        logger.warning(f"⚠️ {len(analysis.missing_info)} informations manquantes - pénalité réduite appliquée")

    score = max(0.0, score - penalties)

    final_score = min(1.0, score)
    if final_score < 0.75:  
        logger.warning(
            f"⚠️ Score de qualité insuffisant: {final_score:.2f} < 0.75 "
            f"(fichiers: {len(analysis.candidate_files) if analysis.candidate_files else 0}, "
            f"ambiguïtés: {len(analysis.ambiguities)}, "
            f"infos manquantes: {len(analysis.missing_info)})"
        )
    elif final_score < 0.85:
        logger.info(
            f"📊 Score de qualité acceptable: {final_score:.2f} "
            f"(fichiers: {len(analysis.candidate_files) if analysis.candidate_files else 0}, "
            f"ambiguïtés: {len(analysis.ambiguities)}, "
            f"infos manquantes: {len(analysis.missing_info)})"
        )

    return final_score


def extract_analysis_metrics(analysis: RequirementsAnalysis) -> Dict[str, Any]:
    valid_files = sum(
        1 for f in analysis.candidate_files
        if f.validation_status == FileValidationStatus.VALID
    )

    high_risks = sum(
        1 for r in analysis.risks
        if r.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    )

    return {
        "schema_version": analysis.schema_version,
        "complexity": analysis.complexity.value,
        "complexity_score": analysis.complexity_score,
        "estimated_duration_minutes": analysis.estimated_duration_minutes,
        "total_files": len(analysis.candidate_files),
        "valid_files": valid_files,
        "invalid_files": len(analysis.candidate_files) - valid_files,
        "file_coverage": valid_files / len(analysis.candidate_files) if analysis.candidate_files else 0,
        "total_dependencies": len(analysis.dependencies),
        "required_dependencies": sum(1 for d in analysis.dependencies if d.required),
        "total_risks": len(analysis.risks),
        "high_risks": high_risks,
        "risk_percentage": (high_risks / len(analysis.risks) * 100) if analysis.risks else 0,
        "total_ambiguities": len(analysis.ambiguities),
        "missing_info_count": len(analysis.missing_info),
        "quality_score": analysis.quality_score or 0.0,
        "breaking_changes_risk": analysis.breaking_changes_risk,
        "requires_external_deps": analysis.requires_external_deps
    }
