"""
Service pour récupérer des informations depuis GitHub.

Ce service permet de répondre à des questions sur :
- Les Pull Requests (dernière PR, PR ouvertes, etc.)
- Le repository (owner, description, langages, etc.)
- Les issues, contributors, etc.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from github import Github, GithubException

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GitHubInfoService:
    """Service pour récupérer des informations depuis GitHub."""
    
    def __init__(self):
        """Initialise le service avec le client GitHub."""
        self.github_client = Github(settings.github_token)
    
    def _extract_repo_name(self, repo_url: str) -> str:
        """
        Extrait le nom du repository depuis l'URL.
        
        Args:
            repo_url: URL du repository GitHub
            
        Returns:
            Nom du repository au format 'owner/repo'
        """
        if not repo_url:
            raise ValueError("URL du repository non fournie")
        
        repo_url = repo_url.strip()
        if "github.com/" in repo_url:
            parts = repo_url.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1].replace(".git", "")
                return f"{owner}/{repo}"
        
        raise ValueError(f"Format d'URL GitHub invalide: {repo_url}")
    
    async def get_repository_info(self, repo_url: str) -> Dict[str, Any]:
        try:
            repo_name = self._extract_repo_name(repo_url)
            logger.info(f"📊 Récupération infos repository: {repo_name}")
            
            repo = self.github_client.get_repo(repo_name)
            
            return {
                "success": True,
                "name": repo.name,
                "full_name": repo.full_name,
                "owner": repo.owner.login,
                "owner_type": repo.owner.type, 
                "description": repo.description,
                "language": repo.language,
                "languages": self._get_repository_languages(repo),
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "open_issues": repo.open_issues_count,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                "default_branch": repo.default_branch,
                "is_private": repo.private,
                "url": repo.html_url
            }
        
        except GithubException as e:
            logger.error(f"❌ Erreur GitHub API: {e.status} - {e.data}")
            return {
                "success": False,
                "error": f"Erreur GitHub: {e.status}",
                "message": str(e.data.get("message", "Erreur inconnue"))
            }
        except Exception as e:
            logger.error(f"❌ Erreur récupération infos repository: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_repository_languages(self, repo) -> Dict[str, int]:
        """Récupère les langages utilisés dans le repository."""
        try:
            return repo.get_languages()
        except:
            return {}
    
    async def get_pr_files(
        self,
        repo_url: str,
        pr_number: int
    ) -> Dict[str, Any]:
        """
        Récupère les fichiers modifiés dans une Pull Request spécifique.
        
        Args:
            repo_url: URL du repository
            pr_number: Numéro de la Pull Request
            
        Returns:
            Liste des fichiers modifiés avec leurs changements
        """
        try:
            repo_name = self._extract_repo_name(repo_url)
            logger.info(f"📄 Récupération fichiers PR #{pr_number}: {repo_name}")
            
            repo = self.github_client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            
            files_list = []
            for file in pr.get_files():
                files_list.append({
                    "filename": file.filename,
                    "status": file.status,  
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch[:500] if file.patch else None  
                })
            
            return {
                "success": True,
                "files": files_list,
                "total_files": len(files_list),
                "total_additions": sum(f["additions"] for f in files_list),
                "total_deletions": sum(f["deletions"] for f in files_list)
            }
        
        except GithubException as e:
            logger.error(f"❌ Erreur GitHub API PR #{pr_number}: {e.status}")
            return {
                "success": False,
                "error": f"Erreur GitHub: {e.status}",
                "files": []
            }
        except Exception as e:
            logger.error(f"❌ Erreur récupération fichiers PR #{pr_number}: {e}")
            return {
                "success": False,
                "error": str(e),
                "files": []
            }
    
    async def get_pull_requests(
        self,
        repo_url: str,
        state: str = "all",
        limit: int = 10,
        include_files: bool = False
    ) -> Dict[str, Any]:
        """
        Récupère les Pull Requests du repository.
        
        Args:
            repo_url: URL du repository
            state: État des PRs ('open', 'closed', 'all')
            limit: Nombre maximum de PRs à récupérer
            include_files: Si True, inclut les fichiers modifiés pour chaque PR
            
        Returns:
            Liste des Pull Requests
        """
        try:
            repo_name = self._extract_repo_name(repo_url)
            logger.info(f"📋 Récupération PRs ({state}): {repo_name}")
            
            repo = self.github_client.get_repo(repo_name)
            pulls = repo.get_pulls(state=state, sort='created', direction='desc')
            
            prs_list = []
            for pr in list(pulls)[:limit]:
                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "user": pr.user.login if pr.user else "Unknown",
                    "created_at": pr.created_at.isoformat() if pr.created_at else None,
                    "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
                    "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                    "body": pr.body[:300] if pr.body else "",  # Limiter la taille
                    "url": pr.html_url,
                    "head_branch": pr.head.ref,
                    "base_branch": pr.base.ref,
                    "mergeable": pr.mergeable,
                    "merged": pr.merged
                }
                
                if include_files:
                    try:
                        files = pr.get_files()
                        pr_data["files"] = [{
                            "filename": f.filename,
                            "status": f.status,
                            "additions": f.additions,
                            "deletions": f.deletions,
                            "changes": f.changes
                        } for f in list(files)[:50]]  
                        pr_data["total_files"] = len(pr_data["files"])
                    except Exception as file_error:
                        logger.warning(f"⚠️ Impossible de récupérer fichiers pour PR #{pr.number}: {file_error}")
                        pr_data["files"] = []
                        pr_data["total_files"] = 0
                
                prs_list.append(pr_data)
            
            return {
                "success": True,
                "pull_requests": prs_list,
                "count": len(prs_list)
            }
        
        except GithubException as e:
            logger.error(f"❌ Erreur GitHub API: {e.status}")
            return {
                "success": False,
                "error": f"Erreur GitHub: {e.status}",
                "pull_requests": []
            }
        except Exception as e:
            logger.error(f"❌ Erreur récupération PRs: {e}")
            return {
                "success": False,
                "error": str(e),
                "pull_requests": []
            }
    
    async def get_latest_pull_request(
        self,
        repo_url: str,
        include_files: bool = True
    ) -> Dict[str, Any]:
        """
        Récupère la dernière Pull Request créée.
        
        Args:
            repo_url: URL du repository
            include_files: Si True, inclut les fichiers modifiés dans la PR
            
        Returns:
            Informations sur la dernière PR avec fichiers modifiés
        """
        result = await self.get_pull_requests(
            repo_url,
            state="all",
            limit=1,
            include_files=include_files
        )
        
        if result["success"] and result["pull_requests"]:
            pr = result["pull_requests"][0]
            
            if include_files and "files" not in pr:
                files_result = await self.get_pr_files(repo_url, pr["number"])
                if files_result["success"]:
                    pr["files"] = files_result["files"]
                    pr["total_files"] = files_result["total_files"]
                    pr["total_additions"] = files_result["total_additions"]
                    pr["total_deletions"] = files_result["total_deletions"]
            
            return {
                "success": True,
                "pull_request": pr
            }
        
        return {
            "success": False,
            "error": "Aucune Pull Request trouvée",
            "pull_request": None
        }
    
    async def get_issues(
        self,
        repo_url: str,
        state: str = "open",
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Récupère les issues du repository.
        
        Args:
            repo_url: URL du repository
            state: État des issues ('open', 'closed', 'all')
            limit: Nombre maximum d'issues à récupérer
            
        Returns:
            Liste des issues
        """
        try:
            repo_name = self._extract_repo_name(repo_url)
            logger.info(f"🐛 Récupération issues ({state}): {repo_name}")
            
            repo = self.github_client.get_repo(repo_name)
            issues = repo.get_issues(state=state, sort='created', direction='desc')
            
            issues_list = []
            for issue in list(issues)[:limit]:
                if issue.pull_request is None:
                    issues_list.append({
                        "number": issue.number,
                        "title": issue.title,
                        "state": issue.state,
                        "user": issue.user.login if issue.user else "Unknown",
                        "created_at": issue.created_at.isoformat() if issue.created_at else None,
                        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                        "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                        "body": issue.body[:300] if issue.body else "",
                        "url": issue.html_url,
                        "labels": [label.name for label in issue.labels]
                    })
            
            return {
                "success": True,
                "issues": issues_list,
                "count": len(issues_list)
            }
        
        except GithubException as e:
            logger.error(f"❌ Erreur GitHub API: {e.status}")
            return {
                "success": False,
                "error": f"Erreur GitHub: {e.status}",
                "issues": []
            }
        except Exception as e:
            logger.error(f"❌ Erreur récupération issues: {e}")
            return {
                "success": False,
                "error": str(e),
                "issues": []
            }
    
    async def get_contributors(
        self,
        repo_url: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Récupère les contributeurs du repository.
        
        Args:
            repo_url: URL du repository
            limit: Nombre maximum de contributeurs à récupérer
            
        Returns:
            Liste des contributeurs
        """
        try:
            repo_name = self._extract_repo_name(repo_url)
            logger.info(f"👥 Récupération contributeurs: {repo_name}")
            
            repo = self.github_client.get_repo(repo_name)
            contributors = repo.get_contributors()
            
            contributors_list = []
            for contributor in list(contributors)[:limit]:
                contributors_list.append({
                    "login": contributor.login,
                    "contributions": contributor.contributions,
                    "type": contributor.type,
                    "url": contributor.html_url
                })
            
            return {
                "success": True,
                "contributors": contributors_list,
                "count": len(contributors_list)
            }
        
        except GithubException as e:
            logger.error(f"❌ Erreur GitHub API: {e.status}")
            return {
                "success": False,
                "error": f"Erreur GitHub: {e.status}",
                "contributors": []
            }
        except Exception as e:
            logger.error(f"❌ Erreur récupération contributeurs: {e}")
            return {
                "success": False,
                "error": str(e),
                "contributors": []
            }
    
    async def get_github_context(
        self,
        repo_url: str,
        include_prs: bool = True,
        include_issues: bool = False,
        include_contributors: bool = False
    ) -> Dict[str, Any]:
        """
        Récupère un contexte GitHub complet pour enrichir les réponses.
        
        Args:
            repo_url: URL du repository
            include_prs: Inclure les PRs
            include_issues: Inclure les issues
            include_contributors: Inclure les contributeurs
            
        Returns:
            Contexte GitHub enrichi
        """
        logger.info(f"📦 Récupération contexte GitHub complet: {repo_url}")
        
        context = {
            "repository_url": repo_url
        }
        
        repo_info = await self.get_repository_info(repo_url)
        context["repository"] = repo_info
        
        if include_prs and repo_info.get("success"):
            prs_info = await self.get_pull_requests(repo_url, state="all", limit=5)
            context["pull_requests"] = prs_info.get("pull_requests", [])
            context["latest_pr"] = prs_info["pull_requests"][0] if prs_info.get("pull_requests") else None
        
        if include_issues and repo_info.get("success"):
            issues_info = await self.get_issues(repo_url, state="open", limit=5)
            context["issues"] = issues_info.get("issues", [])
        
        if include_contributors and repo_info.get("success"):
            contributors_info = await self.get_contributors(repo_url, limit=5)
            context["contributors"] = contributors_info.get("contributors", [])
        
        return context


github_info_service = GitHubInfoService()

