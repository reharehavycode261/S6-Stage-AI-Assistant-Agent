"""
Service d'exploration de projet pour les questions informatives.

Ce service permet d'exécuter les nœuds d'exploration du workflow (prepare, analyze)
SANS exécuter les nœuds d'implémentation ou de validation humaine.

Flux pour les questions @vydata:
1. Clone le repository (prepare_environment)
2. Analyse le projet (analyze_requirements)
3. Arrêt avant implémentation
4. Retourne le contexte complet pour génération de réponse
"""

from typing import Dict, Any, Optional
from datetime import datetime
from utils.logger import get_logger
from models.state import GraphState
from nodes.prepare_node import prepare_environment
from nodes.analyze_node import analyze_requirements

logger = get_logger(__name__)


class ProjectExplorationService:
    """
    Service pour explorer un projet sans modifications de code.
    
    Utilisé pour les questions @vydata qui nécessitent une analyse
    complète du projet sans déclencher le workflow complet.
    """
    
    def __init__(self):
        """Initialise le service d'exploration."""
        pass
    
    async def explore_project_for_question(
        self,
        task: Any,
        question: str,
        task_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Explore le projet pour répondre à une question.
        
        Exécute uniquement les nœuds d'exploration:
        - prepare_environment: Clone le repo, setup l'environnement
        - analyze_requirements: Analyse le code, structure, technologies
        
        N'exécute PAS:
        - Nœud d'implémentation (pas de modifications)
        - Nœud de tests
        - Nœud de PR
        - Nœud de validation humaine
        
        Args:
            task: Tâche contenant les informations du projet
            question: Question posée par l'utilisateur
            task_context: Contexte additionnel de la tâche
            
        Returns:
            Contexte enrichi du projet avec:
            - project_structure: Structure des fichiers
            - technologies_detected: Technologies utilisées
            - code_analysis: Analyse du code
            - repository_info: Informations du repository
        """
        logger.info("="*80)
        logger.info("🔍 EXPLORATION DE PROJET POUR QUESTION")
        logger.info("="*80)
        task_title = task.get('title', 'N/A') if isinstance(task, dict) else getattr(task, 'title', 'N/A')
        logger.info(f"📝 Task: {task_title}")
        logger.info(f"❓ Question: '{question[:100]}...'")
        logger.info(f"🎯 Mode: Exploration uniquement (pas de modifications)")
        logger.info("="*80)
        
        try:
            exploration_state = self._create_exploration_state(task, question, task_context)
            
            logger.info("📦 Étape 1/2: Préparation de l'environnement...")
            try:
                exploration_state = await prepare_environment(exploration_state)
                
                if exploration_state.get("results", {}).get("error"):
                    error_msg = exploration_state["results"]["error"]
                    logger.error(f"❌ Erreur préparation environnement: {error_msg}")
                    return {
                        "success": False,
                        "error": f"Impossible de préparer l'environnement: {error_msg}",
                        "phase": "prepare_environment"
                    }
                
                logger.info("✅ Environnement préparé avec succès")
                
            except Exception as e:
                logger.error(f"❌ Erreur prepare_environment: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": f"Erreur préparation environnement: {str(e)}",
                    "phase": "prepare_environment"
                }
            
            logger.info("🔍 Étape 2/2: Analyse des requirements...")
            try:
                exploration_state = await analyze_requirements(exploration_state)
                
                if exploration_state.get("results", {}).get("error"):
                    error_msg = exploration_state["results"]["error"]
                    logger.error(f"❌ Erreur analyse requirements: {error_msg}")
                    return {
                        "success": False,
                        "error": f"Impossible d'analyser le projet: {error_msg}",
                        "phase": "analyze_requirements",
                        "partial_context": self._extract_partial_context(exploration_state)
                    }
                
                logger.info("✅ Analyse des requirements terminée")
                
            except Exception as e:
                logger.error(f"❌ Erreur analyze_requirements: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": f"Erreur analyse requirements: {str(e)}",
                    "phase": "analyze_requirements",
                    "partial_context": self._extract_partial_context(exploration_state)
                }
            
            
            project_context = self._extract_project_context(exploration_state)
            
            logger.info("="*80)
            logger.info("✅ EXPLORATION TERMINÉE")
            logger.info("="*80)
            logger.info(f"📊 Technologies: {len(project_context.get('technologies', []))}")
            logger.info(f"   • Liste: {project_context.get('technologies', [])}")
            logger.info(f"📁 Fichiers analysés: {len(project_context.get('file_structure', []))}")
            if project_context.get('file_structure'):
                logger.info(f"   • Exemples: {project_context['file_structure'][:5]}")
            logger.info(f"🔍 Contexte enrichi: {project_context.get('has_code_analysis', False)}")
            logger.info("="*80)
            
            return {
                "success": True,
                "project_context": project_context,
                "exploration_state": exploration_state,
                "message": "Exploration du projet terminée avec succès"
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur exploration projet: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Erreur lors de l'exploration: {str(e)}",
                "phase": "general"
            }
    
    def _create_exploration_state(
        self,
        task: Any,
        question: str,
        task_context: Dict[str, Any]
    ) -> GraphState:
        """
        Crée un état GraphState minimal pour l'exploration.
        
        Args:
            task: Tâche à explorer (peut être un dict ou un objet)
            question: Question de l'utilisateur
            task_context: Contexte additionnel
            
        Returns:
            GraphState initialisé pour l'exploration
        """
        if isinstance(task, dict):
            from types import SimpleNamespace
            
            task_dict = task.copy()
            
            task_dict.setdefault('task_type', 'feature')
            task_dict.setdefault('acceptance_criteria', '')
            task_dict.setdefault('technical_context', '')
            task_dict.setdefault('files_to_modify', [])
            task_dict.setdefault('estimated_complexity', '')
            
            if 'tasks_id' in task_dict and 'task_id' not in task_dict:
                task_dict['task_id'] = task_dict['tasks_id']
            
            task_object = SimpleNamespace(**task_dict)
        else:
            task_object = task
        
        if isinstance(task, dict):
            repository_url = task.get('repository_url', '')
        else:
            repository_url = getattr(task, 'repository_url', '')
        
        return {
            "task": task_object,
            "task_run": None,
            "repository": repository_url,
            "results": {
                "ai_messages": [],
                "context": {
                    "exploration_mode": True,
                    "question": question,
                    "task_context": task_context
                }
            },
            "metadata": {
                "start_time": datetime.utcnow().isoformat(),
                "mode": "exploration_for_question",
                "question": question
            }
        }
    
    def _extract_project_context(self, exploration_state: GraphState) -> Dict[str, Any]:
        """
        Extrait le contexte du projet depuis l'état d'exploration.
        
        Args:
            exploration_state: État après exploration
            
        Returns:
            Contexte enrichi du projet
        """
        results = exploration_state.get("results", {})
        
        repository_url = exploration_state.get("repository", "")
        workspace_path = results.get("workspace_path") or exploration_state.get("working_directory")
        repo_cloned = results.get("repo_cloned", False)
        
        requirements_analysis = results.get("requirements_analysis", {})
        structured_analysis = results.get("structured_requirements_analysis", {})
        analysis_metrics = results.get("analysis_metrics", {})
        
        project_scan = results.get("project_scan", {})
        technologies = list(project_scan.get("technologies", [])) if project_scan else []
        file_structure = list(project_scan.get("main_files", [])) if project_scan else []
        
        logger.info(f"🔍 Scan projet trouvé: {len(technologies)} technos, {len(file_structure)} fichiers")
        
        dependencies = requirements_analysis.get("dependencies", [])
        
        if not technologies and structured_analysis:
            candidate_files = structured_analysis.get("candidate_files", [])
            if not file_structure:
                file_structure = [f.get("path") for f in candidate_files if isinstance(f, dict) and "path" in f]
            
            if dependencies:
                for dep in dependencies:
                    if isinstance(dep, dict) and "name" in dep:
                        dep_name = dep["name"]
                        if any(java_dep in dep_name.lower() for java_dep in ["java", "spring", "maven", "gradle"]):
                            if "Java" not in technologies:
                                technologies.append("Java")
                        elif any(py_dep in dep_name.lower() for py_dep in ["python", "django", "flask", "fastapi"]):
                            if "Python" not in technologies:
                                technologies.append("Python")
                        elif any(js_dep in dep_name.lower() for js_dep in ["javascript", "node", "react", "vue", "angular"]):
                            if "JavaScript" not in technologies:
                                technologies.append("JavaScript")
        
            technical_context = structured_analysis.get("technical_context", "") if structured_analysis else ""
            if "Java" in technical_context and "Java" not in technologies:
                technologies.append("Java")
            if "Python" in technical_context and "Python" not in technologies:
                technologies.append("Python")
            if "JavaScript" in technical_context or "TypeScript" in technical_context:
                if "JavaScript/TypeScript" not in technologies:
                    technologies.append("JavaScript/TypeScript")
        
        ai_messages = results.get("ai_messages", [])
        analysis_summary = "\n".join(ai_messages) if ai_messages else "Aucune analyse disponible"
        
        context = {
            "success": True,
            "exploration_successful": True,
            "exploration_completed": True,
            "repository_url": repository_url,
            "workspace_path": workspace_path,
            "repo_cloned": repo_cloned,
            
            "technologies": technologies,
            "file_structure": file_structure,
            "requirements_analysis": requirements_analysis,
            "structured_analysis": structured_analysis,
            "analysis_metrics": analysis_metrics,
            "dependencies": dependencies,
            
            "analysis_summary": analysis_summary,
            "has_code_analysis": bool(requirements_analysis or structured_analysis),
            
            "nodes_executed": ["prepare_environment", "analyze_requirements"]
        }
        
        return context
    
    def _extract_partial_context(self, exploration_state: GraphState) -> Dict[str, Any]:
        """
        Extrait un contexte partiel si l'exploration a échoué.
        
        Args:
            exploration_state: État partiel
            
        Returns:
            Contexte partiel disponible
        """
        results = exploration_state.get("results", {})
        
        project_scan = results.get("project_scan", {})
        technologies = list(project_scan.get("technologies", [])) if project_scan else []
        file_structure = list(project_scan.get("main_files", [])[:10]) if project_scan else []
        
        return {
            "success": False,
            "exploration_successful": False,
            "repository_url": exploration_state.get("repository", ""),
            "workspace_path": results.get("workspace_path"),
            "repo_cloned": results.get("repo_cloned", False),
            "partial_analysis": results.get("requirements_analysis", {}),
            "ai_messages": results.get("ai_messages", []),
            "error": results.get("error"),
            "technologies": technologies,
            "file_structure": file_structure,
            "exploration_error": results.get("error", "Erreur inconnue")
        }


project_exploration_service = ProjectExplorationService()

