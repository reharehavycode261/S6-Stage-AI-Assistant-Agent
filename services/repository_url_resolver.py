"""Service pour résoudre l'URL du repository avec fallback intelligent."""

import re
from typing import Optional, Dict, Any
from utils.logger import get_logger
from services.database_persistence_service import db_persistence

logger = get_logger(__name__)


class RepositoryUrlResolver:
    """Résolveur intelligent d'URL repository avec fallbacks multiples."""
    
    @staticmethod
    async def resolve_repository_url(
        task: Any = None, 
        monday_item_id: str = None,
        task_db_id: int = None
    ) -> Optional[str]:
        """
        Résout l'URL du repository avec fallbacks intelligents.
        
        Ordre de priorité:
        1. URL définie dans la tâche (task.repository_url)
        2. URL de la dernière PR créée pour cette tâche
        3. URL de la dernière PR créée globalement (même repository)
        
        Args:
            task: Objet tâche avec possiblement repository_url
            monday_item_id: ID Monday.com pour recherche
            task_db_id: ID base de données de la tâche
            
        Returns:
            URL du repository GitHub ou None si introuvable
        """
        try:
            logger.info(f"🔍 Résolution URL repository pour tâche {task_db_id or monday_item_id}")
            
            task_repo_url = None
            if task:
                if isinstance(task, dict):
                    task_repo_url = task.get('repository_url')
                elif hasattr(task, 'repository_url'):
                    task_repo_url = task.repository_url
            
            if task_repo_url and RepositoryUrlResolver._is_valid_github_url(task_repo_url):
                logger.info(f"✅ URL trouvée dans tâche: {task_repo_url}")
                return task_repo_url
            
            if task_db_id:
                task_pr_url = await RepositoryUrlResolver._get_latest_pr_url_for_task(task_db_id)
                if task_pr_url:
                    repo_url = RepositoryUrlResolver._extract_repo_url_from_pr(task_pr_url)
                    if repo_url:
                        logger.info(f"✅ URL extraite de la dernière PR de cette tâche: {repo_url}")
                        await RepositoryUrlResolver._update_task_repository_url(task_db_id, repo_url)
                        return repo_url
            
            global_pr_url = await RepositoryUrlResolver._get_latest_global_pr_url()
            if global_pr_url:
                repo_url = RepositoryUrlResolver._extract_repo_url_from_pr(global_pr_url)
                if repo_url:
                    logger.info(f"🔄 URL extraite de la dernière PR globale: {repo_url}")
                    if task_db_id:
                        await RepositoryUrlResolver._update_task_repository_url(task_db_id, repo_url)
                    return repo_url
            
            from config.settings import get_settings
            settings = get_settings()
            if settings.default_repo_url:
                logger.warning(f"🔄 Utilisation du repository par défaut: {settings.default_repo_url}")
                if task_db_id:
                    await RepositoryUrlResolver._update_task_repository_url(task_db_id, settings.default_repo_url)
                return settings.default_repo_url
            
            logger.warning(f"⚠️ Impossible de résoudre l'URL repository pour tâche {task_db_id or monday_item_id}")
            logger.warning(f"💡 Configurez DEFAULT_REPO_URL dans .env pour un fallback automatique")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur résolution URL repository: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def _get_latest_pr_url_for_task(task_id: int) -> Optional[str]:
        """Récupère l'URL de la dernière PR pour une tâche spécifique."""
        try:
            if not db_persistence.db_manager._is_initialized:
                await db_persistence.initialize()
            
            async with db_persistence.db_manager.get_connection() as conn:
                result = await conn.fetchval("""
                    SELECT github_pr_url 
                    FROM pull_requests 
                    WHERE task_id = $1 
                    AND github_pr_url IS NOT NULL
                    AND github_pr_url != ''
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, task_id)
                
                if result:
                    logger.debug(f"📋 PR trouvée pour tâche {task_id}: {result}")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération PR pour tâche {task_id}: {e}")
            return None
    
    @staticmethod
    async def _get_latest_global_pr_url() -> Optional[str]:
        """Récupère l'URL de la dernière PR créée globalement."""
        try:
            if not db_persistence.db_manager._is_initialized:
                await db_persistence.initialize()
            
            async with db_persistence.db_manager.get_connection() as conn:
                result = await conn.fetchval("""
                    SELECT github_pr_url 
                    FROM pull_requests 
                    WHERE github_pr_url IS NOT NULL
                    AND github_pr_url != ''
                    AND github_pr_url LIKE 'https://github.com/%'
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                
                if result:
                    logger.debug(f"📋 Dernière PR globale trouvée: {result}")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération dernière PR globale: {e}")
            return None
    
    @staticmethod
    def _extract_repo_url_from_pr(pr_url: str) -> Optional[str]:
        """Extrait l'URL du repository depuis l'URL d'une PR."""
        try:
            
            if not pr_url or not isinstance(pr_url, str):
                return None
            
            pattern = r'(https://github\.com/[^/]+/[^/]+)/pull/\d+'
            match = re.match(pattern, pr_url.strip())
            
            if match:
                repo_url = match.group(1)
                logger.debug(f"🔗 URL repository extraite: {pr_url} → {repo_url}")
                return repo_url
            
            if pr_url.startswith('https://github.com/') and '/pull/' not in pr_url:
                clean_url = pr_url.rstrip('/').split('/tree/')[0].split('/blob/')[0]
                if RepositoryUrlResolver._is_valid_github_url(clean_url):
                    return clean_url
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction URL repo depuis PR '{pr_url}': {e}")
            return None
    
    @staticmethod
    def _is_valid_github_url(url: str) -> bool:
        """Vérifie si une URL GitHub est valide."""
        if not url or not isinstance(url, str):
            return False
        
        pattern = r'^https://github\.com/[^/]+/[^/]+/?$'
        return bool(re.match(pattern, url.strip().rstrip('/')))
    
    @staticmethod
    async def _update_task_repository_url(task_id: int, repository_url: str):
        """Met à jour l'URL repository de la tâche en base."""
        try:
            if not db_persistence.db_manager._is_initialized:
                await db_persistence.initialize()
            
            async with db_persistence.db_manager.get_connection() as conn:
                await conn.execute("""
                    UPDATE tasks 
                    SET repository_url = $1, updated_at = NOW()
                    WHERE tasks_id = $2 
                    AND (repository_url IS NULL OR repository_url = '')
                """, repository_url, task_id)
                
                logger.info(f"📝 URL repository mise à jour pour tâche {task_id}: {repository_url}")
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour URL repository tâche {task_id}: {e}")

repository_url_resolver = RepositoryUrlResolver()
