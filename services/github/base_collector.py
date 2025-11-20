"""
Classe de base abstraite pour les collecteurs d'informations GitHub.

Architecture orientée objet permettant d'ajouter facilement de nouveaux types
d'informations GitHub sans modifier le code existant.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from github import Github, GithubException

from utils.logger import get_logger

logger = get_logger(__name__)


class GitHubDataCollector(ABC):
    """
    Classe de base abstraite pour tous les collecteurs d'informations GitHub.
    
    Chaque collecteur est responsable d'un type spécifique d'informations
    (PRs, issues, commits, etc.).
    """
    
    def __init__(self, github_client: Github):
        """
        Initialise le collecteur avec un client GitHub.
        
        Args:
            github_client: Instance du client PyGithub
        """
        self.github_client = github_client
        self.logger = logger
    
    @property
    @abstractmethod
    def collector_name(self) -> str:
        """
        Nom du collecteur (pour les logs et le contexte).
        
        Returns:
            Nom descriptif du collecteur
        """
        pass
    
    @property
    @abstractmethod
    def data_key(self) -> str:
        """
        Clé utilisée pour stocker les données dans le contexte.
        
        Returns:
            Clé du dictionnaire de contexte
        """
        pass
    
    @abstractmethod
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les informations depuis l'API GitHub.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration (limite, filtres, etc.)
            
        Returns:
            Dictionnaire avec les données collectées et metadata
        """
        pass
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """
        Formate les données pour inclusion dans le prompt LLM.
        
        Args:
            data: Données collectées par collect()
            
        Returns:
            String formaté lisible pour le LLM
        """
        return f"{self.collector_name}:\n{data}"
    
    def handle_error(self, error: Exception, context: str = "") -> Dict[str, Any]:
        """
        Gère les erreurs de manière uniforme.
        
        Args:
            error: Exception levée
            context: Contexte additionnel pour les logs
            
        Returns:
            Dictionnaire d'erreur standardisé
        """
        error_msg = f"{self.collector_name} - {context}: {str(error)}"
        
        if isinstance(error, GithubException):
            self.logger.warning(f"⚠️ GitHub API error ({error.status}): {error_msg}")
            return {
                "success": False,
                "error": f"GitHub API error: {error.status}",
                "error_type": "github_api",
                "data": None
            }
        else:
            self.logger.error(f"❌ {error_msg}", exc_info=True)
            return {
                "success": False,
                "error": str(error),
                "error_type": "unknown",
                "data": None
            }
    
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


class GitHubCollectorConfig:
    """Configuration pour les collecteurs d'informations GitHub."""
    
    def __init__(
        self,
        limit_prs: int = 5,
        limit_issues: int = 10,
        limit_commits: int = 10,
        limit_branches: int = 10,
        limit_releases: int = 5,
        limit_contributors: int = 10,
        limit_labels: int = 20,
        limit_milestones: int = 5,
        include_pr_files: bool = True,
        include_commit_files: bool = False,
        include_closed_issues: bool = False,
        include_all_branches: bool = False
    ):
        """
        Initialise la configuration des collecteurs.
        
        Args:
            limit_*: Nombre maximum d'éléments à récupérer par type
            include_*: Flags pour inclure des données supplémentaires
        """
        self.limit_prs = limit_prs
        self.limit_issues = limit_issues
        self.limit_commits = limit_commits
        self.limit_branches = limit_branches
        self.limit_releases = limit_releases
        self.limit_contributors = limit_contributors
        self.limit_labels = limit_labels
        self.limit_milestones = limit_milestones
        self.include_pr_files = include_pr_files
        self.include_commit_files = include_commit_files
        self.include_closed_issues = include_closed_issues
        self.include_all_branches = include_all_branches
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la configuration en dictionnaire."""
        return {
            "limit_prs": self.limit_prs,
            "limit_issues": self.limit_issues,
            "limit_commits": self.limit_commits,
            "limit_branches": self.limit_branches,
            "limit_releases": self.limit_releases,
            "limit_contributors": self.limit_contributors,
            "limit_labels": self.limit_labels,
            "limit_milestones": self.limit_milestones,
            "include_pr_files": self.include_pr_files,
            "include_commit_files": self.include_commit_files,
            "include_closed_issues": self.include_closed_issues,
            "include_all_branches": self.include_all_branches
        }

