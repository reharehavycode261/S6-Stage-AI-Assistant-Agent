"""
Collecteur d'informations sur les Commits et Branches GitHub.

Récupère les commits récents et les branches du repository.
"""

from typing import Dict, Any, Optional

from services.github.base_collector import GitHubDataCollector


class CommitCollector(GitHubDataCollector):
    """Collecte les commits du repository."""
    
    @property
    def collector_name(self) -> str:
        return "Commits"
    
    @property
    def data_key(self) -> str:
        return "commits"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les commits récents.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration
                - limit: Nombre max de commits (défaut: 10)
                - branch: Branche à analyser (défaut: branche par défaut)
                - include_files: Inclure les fichiers modifiés (défaut: False)
                
        Returns:
            Liste des commits avec leurs détails
        """
        try:
            options = options or {}
            limit = options.get("limit", 10)
            branch = options.get("branch", repo.default_branch)
            include_files = options.get("include_files", False)
            
            self.logger.info(f"📝 {self.collector_name}: Récupération (branch={branch}, limit={limit})...")
            
            commits_list = []
            commits = repo.get_commits(sha=branch)
            
            for i, commit in enumerate(commits):
                if i >= limit:
                    break
                
                commit_data = {
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": commit.commit.author.name if commit.commit.author else "Unknown",
                    "author_login": commit.author.login if commit.author else None,
                    "author_email": commit.commit.author.email if commit.commit.author else None,
                    "date": commit.commit.author.date.isoformat() if commit.commit.author else None,
                    "committer": commit.commit.committer.name if commit.commit.committer else "Unknown",
                    "committed_date": commit.commit.committer.date.isoformat() if commit.commit.committer else None,
                    "verified": False,  # Sera défini ci-dessous si disponible
                    "parents_count": len(commit.parents)
                }
                
                # Vérifier si l'attribut verification existe (peut ne pas exister dans toutes les versions)
                try:
                    if hasattr(commit.commit, 'verification') and commit.commit.verification:
                        commit_data["verified"] = commit.commit.verification.verified
                except Exception:
                    pass  # Garder False par défaut
                
                # Récupérer les fichiers modifiés si demandé
                if include_files:
                    try:
                        files_list = []
                        for file in commit.files:
                            files_list.append({
                                "filename": file.filename,
                                "status": file.status,
                                "additions": file.additions,
                                "deletions": file.deletions,
                                "changes": file.changes
                            })
                        commit_data["files"] = files_list
                        commit_data["files_count"] = len(files_list)
                    except Exception as file_error:
                        self.logger.warning(f"⚠️ Erreur fichiers commit {commit.sha[:7]}: {file_error}")
                        commit_data["files"] = []
                        commit_data["files_count"] = 0
                
                commits_list.append(commit_data)
            
            self.logger.info(f"✅ {self.collector_name}: {len(commits_list)} commits récupérés")
            
            return {
                "success": True,
                "commits": commits_list,
                "count": len(commits_list),
                "branch": branch,
                "latest_commit": commits_list[0] if commits_list else None
            }
            
        except Exception as e:
            return self.handle_error(e, "collect commits")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les commits pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        commits = data.get("commits", [])
        branch = data.get("branch", "unknown")
        
        if not commits:
            return f"{self.collector_name}: Aucun commit trouvé sur {branch}"
        
        lines = [f"{self.collector_name} sur {branch} ({len(commits)} commit{'s' if len(commits) > 1 else ''}):"]
        
        for commit in commits:
            commit_line = f"""
Commit {commit['sha'][:7]}:
  - Message: {commit['message'].split(chr(10))[0][:100]}
  - Auteur: {commit['author']} ({commit.get('author_login', 'N/A')})
  - Date: {commit['date']}
  - Vérifié: {'Oui' if commit.get('verified') else 'Non'}"""
            
            if commit.get('files'):
                commit_line += f"\n  - Fichiers modifiés ({commit.get('files_count', 0)}):"
                for file in commit['files'][:5]:
                    commit_line += f"\n    • {file['filename']} (+{file['additions']} -{file['deletions']})"
                if commit.get('files_count', 0) > 5:
                    commit_line += f"\n    ... et {commit['files_count'] - 5} autres fichiers"
            
            lines.append(commit_line)
        
        return "\n".join(lines)


class BranchCollector(GitHubDataCollector):
    """Collecte les branches du repository."""
    
    @property
    def collector_name(self) -> str:
        return "Branches"
    
    @property
    def data_key(self) -> str:
        return "branches"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les branches.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration
                - limit: Nombre max de branches (défaut: 10)
                - include_all: Inclure toutes les branches (défaut: False)
                
        Returns:
            Liste des branches avec leurs détails
        """
        try:
            options = options or {}
            limit = options.get("limit", 10)
            include_all = options.get("include_all", False)
            
            self.logger.info(f"🌿 {self.collector_name}: Récupération (limit={limit})...")
            
            branches_list = []
            branches = repo.get_branches()
            
            for i, branch in enumerate(branches):
                if not include_all and i >= limit:
                    break
                
                branch_data = {
                    "name": branch.name,
                    "protected": branch.protected,
                    "commit_sha": branch.commit.sha if branch.commit else None,
                    "commit_date": branch.commit.commit.author.date.isoformat() if branch.commit and branch.commit.commit.author else None
                }
                
                branches_list.append(branch_data)
            
            self.logger.info(f"✅ {self.collector_name}: {len(branches_list)} branches récupérées")
            
            return {
                "success": True,
                "branches": branches_list,
                "count": len(branches_list),
                "default_branch": repo.default_branch
            }
            
        except Exception as e:
            return self.handle_error(e, "collect branches")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les branches pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        branches = data.get("branches", [])
        default_branch = data.get("default_branch", "main")
        
        if not branches:
            return f"{self.collector_name}: Aucune branche trouvée"
        
        lines = [f"{self.collector_name} ({len(branches)} branche{'s' if len(branches) > 1 else ''}):"]
        lines.append(f"- Branche par défaut: {default_branch}")
        
        for branch in branches:
            branch_line = f"  - {branch['name']}"
            if branch.get('protected'):
                branch_line += " (protégée)"
            if branch['name'] == default_branch:
                branch_line += " [DEFAULT]"
            if branch.get('commit_date'):
                branch_line += f" | Dernier commit: {branch['commit_date']}"
            lines.append(branch_line)
        
        return "\n".join(lines)

