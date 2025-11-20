"""
Service d'enrichissement du contexte avec les données GitHub.

Architecture orientée objet pour gérer proprement l'intégration des données GitHub
dans les prompts LLM de manière maintenable et extensible.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GitHubCommitInfo:
    """Informations d'un commit GitHub."""
    message: str
    author_name: str
    author_email: str
    date: str
    sha: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GitHubCommitInfo':
        """Crée une instance depuis un dictionnaire."""
        author_name = data.get('author', 'N/A')
        author_email = data.get('author_email', 'N/A')
        
        return cls(
            message=data.get('message', 'N/A'),
            author_name=author_name if isinstance(author_name, str) else 'N/A',
            author_email=author_email if isinstance(author_email, str) else 'N/A',
            date=data.get('date', 'N/A'),
            sha=data.get('sha', 'N/A')
        )
    
    def format_for_prompt(self) -> str:
        """Formate pour inclusion dans un prompt LLM."""
        return f"""📝 **DERNIER COMMIT:**
- **Message du commit:** "{self.message}"
- **Auteur:** {self.author_name} ({self.author_email})
- **Date:** {self.date}
- **SHA:** {self.sha[:7]}

🎯 RÉPONDEZ EN CITANT EXPLICITEMENT:
"Le message du dernier commit sur la branche main est: **\"{self.message}\"**"""


@dataclass
class GitHubPullRequestInfo:
    """Informations d'une Pull Request GitHub."""
    title: str
    number: int
    author: str
    state: str
    created_at: str
    head_branch: str
    base_branch: str
    body: str
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    merged_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GitHubPullRequestInfo':
        """Crée une instance depuis un dictionnaire."""
        user = data.get('user', {})
        author = user.get('login', 'N/A') if isinstance(user, dict) else data.get('author', 'N/A')
        
        head = data.get('head', {})
        head_branch = head.get('ref', 'N/A') if isinstance(head, dict) else data.get('head_branch', 'N/A')
        
        base = data.get('base', {})
        base_branch = base.get('ref', 'N/A') if isinstance(base, dict) else data.get('base_branch', 'N/A')
        
        return cls(
            title=data.get('title', 'N/A'),
            number=data.get('number', 0),
            author=author,
            state=data.get('state', 'N/A'),
            created_at=data.get('created_at', 'N/A'),
            head_branch=head_branch,
            base_branch=base_branch,
            body=data.get('body', 'Pas de description'),
            files_changed=data.get('changed_files', data.get('files_changed', 0)),
            additions=data.get('additions', 0),
            deletions=data.get('deletions', 0),
            merged_at=data.get('merged_at', None)
        )
    
    def format_for_prompt(self) -> str:
        """Formate pour inclusion dans un prompt LLM."""
        description = self.body if self.body and self.body != "Pas de description" else "Aucune description fournie"
        if len(description) > 300:
            description = description[:300] + "..."
        
        stats = f"**Fichiers modifiés:** {self.files_changed}" if self.files_changed > 0 else ""
        if self.additions > 0 or self.deletions > 0:
            stats += f" (+{self.additions} / -{self.deletions} lignes)"
        
        merged_info = f"\n- **Fusionné le:** {self.merged_at}" if self.merged_at else ""
        
        return f"""🔀 **DERNIER PULL REQUEST:**
- **Titre:** {self.title}
- **Numéro:** #{self.number}
- **Auteur:** {self.author}
- **État:** {self.state}{merged_info}
- **Date de création:** {self.created_at}
- **Branches:** {self.head_branch} → {self.base_branch}
{"- " + stats if stats else ""}

📝 **Description:**
{description}"""


