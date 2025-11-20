"""
Orchestrateur pour la collecte d'informations GitHub.

Coordonne tous les collecteurs et récupère les informations de manière optimisée.
"""

import asyncio
from typing import Dict, Any, Optional, List, Type
from github import Github, GithubException

from services.github.base_collector import GitHubDataCollector, GitHubCollectorConfig
from services.github.collectors.repository_collector import RepositoryCollector
from services.github.collectors.pullrequest_collector import PullRequestCollector
from services.github.collectors.issue_collector import IssueCollector
from services.github.collectors.commit_collector import CommitCollector, BranchCollector
from services.github.collectors.release_collector import ReleaseCollector, TagCollector
from services.github.collectors.contributor_collector import ContributorCollector, CollaboratorCollector
from services.github.collectors.metadata_collector import (
    LabelCollector,
    MilestoneCollector,
    WorkflowCollector,
    SecurityCollector
)
from utils.logger import get_logger

logger = get_logger(__name__)


class GitHubInformationOrchestrator:
    """
    Orchestrateur pour collecter toutes les informations GitHub de manière optimisée.
    
    Architecture orientée objet extensible permettant d'ajouter facilement
    de nouveaux collecteurs sans modifier le code existant.
    """
    AVAILABLE_COLLECTORS: Dict[str, Type[GitHubDataCollector]] = {
        "repository": RepositoryCollector,
        "pull_requests": PullRequestCollector,
        "issues": IssueCollector,
        "commits": CommitCollector,
        "branches": BranchCollector,
        "releases": ReleaseCollector,
        "tags": TagCollector,
        "contributors": ContributorCollector,
        "collaborators": CollaboratorCollector,
        "labels": LabelCollector,
        "milestones": MilestoneCollector,
        "workflows": WorkflowCollector,
        "security": SecurityCollector
    }
    
    def __init__(self, github_token: str):
        """
        Initialise l'orchestrateur avec un token GitHub.
        
        Args:
            github_token: Token d'authentification GitHub
        """
        self.github_token = github_token
        self.github_client = Github(github_token)
        self.logger = logger
    
    async def collect_all(
        self,
        repository_url: str,
        config: Optional[GitHubCollectorConfig] = None,
        collectors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Collecte toutes les informations GitHub de manière optimisée.
        
        Args:
            repository_url: URL du repository GitHub
            config: Configuration pour les collecteurs
            collectors: Liste des collecteurs à utiliser (None = tous)
            
        Returns:
            Dictionnaire avec toutes les données collectées
        """
        try:
            self.logger.info("="*80)
            self.logger.info("📦 ORCHESTRATEUR GITHUB - COLLECTE COMPLÈTE")
            self.logger.info("="*80)
            
            repo_name = self._extract_repo_name(repository_url)
            self.logger.info(f"🎯 Repository: {repo_name}")
            
            try:
                repo = self.github_client.get_repo(repo_name)
            except GithubException as e:
                self.logger.error(f"❌ Erreur accès repository: {e.status} - {e.data}")
                return {
                    "success": False,
                    "error": f"Repository inaccessible: {e.status}",
                    "repository_url": repository_url
                }
            
            if config is None:
                config = GitHubCollectorConfig()
            
            if collectors is None:
                collectors = list(self.AVAILABLE_COLLECTORS.keys())
            
            self.logger.info(f"🔧 Collecteurs activés: {', '.join(collectors)}")
            
            collector_instances = []
            for collector_name in collectors:
                if collector_name in self.AVAILABLE_COLLECTORS:
                    collector_class = self.AVAILABLE_COLLECTORS[collector_name]
                    collector_instances.append(collector_class(self.github_client))
                else:
                    self.logger.warning(f"⚠️ Collecteur inconnu: {collector_name}")
            
            self.logger.info(f"🚀 Lancement de {len(collector_instances)} collecteurs en parallèle...")
            
            collection_tasks = []
            for collector in collector_instances:
                options = self._prepare_collector_options(collector, config)
                task = self._safe_collect(collector, repo, options)
                collection_tasks.append(task)
            
            results = await asyncio.gather(*collection_tasks, return_exceptions=True)
            
            aggregated_data = {
                "success": True,
                "repository_url": repository_url,
                "repository_name": repo_name,
                "collected_at": None,  
                "collectors_used": collectors,
                "data": {}
            }
            
            for collector, result in zip(collector_instances, results):
                if isinstance(result, Exception):
                    self.logger.error(f"❌ Exception dans {collector.collector_name}: {result}", exc_info=True)
                    aggregated_data["data"][collector.data_key] = {
                        "success": False,
                        "error": str(result),
                        "error_type": "exception"
                    }
                else:
                    aggregated_data["data"][collector.data_key] = result
            
            successful_collectors = sum(
                1 for data in aggregated_data["data"].values()
                if data.get("success", False)
            )
            
            self.logger.info("="*80)
            self.logger.info(f"✅ COLLECTE TERMINÉE: {successful_collectors}/{len(collector_instances)} collecteurs réussis")
            self.logger.info("="*80)
            
            return aggregated_data
            
        except Exception as e:
            self.logger.error(f"❌ Erreur orchestrateur: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "repository_url": repository_url
            }
    
    async def collect_specific(
        self,
        repository_url: str,
        collector_name: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte des informations avec un collecteur spécifique.
        
        Args:
            repository_url: URL du repository GitHub
            collector_name: Nom du collecteur à utiliser
            options: Options pour le collecteur
            
        Returns:
            Données collectées par le collecteur
        """
        try:
            if collector_name not in self.AVAILABLE_COLLECTORS:
                return {
                    "success": False,
                    "error": f"Collecteur inconnu: {collector_name}"
                }
            
            repo_name = self._extract_repo_name(repository_url)
            repo = self.github_client.get_repo(repo_name)
            
            collector_class = self.AVAILABLE_COLLECTORS[collector_name]
            collector = collector_class(self.github_client)
            
            result = await collector.collect(repo, options)
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Erreur collect_specific ({collector_name}): {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def format_for_llm(
        self,
        collected_data: Dict[str, Any],
        collectors: Optional[List[str]] = None
    ) -> str:
        """
        Formate toutes les données collectées pour inclusion dans un prompt LLM.
        
        Args:
            collected_data: Données collectées par collect_all()
            collectors: Liste des collecteurs à formater (None = tous)
            
        Returns:
            String formaté pour le LLM
        """
        if not collected_data.get("success"):
            return f"Erreur collecte GitHub: {collected_data.get('error', 'Inconnue')}"
        
        data = collected_data.get("data", {})
        
        if collectors is None:
            collectors = list(data.keys())
        
        formatted_sections = []
        formatted_sections.append("INFORMATIONS GITHUB COMPLÈTES (À UTILISER POUR RÉPONDRE):")
        formatted_sections.append("="*80)
        
        for collector_name in collectors:
            if collector_name not in data:
                continue
            
            collector_data = data[collector_name]
            
            if collector_name in self.AVAILABLE_COLLECTORS:
                collector_class = self.AVAILABLE_COLLECTORS[collector_name]
                collector = collector_class(self.github_client)
                formatted = collector.format_for_llm(collector_data)
                formatted_sections.append(formatted)
                formatted_sections.append("-"*80)
        
        return "\n\n".join(formatted_sections)
    
    async def _safe_collect(
        self,
        collector: GitHubDataCollector,
        repo,
        options: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Collecte de manière sûre (gère les exceptions).
        
        Args:
            collector: Instance du collecteur
            repo: Repository PyGithub
            options: Options pour le collecteur
            
        Returns:
            Résultat de la collecte
        """
        try:
            return await collector.collect(repo, options)
        except Exception as e:
            self.logger.error(f"❌ Erreur dans {collector.collector_name}: {e}", exc_info=True)
            return collector.handle_error(e, "collection failed")
    
    def _prepare_collector_options(
        self,
        collector: GitHubDataCollector,
        config: GitHubCollectorConfig
    ) -> Dict[str, Any]:
        """
        Prépare les options pour un collecteur basé sur la config globale.
        
        Args:
            collector: Instance du collecteur
            config: Configuration globale
            
        Returns:
            Dictionnaire d'options pour le collecteur
        """
        options = {}
        
        config_dict = config.to_dict()
        
        if isinstance(collector, PullRequestCollector):
            options["limit"] = config_dict["limit_prs"]
            options["include_files"] = config_dict["include_pr_files"]
        elif isinstance(collector, IssueCollector):
            options["limit"] = config_dict["limit_issues"]
            options["state"] = "all" if config_dict["include_closed_issues"] else "open"
        elif isinstance(collector, CommitCollector):
            options["limit"] = config_dict["limit_commits"]
            options["include_files"] = config_dict["include_commit_files"]
        elif isinstance(collector, BranchCollector):
            options["limit"] = config_dict["limit_branches"]
            options["include_all"] = config_dict["include_all_branches"]
        elif isinstance(collector, ReleaseCollector):
            options["limit"] = config_dict["limit_releases"]
        elif isinstance(collector, ContributorCollector):
            options["limit"] = config_dict["limit_contributors"]
        elif isinstance(collector, LabelCollector):
            options["limit"] = config_dict["limit_labels"]
        elif isinstance(collector, MilestoneCollector):
            options["limit"] = config_dict["limit_milestones"]
        
        return options
    
    def _extract_repo_name(self, repo_url: str) -> str:
        """
        Extrait le nom du repository depuis l'URL.
        
        Args:
            repo_url: URL du repository
            
        Returns:
            Nom au format 'owner/repo'
        """
        if "github.com/" in repo_url:
            parts = repo_url.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1].replace(".git", "")
                return f"{owner}/{repo}"
        raise ValueError(f"Format d'URL GitHub invalide: {repo_url}")
    
    @classmethod
    def get_available_collectors(cls) -> List[str]:
        """
        Retourne la liste des collecteurs disponibles.
        
        Returns:
            Liste des noms de collecteurs
        """
        return list(cls.AVAILABLE_COLLECTORS.keys())
    
    @classmethod
    def register_collector(cls, name: str, collector_class: Type[GitHubDataCollector]):
        """
        Enregistre un nouveau collecteur (permet d'étendre l'orchestrateur).
        
        Args:
            name: Nom du collecteur
            collector_class: Classe du collecteur
        """
        cls.AVAILABLE_COLLECTORS[name] = collector_class
        logger.info(f"✅ Nouveau collecteur enregistré: {name}")

