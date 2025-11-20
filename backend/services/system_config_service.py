"""Service de gestion de la configuration système."""

import asyncpg
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)


class SystemConfigService:
    """Service pour gérer la configuration système en base de données."""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_pool: Optional[asyncpg.Pool] = None
    
    async def init_db_pool(self):
        """Initialise le pool de connexions à la base de données."""
        if not self.db_pool:
            try:
                self.db_pool = await asyncpg.create_pool(
                    self.settings.database_url,
                    min_size=2,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("✅ Pool de connexions system_config initialisé")
            except Exception as e:
                logger.error(f"❌ Erreur initialisation pool DB system_config: {e}")
                raise
    
    async def close_db_pool(self):
        """Ferme le pool de connexions."""
        if self.db_pool:
            await self.db_pool.close()
            self.db_pool = None
            logger.info("🔒 Pool system_config fermé")
    
    async def create_or_update_config(
        self,
        key: str,
        value: Any,
        description: Optional[str] = None,
        config_type: str = "application",
        updated_by: Optional[str] = None
    ) -> bool:
        """
        Crée ou met à jour une configuration système.
        
        Args:
            key: Clé de configuration (unique)
            value: Valeur de configuration (sera converti en JSONB)
            description: Description de la configuration
            config_type: Type de configuration ('application', 'workflow', 'integration', 'monitoring')
            updated_by: Nom de l'utilisateur ou du système qui fait la mise à jour
            
        Returns:
            True si succès, False sinon
        """
        if not self.db_pool:
            await self.init_db_pool()
        
        valid_types = ['application', 'workflow', 'integration', 'monitoring']
        if config_type not in valid_types:
            logger.error(f"❌ Type de config invalide: {config_type}. Valides: {valid_types}")
            return False
        
        try:
            async with self.db_pool.acquire() as conn:
                existing = await conn.fetchval("""
                    SELECT system_config_id FROM system_config WHERE key = $1
                """, key)
                
                value_json = json.dumps(value) if not isinstance(value, str) else json.dumps({"value": value})
                
                if existing:
                    await conn.execute("""
                        UPDATE system_config
                        SET value = $2,
                            description = COALESCE($3, description),
                            config_type = $4,
                            updated_at = NOW(),
                            updated_by = $5
                        WHERE key = $1
                    """, key, value_json, description, config_type, updated_by)
                    logger.info(f"✅ Configuration '{key}' mise à jour")
                else:
                    await conn.execute("""
                        INSERT INTO system_config (key, value, description, config_type, updated_by, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                    """, key, value_json, description, config_type, updated_by)
                    logger.info(f"✅ Configuration '{key}' créée")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Erreur création/mise à jour config '{key}': {e}")
            return False
    
    async def get_config(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Récupère une configuration système par sa clé.
        
        Args:
            key: Clé de configuration
            
        Returns:
            Dictionnaire avec les détails de configuration ou None si non trouvée
        """
        if not self.db_pool:
            await self.init_db_pool()
        
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        system_config_id,
                        key,
                        value,
                        description,
                        config_type,
                        created_at,
                        updated_at,
                        updated_by
                    FROM system_config
                    WHERE key = $1
                """, key)
                
                if not row:
                    return None
                
                return {
                    "id": row['system_config_id'],
                    "key": row['key'],
                    "value": row['value'],
                    "description": row['description'],
                    "config_type": row['config_type'],
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                    "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None,
                    "updated_by": row['updated_by']
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération config '{key}': {e}")
            return None
    
    async def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Récupère uniquement la valeur d'une configuration.
        
        Args:
            key: Clé de configuration
            default: Valeur par défaut si non trouvée
            
        Returns:
            Valeur de configuration ou default
        """
        config = await self.get_config(key)
        if config:
            return config['value']
        return default
    
    async def list_configs(
        self,
        config_type: Optional[str] = None,
        search_pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Liste toutes les configurations système.
        
        Args:
            config_type: Filtrer par type de configuration (optionnel)
            search_pattern: Pattern de recherche pour les clés (SQL LIKE, optionnel)
            
        Returns:
            Liste des configurations
        """
        if not self.db_pool:
            await self.init_db_pool()
        
        try:
            async with self.db_pool.acquire() as conn:
                query = """
                    SELECT 
                        system_config_id,
                        key,
                        value,
                        description,
                        config_type,
                        created_at,
                        updated_at,
                        updated_by
                    FROM system_config
                    WHERE 1=1
                """
                params = []
                param_count = 1
                
                if config_type:
                    query += f" AND config_type = ${param_count}"
                    params.append(config_type)
                    param_count += 1
                
                if search_pattern:
                    query += f" AND key LIKE ${param_count}"
                    params.append(f"%{search_pattern}%")
                    param_count += 1
                
                query += " ORDER BY config_type, key"
                
                rows = await conn.fetch(query, *params)
                
                configs = []
                for row in rows:
                    configs.append({
                        "id": row['system_config_id'],
                        "key": row['key'],
                        "value": row['value'],
                        "description": row['description'],
                        "config_type": row['config_type'],
                        "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                        "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None,
                        "updated_by": row['updated_by']
                    })
                
                return configs
                
        except Exception as e:
            logger.error(f"❌ Erreur liste configs: {e}")
            return []
    
    async def delete_config(self, key: str) -> bool:
        """
        Supprime une configuration système.
        
        Args:
            key: Clé de configuration à supprimer
            
        Returns:
            True si succès, False sinon
        """
        if not self.db_pool:
            await self.init_db_pool()
        
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM system_config WHERE key = $1
                """, key)
                
                if result == "DELETE 0":
                    logger.warning(f"⚠️ Configuration '{key}' non trouvée pour suppression")
                    return False
                
                logger.info(f"✅ Configuration '{key}' supprimée")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erreur suppression config '{key}': {e}")
            return False
    
    async def get_configs_by_type(self, config_type: str) -> Dict[str, Any]:
        """
        Récupère toutes les configurations d'un type donné sous forme de dictionnaire clé->valeur.
        
        Args:
            config_type: Type de configuration
            
        Returns:
            Dictionnaire {key: value}
        """
        configs = await self.list_configs(config_type=config_type)
        return {config['key']: config['value'] for config in configs}
    
    async def bulk_create_or_update(
        self,
        configs: List[Dict[str, Any]],
        updated_by: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Crée ou met à jour plusieurs configurations en batch.
        
        Args:
            configs: Liste de dictionnaires avec 'key', 'value', 'description' (optionnel), 'config_type' (optionnel)
            updated_by: Nom de l'utilisateur ou du système qui fait la mise à jour
            
        Returns:
            Dictionnaire avec le nombre de succès et d'échecs
        """
        if not self.db_pool:
            await self.init_db_pool()
        
        results = {"success": 0, "failed": 0}
        
        for config in configs:
            key = config.get('key')
            value = config.get('value')
            description = config.get('description')
            config_type = config.get('config_type', 'application')
            
            if not key:
                logger.warning(f"⚠️ Configuration sans clé ignorée: {config}")
                results["failed"] += 1
                continue
            
            success = await self.create_or_update_config(
                key=key,
                value=value,
                description=description,
                config_type=config_type,
                updated_by=updated_by
            )
            
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
        
        logger.info(f"✅ Batch configs: {results['success']} succès, {results['failed']} échecs")
        return results
    
    async def initialize_default_configs(self) -> bool:
        """
        Initialise les configurations par défaut du système.
        Utile lors du premier démarrage.
        
        Returns:
            True si succès, False sinon
        """
        default_configs = [
            {
                "key": "workflow.max_retry_attempts",
                "value": 3,
                "description": "Nombre maximum de tentatives de retry pour un workflow",
                "config_type": "workflow"
            },
            {
                "key": "workflow.default_timeout_minutes",
                "value": 60,
                "description": "Timeout par défaut pour un workflow en minutes",
                "config_type": "workflow"
            },
            {
                "key": "ai.default_provider",
                "value": "anthropic",
                "description": "Provider IA par défaut (anthropic ou openai)",
                "config_type": "application"
            },
            {
                "key": "ai.max_tokens_per_request",
                "value": 4000,
                "description": "Nombre maximum de tokens par requête IA",
                "config_type": "application"
            },
            {
                "key": "human_validation.default_timeout_hours",
                "value": 24,
                "description": "Timeout par défaut pour les validations humaines en heures",
                "config_type": "workflow"
            },
            {
                "key": "monitoring.performance_metrics_enabled",
                "value": True,
                "description": "Activer l'enregistrement des métriques de performance",
                "config_type": "monitoring"
            },
            {
                "key": "monitoring.log_retention_days",
                "value": 90,
                "description": "Durée de rétention des logs en jours",
                "config_type": "monitoring"
            },
            {
                "key": "integration.monday.auto_update_status",
                "value": True,
                "description": "Mettre à jour automatiquement le statut Monday.com",
                "config_type": "integration"
            }
        ]
        
        results = await self.bulk_create_or_update(
            default_configs,
            updated_by="system_initialization"
        )
        
        success = results["failed"] == 0
        if success:
            logger.info(f"✅ Configurations par défaut initialisées: {results['success']} configs")
        else:
            logger.warning(f"⚠️ Initialisation configs: {results['success']} succès, {results['failed']} échecs")
        
        return success


system_config_service = SystemConfigService()
