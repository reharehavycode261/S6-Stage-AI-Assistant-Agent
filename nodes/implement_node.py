"""Nœud d'implémentation - génère et applique le code."""

from typing import Dict, Any, List, Optional, Tuple
from models.state import GraphState
from anthropic import Client
from openai import AsyncOpenAI
from config.settings import get_settings
from tools.claude_code_tool import ClaudeCodeTool
from utils.logger import get_logger
from utils.persistence_decorator import with_persistence, log_code_generation_decorator
from utils.helpers import get_working_directory, validate_working_directory, ensure_working_directory
import os

logger = get_logger(__name__)


async def _call_llm_with_fallback(anthropic_client: Client, openai_client: AsyncOpenAI, prompt: str, max_tokens: int = 4000) -> Tuple[str, str]:
    """
    Appelle le LLM avec fallback automatique Anthropic → OpenAI.
    
    Returns:
        Tuple[content, provider_used]
    """
    try:
        logger.info("🚀 Tentative avec Anthropic...")
        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.content[0].text
        logger.info("✅ Anthropic réussi")
        return content, "anthropic"
    except Exception as e:
        logger.warning(f"⚠️ Anthropic échoué: {e}")
        
        if openai_client:
            try:
                logger.info("🔄 Fallback vers OpenAI...")
                response = await openai_client.chat.completions.create(
                    model="gpt-4o",
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.choices[0].message.content
                logger.info("✅ OpenAI fallback réussi")
                return content, "openai"
            except Exception as e2:
                logger.error(f"❌ OpenAI fallback échoué: {e2}")
                raise Exception(f"Anthropic et OpenAI ont échoué. Anthropic: {e}, OpenAI: {e2}")
        else:
            logger.error("❌ Pas de fallback OpenAI disponible")
            raise Exception(f"Anthropic échoué et pas de fallback OpenAI: {e}")

@with_persistence("implement_task")
@log_code_generation_decorator("claude", "claude-3-5-sonnet-20241022", "initial")
async def implement_task(state: GraphState) -> GraphState:
    """
    Nœud d'implémentation: génère et applique le code nécessaire.
    
    Ce nœud :
    1. Analyse les requirements et le contexte technique
    2. Génère un plan d'implémentation avec Claude
    3. Applique les modifications nécessaires
    4. Valide que l'implémentation répond aux critères
    
    Args:
        state: État actuel du graphe
        
    Returns:
        État mis à jour avec l'implémentation
    """
    logger.info(f"💻 Implémentation de: {state['task'].title}")

    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    state["results"]["ai_messages"].append("Début de l'implémentation...")
    
    try:
        settings = get_settings()
        claude_tool = ClaudeCodeTool()
        anthropic_client = Client(api_key=settings.anthropic_api_key)
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        task = state["task"]

        if not task:

            logger.error("❌ Aucune tâche fournie")

            return state
        



        if "results" not in state:

            state["results"] = {}
        working_directory = get_working_directory(state)
        
        if not validate_working_directory(working_directory, "implement_node"):
            try:
                working_directory = ensure_working_directory(state, "implement_node_")
                logger.info(f"📁 Répertoire de travail de secours créé: {working_directory}")
            except Exception as e:
                error_msg = f"Impossible de créer un répertoire de travail pour l'implémentation: {e}"
                logger.error(f"❌ {error_msg}")
                state["results"]["error_logs"].append(error_msg)
                state["results"]["ai_messages"].append(f"❌ {error_msg}")
                state["results"]["last_operation_result"] = error_msg
                state["results"]["should_continue"] = False
                state["results"]["current_status"] = "failed".lower()
                return state
        
        if not working_directory:
            error_msg = "Aucun répertoire de travail disponible pour l'implémentation"
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["should_continue"] = False
            state["results"]["current_status"] = "failed".lower()
            return state
        
        if not os.path.exists(working_directory):
            error_msg = f"Répertoire de travail introuvable: {working_directory}"
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ {error_msg}")
            state["results"]["should_continue"] = False
            state["results"]["current_status"] = "failed".lower()
            return state
        
        if "code_changes" not in state["results"] or not isinstance(state["results"]["code_changes"], dict):
            state["results"]["code_changes"] = {}

        if "modified_files" not in state["results"] or not isinstance(state["results"]["modified_files"], list):
            state["results"]["modified_files"] = []
        
        from tools.ai_engine_hub import ai_hub, AIRequest, TaskType
        
        claude_tool.working_directory = working_directory
        
        logger.info("📋 Analyse de la structure du projet...")
        try:
            project_analysis_dict = await _analyze_project_structure(claude_tool)
            project_analysis = {
                "language_info": project_analysis_dict.get("language_info"),  
                "project_type": project_analysis_dict.get("project_type", "unknown"),
                "structure": project_analysis_dict.get("structure_text", ""),
                "files": project_analysis_dict.get("files", []),
                "main_language": project_analysis_dict.get("main_language", "Unknown"),
                "confidence": project_analysis_dict.get("confidence", 0.0),  
                "extensions": project_analysis_dict.get("extensions", []),  
                "build_files": project_analysis_dict.get("build_files", []),  
                "error": None
            }
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de l'analyse du projet: {e}")
            project_analysis = {
                "language_info": None,
                "project_type": "unknown",
                "structure": "Analyse échouée",
                "files": [],
                "main_language": "Unknown",
                "confidence": 0.0,
                "extensions": [],
                "build_files": [],
                "error": str(e)
            }
        
        detected_type = project_analysis.get('project_type', 'unknown')
        detected_lang = project_analysis.get('main_language', 'Unknown')
        detected_confidence = project_analysis.get('confidence', 0.0)
        
        logger.info(f"📊 Langage détecté: {detected_lang} ({detected_type})")
        logger.info(f"📊 Confiance: {detected_confidence:.2f}")
        
        if detected_type == "unknown":
            logger.warning("⚠️ Type de projet non détecté - le code généré pourrait être incorrect!")
            state["results"]["ai_messages"].append("⚠️ Type de projet non détecté - génération de code risquée")
        elif detected_confidence < 0.7:
            logger.warning(f"⚠️ Confiance faible ({detected_confidence:.2f}) - vérifier le langage détecté")
            state["results"]["ai_messages"].append(f"⚠️ Confiance de détection: {detected_confidence:.2f} - validation recommandée")
        else:
            logger.info(f"✅ Détection réussie: {detected_lang} (confiance: {detected_confidence:.2f})")
            state["results"]["ai_messages"].append(f"✅ Langage détecté: {detected_lang}")
        
        if "enhanced_info" in project_analysis and project_analysis["enhanced_info"]:
            enhanced = project_analysis["enhanced_info"]
            logger.info("=" * 60)
            logger.info("🤖 ANALYSE LLM DU PROJET")
            logger.info("=" * 60)
            logger.info(f"Type: {enhanced.project_type}")
            logger.info(f"Framework: {enhanced.framework or 'Aucun'}")
            logger.info(f"Architecture: {enhanced.architecture}")
            logger.info(f"Stack: {', '.join(enhanced.tech_stack)}")
            logger.info(f"Description: {enhanced.description[:100]}...")
            logger.info("=" * 60)
            
            state["results"]["ai_messages"].append(f"🤖 Framework détecté: {enhanced.framework or 'Aucun'}")
            state["results"]["ai_messages"].append(f"🤖 Architecture: {enhanced.architecture}")
        
        logger.info("=" * 70)
        logger.info("🔍 PHASE D'EXPLORATION APPROFONDIE DU REPOSITORY")
        logger.info("=" * 70)
        
        from utils.repository_explorer import RepositoryExplorer
        
        explorer = RepositoryExplorer(working_directory)
        exploration_result = await explorer.explore_for_task(
            task_description=task.description,
            files_mentioned=task.files_to_modify if hasattr(task, 'files_to_modify') else None,
            max_files_to_read=15
        )
        
        repository_context = explorer.build_context_summary(exploration_result)
        
        state["results"]["repository_context"] = exploration_result
        state["results"]["repository_context_summary"] = repository_context
        
        logger.info(f"✅ Exploration terminée: {len(exploration_result['files_read'])} fichiers analysés")
        logger.info(f"✅ {len(exploration_result['patterns_detected'])} patterns détectés")
        state["results"]["ai_messages"].append(f"🔍 Repository exploré: {len(exploration_result['files_read'])} fichiers analysés")
        
        logger.info("=" * 70)
        
        previous_errors = state["results"].get("error_logs", []) if hasattr(state, "results") else []
        implementation_prompt = await _create_implementation_prompt(
            task, 
            project_analysis.get("structure", "Structure non disponible"), 
            previous_errors,
            language_info=project_analysis.get("language_info"),  
            repository_context=repository_context,  
            state=state  
        )
        
        logger.info("🤖 Génération du plan d'implémentation avec le moteur IA...")
        
        structured_plan = None
        plan_metrics = None
        use_legacy_plan = False
        
        try:
            from ai.chains.implementation_plan_chain import (
                generate_implementation_plan,
                extract_plan_metrics
            )
            
            logger.info("🔗 Tentative génération plan structuré via LangChain...")
            state["results"]["ai_messages"].append("🔗 Génération plan structuré...")
            
            run_step_id = state.get("db_step_id")
            structured_plan = await generate_implementation_plan(
                task_title=task.title,
                task_description=task.description,
                task_type=str(task.task_type) if hasattr(task, 'task_type') else "feature",
                additional_context={
                    "project_analysis": project_analysis.get("structure", "Non disponible"),
                    "previous_errors": previous_errors[-3:] if previous_errors else []
                },
                provider="openai",
                fallback_to_openai=True,
                run_step_id=run_step_id
            )
            
            plan_metrics = extract_plan_metrics(structured_plan)
            
            state["results"]["implementation_plan_structured"] = structured_plan.dict()
            state["results"]["implementation_plan_metrics"] = plan_metrics
            
            logger.info(f"✅ Plan structuré généré: {plan_metrics['total_steps']} étapes, complexité={plan_metrics['total_complexity']}")
            state["results"]["ai_messages"].append(
                f"✅ Plan structuré: {plan_metrics['total_steps']} étapes, "
                f"complexité totale={plan_metrics['total_complexity']}, "
                f"risques élevés={plan_metrics['high_risk_steps_count']}"
            )
            
            implementation_plan = _convert_structured_plan_to_text(structured_plan)
            
        except Exception as e:
            logger.warning(f"⚠️ Échec génération plan structuré via LangChain: {e}")
            logger.info("🔄 Fallback vers génération plan legacy...")
            state["results"]["ai_messages"].append("⚠️ Plan structuré échoué, utilisation méthode classique")
            use_legacy_plan = True
        
        if use_legacy_plan or structured_plan is None:
            logger.info("🤖 Génération du plan d'implémentation (méthode legacy)...")
            
            ai_request = AIRequest(
                prompt=implementation_prompt,
                task_type=TaskType.CODE_GENERATION,
                context={
                    "task": task.dict(), 
                    "project_analysis": project_analysis,
                    "workflow_id": state.get("workflow_id", "unknown"),
                    "task_id": task.task_id
                }
            )
            
            try:
                response = await ai_hub.generate_code(ai_request)
            except Exception as e:
                error_msg = f"Erreur lors de l'appel au moteur IA: {e}"
                state["results"]["error_logs"].append(error_msg)
                state["results"]["ai_messages"].append(f"❌ {error_msg}")
                state["results"]["should_continue"] = False
                state["results"]["current_status"] = "failed"
                return state
            
            if not response.success:
                error_msg = f"Erreur lors de la génération du plan: {response.error}"
                state["results"]["error_logs"].append(error_msg)
                state["results"]["ai_messages"].append(f"❌ {error_msg}")
                state["results"]["last_operation_result"] = error_msg
                state["results"]["should_continue"] = False
                state["results"]["current_status"] = "failed".lower()
                return state
            
            implementation_plan = response.content
            state["results"]["ai_messages"].append(f"📋 Plan généré (legacy):\n{implementation_plan[:200]}...")
        
        success = await _execute_implementation_plan(
            claude_tool, anthropic_client, openai_client, implementation_plan, task, state
        )
        
        implementation_result = _validate_implementation_result(success, state)
        
        if implementation_result["success"]:
            state["results"]["ai_messages"].append("✅ Implémentation terminée avec succès")
            state["results"]["last_operation_result"] = "Implémentation réussie"
            state["results"]["implementation_success"] = True
            state["results"]["current_status"] = "implemented"
            state["results"]["implementation_metrics"] = implementation_result["metrics"]
            logger.info(f"✅ Implémentation terminée avec succès - {implementation_result['summary']}")
        else:
            failure_reason = implementation_result.get("failure_reason", "Raison inconnue")
            state["results"]["ai_messages"].append(f"❌ Échec de l'implémentation: {failure_reason}")
            state["results"]["last_operation_result"] = f"Échec implémentation: {failure_reason}"
            state["results"]["implementation_success"] = False
            state["results"]["current_status"] = "implementation_failed"
            state["results"]["implementation_error_details"] = implementation_result.get("error_details", {})
            logger.error(f"❌ Échec de l'implémentation: {failure_reason}")
        
        state["results"]["should_continue"] = True
        state["results"]["workflow_stage"] = "implementation_completed"
        
    except Exception as e:
        error_msg = f"Exception critique lors de l'implémentation: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ Exception critique: {error_msg}")
        state["results"]["last_operation_result"] = error_msg
        state["results"]["implementation_success"] = False 
        state["results"]["current_status"] = "implementation_exception"
        state["results"]["workflow_stage"] = "implementation_failed"
        state["results"]["should_continue"] = True
    
    logger.info("🏁 Implémentation terminée")
    return state


