"""
Collecteur d'informations sur les Issues GitHub.

Récupère les issues ouvertes/fermées avec leurs métadonnées.
"""

from typing import Dict, Any, Optional

from services.github.base_collector import GitHubDataCollector


class IssueCollector(GitHubDataCollector):
    """Collecte les Issues du repository."""
    
    @property
    def collector_name(self) -> str:
        return "Issues"
    
    @property
    def data_key(self) -> str:
        return "issues"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les Issues.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration
                - limit: Nombre max d'issues (défaut: 10)
                - state: État (open/closed/all, défaut: open)
                
        Returns:
            Liste des Issues avec leurs détails
        """
        try:
            options = options or {}
            limit = options.get("limit", 10)
            state = options.get("state", "open")
            
            self.logger.info(f"🐛 {self.collector_name}: Récupération (state={state}, limit={limit})...")
            
            issues_list = []
            issues = repo.get_issues(state=state, sort="updated", direction="desc")
            
            for i, issue in enumerate(issues):
                if i >= limit:
                    break
                
                if issue.pull_request:
                    continue
                
                issue_data = {
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "user": issue.user.login if issue.user else "Unknown",
                    "created_at": issue.created_at.isoformat() if issue.created_at else None,
                    "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                    "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                    "closed_by": issue.closed_by.login if issue.closed_by else None,
                    "labels": [label.name for label in issue.labels],
                    "assignees": [assignee.login for assignee in issue.assignees],
                    "milestone": issue.milestone.title if issue.milestone else None,
                    "comments_count": issue.comments,
                    "body": issue.body[:500] if issue.body else None  
                }
                
                issues_list.append(issue_data)
            
            self.logger.info(f"✅ {self.collector_name}: {len(issues_list)} issues récupérées")
            
            return {
                "success": True,
                "issues": issues_list,
                "count": len(issues_list)
            }
            
        except Exception as e:
            return self.handle_error(e, "collect issues")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les issues pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        issues = data.get("issues", [])
        if not issues:
            return f"{self.collector_name}: Aucune issue trouvée"
        
        lines = [f"{self.collector_name} ({len(issues)} issue{'s' if len(issues) > 1 else ''}):"]
        
        for issue in issues:
            issue_line = f"""
Issue #{issue['number']} ({issue['state']}):
  - Titre: {issue['title']}
  - Auteur: {issue['user']}
  - Créée le: {issue['created_at']}
  - Mise à jour le: {issue['updated_at']}"""
            
            if issue.get('closed_at'):
                issue_line += f"\n  - Fermée le: {issue['closed_at']}"
                if issue.get('closed_by'):
                    issue_line += f" par {issue['closed_by']}"
            
            if issue.get('labels'):
                issue_line += f"\n  - Labels: {', '.join(issue['labels'])}"
            
            if issue.get('assignees'):
                issue_line += f"\n  - Assignées à: {', '.join(issue['assignees'])}"
            
            if issue.get('milestone'):
                issue_line += f"\n  - Milestone: {issue['milestone']}"
            
            if issue.get('comments_count'):
                issue_line += f"\n  - Commentaires: {issue['comments_count']}"
            
            lines.append(issue_line)
        
        return "\n".join(lines)

