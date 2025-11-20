"""
Collecteur d'informations sur les Pull Requests GitHub.

Récupère les PRs avec toutes leurs métadonnées et optionnellement les fichiers modifiés.
"""

from typing import Dict, Any, Optional, List

from services.github.base_collector import GitHubDataCollector


class PullRequestCollector(GitHubDataCollector):
    """Collecte les Pull Requests avec leurs détails."""
    
    @property
    def collector_name(self) -> str:
        return "Pull Requests"
    
    @property
    def data_key(self) -> str:
        return "pull_requests"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les Pull Requests.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration
                - limit: Nombre max de PRs (défaut: 5)
                - state: État des PRs (all/open/closed, défaut: all)
                - include_files: Inclure fichiers modifiés (défaut: True)
            
        Returns:
            Liste des Pull Requests avec leurs détails
        """
        try:
            options = options or {}
            limit = options.get("limit", 5)
            state = options.get("state", "all")
            include_files = options.get("include_files", True)
            
            self.logger.info(f"📋 {self.collector_name}: Récupération ({state}, limit={limit}, files={include_files})...")
            
            prs_list = []
            pulls = repo.get_pulls(state=state, sort="updated", direction="desc")
            
            for i, pr in enumerate(pulls):
                if i >= limit:
                    break
                
                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "user": pr.user.login if pr.user else "Unknown",
                    "created_at": pr.created_at.isoformat() if pr.created_at else None,
                    "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
                    "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
                    "merged": pr.merged,
                    "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                    "merged_by": pr.merged_by.login if pr.merged_by else None,
                    "head_branch": pr.head.ref,
                    "base_branch": pr.base.ref,
                    "draft": pr.draft,
                    "labels": [label.name for label in pr.labels],
                    "assignees": [assignee.login for assignee in pr.assignees],
                    "reviewers": [reviewer.login for reviewer in pr.requested_reviewers],
                    "comments_count": pr.comments,
                    "review_comments_count": pr.review_comments,
                    "commits_count": pr.commits,
                    "additions": pr.additions,
                    "deletions": pr.deletions,
                    "changed_files": pr.changed_files
                }

                if include_files:
                    try:
                        
                        MAX_FILES_SAFE = 100  
                        if pr.changed_files > MAX_FILES_SAFE:
                            self.logger.warning(
                                f"⚠️ PR #{pr.number} a {pr.changed_files} fichiers (> {MAX_FILES_SAFE}) - "
                                f"Récupération des fichiers ignorée pour éviter timeout GitHub API"
                            )
                            pr_data["files"] = []
                            pr_data["total_files"] = pr.changed_files
                            pr_data["files_skipped"] = True
                            pr_data["files_skipped_reason"] = f"Too many files ({pr.changed_files})"
                        else:
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
                            pr_data["files"] = files_list
                            pr_data["total_files"] = len(files_list)
                    except Exception as file_error:
                        error_str = str(file_error)
                        if "422" in error_str or "too long to generate" in error_str.lower():
                            self.logger.warning(
                                f"⚠️ Erreur récupération fichiers PR #{pr.number}: {error_str}\n"
                                f"💡 GitHub API 422: Diff trop volumineux - Ignoré (non-bloquant)"
                            )
                        else:
                            self.logger.warning(f"⚠️ Erreur récupération fichiers PR #{pr.number}: {file_error}")
                        pr_data["files"] = []
                        pr_data["total_files"] = 0
                
                prs_list.append(pr_data)
            
            self.logger.info(f"✅ {self.collector_name}: {len(prs_list)} PRs récupérées")
            
            return {
                "success": True,
                "pull_requests": prs_list,
                "count": len(prs_list),
                "latest_pr": prs_list[0] if prs_list else None
            }
            
        except Exception as e:
            return self.handle_error(e, "collect pull requests")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les PRs pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        prs = data.get("pull_requests", [])
        if not prs:
            return f"{self.collector_name}: Aucune PR trouvée"
        
        lines = [f"{self.collector_name} ({len(prs)} PR{'s' if len(prs) > 1 else ''}):"]
        
        for pr in prs:
            pr_line = f"""
PR #{pr['number']} ({pr['state']}{'merged)' if pr.get('merged') else ')'}:
  - Titre: {pr['title']}
  - Auteur: {pr['user']}
  - Branches: {pr['head_branch']} → {pr['base_branch']}
  - Créée le: {pr['created_at']}
  - Mise à jour le: {pr['updated_at']}"""
            
            if pr.get('merged') and pr.get('merged_at'):
                pr_line += f"\n  - Mergée le: {pr['merged_at']} par {pr.get('merged_by', 'N/A')}"
            
            if pr.get('draft'):
                pr_line += "\n  - Statut: DRAFT"
            
            pr_line += f"\n  - Statistiques: {pr['commits_count']} commits, +{pr['additions']} -{pr['deletions']}, {pr['changed_files']} fichiers"
            
            if pr.get('labels'):
                pr_line += f"\n  - Labels: {', '.join(pr['labels'])}"
            
            if pr.get('files'):
                pr_line += f"\n  - Fichiers modifiés ({pr.get('total_files', len(pr['files']))}):"
                for file in pr['files'][:10]:
                    pr_line += f"\n    • {file['filename']} ({file['status']}: +{file['additions']} -{file['deletions']})"
                if pr.get('total_files', 0) > 10:
                    pr_line += f"\n    ... et {pr['total_files'] - 10} autres fichiers"
            
            lines.append(pr_line)
        
        return "\n".join(lines)

