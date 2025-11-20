"""
Collecteur d'informations sur les Contributeurs et Permissions GitHub.

Récupère les contributeurs et collaborateurs du repository.
"""

from typing import Dict, Any, Optional

from services.github.base_collector import GitHubDataCollector


class ContributorCollector(GitHubDataCollector):
    """Collecte les contributeurs du repository."""
    
    @property
    def collector_name(self) -> str:
        return "Contributeurs"
    
    @property
    def data_key(self) -> str:
        return "contributors"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les contributeurs.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration
                - limit: Nombre max de contributeurs (défaut: 10)
                
        Returns:
            Liste des contributeurs avec leurs statistiques
        """
        try:
            options = options or {}
            limit = options.get("limit", 10)
            
            self.logger.info(f"👥 {self.collector_name}: Récupération (limit={limit})...")
            
            contributors_list = []
            contributors = repo.get_contributors()
            
            for i, contributor in enumerate(contributors):
                if i >= limit:
                    break
                
                contributor_data = {
                    "login": contributor.login,
                    "name": contributor.name if hasattr(contributor, 'name') else None,
                    "type": contributor.type,
                    "contributions": contributor.contributions,
                    "avatar_url": contributor.avatar_url
                }
                
                contributors_list.append(contributor_data)
            
            self.logger.info(f"✅ {self.collector_name}: {len(contributors_list)} contributeurs récupérés")
            
            return {
                "success": True,
                "contributors": contributors_list,
                "count": len(contributors_list),
                "top_contributor": contributors_list[0] if contributors_list else None
            }
            
        except Exception as e:
            return self.handle_error(e, "collect contributors")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les contributeurs pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        contributors = data.get("contributors", [])
        
        if not contributors:
            return f"{self.collector_name}: Aucun contributeur trouvé"
        
        lines = [f"{self.collector_name} ({len(contributors)} contributeur{'s' if len(contributors) > 1 else ''}):"]
        
        for contributor in contributors:
            lines.append(f"  - {contributor['login']} ({contributor['type']}): {contributor['contributions']} contributions")
        
        return "\n".join(lines)


class CollaboratorCollector(GitHubDataCollector):
    """Collecte les collaborateurs avec leurs permissions."""
    
    @property
    def collector_name(self) -> str:
        return "Collaborateurs"
    
    @property
    def data_key(self) -> str:
        return "collaborators"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les collaborateurs avec permissions.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options (non utilisées ici)
                
        Returns:
            Liste des collaborateurs avec leurs permissions
        """
        try:
            self.logger.info(f"🔐 {self.collector_name}: Récupération...")
            
            collaborators_list = []
            
            try:
                collaborators = repo.get_collaborators()
                
                for collaborator in collaborators:
                    try:
                        permission = repo.get_collaborator_permission(collaborator)
                        
                        collaborator_data = {
                            "login": collaborator.login,
                            "type": collaborator.type,
                            "permission": permission
                        }
                        
                        collaborators_list.append(collaborator_data)
                    except Exception as perm_error:
                        self.logger.debug(f"Erreur permission pour {collaborator.login}: {perm_error}")
            
            except Exception as collab_error:
                self.logger.warning(f"⚠️ Impossible de récupérer les collaborateurs: {collab_error}")
                return {
                    "success": True,
                    "collaborators": [],
                    "count": 0,
                    "access_denied": True
                }
            
            self.logger.info(f"✅ {self.collector_name}: {len(collaborators_list)} collaborateurs récupérés")
            
            return {
                "success": True,
                "collaborators": collaborators_list,
                "count": len(collaborators_list),
                "access_denied": False
            }
            
        except Exception as e:
            return self.handle_error(e, "collect collaborators")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les collaborateurs pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        if data.get("access_denied"):
            return f"{self.collector_name}: Accès refusé (permissions insuffisantes)"
        
        collaborators = data.get("collaborators", [])
        
        if not collaborators:
            return f"{self.collector_name}: Aucun collaborateur trouvé"
        
        lines = [f"{self.collector_name} ({len(collaborators)} collaborateur{'s' if len(collaborators) > 1 else ''}):"]
        
        for collab in collaborators:
            lines.append(f"  - {collab['login']} ({collab['type']}): {collab['permission']}")
        
        return "\n".join(lines)

