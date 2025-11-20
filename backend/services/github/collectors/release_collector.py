"""
Collecteur d'informations sur les Releases et Tags GitHub.

Récupère les releases et tags du repository.
"""

from typing import Dict, Any, Optional

from services.github.base_collector import GitHubDataCollector


class ReleaseCollector(GitHubDataCollector):
    """Collecte les releases du repository."""
    
    @property
    def collector_name(self) -> str:
        return "Releases"
    
    @property
    def data_key(self) -> str:
        return "releases"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les releases.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration
                - limit: Nombre max de releases (défaut: 5)
                
        Returns:
            Liste des releases avec leurs détails
        """
        try:
            options = options or {}
            limit = options.get("limit", 5)
            
            self.logger.info(f"🚀 {self.collector_name}: Récupération (limit={limit})...")
            
            releases_list = []
            releases = repo.get_releases()
            
            for i, release in enumerate(releases):
                if i >= limit:
                    break
                
                release_data = {
                    "id": release.id,
                    "tag_name": release.tag_name,
                    "name": release.title,
                    "draft": release.draft,
                    "prerelease": release.prerelease,
                    "created_at": release.created_at.isoformat() if release.created_at else None,
                    "published_at": release.published_at.isoformat() if release.published_at else None,
                    "author": release.author.login if release.author else "Unknown",
                    "body": release.body[:500] if release.body else None,
                    "assets_count": len(list(release.get_assets())),
                    "target_commitish": release.target_commitish
                }
                
                releases_list.append(release_data)
            
            self.logger.info(f"✅ {self.collector_name}: {len(releases_list)} releases récupérées")
            
            return {
                "success": True,
                "releases": releases_list,
                "count": len(releases_list),
                "latest_release": releases_list[0] if releases_list else None
            }
            
        except Exception as e:
            return self.handle_error(e, "collect releases")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les releases pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        releases = data.get("releases", [])
        
        if not releases:
            return f"{self.collector_name}: Aucune release trouvée"
        
        lines = [f"{self.collector_name} ({len(releases)} release{'s' if len(releases) > 1 else ''}):"]
        
        for release in releases:
            release_line = f"""
Release {release['tag_name']}:
  - Nom: {release['name']}
  - Auteur: {release['author']}
  - Publiée le: {release['published_at']}
  - Type: {'Draft' if release['draft'] else 'Prerelease' if release['prerelease'] else 'Stable'}
  - Assets: {release['assets_count']}"""
            
            if release.get('body'):
                release_line += f"\n  - Description: {release['body'][:200]}..."
            
            lines.append(release_line)
        
        return "\n".join(lines)


class TagCollector(GitHubDataCollector):
    """Collecte les tags du repository."""
    
    @property
    def collector_name(self) -> str:
        return "Tags"
    
    @property
    def data_key(self) -> str:
        return "tags"
    
    async def collect(
        self,
        repo,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collecte les tags.
        
        Args:
            repo: Instance du repository PyGithub
            options: Options de configuration
                - limit: Nombre max de tags (défaut: 10)
                
        Returns:
            Liste des tags
        """
        try:
            options = options or {}
            limit = options.get("limit", 10)
            
            self.logger.info(f"🏷️  {self.collector_name}: Récupération (limit={limit})...")
            
            tags_list = []
            tags = repo.get_tags()
            
            for i, tag in enumerate(tags):
                if i >= limit:
                    break
                
                tag_data = {
                    "name": tag.name,
                    "commit_sha": tag.commit.sha if tag.commit else None,
                    "commit_date": tag.commit.commit.author.date.isoformat() if tag.commit and tag.commit.commit.author else None
                }
                
                tags_list.append(tag_data)
            
            self.logger.info(f"✅ {self.collector_name}: {len(tags_list)} tags récupérés")
            
            return {
                "success": True,
                "tags": tags_list,
                "count": len(tags_list)
            }
            
        except Exception as e:
            return self.handle_error(e, "collect tags")
    
    def format_for_llm(self, data: Dict[str, Any]) -> str:
        """Formate les tags pour le LLM."""
        if not data.get("success"):
            return f"{self.collector_name}: Erreur - {data.get('error', 'Inconnue')}"
        
        tags = data.get("tags", [])
        
        if not tags:
            return f"{self.collector_name}: Aucun tag trouvé"
        
        lines = [f"{self.collector_name} ({len(tags)} tag{'s' if len(tags) > 1 else ''}):"]
        
        for tag in tags:
            tag_line = f"  - {tag['name']}"
            if tag.get('commit_date'):
                tag_line += f" (créé: {tag['commit_date']})"
            lines.append(tag_line)
        
        return "\n".join(lines)

