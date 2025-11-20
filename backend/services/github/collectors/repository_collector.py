"""
Collecteur d'informations sur le repository GitHub.

Récupère les métadonnées générales du repository.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from services.github.base_collector import GitHubDataCollector


class RepositoryCollector(GitHubDataCollector):
    """Collecte les métadonnées du repository."""
    
    @property
    def collector_name(self) -> str:
        return "Repository Metadata"
    
    @property
    def data_key(self) -> str:
        return "repository"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les métadonnées du repository.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options (non utilisées ici)
            
        Returns:
            Métadonnées du repository
        """
        try:
            self.logger.info(f"📊 {self.collector_name}: Récupération des métadonnées...")
            
            data = {
                "success": True,
                "name": repo.name,
                "full_name": repo.full_name,
                "owner": repo.owner.login,
                "owner_type": repo.owner.type,
                "description": repo.description,
                "language": repo.language,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "watchers": repo.watchers_count,
                "open_issues": repo.open_issues_count,
                "default_branch": repo.default_branch,
                "is_private": repo.private,
                "is_fork": repo.fork,
                "is_archived": repo.archived,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                "size": repo.size,
                "topics": list(repo.get_topics()),
                "license": repo.license.name if repo.license else None,
                "has_issues": repo.has_issues,
                "has_projects": repo.has_projects,
                "has_wiki": repo.has_wiki,
                "has_discussions": getattr(repo, 'has_discussions', False)  
            }

            try:
                structure = self._get_repository_structure(repo, options)
                if structure:
                    data["structure"] = structure
                    self.logger.info(f"✅ Structure récupérée: {len(structure)} éléments")
            except Exception as e:
                self.logger.warning(f"⚠️ Impossible de récupérer la structure: {e}")
            
            self.logger.info(f"✅ {self.collector_name}: {repo.full_name} récupéré")
            return data
            
        except Exception as e:
            return self.handle_error(e, "collect repository metadata")
    
    def _get_repository_structure(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> list:
        """
        Récupère la structure des fichiers du repository.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options (max_depth, max_files)
            
        Returns:
            Liste des fichiers et dossiers
        """
        max_files = (options or {}).get("max_structure_files", 50)
        
        try:
            default_branch = repo.default_branch
            branch = repo.get_branch(default_branch)
            tree = repo.get_git_tree(branch.commit.sha, recursive=True)
            
            structure = []
            for item in tree.tree[:max_files]:
                structure.append({
                    "path": item.path,
                    "type": item.type,  
                    "size": item.size if hasattr(item, 'size') else 0
                })
            
            return structure
            
        except Exception as e:
            self.logger.warning(f"Erreur récupération structure: {e}")
            return []
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les métadonnées pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        return f"""Repository:
- Nom complet: {data.get('full_name')}
- Owner: {data.get('owner')} ({data.get('owner_type')})
- Description: {data.get('description', 'N/A')}
- Langage principal: {data.get('language', 'N/A')}
- Stars: {data.get('stars', 0)}, Forks: {data.get('forks', 0)}, Watchers: {data.get('watchers', 0)}
- Issues ouvertes: {data.get('open_issues', 0)}
- Branche par défaut: {data.get('default_branch', 'main')}
- Créé le: {data.get('created_at', 'N/A')}
- Dernière mise à jour: {data.get('updated_at', 'N/A')}
- Dernier push: {data.get('pushed_at', 'N/A')}
- Privé: {'Oui' if data.get('is_private') else 'Non'}
- Archivé: {'Oui' if data.get('is_archived') else 'Non'}
- Fork: {'Oui' if data.get('is_fork') else 'Non'}
- Topics: {', '.join(data.get('topics', [])) if data.get('topics') else 'Aucun'}
- Licence: {data.get('license', 'N/A')}
- Features: Issues={data.get('has_issues')}, Wiki={data.get('has_wiki')}, Discussions={data.get('has_discussions')}"""

