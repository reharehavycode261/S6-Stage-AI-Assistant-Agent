"""Service pour gérer les Pull Requests GitHub et récupérer la dernière PR fusionnée."""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from github import Github, GithubException
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)


class GitHubPRService:
    """Service pour gérer les opérations liées aux Pull Requests GitHub."""
    
    def __init__(self):
        """Initialise le service GitHub PR."""
        self.settings = get_settings()
        self.github_client = Github(self.settings.github_token)
    
    def _extract_repo_name(self, repo_url: str) -> str:
        """
        Extrait le nom du repository depuis une URL GitHub.
        
        Supporte les formats:
        - HTTPS: https://github.com/owner/repo
        - SSH: git@github.com:owner/repo
        - Sans protocole: github.com/owner/repo
        
        Args:
            repo_url: URL du repository
            
        Returns:
            Nom du repository au format owner/repo
            
        Raises:
            ValueError: Si l'URL est invalide
        """
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
        
        if repo_url.startswith('git@github.com:'):
            parts = repo_url.replace('git@github.com:', '')
            parts = parts.split('/')[0:2]
            return '/'.join(parts)
        
        if 'github.com/' in repo_url:
            parts = repo_url.split('github.com/')[-1]
            parts = parts.split('/')[0:2]
            return '/'.join(parts)
        
        raise ValueError(f"URL de repository invalide: {repo_url}")
    
    async def get_last_merged_pr(self, repo_url: str) -> Optional[Dict[str, Any]]:
        """
        Récupère la dernière Pull Request fusionnée sur un repository.
        
        Args:
            repo_url: URL du repository GitHub
            
        Returns:
            Dictionnaire avec les informations de la dernière PR fusionnée ou None si aucune PR trouvée
        """
        try:
            repo_name = self._extract_repo_name(repo_url)
            logger.info(f"🔍 Recherche de la dernière PR fusionnée sur {repo_name}")
            
            repo = self.github_client.get_repo(repo_name)
            
            pulls = repo.get_pulls(
                state='closed',
                sort='updated',
                direction='desc'
            )
            
            for pr in pulls:
                if pr.merged:
                    logger.info(f"✅ Dernière PR fusionnée trouvée: #{pr.number} - {pr.title}")
                    
                    return {
                        "success": True,
                        "pr_number": pr.number,
                        "pr_title": pr.title,
                        "pr_url": pr.html_url,
                        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                        "merged_by": pr.merged_by.login if pr.merged_by else None,
                        "head_branch": pr.head.ref,
                        "base_branch": pr.base.ref,
                        "commit_sha": pr.merge_commit_sha
                    }
            
            logger.warning(f"⚠️ Aucune PR fusionnée trouvée sur {repo_name}")
            return {
                "success": False,
                "error": "Aucune PR fusionnée trouvée",
                "repo_url": repo_url
            }
        
        except GithubException as e:
            logger.error(f"❌ Erreur GitHub API: {e}")
            return {
                "success": False,
                "error": f"Erreur GitHub API: {str(e)}",
                "status_code": e.status
            }
        
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération de la dernière PR: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_pr_by_number(self, repo_url: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """
        Récupère une PR spécifique par son numéro.
        
        Args:
            repo_url: URL du repository GitHub
            pr_number: Numéro de la PR
            
        Returns:
            Dictionnaire avec les informations de la PR ou None
        """
        try:
            repo_name = self._extract_repo_name(repo_url)
            repo = self.github_client.get_repo(repo_name)
            
            pr = repo.get_pull(pr_number)
            
            return {
                "success": True,
                "pr_number": pr.number,
                "pr_title": pr.title,
                "pr_url": pr.html_url,
                "state": pr.state,
                "merged": pr.merged,
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "head_branch": pr.head.ref,
                "base_branch": pr.base.ref
            }
        
        except GithubException as e:
            logger.error(f"❌ Erreur récupération PR #{pr_number}: {e}")
            return {
                "success": False,
                "error": f"PR #{pr_number} non trouvée: {str(e)}"
            }
        
        except Exception as e:
            logger.error(f"❌ Erreur inattendue: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_merged_prs_since(self, repo_url: str, since_date: datetime) -> List[Dict[str, Any]]:
        """
        Récupère toutes les PRs fusionnées depuis une date donnée.
        
        Args:
            repo_url: URL du repository GitHub
            since_date: Date à partir de laquelle chercher
            
        Returns:
            Liste des PRs fusionnées
        """
        try:
            repo_name = self._extract_repo_name(repo_url)
            repo = self.github_client.get_repo(repo_name)
            
            pulls = repo.get_pulls(
                state='closed',
                sort='updated',
                direction='desc'
            )
            
            merged_prs = []
            for pr in pulls:
                if pr.merged and pr.merged_at and pr.merged_at >= since_date:
                    merged_prs.append({
                        "pr_number": pr.number,
                        "pr_title": pr.title,
                        "pr_url": pr.html_url,
                        "merged_at": pr.merged_at.isoformat(),
                        "head_branch": pr.head.ref,
                        "base_branch": pr.base.ref
                    })
                elif pr.merged_at and pr.merged_at < since_date:
                    break
            
            logger.info(f"✅ {len(merged_prs)} PR(s) fusionnée(s) trouvée(s) depuis {since_date.isoformat()}")
            return merged_prs
        
        except Exception as e:
            logger.error(f"❌ Erreur récupération PRs: {e}")
            return []


github_pr_service = GitHubPRService()

