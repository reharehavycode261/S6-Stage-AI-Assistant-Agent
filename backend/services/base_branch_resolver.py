"""Service intelligent de résolution de la branche de base (base_branch) pour les Pull Requests."""

import json
import re
from typing import Optional, Dict, Any
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class BaseBranchResolver:
    """
    Service de résolution intelligente de la branche de base avec multiples niveaux de fallback.
    
    Ordre de priorité (du plus au moins prioritaire):
    1. base_branch depuis Monday.com (colonne spécifique)
    2. Configuration par repository (REPO_BASE_BRANCHES)
    3. Règles intelligentes par type de tâche (BASE_BRANCH_RULES)
    4. Inférence depuis le titre/description de la tâche
    5. Fallback ultime: DEFAULT_BASE_BRANCH (main)
    """
    
    def __init__(self):
        """Initialise le resolver avec les règles configurées."""
        self.default_base_branch = settings.default_base_branch
        
        self.base_branch_rules = self._load_json_config(settings.base_branch_rules, {
            "hotfix": "main",
            "bug": "main",
            "bugfix": "main",
            "feature": "develop",
            "feat": "develop",
            "experiment": "staging",
            "test": "staging",
            "release": "release"
        })
        
        self.repo_base_branches = self._load_json_config(settings.repo_base_branches, {})
        
        logger.info(f"✅ BaseBranchResolver initialisé - Branche par défaut: {self.default_base_branch}")
    
    def _load_json_config(self, json_str: Optional[str], default: Dict[str, str]) -> Dict[str, str]:
        """
        Charge une configuration JSON depuis les settings.
        
        Args:
            json_str: String JSON à parser
            default: Configuration par défaut
            
        Returns:
            Dictionnaire de configuration
        """
        if not json_str:
            return default
        
        try:
            config = json.loads(json_str)
            logger.info(f"✅ Configuration JSON chargée: {len(config)} entrées")
            return config
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Erreur parsing JSON config: {e} - utilisation valeurs par défaut")
            return default
    
    async def resolve_base_branch(
        self,
        task: Any,
        repository_url: Optional[str] = None,
        monday_base_branch: Optional[str] = None
    ) -> str:
        """
        Résout la branche de base avec logique intelligente et multiples fallbacks.
        
        Args:
            task: Objet tâche contenant les informations
            repository_url: URL du repository (pour config par repo)
            monday_base_branch: base_branch récupérée depuis Monday.com (prioritaire)
            
        Returns:
            Nom de la branche de base à utiliser
        """
        
        # 🔍 DEBUG: Log ce qui est reçu
        logger.info(f"🔍 DEBUG resolve_base_branch: monday_base_branch={monday_base_branch} (type={type(monday_base_branch).__name__})")
        
        # ==========================================
        # NIVEAU 1: base_branch depuis Monday.com
        # ==========================================
        if monday_base_branch:
            logger.info(f"🔍 DEBUG: Vérification validité de '{monday_base_branch}'...")
            is_valid = self._is_valid_branch_name(monday_base_branch)
            logger.info(f"🔍 DEBUG: '{monday_base_branch}' est valide ? {is_valid}")
            
            if is_valid:
                logger.info(f"🎯 Base branch depuis Monday.com: {monday_base_branch}")
                return self._sanitize_branch_name(monday_base_branch)
            else:
                logger.warning(f"⚠️ base_branch de Monday.com '{monday_base_branch}' rejetée (invalide)")
        else:
            logger.info(f"ℹ️  Aucune base_branch depuis Monday.com, passage aux niveaux suivants")
        
        # ==========================================
        # NIVEAU 2: Configuration par repository
        # ==========================================
        if repository_url and self.repo_base_branches:
            repo_name = self._extract_repo_name(repository_url)
            if repo_name in self.repo_base_branches:
                base_branch = self.repo_base_branches[repo_name]
                logger.info(f"🎯 Base branch depuis config repository ({repo_name}): {base_branch}")
                return base_branch
        
        # ==========================================
        # NIVEAU 3: Règles intelligentes par type
        # ==========================================
        task_title = getattr(task, 'title', '') or getattr(task, 'task_title', '') or ''
        task_description = getattr(task, 'description', '') or getattr(task, 'task_description', '') or ''
        task_priority = getattr(task, 'priority', '').lower() if hasattr(task, 'priority') else ''
        
        inferred_type = self._infer_task_type(task_title, task_description, task_priority)
        
        if inferred_type and inferred_type in self.base_branch_rules:
            base_branch = self.base_branch_rules[inferred_type]
            logger.info(f"🎯 Base branch depuis règles intelligentes (type: {inferred_type}): {base_branch}")
            return base_branch
        
        # ==========================================
        # NIVEAU 4: Inférence avancée depuis le contenu
        # ==========================================
        advanced_inference = self._advanced_branch_inference(task_title, task_description)
        if advanced_inference:
            logger.info(f"🎯 Base branch depuis inférence avancée: {advanced_inference}")
            return advanced_inference
        
        # ==========================================
        # NIVEAU 5: Fallback ultime
        # ==========================================
        logger.info(f"🎯 Base branch par défaut (fallback): {self.default_base_branch}")
        return self.default_base_branch
    
    def _extract_repo_name(self, repository_url: str) -> str:
        """
        Extrait owner/repo depuis une URL GitHub.
        
        Examples:
            https://github.com/owner/repo → owner/repo
            https://github.com/owner/repo.git → owner/repo
        """
        url = repository_url.strip().rstrip('/')
        url = url.replace('.git', '')
        
        match = re.search(r'github\.com[/:]([^/]+/[^/]+)', url)
        if match:
            return match.group(1)
        
        parts = url.split('/')
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        
        return ""
    
    def _infer_task_type(self, title: str, description: str, priority: str) -> Optional[str]:
        """
        Infère le type de tâche depuis le titre, description et priorité.
        
        Returns:
            Type inféré (hotfix, feature, experiment, etc.) ou None
        """
        content = f"{title} {description}".lower()
        
        type_patterns = {
            "hotfix": [
                r'\bhotfix\b', r'\bcritique\b', r'\burgent\b', r'\bproduction\b',
                r'\bprod\b', r'\bdown\b', r'\bbloquant\b'
            ],
            "bug": [
                r'\bbug\b', r'\berreur\b', r'\bfix\b', r'\bcorrection\b', 
                r'\bprobleme\b', r'\bproblem\b'
            ],
            "feature": [
                r'\bfeature\b', r'\bfonctionnalit[ée]\b', r'\bajoute\b',
                r'\bnouveau\b', r'\badd\b', r'\bcr[ée]e\b'
            ],
            "experiment": [
                r'\btest\b', r'\bexp[ée]rimen\b', r'\bessai\b', r'\bpoc\b',
                r'\bproof.of.concept\b'
            ],
            "release": [
                r'\brelease\b', r'\bversion\b', r'\bv\d+\.\d+', r'\bd[ée]ploiement\b'
            ]
        }
        
        for task_type, patterns in type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    return task_type
        
        if priority in ['critical', 'high', 'urgent']:
            return "hotfix"
        
        return None
    
    def _advanced_branch_inference(self, title: str, description: str) -> Optional[str]:
        """
        Inférence avancée: détecte des branches spécifiques mentionnées explicitement.
        
        Examples:
            "merge vers develop" → develop
            "base: staging" → staging
        """
        content = f"{title} {description}".lower()
        
        # 🔍 DEBUG: Log le contenu analysé
        logger.info(f"🔍 DEBUG _advanced_branch_inference: Analyse du contenu (100 premiers car): '{content[:100]}'")
        
        branch_mention_patterns = [
            r'base[:\s]+(\w+)',
            r'vers[:\s]+(\w+)',
            r'into[:\s]+(\w+)',
            r'target[:\s]+(\w+)',
            r'sur[:\s]+(\w+)'
        ]
        
        for pattern in branch_mention_patterns:
            match = re.search(pattern, content)
            if match:
                branch = match.group(1)
                logger.info(f"🔍 DEBUG: Pattern '{pattern}' a matché: '{branch}'")
                
                if self._is_valid_branch_name(branch):
                    logger.info(f"✅ Branche '{branch}' validée par inférence avancée")
                    return branch
                else:
                    logger.info(f"❌ Branche '{branch}' rejetée (invalide ou code langue)")
        
        logger.info(f"ℹ️  Aucune branche détectée par inférence avancée")
        return None
    
    def _is_valid_branch_name(self, branch_name: str) -> bool:
        """
        Vérifie si un nom de branche est valide selon les conventions Git.
        
        Args:
            branch_name: Nom de branche à valider
            
        Returns:
            True si valide, False sinon
        """
        if not branch_name or not isinstance(branch_name, str):
            return False
        
        valid_branches = {
            'main', 'master', 'develop', 'development', 'dev',
            'staging', 'stage', 'production', 'prod',
            'release', 'hotfix', 'feature', 'fix', 'test'
        }
        
        branch_lower = branch_name.lower()
        if branch_lower in valid_branches:
            return True
        
        for valid in valid_branches:
            if branch_lower.startswith(f"{valid}/"):
                return True
        
        # ⚠️ IMPORTANT: Inclure les codes ISO 639-1 pour éviter confusion langue/branche
        language_codes = {
            'fr', 'en', 'es', 'de', 'it', 'pt', 'zh', 'ja', 'ru', 'ar',
            'nl', 'pl', 'tr', 'ko', 'hi', 'sv', 'no', 'da', 'fi', 'cs',
            'el', 'he', 'id', 'ms', 'th', 'vi', 'uk', 'ro', 'bg', 'sk'
        }
        
        invalid_words = {
            'les', 'des', 'une', 'the', 'and', 'or', 'but', 'for', 'with',
            'sur', 'dans', 'pour', 'avec', 'par', 'cette', 'nouveau',
            'ajoute', 'uniformisez', 'états', 'vides', 'loaders', 'messages'
        }
        
        # Combiner codes langues et mots invalides
        invalid_words = invalid_words.union(language_codes)
        
        if branch_lower in invalid_words:
            return False
        
        invalid_patterns = [
            r'^[\.\-]',  
            r'[\.\-]$',  
            r'\.\.',     
            r'[\s~\^:\?*\[]',  
            r'//',       
            r'@\{',      
            r'\\',       
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, branch_name):
                return False
        
        if len(branch_name) > 255:
            return False
        
        return True
    
    def _sanitize_branch_name(self, branch_name: str) -> str:
        """
        Nettoie et sanitise un nom de branche.
        
        Args:
            branch_name: Nom de branche à nettoyer
            
        Returns:
            Nom de branche nettoyé
        """
        cleaned = branch_name.strip()
        
        cleaned = re.sub(r'\s+', '-', cleaned)
        
        cleaned = re.sub(r'[~\^:\?\*\[\]\\]', '', cleaned)
        
        cleaned = re.sub(r'\.\.+', '.', cleaned)
        
        cleaned = re.sub(r'//+', '/', cleaned)
        
        cleaned = cleaned.strip('.-')
        
        return cleaned or self.default_base_branch


_base_branch_resolver = None

def get_base_branch_resolver() -> BaseBranchResolver:
    """Retourne l'instance singleton du BaseBranchResolver."""
    global _base_branch_resolver
    if _base_branch_resolver is None:
        _base_branch_resolver = BaseBranchResolver()
    return _base_branch_resolver