def _validate_implementation_result(success: bool, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valide et enrichit le résultat d'implémentation avec des métriques détaillées.
    
    Args:
        success: Résultat brut de l'implémentation
        state: État du workflow pour extraire les métriques
        
    Returns:
        Dictionnaire avec les détails de validation et métriques
    """
    result = {
        "success": False,
        "failure_reason": None,
        "error_details": {},
        "metrics": {},
        "summary": ""
    }
    
    try:
        results = state.get("results", {})
        
        modified_files = results.get("modified_files", [])
        code_changes = results.get("code_changes", {})
        error_logs = results.get("error_logs", [])
        
        result["metrics"] = {
            "files_modified": len(modified_files),
            "code_changes_count": len(code_changes),
            "error_count": len(error_logs),
            "has_errors": len(error_logs) > 0
        }
        
        if success:
            if len(modified_files) == 0 and len(code_changes) == 0:
                result["success"] = False
                result["failure_reason"] = "Aucun fichier modifié détecté malgré le succès apparent"
                result["error_details"]["validation"] = "No files were actually modified"
            elif len(error_logs) > 0:
                result["success"] = True
                result["summary"] = f"{len(modified_files)} fichier(s) modifié(s) avec {len(error_logs)} avertissement(s)"
                logger.warning(f"⚠️ Implémentation réussie mais avec {len(error_logs)} erreur(s)")
            else:
                result["success"] = True
                result["summary"] = f"{len(modified_files)} fichier(s) modifié(s) sans erreur"
        else:
            if len(error_logs) > 0:
                result["failure_reason"] = f"Erreurs détectées: {error_logs[-1]}"  # Dernière erreur
                result["error_details"]["last_error"] = error_logs[-1]
                result["error_details"]["total_errors"] = len(error_logs)
            else:
                result["failure_reason"] = "Échec sans erreur spécifique détectée"
                result["error_details"]["analysis"] = "No specific error found in logs"
        
        if "started_at" in state:
            result["metrics"]["execution_context"] = {
                "started_at": state["started_at"],
                "workflow_id": state.get("workflow_id", "unknown")
            }
            
    except Exception as e:
        logger.error(f"❌ Erreur validation résultat implémentation: {e}")
        result["success"] = False
        result["failure_reason"] = f"Erreur de validation: {str(e)}"
        result["error_details"]["validation_error"] = str(e)
    
    return result

async def _analyze_project_structure(claude_tool: ClaudeCodeTool) -> Dict[str, Any]:
    """
    Analyse la structure du projet avec enrichissement LLM.
    
    Combine détection automatique + analyse LLM pour cas complexes.
    """
    try:
        ls_result = await claude_tool._arun(
            action="execute_command", 
            command="find . -type f -not -path './.git/*' -not -path './venv/*' -not -path './node_modules/*' | head -50"
        )
        
        structure_info = "Structure du projet:\n"
        files_found = []
        
        if ls_result["success"]:
            structure_info += ls_result["stdout"]
            files_found = ls_result["stdout"].strip().split('\n') if ls_result["stdout"].strip() else []
        
        readme_content = None
        try:
            readme_result = await claude_tool._arun(action="read_file", file_path="README.md", required=False)
            if readme_result["success"]:
                readme_content = readme_result.get("content", "")[:2000]
        except:
            pass
        
        package_json_content = None
        try:
            pkg_result = await claude_tool._arun(action="read_file", file_path="package.json", required=False)
            if pkg_result["success"]:
                package_json_content = pkg_result.get("content", "")[:1000]
        except:
            pass
        
        requirements_content = None
        try:
            req_result = await claude_tool._arun(action="read_file", file_path="requirements.txt", required=False)
            if req_result["success"]:
                requirements_content = req_result.get("content", "")[:1000]
        except:
            pass
        
        from utils.llm_enhanced_detector import detect_project_with_llm
        
        logger.info("🤖 Analyse du projet avec enrichissement LLM...")
        
        enhanced_info = await detect_project_with_llm(
            files=files_found,
            readme_content=readme_content,
            package_json_content=package_json_content,
            requirements_txt_content=requirements_content,
            use_llm=True  # Activer l'analyse LLM
        )
        
        logger.info(f"📊 Langage principal: {enhanced_info.primary_language.name} (confiance: {enhanced_info.confidence:.2f})")
        logger.info(f"📊 Type de projet: {enhanced_info.project_type}")
        logger.info(f"📊 Framework: {enhanced_info.framework or 'Aucun'}")
        logger.info(f"📊 Stack technique: {', '.join(enhanced_info.tech_stack)}")
        logger.info(f"📊 Architecture: {enhanced_info.architecture}")
        
        if enhanced_info.secondary_languages:
            logger.info(f"📊 Langages secondaires: {', '.join(enhanced_info.secondary_languages)}")
        
        return {
            "language_info": enhanced_info.primary_language,
            "enhanced_info": enhanced_info,  # ✨ NOUVEAU
            "project_type": enhanced_info.primary_language.type_id,
            "structure_text": structure_info,
            "files": files_found,
            "main_language": enhanced_info.primary_language.name,
            "confidence": enhanced_info.confidence,
            "extensions": enhanced_info.primary_language.primary_extensions,
            "build_files": enhanced_info.primary_language.build_files,
            "conventions": enhanced_info.primary_language.conventions,
            # Nouvelles informations enrichies
            "detected_framework": enhanced_info.framework,
            "detected_project_type": enhanced_info.project_type,
            "tech_stack": enhanced_info.tech_stack,
            "architecture": enhanced_info.architecture,
            "llm_recommendations": enhanced_info.recommendations
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'analyse du projet: {e}", exc_info=True)
        from utils.language_detector import detect_language, LanguageInfo
        
        basic_detection = detect_language(files_found if 'files_found' in locals() else [])
        
        return {
            "language_info": basic_detection,
            "enhanced_info": None,
            "project_type": basic_detection.type_id,
            "structure_text": "Structure du projet non disponible",
            "files": [],
            "main_language": basic_detection.name,
            "confidence": basic_detection.confidence,
            "extensions": basic_detection.primary_extensions,
            "build_files": basic_detection.build_files,
            "conventions": basic_detection.conventions
        }

async def _create_implementation_prompt(
    task, 
    project_analysis: str, 
    error_logs: List[str],
    language_info=None,  
    repository_context: Optional[str] = None,  
    state: Optional[Dict[str, Any]] = None  
) -> str:
    """
    Crée un prompt détaillé pour l'implémentation avec instructions adaptatives.
    
    Args:
        task: Tâche à implémenter
        project_analysis: Analyse du projet (texte)
        error_logs: Erreurs précédentes
        language_info: Objet LanguageInfo du détecteur (si disponible)
        repository_context: Contexte riche du repository (code lu et analysé)
        state: État du workflow (pour récupérer instructions de modification)
    
    Returns:
        Prompt complet avec instructions adaptatives
    """
    extracted_specs = _extract_technical_specifications(task.description)
    
    if language_info:
        from utils.instruction_generator import get_adaptive_prompt_supplement
        
        language_instructions = get_adaptive_prompt_supplement(language_info)
        main_language = language_info.name
        project_type = language_info.type_id
        confidence = language_info.confidence
    else:
        logger.warning("⚠️ Aucune info de langage disponible - utilisation d'instructions génériques")
        language_instructions = """
⚠️ TYPE DE PROJET NON DÉTECTÉ

Analyse le code existant pour identifier:
- Le langage de programmation utilisé
- Les conventions de nommage
- La structure des fichiers
- Les build tools

Puis génère du code cohérent avec le projet existant.
"""
        main_language = "Unknown"
        project_type = "unknown"
        confidence = 0.0
    
    prompt = f"""Tu es un développeur expert. Tu dois implémenter la tâche suivante dans un projet existant.

{language_instructions}

## TÂCHE À IMPLÉMENTER
**Titre**: {task.title}

**Description complète**: 
{task.description}

**Spécifications techniques extraites**:
{extracted_specs}

**Branche**: {task.branch_name}
**Priorité**: {task.priority}"""
    
    if state and state.get("results", {}).get("modification_instructions"):
        modification_instructions = state["results"]["modification_instructions"]
        rejection_count = state["results"].get("rejection_count", 1)
        
        import re
        clean_instructions = re.sub(r'<[^>]+>', '', modification_instructions)
        
        prompt += f"""

## ⚠️ INSTRUCTIONS DE MODIFICATION HUMAINE (PRIORITÉ ABSOLUE)

**Ce code a été rejeté par un humain ({rejection_count}/3 rejets).**

**Instructions spécifiques de l'humain**:
{clean_instructions}

**⚠️ TU DOIS IMPÉRATIVEMENT**:
1. Prendre en compte TOUTES les demandes de l'humain ci-dessus
2. Modifier/compléter le code existant selon ces instructions
3. NE PAS ignorer ou oublier aucune partie de la demande humaine
4. Vérifier que chaque point demandé est bien implémenté

Ces instructions sont PLUS IMPORTANTES que la description de la tâche originale.
"""
    
    prompt += f"""

## CONTEXTE DU PROJET
{project_analysis}"""
    
    enhanced_info = project_analysis.get('enhanced_info') if isinstance(project_analysis, dict) else None
    if enhanced_info and hasattr(enhanced_info, 'description'):
        prompt += f"""

## 🤖 ANALYSE ENRICHIE DU PROJET

**Type de projet détecté**: {enhanced_info.project_type}
**Framework**: {enhanced_info.framework or 'Aucun framework spécifique détecté'}
**Architecture**: {enhanced_info.architecture}
**Stack technique complète**: {', '.join(enhanced_info.tech_stack)}

**Description du projet**:
{enhanced_info.description}

**Recommandations du LLM pour l'implémentation**:
"""
        for i, rec in enumerate(enhanced_info.recommendations, 1):
            prompt += f"\n{i}. {rec}"
        
        if enhanced_info.secondary_languages:
            prompt += f"""

**⚠️ ATTENTION - Langages secondaires détectés**: {', '.join(enhanced_info.secondary_languages)}
Assure-toi que ton implémentation est compatible avec ces langages si nécessaire.
"""
    
    if repository_context:
        prompt += f"""

{repository_context}

⚠️ **RÈGLE ABSOLUE**: Tu DOIS respecter STRICTEMENT les patterns, conventions et architecture détectés ci-dessus.
Le code généré doit s'intégrer parfaitement dans le code existant.
"""
    
    prompt += f"""

## HISTORIQUE D'ERREURS (si tentatives précédentes)
{chr(10).join(error_logs) if error_logs else "Aucune erreur précédente"}

## INSTRUCTIONS DÉTAILLÉES

1. **Analyse** d'abord le code existant pour comprendre l'architecture
2. **Identifie** les patterns et conventions utilisés dans le projet
3. **Extrait** les spécifications exactes de la description (endpoints, fonctionnalités, etc.)
4. **Planifie** les modifications nécessaires en respectant l'architecture existante
5. **Implémente** les changements de manière incrémentale EN {main_language}

Réponds avec un plan d'implémentation structuré sous cette forme:

```
PLAN D'IMPLÉMENTATION

## 1. ANALYSE DE LA TÂCHE
- [Ce que tu comprends exactement de la demande]
- [Spécifications techniques identifiées]
- [Architecture cible à implémenter]

## 2. ANALYSE DU PROJET EXISTANT
- [Fichiers importants identifiés]
- [Patterns et conventions observés]
- [Architecture actuelle comprise]

## 3. MODIFICATIONS REQUISES
### Nouveaux fichiers à créer:
- [Liste des nouveaux fichiers avec leur rôle]

### Fichiers existants à modifier:
- [Liste des fichiers à modifier avec description des changements]

## 4. ÉTAPES D'EXÉCUTION DÉTAILLÉES
1. [Première étape avec commandes/modifications précises]
2. [Deuxième étape avec commandes/modifications précises]
3. [etc.]

## 5. TESTS ET VALIDATION
- [Tests ou validations à effectuer]
- [Comment vérifier que l'implémentation fonctionne]
```

**IMPORTANT**: Sois extrêmement précis dans l'extraction des spécifications. Si la description mentionne un endpoint spécifique, assure-toi de l'implémenter exactement comme demandé."""

    return prompt


def _extract_technical_specifications(description: str) -> str:
    """Extrait les spécifications techniques d'une description de tâche."""
    import re
    
    specs = []
    
    endpoint_patterns = [
        r'endpoint\s+["`]([^"`]+)["`]',
        r'endpoint\s+([/\w-]+)',
        r'API\s+["`]([^"`]+)["`]',
        r'route\s+["`]([^"`]+)["`]',
        r'(/\w+(?:/\w+)*)',  
    ]
    
    for pattern in endpoint_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        for match in matches:
            if match.startswith('/'):
                specs.append(f"• Endpoint à créer: {match}")
    
    feature_patterns = [
        (r'visualiser\s+([^.]+)', "• Fonctionnalité de visualisation: {}"),
        (r'monitorer\s+([^.]+)', "• Fonctionnalité de monitoring: {}"),
        (r'tracker?\s+([^.]+)', "• Fonctionnalité de tracking: {}"),
        (r'dashboard\s+([^.]+)', "• Dashboard à créer: {}"),
        (r'rapport\s+([^.]+)', "• Rapport à générer: {}"),
        (r'afficher\s+([^.]+)', "• Affichage requis: {}"),
    ]
    
    for pattern, template in feature_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        for match in matches:
            specs.append(template.format(match.strip()))
    
    tech_patterns = [
        (r'FastAPI', "• Utiliser FastAPI pour les endpoints"),
        (r'React', "• Interface React requise"),
        (r'Vue', "• Interface Vue.js requise"),
        (r'PostgreSQL', "• Base de données PostgreSQL"),
        (r'MongoDB', "• Base de données MongoDB"),
        (r'REST API', "• API REST à implémenter"),
        (r'GraphQL', "• API GraphQL à implémenter"),
    ]
    
    for pattern, spec in tech_patterns:
        if re.search(pattern, description, re.IGNORECASE):
            specs.append(spec)
    
    data_patterns = [
        (r'coûts?\s+([^.]+)', "• Données de coûts: {}"),
        (r'métriques?\s+([^.]+)', "• Métriques: {}"),
        (r'statistiques?\s+([^.]+)', "• Statistiques: {}"),
        (r'logs?\s+([^.]+)', "• Logs: {}"),
    ]
    
    for pattern, template in data_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        for match in matches:
            specs.append(template.format(match.strip()))
    
    provider_patterns = [
        (r'provider[s]?\s+([^.]+)', "• Providers: {}"),
        (r'service[s]?\s+([^.]+)', "• Services: {}"),
        (r'(Claude|OpenAI|Anthropic)', "• Provider IA: {}"),
    ]
    
    for pattern, template in provider_patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        for match in matches:
            specs.append(template.format(match.strip()))
    
    if not specs:
        specs.append("• Aucune spécification technique spécifique détectée")
        specs.append("• Analyse manuelle de la description requise")
    
    return "\n".join(specs)

async def _execute_implementation_plan(
    claude_tool: ClaudeCodeTool, 
    anthropic_client: Client,
    openai_client: AsyncOpenAI,
    implementation_plan: str,
    task,
    state: Dict[str, Any]
) -> bool:
    """Exécute le plan d'implémentation étape par étape."""
    
    try:
        logger.info("🚀 Exécution du plan d'implémentation...")
        
        language_info = state.get("results", {}).get("language_info")
        language_specific_instructions = ""
        
        if language_info and hasattr(language_info, 'name'):
            from utils.instruction_generator import get_adaptive_prompt_supplement
            language_specific_instructions = f"""

## 🎯 INSTRUCTIONS SPÉCIFIQUES AU LANGAGE {language_info.name.upper()}

{get_adaptive_prompt_supplement(language_info)}

⚠️ RESPECTE STRICTEMENT ces conventions et patterns pour {language_info.name}.
"""
        
        repository_context_exec = state.get("results", {}).get("repository_context_summary", "")
        if repository_context_exec:
            language_specific_instructions += f"""

{repository_context_exec}
"""
        
        execution_prompt = f"""🚀 TU DOIS MAINTENANT IMPLÉMENTER LA FONCTIONNALITÉ EN MODIFIANT LES FICHIERS !

⚠️ **MISSION CRITIQUE** : IMPLÉMENTE la fonctionnalité demandée en CRÉANT/MODIFIANT les fichiers du projet.
Tu ne dois PAS juste lire ou analyser, tu dois ÉCRIRE DU CODE FONCTIONNEL.

PLAN À IMPLÉMENTER:
{implementation_plan}

FONCTIONNALITÉ À IMPLÉMENTER:
{task.description}

{language_specific_instructions}

⚠️ IMPORTANT: Tu travailles dans un repository Git DÉJÀ CLONÉ. 
- NE PAS utiliser 'git clone' - le repository est déjà disponible localement
- NE PAS créer de nouveaux répertoires pour le repository
- Travaille directement dans le répertoire actuel

🎯 RÈGLES ABSOLUES - AUCUNE EXCEPTION:
1. ❌ NE JAMAIS utiliser execute_command avec cat/echo/touch pour créer/modifier des fichiers
2. ✅ TOUJOURS utiliser action:modify_file pour CRÉER ou MODIFIER un fichier
3. ✅ Tu DOIS générer du code COMPLET et FONCTIONNEL (pas de TODO, pas de placeholders)
4. ✅ Si un fichier existe déjà, action:modify_file le remplacera complètement
5. ✅ RESPECTE STRICTEMENT les conventions et patterns du code existant

Pour chaque fichier que tu dois CRÉER ou MODIFIER, utilise ce format EXACT:

```action:modify_file
file_path: chemin/vers/fichier.txt
description: Création du fichier avec son contenu
content:
[Le contenu COMPLET du fichier à créer/modifier]
```

📝 EXEMPLE CONCRET - AJOUTER UNE MÉTHODE count() À GenericDAO.java:

```action:modify_file
file_path: src/database/core/GenericDAO.java
description: Ajout de la méthode count() pour compter les enregistrements
content:
package database.core;

import java.sql.*;
import java.util.*;

public class GenericDAO<T> {{
    // ... code existant ...
    
    /**
     * Compte le nombre total d'enregistrements dans la table
     * @return Le nombre d'enregistrements
     * @throws SQLException en cas d'erreur SQL
     */
    public long count() throws SQLException {{
        String sql = "SELECT COUNT(*) FROM " + tableName;
        try (PreparedStatement stmt = connection.prepareStatement(sql);
             ResultSet rs = stmt.executeQuery()) {{
            if (rs.next()) {{
                return rs.getLong(1);
            }}
            return 0;
        }}
    }}
    
    // ... reste du code existant ...
}}
```

⚠️ **CE QU'IL NE FAUT JAMAIS FAIRE**:
❌ ```action:execute_command
command: cat src/database/core/GenericDAO.java
``` 
→ Ceci ne MODIFIE PAS le fichier, ça ne fait que le LIRE !

❌ ```action:execute_command
command: echo "code" >> GenericDAO.java
```
→ N'utilise JAMAIS echo/cat/touch pour modifier des fichiers !

✅ **CE QU'IL FAUT FAIRE**:
```action:modify_file
file_path: src/database/core/GenericDAO.java
description: Implémentation de la méthode count()
content:
[CODE COMPLET DU FICHIER AVEC LA NOUVELLE MÉTHODE]
```

🎯 COMMENCE MAINTENANT L'IMPLÉMENTATION avec action:modify_file !
Tu DOIS modifier les fichiers pour implémenter la fonctionnalité demandée."""

        execution_steps, provider_used = await _call_llm_with_fallback(
            anthropic_client, openai_client, execution_prompt, max_tokens=4000
        )
        
        logger.info(f"✅ Plan d'exécution généré avec {provider_used}")
        
        success = await _parse_and_execute_actions(claude_tool, execution_steps, state)
        
        return success
        
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du plan: {e}")
        state["results"]["error_logs"].append(f"Erreur exécution plan: {str(e)}")
        return False

async def _parse_and_execute_actions(claude_tool: ClaudeCodeTool, execution_text: str, state: Dict[str, Any]) -> bool:
    """Parse le texte d'exécution et effectue les actions."""
    
    import re
    import hashlib
    
    success_count = 0
    total_actions = 0
    
    action_patterns = [
        r'```action:(\w+)\n(.*?)\n```',
        r'```action:\s*(\w+)\n(.*?)```',
        r'```action:(\w+)(.*?)```',
        r'```(\w+)\s*#\s*action\n(.*?)```'
    ]
    
    actions = []
    for pattern in action_patterns:
        found_actions = re.findall(pattern, execution_text, re.DOTALL | re.MULTILINE)
        if found_actions:
            actions.extend(found_actions)
            logger.info(f"✅ {len(found_actions)} action(s) détectée(s) avec pattern: {pattern[:30]}...")
    
    if not actions:
        logger.warning("⚠️ Aucune action structurée détectée - analyse du contenu...")
        actions = await _detect_implicit_actions(execution_text)
    
    seen_actions = set()
    deduplicated_actions = []
    duplicate_count = 0
    duplicate_types = []
    
    for action_type, action_content in actions:
        action_hash = hashlib.md5(f"{action_type}:{action_content.strip()}".encode()).hexdigest()
        
        if action_hash in seen_actions:
            duplicate_count += 1
            duplicate_types.append(action_type)
            continue
        
        seen_actions.add(action_hash)
        deduplicated_actions.append((action_type, action_content))
    
    if duplicate_count > 0:
        from collections import Counter
        type_counts = Counter(duplicate_types)
        types_summary = ", ".join([f"{count}x {t}" for t, count in type_counts.items()])
        logger.info(f"🧹 {duplicate_count} action(s) dupliquée(s) ignorée(s) ({types_summary})")
    
    logger.info(f"📊 Actions uniques à exécuter: {len(deduplicated_actions)}")
    
    for action_type, action_content in deduplicated_actions:
        total_actions += 1
        logger.info(f"🔧 Exécution action: {action_type}")
        logger.debug(f"📄 Contenu action (premiers 200 chars): {action_content[:200]}...")
        
        try:
            if action_type == "modify_file" or action_type == "create_file" or action_type == "write_file":
                success = await _execute_file_modification(claude_tool, action_content, state)
            elif action_type == "execute_command" or action_type == "run_command":
                command_line = action_content.strip()
                if "command:" in command_line:
                    command_line = command_line.split("command:", 1)[1].strip()
                
                git_commands_blocked = ["git add", "git commit", "git push"]
                if any(cmd in command_line.lower() for cmd in git_commands_blocked):
                    logger.warning(f"⛔ Commande Git bloquée: {command_line[:50]}")
                    logger.info("💡 Les opérations Git (add/commit/push) sont gérées automatiquement par le nœud de finalisation")
                    success_count += 1
                    continue
                
                is_suspicious = False
                if "echo " in command_line.lower() and ">" in command_line:
                    is_suspicious = True
                elif "touch " in command_line.lower():
                    is_suspicious = True
                elif "cat " in command_line.lower() and (">" in command_line or ">>" in command_line):
                    is_suspicious = True
                
                if is_suspicious:
                    logger.warning(f"⚠️ Commande suspecte détectée: {command_line[:50]}...")
                    logger.warning("💡 Cette commande devrait probablement être une action:modify_file")
                
                success = await _execute_command_action(claude_tool, action_content, state)
            else:
                logger.warning(f"Type d'action non reconnu: {action_type}")
                continue
            
            if success:
                success_count += 1
            else:
                logger.warning(f"⚠️ Action {action_type} échouée - voir logs pour détails")
                
        except Exception as e:
            logger.error(f"❌ Exception lors de l'action {action_type}: {e}", exc_info=True)
            state["results"]["error_logs"].append(f"Erreur action {action_type}: {str(e)}")
    
    if total_actions == 0:
        logger.warning("⚠️ Aucune action structurée trouvée!")
        logger.info("🔍 Tentative de traitement direct du code...")
        
        code_blocks = re.findall(r'```(?:python|javascript|typescript|js|py|java|go|rust|html|css)?\n(.*?)\n```', execution_text, re.DOTALL)
        
        if code_blocks:
            logger.info(f"📦 {len(code_blocks)} bloc(s) de code détecté(s)")
            for idx, code_block in enumerate(code_blocks):
                if len(code_block.strip()) > 30:  
                    filename = _guess_filename_from_code(code_block, idx)
                    logger.info(f"📝 Traitement bloc {idx + 1}: {filename}")
                    
                    formatted_action = f"file_path: {filename}\ndescription: Code extrait automatiquement du bloc {idx + 1}\ncontent:\n{code_block}"
                    success = await _execute_file_modification(claude_tool, formatted_action, state)
                    
                    if success:
                        success_count += 1
                        total_actions += 1
            
            if total_actions > 0:
                logger.info(f"✅ {success_count}/{total_actions} bloc(s) traité(s) avec succès")
            else:
                logger.error("❌ Aucun bloc de code valide n'a pu être traité")
                state["results"]["error_logs"].append("Aucun fichier créé - blocs de code trop courts ou invalides")
                return False
        else:
            logger.error("❌ ÉCHEC CRITIQUE: Aucun code détecté dans la réponse de l'IA!")
            logger.error("💡 L'IA a peut-être juste décrit ce qu'il faut faire sans générer le code")
            state["results"]["error_logs"].append("ÉCHEC: L'IA n'a généré aucun code - elle a peut-être seulement fourni des instructions textuelles")
            return False
    
    success_rate = success_count / max(total_actions, 1)
    logger.info(f"📊 Actions exécutées: {success_count}/{total_actions} (taux: {success_rate:.1%})")
    
    return success_rate >= 0.5  

async def _detect_implicit_actions(execution_text: str) -> list:
    """
    Détecte les actions implicites dans le texte d'exécution.
    Utile quand Claude ne suit pas exactement le format demandé.
    ✅ AMÉLIORATION: Détection plus robuste des fichiers à créer/modifier.
    """
    import re
    
    actions = []
    
    file_with_code_pattern = r'(?:fichier|file|créer|create|modifier|modify|créez|modifiez|add|ajouter|aggiungi|hinzufügen)\s*[:`]?\s*([a-zA-Z0-9_./\\-]+\.[a-z]+)[:`]?\s*```(?:python|javascript|typescript|js|py|jsx|tsx|html|css|java|go|rust|cpp|c)?\n(.*?)```'
    
    matches = re.findall(file_with_code_pattern, execution_text, re.DOTALL | re.IGNORECASE)
    for file_path, code_content in matches:
        formatted_action = f"file_path: {file_path}\ndescription: Modification détectée implicitement\ncontent:\n{code_content}"
        actions.append(("modify_file", formatted_action))
        logger.info(f"🔍 Action implicite détectée: modifier {file_path}")
    
    file_path_pattern = r'(?:^|\n)([a-zA-Z0-9_./\\-]+\.[a-z]+)\s*:\s*\n```(?:python|javascript|typescript|js|py|jsx|tsx|html|css|java|go|rust)?\n(.*?)```'
    
    matches_2 = re.findall(file_path_pattern, execution_text, re.DOTALL | re.MULTILINE)
    for file_path, code_content in matches_2:
        formatted_action = f"file_path: {file_path}\ndescription: Fichier avec code détecté\ncontent:\n{code_content}"
        actions.append(("modify_file", formatted_action))
        logger.info(f"🔍 Fichier avec code détecté: {file_path}")
    
    if not actions:
        code_blocks = re.findall(r'```(?:python|javascript|typescript|js|py|java|go)?\n(.*?)```', execution_text, re.DOTALL)
        if code_blocks:
            for idx, code_block in enumerate(code_blocks):
                if len(code_block.strip()) > 50:  
                    filename = _guess_filename_from_code(code_block, idx)
                    formatted_action = f"file_path: {filename}\ndescription: Code généré sans nom de fichier explicite\ncontent:\n{code_block}"
                    actions.append(("modify_file", formatted_action))
                    logger.info(f"🔍 Code détecté sans nom de fichier - utilisation de '{filename}' par défaut")
    
    if not actions:
        creation_intent_pattern = r'(?:je vais créer|I will create|voy a crear|creerò|ich werde erstellen)\s+(?:le fichier|the file|el archivo|il file|die Datei)\s+([a-zA-Z0-9_./\\-]+\.[a-z]+)'
        intent_matches = re.findall(creation_intent_pattern, execution_text, re.IGNORECASE)
        if intent_matches:
            logger.warning(f"⚠️ L'IA mentionne créer {len(intent_matches)} fichier(s) mais n'a pas fourni de code!")
            logger.warning("💡 Suggestion: Demandez explicitement le contenu des fichiers")
    
    return actions


def _guess_filename_from_code(code: str, index: int = 0) -> str:
    """
    Devine le nom de fichier approprié basé sur le contenu du code.
    Support multi-langages
    """
    code_lower = code.lower()
    
    if "def " in code or "import " in code or "class " in code and ":" in code:
        return f"module_{index}.py" if index > 0 else "implementation.py"
    
    elif "function " in code or "const " in code or "let " in code or "=>" in code:
        if "interface " in code or ": " in code and "=>" in code:
            return f"module_{index}.ts" if index > 0 else "implementation.ts"
        return f"module_{index}.js" if index > 0 else "implementation.js"
    
    elif "public class " in code or "private class " in code:
        class_match = re.search(r'class\s+([A-Z][a-zA-Z0-9_]*)', code)
        if class_match:
            return f"{class_match.group(1)}.java"
        return "Implementation.java"
    
    elif "package " in code and "func " in code:
        return f"implementation_{index}.go" if index > 0 else "implementation.go"
    
    elif "<html" in code_lower or "<!doctype" in code_lower:
        return f"page_{index}.html" if index > 0 else "index.html"
    elif "body {" in code_lower or "div {" in code_lower:
        return f"style_{index}.css" if index > 0 else "style.css"
    
    return f"generated_code_{index}.txt"


async def _execute_file_modification(claude_tool: ClaudeCodeTool, action_content: str, state: Dict[str, Any]) -> bool:
    """Exécute une modification de fichier."""
    try:
        lines = action_content.strip().split('\n')
        file_path = None
        description = ""
        content = ""
        
        content_started = False
        for line in lines:
            if line.startswith('file_path:'):
                file_path = line.split(':', 1)[1].strip()
            elif line.startswith('description:'):
                description = line.split(':', 1)[1].strip()
            elif line.startswith('content:'):
                content_started = True
            elif content_started:
                content += line + '\n'
        
        if file_path and content:
            task = state.get("task")
            context = {
                "workflow_id": state.get("workflow_id", "unknown"),
                "task_id": task.task_id if task else "unknown"
            }
            
            result = await claude_tool._arun(
                action="write_file",
                file_path=file_path,
                content=content.strip(),
                context=context
            )
            
            if result["success"]:
                repository_context = state.get("results", {}).get("repository_context", {})
                conventions = repository_context.get("conventions", {})
                
                validation_result = await _validate_generated_code(
                    file_path, 
                    content.strip(),
                    expected_conventions=conventions
                )
                
                if not validation_result["is_valid"]:
                    warning_msg = f"⚠️ Code généré pour {file_path} a des problèmes de qualité: {', '.join(validation_result['issues'])}"
                    logger.warning(warning_msg)
                    state["results"]["ai_messages"].append(warning_msg)
                    if "code_quality_warnings" not in state["results"]:
                        state["results"]["code_quality_warnings"] = []
                    state["results"]["code_quality_warnings"].append({
                        "file": file_path,
                        "issues": validation_result["issues"]
                    })
                
                state["results"]["code_changes"][file_path] = content.strip()
                state["results"]["modified_files"].append(file_path)
                state["results"]["ai_messages"].append(f"✅ Fichier modifié: {file_path}")
                logger.info(f"✅ Fichier modifié: {file_path}")
                return True
            else:
                error = result.get("error", "Erreur inconnue")
                state["results"]["error_logs"].append(f"Échec modification {file_path}: {error}")
                logger.error(f"❌ Échec modification {file_path}: {error}")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur modification fichier: {e}")
        return False

async def _validate_generated_code(
    file_path: str, 
    content: str,
    expected_conventions: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Valide la qualité du code généré avant de l'écrire.
    
    ✅ AMÉLIORATION MAJEURE: Validation contextualisée avec les conventions détectées
    
    Args:
        file_path: Chemin du fichier
        content: Contenu du code
        expected_conventions: Conventions attendues du repository (détectées par l'explorateur)
        
    Returns:
        Dict avec is_valid (bool) et issues (list)
    """
    import re
    issues = []
    
    expected_conventions = expected_conventions or {}
    
    # 1. Vérifier les placeholders et TODO
    placeholder_patterns = [
        r'TODO\s*:',
        r'FIXME\s*:',
        r'XXX\s*:',
        r'PLACEHOLDER',
        r'#\s*[Aa]dd\s+code\s+here',
        r'//\s*[Aa]dd\s+code\s+here',
        r'\/\*\s*[Tt]o\s+be\s+implemented',
        r'#\s*[Tt]o\s+be\s+implemented'
    ]
    
    for pattern in placeholder_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append(f"Code contient des placeholders/TODO (pattern: {pattern})")
            break
    
    if len(content.strip()) < 20:
        issues.append("Code trop court (moins de 20 caractères)")
    

    extension = file_path.split('.')[-1] if '.' in file_path else ''
    
    if extension == 'py':
        try:
            import ast
            ast.parse(content)
        except SyntaxError as e:
            issues.append(f"Erreur de syntaxe: {str(e)}")
    
    else:
        if '{' in content or '}' in content:
            if content.count('{') != content.count('}'):
                issues.append("Accolades {} non balancées")
        
        if '(' in content or ')' in content:
            if content.count('(') != content.count(')'):
                issues.append("Parenthèses () non balancées")
        
        if '[' in content or ']' in content:
            if content.count('[') != content.count(']'):
                issues.append("Crochets [] non balancés")
        
        if content.count('"') % 2 != 0:
            issues.append("Guillemets \" non balancés")
        
        char_literal_langs = ['java', 'c', 'cpp', 'cc', 'h', 'hpp', 'cs', 'rs', 'go', 'm', 'mm']
        doc_files = ['md', 'markdown', 'html', 'htm', 'txt', 'rst', 'adoc', 'asciidoc']
        
        if extension.lower() not in char_literal_langs and extension.lower() not in doc_files:
            content_without_comments = re.sub(r'(#|//).*?$', '', content, flags=re.MULTILINE)
            content_without_comments = re.sub(r'/\*.*?\*/', '', content_without_comments, flags=re.DOTALL)
            
            if content_without_comments.count("'") % 2 != 0:
                issues.append("Apostrophes ' non balancées")
    
    lines = content.split('\n')
    comment_lines = sum(1 for line in lines if line.strip().startswith(('#', '//', '/*', '*')))
    code_lines = len([line for line in lines if line.strip() and not line.strip().startswith(('#', '//', '/*', '*'))])
    
    if code_lines > 0 and comment_lines / code_lines > 0.5:
        issues.append("Trop de commentaires par rapport au code (ratio > 50%)")
    
    if expected_conventions:
        if 'naming' in expected_conventions:
            expected_naming = expected_conventions['naming']
            
            if expected_naming == 'snake_case':
                if re.search(r'def\s+[a-z][a-zA-Z]+[A-Z]', content):
                    issues.append(f"Convention de nommage non respectée: attendu {expected_naming}, trouvé camelCase")
            
            elif expected_naming == 'camelCase':
                if re.search(r'function\s+[a-z][a-z_]+_[a-z]', content):
                    issues.append(f"Convention de nommage non respectée: attendu {expected_naming}, trouvé snake_case")
        
        if expected_conventions.get('async') and 'async ' not in content and 'await ' not in content:
            if 'def ' in content or 'function ' in content:
                issues.append("Le projet utilise du code asynchrone, mais le code généré n'utilise ni async ni await")
    
    is_valid = len(issues) == 0
    
    if not is_valid:
        logger.warning(f"⚠️ Validation du code pour {file_path}: {len(issues)} problème(s) détecté(s)")
    
    return {
        "is_valid": is_valid,
        "issues": issues,
        "file_path": file_path
    }


async def _execute_command_action(claude_tool: ClaudeCodeTool, action_content: str, state: Dict[str, Any]) -> bool:
    """Exécute une commande système."""
    try:
        command = None
        for line in action_content.strip().split('\n'):
            if line.startswith('command:'):
                command = line.split(':', 1)[1].strip()
                break
        
        if command:
            if 'git clone' in command.lower():
                logger.warning(f"⚠️ Commande git clone bloquée - le repository est déjà cloné")
                state["results"]["ai_messages"].append(f"⚠️ Commande git clone ignorée (repository déjà disponible)")
                return True
                          
            read_commands = ['cat ', 'head ', 'tail ', 'less ', 'more ']
            for read_cmd in read_commands:
                if command.strip().startswith(read_cmd):
                    parts = command.strip()[len(read_cmd):].split()
                    file_to_read = None
                    for part in parts:
                        if not part.startswith('-'):
                            file_to_read = part
                            break
                    
                    if not file_to_read:
                        continue
                    
                    working_dir = get_working_directory(state)
                    full_path = os.path.join(working_dir, file_to_read) if working_dir else file_to_read
                    
                    if not os.path.exists(full_path):
                        logger.warning(f"⚠️ Fichier inexistant pour commande de lecture: {file_to_read}")
                        state["results"]["ai_messages"].append(f"⚠️ Fichier '{file_to_read}' n'existe pas - commande ignorée")
                        return True
            
            dangerous_commands = ['rm -rf /', 'dd if=', 'mkfs', ':(){:|:&};:', 'wget http']
            if any(dangerous in command.lower() for dangerous in dangerous_commands):
                logger.error(f"❌ Commande dangereuse bloquée: {command}")
                state["results"]["error_logs"].append(f"Commande dangereuse bloquée: {command}")
                return False
            
            result = await claude_tool._arun(action="execute_command", command=command)
            
            if result["success"]:
                state["results"]["ai_messages"].append(f"✅ Commande exécutée: {command}")
                logger.info(f"✅ Commande exécutée: {command}")
                return True
            else:
                error = result.get("stderr", result.get("error", "Erreur inconnue"))
                state["results"]["error_logs"].append(f"Échec commande '{command}': {error}")
                logger.error(f"❌ Échec commande '{command}': {error}")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur exécution commande: {e}")
        return False

async def _handle_direct_code_modification(claude_tool: ClaudeCodeTool, code_content: str, state: Dict[str, Any]) -> bool:
    """Gère une modification de code directe sans structure explicite."""
    try:
        if "def " in code_content or "import " in code_content:
            filename = "main.py"  
        elif "function " in code_content or "const " in code_content:
            filename = "main.js"
        else:
            filename = "implementation.txt"
        
        result = await claude_tool._arun(
            action="write_file",
            file_path=filename,
            content=code_content
        )
        
        if result["success"]:
            state["results"]["code_changes"][filename] = code_content
            state["results"]["modified_files"].append(filename)
            state["results"]["ai_messages"].append(f"✅ Code ajouté: {filename}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur modification directe: {e}")
        return False


def _convert_structured_plan_to_text(structured_plan) -> str:
    """
    Convertit un plan structuré (Pydantic) en texte pour compatibilité avec l'exécution legacy.
    
    Args:
        structured_plan: Instance de ImplementationPlan
        
    Returns:
        Représentation texte du plan
    """
    from ai.chains.implementation_plan_chain import ImplementationPlan
    
    if not isinstance(structured_plan, ImplementationPlan):
        logger.warning("⚠️ Plan structuré invalide, retour vide")
        return ""
    
    text_parts = []
    
    text_parts.append("# PLAN D'IMPLÉMENTATION STRUCTURÉ")
    text_parts.append("")
    text_parts.append(f"## Résumé")
    text_parts.append(structured_plan.task_summary)
    text_parts.append("")
    text_parts.append(f"## Approche architecturale")
    text_parts.append(structured_plan.architecture_approach)
    text_parts.append("")
    
    text_parts.append(f"## Étapes d'implémentation ({len(structured_plan.steps)} étapes)")
    text_parts.append("")
    
    for step in structured_plan.steps:
        text_parts.append(f"### Étape {step.step_number}: {step.title}")
        text_parts.append(f"**Description**: {step.description}")
        text_parts.append(f"**Complexité**: {step.estimated_complexity}/10")
        text_parts.append(f"**Risque**: {step.risk_level.value.upper()}")
        
        if step.files_to_modify:
            text_parts.append(f"**Fichiers**: {', '.join(step.files_to_modify)}")
        
        if step.dependencies:
            text_parts.append(f"**Dépendances**: {', '.join(step.dependencies)}")
        
        if step.risk_mitigation:
            text_parts.append(f"**Mitigation des risques**: {step.risk_mitigation}")
        
        if step.validation_criteria:
            text_parts.append(f"**Critères de validation**:")
            for criterion in step.validation_criteria:
                text_parts.append(f"  - {criterion}")
        
        text_parts.append("")
    
    text_parts.append("## Évaluation globale")
    text_parts.append(f"**Complexité totale**: {structured_plan.total_estimated_complexity}")
    text_parts.append(f"**Risques**: {structured_plan.overall_risk_assessment}")
    text_parts.append(f"**Stratégie de tests**: {structured_plan.recommended_testing_strategy}")
    text_parts.append("")
    
    # Bloqueurs potentiels
    if structured_plan.potential_blockers:
        text_parts.append("## Bloqueurs potentiels identifiés")
        for blocker in structured_plan.potential_blockers:
            text_parts.append(f"- {blocker}")
        text_parts.append("")
    
    return "\n".join(text_parts) 