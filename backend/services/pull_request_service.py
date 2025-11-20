"""
Service de gestion robuste des Pull Requests.

Ce service centralise toute la logique de création, mise à jour et merge des PR
avec gestion d'erreurs, retry, et persistence des états.
"""

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import os

from models.schemas import PullRequestInfo, TaskRequest
from tools.github_tool import GitHubTool
from utils.logger import get_logger
from utils.helpers import get_working_directory

logger = get_logger(__name__)


class PRStatus(Enum):
    """États possibles d'une Pull Request dans notre système."""
    PENDING_CREATION = "pending_creation"
    CREATING = "creating"
    CREATED = "created"
    PENDING_MERGE = "pending_merge"
    MERGING = "merging" 
    MERGED = "merged"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PROperationResult:
    """Résultat d'une opération sur une PR."""
    success: bool
    pr_info: Optional[PullRequestInfo] = None
    error: Optional[str] = None
    retry_after: Optional[int] = None
    should_retry: bool = False


class PullRequestService:
    """Service centralisé pour la gestion des Pull Requests."""
    
    def __init__(self):
        from utils.logger import get_logger
        self.logger = get_logger(__name__)
        self.github_tool = GitHubTool()
        self._pr_cache: Dict[str, Dict[str, Any]] = {}
        
    async def ensure_pull_request_created(
        self, 
        state: Dict[str, Any], 
        force_recreate: bool = False
    ) -> PROperationResult:
        """
        S'assure qu'une Pull Request existe pour la tâche donnée.
        
        Cette méthode est idempotente et peut être appelée plusieurs fois.
        
        Args:
            state: État du workflow
            force_recreate: Forcer la recréation même si une PR existe
            
        Returns:
            Résultat de l'opération avec les informations de la PR
        """
        try:
            task = state.get("task")
            if not task:
                return PROperationResult(
                    success=False, 
                    error="Aucune tâche trouvée dans l'état"
                )
            
            task_id = str(task.task_id) if hasattr(task, 'task_id') else str(task.get('task_id', 'unknown'))
            
            existing_pr = await self._get_existing_pr_info(state, task_id)
            if existing_pr and not force_recreate:
                logger.info(f"✅ PR existante trouvée: #{existing_pr.number}")
                return PROperationResult(success=True, pr_info=existing_pr)
            
            prereq_check = await self._check_pr_prerequisites(state)
            if not prereq_check.success:
                return prereq_check
            
            logger.info(f"📝 Création de la Pull Request pour tâche {task_id}...")
            return await self._create_pull_request_with_retry(state, task_id)
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la création de PR: {e}")
            return PROperationResult(
                success=False,
                error=f"Exception: {str(e)}",
                should_retry=True,
                retry_after=30
            )
    
    async def merge_pull_request(
        self, 
        state: Dict[str, Any], 
        pr_info: PullRequestInfo,
        merge_strategy: str = "squash"
    ) -> PROperationResult:
        """
        Effectue le merge d'une Pull Request.
        
        Args:
            state: État du workflow
            pr_info: Informations de la PR à merger
            merge_strategy: Stratégie de merge ("merge", "squash", "rebase")
            
        Returns:
            Résultat de l'opération de merge
        """
        try:
            task = state.get("task")
            repo_url = self._extract_repository_url(task, state)
            
            if not repo_url:
                return PROperationResult(
                    success=False,
                    error="URL du repository non trouvée pour le merge"
                )
            
            logger.info(f"🔀 Merge de la PR #{pr_info.number} avec stratégie '{merge_strategy}'")
            
            task_title = getattr(task, 'title', 'Automated task') if hasattr(task, 'title') else task.get('title', 'Automated task') if isinstance(task, dict) else 'Automated task'
            task_desc = getattr(task, 'description', '') if hasattr(task, 'description') else task.get('description', '') if isinstance(task, dict) else ''
            
            merge_result = await self.github_tool._arun(
                action="merge_pull_request",
                repo_url=repo_url,
                pr_number=pr_info.number,
                merge_method=merge_strategy,
                commit_title=f"feat: {task_title}",
                commit_message=f"Merge PR #{pr_info.number}\n\n{task_desc[:200]}..."
            )
            
            if merge_result.get("success"):
                pr_info.status = "merged"
                
                task_id = str(task.task_id) if hasattr(task, 'task_id') else 'unknown'
                self._clear_pr_cache(task_id)
                
                logger.info(f"✅ PR #{pr_info.number} mergée avec succès")
                return PROperationResult(success=True, pr_info=pr_info)
            else:
                error_msg = merge_result.get("error", "Erreur inconnue lors du merge")
                logger.error(f"❌ Échec merge PR: {error_msg}")
                return PROperationResult(
                    success=False,
                    error=error_msg,
                    should_retry=True,
                    retry_after=60
                )
                
        except Exception as e:
            logger.error(f"❌ Exception lors du merge: {e}")
            return PROperationResult(
                success=False,
                error=f"Exception: {str(e)}",
                should_retry=True,
                retry_after=30
            )
    
    async def _get_existing_pr_info(
        self, 
        state: Dict[str, Any], 
        task_id: str
    ) -> Optional[PullRequestInfo]:
        """Récupère les informations d'une PR existante."""
        
        pr_info = state.get("results", {}).get("pr_info")
        if pr_info and isinstance(pr_info, PullRequestInfo):
            return pr_info
        
        cached_pr = self._pr_cache.get(task_id, {}).get("pr_info")
        if cached_pr:
            return cached_pr
        
        return None
    
    async def _check_pr_prerequisites(self, state: Dict[str, Any]) -> PROperationResult:
        """Vérifie que tous les prérequis pour créer une PR sont présents."""
        
        task = state.get("task")
        if not task:
            return PROperationResult(success=False, error="Tâche manquante")
        
        repo_url = self._extract_repository_url(task, state)
        if not repo_url:
            return PROperationResult(
                success=False, 
                error="URL du repository non trouvée"
            )
        
        working_directory = get_working_directory(state)
        if not working_directory or not os.path.exists(working_directory):
            return PROperationResult(
                success=False,
                error="Répertoire de travail non trouvé"
            )
        
        branch_name = self._extract_branch_name(state)
        if not branch_name:
            return PROperationResult(
                success=False,
                error="Nom de branche non trouvé"
            )
        
        return PROperationResult(success=True)
    
    async def _create_pull_request_with_retry(
        self, 
        state: Dict[str, Any], 
        task_id: str,
        max_retries: int = 3
    ) -> PROperationResult:
        """Crée une PR avec logique de retry."""
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 Tentative {attempt}/{max_retries} de création PR")
                
                result = await self._create_pull_request_internal(state)
                
                if result.success:
                    self._cache_pr_info(task_id, result.pr_info)
                    return result
                
                if not result.should_retry or attempt == max_retries:
                    return result
                
                wait_time = result.retry_after or (attempt * 10)
                logger.info(f"⏳ Attente {wait_time}s avant retry...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                if attempt == max_retries:
                    return PROperationResult(
                        success=False,
                        error=f"Échec après {max_retries} tentatives: {str(e)}"
                    )
                
                wait_time = attempt * 15
                logger.warning(f"⚠️ Tentative {attempt} échouée: {e}. Retry dans {wait_time}s")
                await asyncio.sleep(wait_time)
        
        return PROperationResult(
            success=False,
            error=f"Échec après {max_retries} tentatives"
        )
    
    async def _create_pull_request_internal(self, state: Dict[str, Any]) -> PROperationResult:
        """Logique interne de création de PR."""
        
        task = state.get("task")
        repo_url = self._extract_repository_url(task, state)
        working_directory = get_working_directory(state)
        branch_name = self._extract_branch_name(state)
        
        from services.base_branch_resolver import get_base_branch_resolver
        
        resolver = get_base_branch_resolver()
        monday_base_branch = getattr(task, 'base_branch', None)
        
        base_branch = await resolver.resolve_base_branch(
            task=task,
            repository_url=repo_url,
            monday_base_branch=monday_base_branch
        )
        
        self.logger.info(f"🎯 Branche de base résolue: {base_branch} pour PR")
        
        pr_title, pr_body = await self._generate_pr_content(task, state)
        
        pr_result = await self.github_tool._arun(
            action="create_pull_request",
            repo_url=repo_url,
            branch_name=branch_name,
            base_branch=base_branch,
            title=pr_title,
            body=pr_body,
            working_directory=working_directory
        )
        
        if pr_result.get("success"):
            pr_info = PullRequestInfo(
                number=pr_result.get("pr_number"),
                title=pr_title,
                url=pr_result.get("pr_url", ""),
                branch=branch_name,
                base_branch=base_branch,
                status="open",
                created_at=datetime.now(timezone.utc)
            )
            
            return PROperationResult(success=True, pr_info=pr_info)
        else:
            error_msg = pr_result.get("error", "Erreur inconnue")
            should_retry = "rate limit" in error_msg.lower() or "timeout" in error_msg.lower()
            
            return PROperationResult(
                success=False,
                error=error_msg,
                should_retry=should_retry,
                retry_after=60 if should_retry else None
            )
    
    def _extract_repository_url(self, task: Any, state: Dict[str, Any]) -> Optional[str]:
        """Extrait l'URL du repository depuis différentes sources."""
        
        if task:
            task_repo_url = None
            if isinstance(task, dict):
                task_repo_url = task.get('repository_url')
            elif hasattr(task, 'repository_url'):
                task_repo_url = task.repository_url
            
            if task_repo_url:
                return task_repo_url
        
        repo_url = state.get("results", {}).get("repository_url")
        if repo_url:
            return repo_url
        
        if task:
            task_desc = None
            if isinstance(task, dict):
                task_desc = task.get('description')
            elif hasattr(task, 'description'):
                task_desc = task.description
            
            if task_desc:
                from utils.github_parser import extract_github_url_from_description
                extracted_url = extract_github_url_from_description(task_desc)
                if extracted_url:
                    return extracted_url
        
        logger.warning(f"⚠️ URL repository non trouvée dans les sources classiques pour tâche {getattr(task, 'task_id', 'unknown')}")
        return None
    
    def _extract_branch_name(self, state: Dict[str, Any]) -> Optional[str]:
        """Extrait le nom de branche depuis l'état."""
        
        results = state.get("results", {})
        if "git_branch" in results and results["git_branch"]:
            return results["git_branch"]
        
        git_result = results.get("git_result")
        if git_result:
            if hasattr(git_result, 'branch'):
                return git_result.branch
            elif hasattr(git_result, 'branch_name'):
                return git_result.branch_name
            elif isinstance(git_result, dict):
                if 'branch' in git_result:
                    return git_result['branch']
                elif 'branch_name' in git_result:
                    return git_result['branch_name']
        
        prepare_result = results.get("prepare_result", {})
        if isinstance(prepare_result, dict):
            if "branch_name" in prepare_result:
                return prepare_result["branch_name"]
            elif "branch" in prepare_result:
                return prepare_result["branch"]
        
        task = state.get("task")
        if task and hasattr(task, 'branch') and task.branch:
            return task.branch
        
        self.logger.warning("⚠️ Impossible d'extraire le nom de branche depuis l'état")
        self.logger.debug(f"🔍 Keys disponibles dans results: {list(results.keys())}")
        
        return None
    
    async def _generate_pr_content(self, task: Any, state: Dict[str, Any]) -> tuple[str, str]:
        """
        Génère le titre et le corps de la PR dans la langue de l'utilisateur.
        
        ⚠️ IMPORTANT: Utilise la langue de l'UTILISATEUR (user_language), 
        PAS la langue du projet (project_language).
        Le CONTENU des fichiers reste dans la langue du projet.
        """
        user_lang = state.get('user_language', 'en')
        
        from services.project_language_detector import project_language_detector
        template = await project_language_detector.get_pr_template(user_lang)
        
        # SÉCURITÉ: Vérification pour garantir que template n'est JAMAIS None ou incomplet
        if not template or not isinstance(template, dict):
            logger.error(f"❌ CRITIQUE: template invalide dans pull_request_service ! Type: {type(template)}")
            template = {
                'title_prefix': 'feat',
                'auto_pr_header': '## 🤖 Automatically generated Pull Request',
                'task_section': '### 📋 Task',
                'description_section': '### 📝 Description',
                'changes_section': '### 🔄 Changes',
                'modified_files': 'Modified files',
                'tests_section': '### 🧪 Tests',
                'validation_section': '### ✅ Validation',
                'validated_text': 'Changes validated by automated tests',
                'footer': 'Automatically generated by VyData AI Agent'
            }
        
        title = f"{template.get('title_prefix', 'feat')}: {task.title}" if hasattr(task, 'title') else f"{template.get('title_prefix', 'feat')}: Automated implementation"
        
        body_parts = [
            template.get('auto_pr_header', '## 🤖 Automatically generated Pull Request'),
            "",
            template.get('task_section', '### 📋 Task')
        ]
        
        id_label = "ID" if user_lang == 'en' else "ID"
        title_label = "Title" if user_lang == 'en' else "Título" if user_lang == 'es' else "Titre"
        priority_label = "Priority" if user_lang == 'en' else "Prioridad" if user_lang == 'es' else "Priorité"
        
        if hasattr(task, 'task_id'):
            body_parts.append(f"**{id_label}**: {task.task_id}")
        if hasattr(task, 'title'):
            body_parts.append(f"**{title_label}**: {task.title}")
        if hasattr(task, 'priority'):
            body_parts.append(f"**{priority_label}**: {task.priority}")
        
        body_parts.extend(["", template.get('description_section', '### 📝 Description')])
        if hasattr(task, 'description') and task.description:
            body_parts.append(task.description)
        else:
            no_desc = "No description available" if user_lang == 'en' else "Sin descripción" if user_lang == 'es' else "Description non disponible"
            body_parts.append(no_desc)
        
        self._add_changes_info(body_parts, state, template, user_lang)
        
        self._add_quality_info(body_parts, state, template, user_lang)
        
        body_parts.extend([
            "",
            template.get('validation_section', '### ✅ Validation'),
            f"✅ {template.get('validated_text', 'Changes validated by automated tests')}",
            "",
            "---",
            f"*{template.get('footer', 'Automatically generated by VyData AI Agent')}*"
        ])
        
        return title, "\n".join(body_parts)
    
    def _add_changes_info(self, body_parts: List[str], state: Dict[str, Any], template: Dict[str, str], user_lang: str) -> None:
        """Ajoute les informations sur les changements à la PR."""
        
        body_parts.extend(["", template.get('changes_section', '### 🔄 Changes')])
        
        modified_files = state.get("results", {}).get("modified_files", [])
        if modified_files:
            body_parts.append(f"\n#### {template.get('modified_files', 'Modified files')}:")
            for file_path in modified_files[:10]:
                body_parts.append(f"- `{file_path}`")
            if len(modified_files) > 10:
                more_text = f"and {len(modified_files) - 10} more files" if user_lang == 'en' else f"y {len(modified_files) - 10} archivos más" if user_lang == 'es' else f"et {len(modified_files) - 10} autres fichiers"
                body_parts.append(f"... {more_text}")
        else:
            no_info = "Modified files: Information not available" if user_lang == 'en' else "Archivos modificados: Información no disponible" if user_lang == 'es' else "Fichiers modifiés: Informations non disponibles"
            body_parts.append(no_info)
    
    def _add_quality_info(self, body_parts: List[str], state: Dict[str, Any], template: Dict[str, str], user_lang: str) -> None:
        """Ajoute les informations de qualité à la PR."""
        
        results = state.get("results", {})
        
        test_results = results.get("test_results")
        if test_results:
            tests_header = template.get('tests_section', '### 🧪 Tests')
            tests_passed = "✅ Tests passed successfully" if user_lang == 'en' else "✅ Pruebas pasadas con éxito" if user_lang == 'es' else "✅ Tests passés avec succès"
            body_parts.extend(["", tests_header, tests_passed])
        
        qa_results = results.get("qa_results")
        if qa_results and isinstance(qa_results, dict):
            score = qa_results.get("overall_score")
            if score:
                qa_header = "### 📊 Code Quality" if user_lang == 'en' else "### 📊 Calidad del código" if user_lang == 'es' else "### 📊 Qualité du code"
                qa_score = f"✅ Quality score: {score}/100" if user_lang == 'en' else f"✅ Puntuación de calidad: {score}/100" if user_lang == 'es' else f"✅ Score qualité: {score}/100"
                body_parts.extend([
                    "",
                    qa_header,
                    qa_score
                ])
    
    def _cache_pr_info(self, task_id: str, pr_info: PullRequestInfo) -> None:
        """Met en cache les informations de PR."""
        
        self._pr_cache[task_id] = {
            "pr_info": pr_info,
            "cached_at": time.time(),
            "expires_at": time.time() + 3600  
        }
    
    def _clear_pr_cache(self, task_id: str) -> None:
        """Nettoie le cache pour une tâche."""
        
        if task_id in self._pr_cache:
            del self._pr_cache[task_id]
    
    def cleanup_expired_cache(self) -> None:
        """Nettoie le cache expiré."""
        
        now = time.time()
        expired_keys = [
            task_id for task_id, cached_data in self._pr_cache.items()
            if cached_data.get("expires_at", 0) < now
        ]
        
        for key in expired_keys:
            del self._pr_cache[key]


pr_service = PullRequestService() 