"""
Collecteur d'informations sur les Labels, Milestones et autres métadonnées GitHub.

Récupère les labels, milestones, workflows, et autres informations du repository.
"""

from typing import Dict, Any, Optional

from services.github.base_collector import GitHubDataCollector


class LabelCollector(GitHubDataCollector):
    """Collecte les labels du repository."""
    
    @property
    def collector_name(self) -> str:
        return "Labels"
    
    @property
    def data_key(self) -> str:
        return "labels"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les labels.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration
                - limit: Nombre max de labels (défaut: 20)
                
        Returns:
            Liste des labels
        """
        try:
            options = options or {}
            limit = options.get("limit", 20)
            
            self.logger.info(f"🏷️  {self.collector_name}: Récupération (limit={limit})...")
            
            labels_list = []
            labels = repo.get_labels()
            
            for i, label in enumerate(labels):
                if i >= limit:
                    break
                
                label_data = {
                    "name": label.name,
                    "color": label.color,
                    "description": label.description
                }
                
                labels_list.append(label_data)
            
            self.logger.info(f"✅ {self.collector_name}: {len(labels_list)} labels récupérés")
            
            return {
                "success": True,
                "labels": labels_list,
                "count": len(labels_list)
            }
            
        except Exception as e:
            return self.handle_error(e, "collect labels")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les labels pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        labels = data.get("labels", [])
        
        if not labels:
            return f"{self.collector_name}: Aucun label trouvé"
        
        lines = [f"{self.collector_name} ({len(labels)} label{'s' if len(labels) > 1 else ''}):"]
        
        for label in labels:
            label_line = f"  - {label['name']}"
            if label.get('description'):
                label_line += f": {label['description']}"
            lines.append(label_line)
        
        return "\n".join(lines)


class MilestoneCollector(GitHubDataCollector):
    """Collecte les milestones du repository."""
    
    @property
    def collector_name(self) -> str:
        return "Milestones"
    
    @property
    def data_key(self) -> str:
        return "milestones"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les milestones.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration
                - limit: Nombre max de milestones (défaut: 5)
                - state: État (open/closed/all, défaut: open)
                
        Returns:
            Liste des milestones
        """
        try:
            options = options or {}
            limit = options.get("limit", 5)
            state = options.get("state", "open")
            
            self.logger.info(f"🎯 {self.collector_name}: Récupération (state={state}, limit={limit})...")
            
            milestones_list = []
            milestones = repo.get_milestones(state=state)
            
            for i, milestone in enumerate(milestones):
                if i >= limit:
                    break
                
                milestone_data = {
                    "number": milestone.number,
                    "title": milestone.title,
                    "state": milestone.state,
                    "description": milestone.description,
                    "created_at": milestone.created_at.isoformat() if milestone.created_at else None,
                    "due_on": milestone.due_on.isoformat() if milestone.due_on else None,
                    "closed_at": milestone.closed_at.isoformat() if milestone.closed_at else None,
                    "open_issues": milestone.open_issues,
                    "closed_issues": milestone.closed_issues
                }
                
                milestones_list.append(milestone_data)
            
            self.logger.info(f"✅ {self.collector_name}: {len(milestones_list)} milestones récupérés")
            
            return {
                "success": True,
                "milestones": milestones_list,
                "count": len(milestones_list)
            }
            
        except Exception as e:
            return self.handle_error(e, "collect milestones")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les milestones pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        milestones = data.get("milestones", [])
        
        if not milestones:
            return f"{self.collector_name}: Aucun milestone trouvé"
        
        lines = [f"{self.collector_name} ({len(milestones)} milestone{'s' if len(milestones) > 1 else ''}):"]
        
        for milestone in milestones:
            milestone_line = f"""
Milestone #{milestone['number']} ({milestone['state']}):
  - Titre: {milestone['title']}
  - Issues: {milestone['open_issues']} ouvertes, {milestone['closed_issues']} fermées"""
            
            if milestone.get('due_on'):
                milestone_line += f"\n  - Échéance: {milestone['due_on']}"
            
            if milestone.get('description'):
                milestone_line += f"\n  - Description: {milestone['description'][:100]}..."
            
            lines.append(milestone_line)
        
        return "\n".join(lines)


class WorkflowCollector(GitHubDataCollector):
    """Collecte les workflows GitHub Actions."""
    
    @property
    def collector_name(self) -> str:
        return "GitHub Actions Workflows"
    
    @property
    def data_key(self) -> str:
        return "workflows"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les workflows GitHub Actions.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options (non utilisées ici)
                
        Returns:
            Liste des workflows
        """
        try:
            self.logger.info(f"⚙️  {self.collector_name}: Récupération...")
            
            workflows_list = []
            
            try:
                workflows = repo.get_workflows()
                
                for workflow in workflows:
                    workflow_data = {
                        "id": workflow.id,
                        "name": workflow.name,
                        "path": workflow.path,
                        "state": workflow.state,
                        "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
                        "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None
                    }
                    
                    workflows_list.append(workflow_data)
            
            except Exception as workflow_error:
                self.logger.debug(f"Pas de workflows ou accès refusé: {workflow_error}")
                return {
                    "success": True,
                    "workflows": [],
                    "count": 0,
                    "has_workflows": False
                }
            
            self.logger.info(f"✅ {self.collector_name}: {len(workflows_list)} workflows récupérés")
            
            return {
                "success": True,
                "workflows": workflows_list,
                "count": len(workflows_list),
                "has_workflows": True
            }
            
        except Exception as e:
            return self.handle_error(e, "collect workflows")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les workflows pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        if not data.get("has_workflows"):
            return f"{self.collector_name}: Aucun workflow configuré"
        
        workflows = data.get("workflows", [])
        
        if not workflows:
            return f"{self.collector_name}: Aucun workflow trouvé"
        
        lines = [f"{self.collector_name} ({len(workflows)} workflow{'s' if len(workflows) > 1 else ''}):"]
        
        for workflow in workflows:
            lines.append(f"  - {workflow['name']} ({workflow['state']}): {workflow['path']}")
        
        return "\n".join(lines)


class SecurityCollector(GitHubDataCollector):
    """Collecte les informations de sécurité (vulnerabilities, security advisories)."""
    
    @property
    def collector_name(self) -> str:
        return "Sécurité"
    
    @property
    def data_key(self) -> str:
        return "security"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les informations de sécurité.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options (non utilisées ici)
                
        Returns:
            Informations de sécurité du repository
        """
        try:
            self.logger.info(f"🔒 {self.collector_name}: Récupération...")
            
            security_info = {
                "has_vulnerability_alerts": False,
                "vulnerability_alerts_enabled": False,
                "security_and_analysis": {}
            }
            
            try:
                if hasattr(repo, 'get_vulnerability_alert'):
                    security_info["has_vulnerability_alerts"] = repo.get_vulnerability_alert()
            except Exception as vuln_error:
                self.logger.debug(f"Pas d'accès aux alertes de vulnérabilité: {vuln_error}")
            
            self.logger.info(f"✅ {self.collector_name}: Informations récupérées")
            
            return {
                "success": True,
                **security_info
            }
            
        except Exception as e:
            return self.handle_error(e, "collect security info")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les infos de sécurité pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        return f"""{self.collector_name}:
- Alertes de vulnérabilité: {'Activées' if data.get('vulnerability_alerts_enabled') else 'Désactivées'}
- Vulnérabilités détectées: {'Oui' if data.get('has_vulnerability_alerts') else 'Non'}"""

