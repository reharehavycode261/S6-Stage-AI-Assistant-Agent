"""
Service de déduplication sémantique des commandes @vydata.

Ce service:
- Détecte les commandes @vydata en doublon (même intention sémantique)
- Stocke l'historique des commandes traitées dans Redis
- Retourne l'URL de la PR si la commande a déjà été traitée
- S'applique UNIQUEMENT aux COMMANDES, PAS aux QUESTIONS

Exemples:
- "@vydata ajoute un fichier main.py" (1ère fois) → Traitement normal
- "@vydata ajoute un fichier main.py" (2ème fois) → "Déjà traité, URL: ..."
- "@vydata crée main.py" (variante) → Détecté comme doublon
- "@vydata pourquoi Java?" → IGNORÉ (c'est une question, pas une commande)
"""

import hashlib
import json
from typing import Optional, Dict, Any, List
from datetime import timedelta
import redis.asyncio as aioredis
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class CommandDeduplicationService:
    """
    Service pour détecter les commandes @vydata en doublon.
    
    Clés Redis utilisées:
    - command:semantic:{hash} → Métadonnées de la commande (TTL 30 jours)
    - command:history:{monday_item_id} → Liste des commandes pour un item (TTL 90 jours)
    
    Données stockées:
    - command_text: Texte original de la commande
    - command_hash: Hash sémantique
    - task_id: ID de la tâche créée
    - run_id: ID du workflow run
    - pr_url: URL de la Pull Request créée
    - created_at: Timestamp de création
    - monday_item_id: ID de l'item Monday.com
    """
    
    def __init__(self):
        """Initialise le service de déduplication."""
        self.redis_client: Optional[aioredis.Redis] = None
        self._initialized = False
        
        self.COMMAND_TTL = 30 * 24 * 3600  
        self.HISTORY_TTL = 90 * 24 * 3600  
    
    async def initialize(self):
        """Initialise la connexion Redis."""
        if self._initialized:
            return
        
        try:
            self.redis_client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0
            )
            
            await self.redis_client.ping()
            logger.info(f"✅ CommandDeduplicationService Redis connecté")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"❌ Erreur connexion Redis (déduplication commandes): {e}")
            logger.warning("⚠️ Mode dégradé: pas de déduplication sémantique")
            self.redis_client = None
            self._initialized = False
    
    async def close(self):
        """Ferme la connexion Redis."""
        if self.redis_client:
            try:
                await self.redis_client.close()
                logger.info("✅ CommandDeduplicationService Redis fermé")
            except Exception as e:
                logger.error(f"❌ Erreur fermeture Redis: {e}")
    
    def _create_semantic_hash(self, command_text: str) -> str:
        """
        Crée un hash sémantique de la commande.
        
        Normalise le texte pour détecter les variantes:
        - Minuscules
        - Supprime ponctuation excessive
        - Supprime articles/mots vides
        - Garde les mots clés importants
        
        Args:
            command_text: Texte de la commande
            
        Returns:
            Hash MD5 du texte normalisé
        """
        normalized = command_text.lower().strip()
        
        stop_words = ['le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'à', 'au', 'aux']
        words = normalized.split()
        filtered_words = [w for w in words if w not in stop_words]

        normalized = ' '.join(filtered_words)
        normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
        normalized = ' '.join(normalized.split())  
        
        hash_obj = hashlib.md5(normalized.encode('utf-8'))
        return hash_obj.hexdigest()
    
    async def check_duplicate_command(
        self,
        command_text: str,
        monday_item_id: str
    ) -> Dict[str, Any]:
        """
        Vérifie si une commande a déjà été traitée.
        
        Args:
            command_text: Texte de la commande
            monday_item_id: ID de l'item Monday.com
            
        Returns:
            Dict avec:
            - is_duplicate: bool
            - previous_command: Dict si doublon trouvé
            - semantic_hash: Hash de la commande
        """
        if not self.redis_client:
            logger.warning("⚠️ Redis non disponible - pas de vérification doublon")
            return {
                "is_duplicate": False,
                "previous_command": None,
                "semantic_hash": None,
                "redis_available": False
            }
        
        try:
            semantic_hash = self._create_semantic_hash(command_text)
            
            logger.info(f"🔍 Vérification doublon commande:")
            logger.info(f"   Texte: '{command_text[:100]}...'")
            logger.info(f"   Hash: {semantic_hash}")
            logger.info(f"   Item: {monday_item_id}")
            
            key = f"command:semantic:{semantic_hash}"
            existing_data = await self.redis_client.get(key)
            
            if existing_data:
                previous_command = json.loads(existing_data)
                
                if previous_command.get("monday_item_id") == monday_item_id:
                    logger.warning(f"🚫 Commande en doublon détectée!")
                    logger.warning(f"   Commande originale: '{previous_command.get('command_text', '')[:100]}...'")
                    logger.warning(f"   PR URL: {previous_command.get('pr_url', 'N/A')}")
                    
                    return {
                        "is_duplicate": True,
                        "previous_command": previous_command,
                        "semantic_hash": semantic_hash,
                        "redis_available": True
                    }
                else:
                    logger.info(f"✅ Hash identique mais item différent - pas un doublon")
            
            logger.info(f"✅ Pas de doublon trouvé")
            return {
                "is_duplicate": False,
                "previous_command": None,
                "semantic_hash": semantic_hash,
                "redis_available": True
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification doublon: {e}", exc_info=True)
            return {
                "is_duplicate": False,
                "previous_command": None,
                "semantic_hash": None,
                "error": str(e)
            }
    
    async def store_command(
        self,
        command_text: str,
        monday_item_id: str,
        task_id: int,
        run_id: Optional[str] = None,
        pr_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Stocke une commande traitée dans Redis.
        
        Args:
            command_text: Texte de la commande
            monday_item_id: ID de l'item Monday.com
            task_id: ID de la tâche créée
            run_id: ID du workflow run (optionnel)
            pr_url: URL de la Pull Request créée (optionnel)
            metadata: Métadonnées additionnelles (optionnel)
            
        Returns:
            True si succès, False sinon
        """
        if not self.redis_client:
            logger.warning("⚠️ Redis non disponible - commande non stockée")
            return False
        
        try:
            semantic_hash = self._create_semantic_hash(command_text)
            
            # Préparer les données
            from datetime import datetime
            command_data = {
                "command_text": command_text,
                "command_hash": semantic_hash,
                "task_id": task_id,
                "run_id": run_id,
                "pr_url": pr_url,
                "monday_item_id": monday_item_id,
                "created_at": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            
            key = f"command:semantic:{semantic_hash}"
            await self.redis_client.setex(
                key,
                self.COMMAND_TTL,
                json.dumps(command_data)
            )
            
            history_key = f"command:history:{monday_item_id}"
            await self.redis_client.rpush(history_key, json.dumps(command_data))
            await self.redis_client.expire(history_key, self.HISTORY_TTL)
            
            logger.info(f"✅ Commande stockée dans Redis:")
            logger.info(f"   Hash: {semantic_hash}")
            logger.info(f"   Task ID: {task_id}")
            logger.info(f"   PR URL: {pr_url or 'N/A'}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur stockage commande: {e}", exc_info=True)
            return False
    
    async def get_command_history(
        self,
        monday_item_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des commandes pour un item Monday.
        
        Args:
            monday_item_id: ID de l'item Monday.com
            limit: Nombre maximum de commandes à retourner
            
        Returns:
            Liste des commandes (plus récentes en premier)
        """
        if not self.redis_client:
            return []
        
        try:
            history_key = f"command:history:{monday_item_id}"
            
            commands_json = await self.redis_client.lrange(history_key, -limit, -1)
            
            commands = [json.loads(cmd) for cmd in commands_json]
            commands.reverse()
            
            return commands
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération historique: {e}")
            return []
    
    async def update_command_pr_url(
        self,
        semantic_hash: str,
        pr_url: str
    ) -> bool:
        """
        Met à jour l'URL de la PR pour une commande.
        
        Args:
            semantic_hash: Hash sémantique de la commande
            pr_url: URL de la Pull Request
            
        Returns:
            True si succès, False sinon
        """
        if not self.redis_client:
            return False
        
        try:
            key = f"command:semantic:{semantic_hash}"
            existing_data = await self.redis_client.get(key)
            
            if existing_data:
                command_data = json.loads(existing_data)
                command_data["pr_url"] = pr_url
                
                ttl = await self.redis_client.ttl(key)
                if ttl > 0:
                    await self.redis_client.setex(key, ttl, json.dumps(command_data))
                    logger.info(f"✅ PR URL mise à jour pour hash {semantic_hash}: {pr_url}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour PR URL: {e}")
            return False


command_deduplication_service = CommandDeduplicationService()