class GitHubContextEnricher:
    """
    Service d'enrichissement du contexte avec données GitHub.
    
    Architecture:
    - Extraction propre des données
    - Formatage cohérent
    - Logging détaillé
    - Extensible facilement
    """
    
    def __init__(self):
        """Initialise le service d'enrichissement."""
        logger.debug("GitHubContextEnricher initialisé")
    
    def extract_github_data(
        self,
        orchestrator_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extrait et structure les données GitHub depuis le résultat de l'orchestrateur.
        
        Args:
            orchestrator_result: Résultat brut de l'orchestrateur GitHub
            
        Returns:
            Dict avec données structurées et typées
        """
        if not orchestrator_result.get("success"):
            logger.warning("Orchestrateur GitHub a échoué")
            return {}
        
        raw_data = orchestrator_result.get("data", {})
        structured_data = {}

        if "commits" in raw_data:
            commits_dict = raw_data["commits"]
            commits_list = commits_dict.get("commits", []) if isinstance(commits_dict, dict) else commits_dict
            
            if commits_list and len(commits_list) > 0:
                try:
                    structured_data["last_commit"] = GitHubCommitInfo.from_dict(commits_list[0])
                    structured_data["commits_count"] = len(commits_list)
                    structured_data["all_commits"] = [
                        GitHubCommitInfo.from_dict(c) for c in commits_list[:5]
                    ]
                    logger.info(f"✅ {len(commits_list)} commits extraits")
                except Exception as e:
                    logger.error(f"❌ Erreur extraction commits: {e}")
        
        if "pull_requests" in raw_data:
            prs_dict = raw_data["pull_requests"]
            prs_list = prs_dict.get("pull_requests", []) if isinstance(prs_dict, dict) else prs_dict
            
            if prs_list and len(prs_list) > 0:
                try:
                    structured_data["last_pr"] = GitHubPullRequestInfo.from_dict(prs_list[0])
                    structured_data["prs_count"] = len(prs_list)
                    structured_data["all_prs"] = [
                        GitHubPullRequestInfo.from_dict(pr) for pr in prs_list[:3]
                    ]
                    logger.info(f"✅ {len(prs_list)} PRs extraits")
                except Exception as e:
                    logger.error(f"❌ Erreur extraction PRs: {e}")
        
        if "repository" in raw_data:
            repo_dict = raw_data["repository"]
            
            if isinstance(repo_dict, dict):
                if "repository" in repo_dict:
                    repo_data = repo_dict["repository"]
                else:
                    repo_data = repo_dict
            else:
                repo_data = repo_dict
            
            if repo_data:
                structured_data["repository"] = {
                    "name": repo_data.get("name", "N/A"),
                    "full_name": repo_data.get("full_name", "N/A"),
                    "description": repo_data.get("description", "N/A"),
                    "language": repo_data.get("language", "N/A"),
                    "stars": repo_data.get("stars", repo_data.get("stargazers_count", 0)),
                    "forks": repo_data.get("forks", repo_data.get("forks_count", 0)),
                    "default_branch": repo_data.get("default_branch", "main")
                }
                
                if "structure" in repo_data:
                    structure_data = repo_data.get("structure", [])
                    if structure_data and len(structure_data) > 0:
                        structured_data["repository_structure"] = structure_data
                        logger.info(f"✅ Structure repo extraite: {len(structure_data)} fichiers")
                    else:
                        logger.warning("⚠️ Structure présente mais vide")
                else:
                    logger.warning(f"⚠️ Clé 'structure' absente. Clés disponibles: {list(repo_data.keys())[:10]}")
        
        logger.info(f"📦 Données GitHub structurées: {list(structured_data.keys())}")
        return structured_data
    
    def format_for_llm_prompt(
        self,
        github_data: Dict[str, Any],
        include_detailed: bool = True
    ) -> str:
        """
        Formate les données GitHub pour inclusion dans un prompt LLM.
        
        Args:
            github_data: Données GitHub structurées
            include_detailed: Inclure les détails étendus
            
        Returns:
            String formaté pour le prompt
        """
        if not github_data:
            return ""
        
        sections = []
        sections.append("\n\n🔍 **DONNÉES GITHUB RÉELLES (UTILISEZ CES INFORMATIONS) :**\n")
        
        if "last_commit" in github_data:
            commit: GitHubCommitInfo = github_data["last_commit"]
            sections.append(commit.format_for_prompt())
        
        if "last_pr" in github_data:
            pr: GitHubPullRequestInfo = github_data["last_pr"]
            sections.append("\n")
            sections.append(pr.format_for_prompt())
        
        if "repository" in github_data:
            repo = github_data["repository"]
            sections.append(f"""

📦 **INFORMATIONS REPOSITORY:**
- Nom: {repo['full_name']}
- Description: {repo['description']}
- Langage principal: {repo['language']}
- Stars: {repo['stars']} | Forks: {repo['forks']}
- Branche par défaut: {repo.get('default_branch', 'main')}""")
        
        if "repository_structure" in github_data:
            structure = github_data["repository_structure"]
            structure_formatted = self._format_repository_structure(structure)
            key_files = self._identify_key_files(structure)
            
            sections.append(f"""

📁 **STRUCTURE DU PROJET:**
{structure_formatted}

🎯 **COMPOSANTS CLÉS IDENTIFIÉS:**
{key_files}

💡 POUR RÉPONDRE: Décrivez la structure ET les composants clés (fichiers .java, README, config, etc.)""")
        
        if include_detailed:
            if "all_commits" in github_data and len(github_data["all_commits"]) > 1:
                commits: List[GitHubCommitInfo] = github_data["all_commits"]
                commits_summary = "\n".join([
                    f"  - {c.sha[:7]} | {c.message[:60]}... | {c.author_name}"
                    for c in commits
                ])
                sections.append(f"""

📜 **5 DERNIERS COMMITS:**
{commits_summary}""")
            
            if "all_prs" in github_data and len(github_data["all_prs"]) > 1:
                prs: List[GitHubPullRequestInfo] = github_data["all_prs"]
                prs_summary = "\n".join([
                    f"  - #{pr.number} | {pr.title[:60]}... | {pr.state}"
                    for pr in prs
                ])
                sections.append(f"""

🔀 **DERNIERS PULL REQUESTS:**
{prs_summary}""")
        
        formatted = "".join(sections)
        
        if not formatted:
            logger.warning("⚠️ Aucune donnée GitHub formatée")
        
        return formatted
    
    def build_instruction_section(self, has_github_data: bool) -> str:
        """
        Construit la section d'instructions pour le LLM.
        
        Args:
            has_github_data: Si des données GitHub sont disponibles
            
        Returns:
            Instructions formatées
        """
        if not has_github_data:
            return """

IMPORTANT:
- Réponds avec les informations disponibles dans le contexte
- Si une information n'est pas disponible, dis-le clairement"""
        
        return """

⚠️ INSTRUCTIONS CRITIQUES - LISEZ ATTENTIVEMENT ⚠️:

1. ✅ Les DONNÉES GITHUB RÉELLES sont FOURNIES ci-dessus dans la section "🔍 DONNÉES GITHUB RÉELLES"
2. ✅ Ces données incluent : commits, pull requests, repository info, etc.
3. ✅ VOUS DEVEZ utiliser CES DONNÉES pour répondre - elles sont COMPLÈTES et EXACTES
4. ✅ Si la question demande "quel est le dernier commit", CITEZ le message/auteur/date fourni
5. ✅ Si la question demande "dernier PR", CITEZ le titre/numéro/état fourni
6. ❌ NE DITES JAMAIS "je ne peux pas accéder aux données" - ELLES SONT DÉJÀ LÀ
7. ❌ NE DITES JAMAIS "j'ai besoin d'un accès" - VOUS L'AVEZ DÉJÀ
8. ❌ N'inventez AUCUNE information - utilisez SEULEMENT ce qui est fourni

EXEMPLE DE BONNE RÉPONSE:
Q: "Quel est le message du dernier commit?"
R: "Le dernier commit est '[message exact du commit ci-dessus]' par [auteur exact] le [date exacte]"

EXEMPLE DE MAUVAISE RÉPONSE (❌ INTERDIT):
R: "Je ne peux pas accéder aux données du repository..."

Rappelez-vous: Les données sont DÉJÀ dans le contexte ci-dessus. UTILISEZ-LES."""
    
    def _format_repository_structure(self, structure: List[Dict[str, Any]], max_items: int = 30) -> str:
        """
        Formate la structure du repository de manière hiérarchique.
        
        Args:
            structure: Liste des fichiers/dossiers
            max_items: Nombre max d'éléments à afficher
            
        Returns:
            Structure formatée en arbre
        """
        if not structure or len(structure) == 0:
            return "Aucune structure disponible"
        
        directories = {}
        root_files = []
        
        for item in structure:
            path = item.get('path', '')
            item_type = 'file' if item.get('type') == 'blob' else 'directory'
            
            if '/' in path:
                parts = path.split('/')
                dir_name = parts[0]
                if dir_name not in directories:
                    directories[dir_name] = []
                directories[dir_name].append({
                    'path': '/'.join(parts[1:]),
                    'type': item_type,
                    'is_file': item_type == 'file'
                })
            else:
                root_files.append({
                    'name': path,
                    'type': item_type,
                    'is_file': item_type == 'file'
                })
        
        lines = []
        lines.append("```")
        
        for file_info in sorted(root_files, key=lambda x: (x['is_file'], x['name']))[:8]:
            icon = "📄" if file_info['is_file'] else "📁"
            lines.append(f"{icon} {file_info['name']}")
        
        sorted_dirs = sorted(directories.items())[:15]
        for dir_name, contents in sorted_dirs:
            lines.append(f"📁 {dir_name}/")
            
            files = [c for c in contents if c['is_file']]
            subdirs = [c for c in contents if not c['is_file']]
            
            for subdir in subdirs[:2]:
                lines.append(f"  📁 {subdir['path']}")
            
            for file in files[:3]:
                lines.append(f"  📄 {file['path']}")
            
            remaining = len(contents) - len(subdirs[:2]) - len(files[:3])
            if remaining > 0:
                lines.append(f"    ... {remaining} autres éléments")
        
        if len(directories) > 15:
            lines.append(f"\n... {len(directories) - 15} autres dossiers")
        
        lines.append("```")
        lines.append(f"\n**Total:** {len(structure)} fichiers/dossiers")
        
        return "\n".join(lines)
    
    def _identify_key_files(self, structure: List[Dict[str, Any]]) -> str:
        """
        Identifie les fichiers clés dans la structure.
        
        Args:
            structure: Liste des fichiers/dossiers
            
        Returns:
            Description des fichiers clés
        """
        if not structure:
            return "Aucun fichier clé identifié"
        
        key_patterns = {
            "DAO/Core": ["DAO", "Database", "Connection", "Manager"],
            "Configuration": ["config", "properties", "yaml", "yml", "env"],
            "Models": ["model", "entity", "domain"],
            "Providers": ["provider", "driver"],
            "Exceptions": ["exception", "error"],
            "Tests": ["test", "spec"],
            "Documentation": ["README", "LICENCE", "CONTRIBUTING"]
        }
        
        found_files = {}
        
        for item in structure:
            path = item.get('path', '')
            filename = path.split('/')[-1]
            
            for category, patterns in key_patterns.items():
                if any(pattern.lower() in path.lower() for pattern in patterns):
                    if category not in found_files:
                        found_files[category] = []
                    if len(found_files[category]) < 5:  
                        found_files[category].append(f"`{path}`")
        
        if not found_files:
            return "Fichiers analysés mais catégories standard non trouvées"
        
        lines = []
        for category, files in found_files.items():
            lines.append(f"- **{category}:** {', '.join(files)}")
        
        return "\n".join(lines)

github_context_enricher = GitHubContextEnricher()