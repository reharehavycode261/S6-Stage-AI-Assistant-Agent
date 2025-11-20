"""Service optimisé pour répondre aux questions simples RAPIDEMENT (sans clone)."""

from typing import Dict, Any, Optional
import httpx
from utils.logger import get_logger
from config.settings import get_settings

logger = get_logger(__name__)


class QuestionLightService:
    """
    Service optimisé pour répondre aux questions simples en 15s maximum.
    
    Caractéristiques:
    - Pas de clone repository
    - Pas d'installation de dépendances
    - Collecte GitHub via API uniquement
    - Réponse basée sur métadonnées
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.github_token = self.settings.github_token
        
    async def is_simple_question(self, question_text: str) -> bool:
        """
        Détermine si une question est "simple" et peut être répondue rapidement.
        
        STRATÉGIE ACTUELLE (MODE COMPLET FORCÉ):
        - TOUTES les questions passent en MODE COMPLET (102s)
        - Analyse complète du code source pour chaque question
        - Clone + Installation + Analyse approfondie
        
        DÉSACTIVÉ:
        - Le MODE LIGHT (15s) est désactivé pour garantir des réponses de qualité
        - Toutes les questions ont accès aux fichiers sources
        - Réponses basées sur analyse réelle du code, pas sur métadonnées
        
        Raison:
        - L'utilisateur demande une vraie analyse valable
        - Pas de "image de réponse" superficielle
        - Accès complet au code source requis
        """
        
        return False
    
    async def answer_simple_question(
        self,
        question: str,
        repository_url: str,
        task_title: str
    ) -> Dict[str, Any]:
        """
        Répond à une question simple en collectant uniquement les métadonnées GitHub.
        
        Args:
            question: La question posée
            repository_url: URL du repository GitHub
            task_title: Titre de la tâche
            
        Returns:
            Dictionnaire avec la réponse générée
        """
        logger.info("⚡ MODE LIGHT ACTIVÉ: Réponse rapide sans clone")
        logger.info(f"❓ Question: {question[:100]}...")
        logger.info(f"🔗 Repository: {repository_url}")
        
        try:
            owner, repo = self._extract_owner_repo(repository_url)
            logger.info(f"📦 Repository détecté: {owner}/{repo}")
            
            metadata = await self._collect_github_metadata_light(owner, repo)
            
            response = await self._generate_simple_answer(
                question=question,
                metadata=metadata,
                repository=f"{owner}/{repo}",
                task_title=task_title
            )
            
            logger.info(f"✅ Réponse générée en mode LIGHT: {len(response)} caractères")
            
            return {
                "success": True,
                "response": response,
                "mode": "light",
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur mode LIGHT: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "mode": "light"
            }
    
    def _extract_owner_repo(self, repository_url: str) -> tuple[str, str]:
        """Extrait owner/repo depuis l'URL GitHub."""
        url = repository_url.strip()
        
        if "github.com/" in url:
            parts = url.split("github.com/")[1].split("/")
            owner = parts[0]
            repo = parts[1].replace(".git", "")
            return owner, repo
        else:
            raise ValueError(f"URL GitHub invalide: {repository_url}")
    
    async def _collect_github_metadata_light(
        self,
        owner: str,
        repo: str
    ) -> Dict[str, Any]:
        """
        Collecte UNIQUEMENT les métadonnées essentielles via API GitHub.
        Pas de clone, juste les infos de base.
        
        Collecte (5s max):
        - Infos repository (description, langages, stars, forks)
        - README (première section)
        - Structure racine (fichiers principaux)
        - 3 derniers commits
        """
        logger.info(f"📊 Collecte métadonnées LIGHT pour {owner}/{repo}")
        
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        metadata = {}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info("1/4 Récupération infos repository...")
            repo_url = f"https://api.github.com/repos/{owner}/{repo}"
            resp = await client.get(repo_url, headers=headers)
            if resp.status_code == 200:
                repo_data = resp.json()
                metadata["repository"] = {
                    "name": repo_data.get("name"),
                    "description": repo_data.get("description"),
                    "language": repo_data.get("language"),
                    "languages_url": repo_data.get("languages_url"),
                    "stars": repo_data.get("stargazers_count", 0),
                    "forks": repo_data.get("forks_count", 0),
                    "open_issues": repo_data.get("open_issues_count", 0),
                    "created_at": repo_data.get("created_at"),
                    "updated_at": repo_data.get("updated_at"),
                    "topics": repo_data.get("topics", [])
                }
                logger.info(f"✅ Repository: {repo_data.get('name')} ({repo_data.get('language')})")
            
            logger.info("2/4 Récupération README...")
            readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
            resp = await client.get(readme_url, headers=headers)
            if resp.status_code == 200:
                readme_data = resp.json()
                import base64
                readme_content = base64.b64decode(readme_data.get("content", "")).decode("utf-8")
                metadata["readme"] = readme_content[:1000]
                logger.info(f"✅ README récupéré: {len(readme_content)} caractères (tronqué à 1000)")
            else:
                metadata["readme"] = "Pas de README disponible"
                logger.info("⚠️ Pas de README trouvé")
            
            logger.info("3/4 Récupération structure racine...")
            contents_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
            resp = await client.get(contents_url, headers=headers)
            if resp.status_code == 200:
                contents = resp.json()
                files = [item["name"] for item in contents if item["type"] == "file"]
                dirs = [item["name"] for item in contents if item["type"] == "dir"]
                metadata["structure"] = {
                    "root_files": files[:20],
                    "root_directories": dirs[:20],
                    "total_items": len(contents)
                }
                logger.info(f"✅ Structure: {len(files)} fichiers, {len(dirs)} dossiers")
            
            logger.info("4/4 Récupération derniers commits...")
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=3"
            resp = await client.get(commits_url, headers=headers)
            if resp.status_code == 200:
                commits_data = resp.json()
                metadata["recent_commits"] = [
                    {
                        "sha": commit["sha"][:7],
                        "message": commit["commit"]["message"],
                        "author": commit["commit"]["author"]["name"],
                        "date": commit["commit"]["author"]["date"]
                    }
                    for commit in commits_data
                ]
                logger.info(f"✅ Commits: {len(metadata['recent_commits'])} récupérés")
            
            if "languages_url" in metadata.get("repository", {}):
                logger.info("5/5 Récupération langages...")
                lang_url = metadata["repository"]["languages_url"]
                resp = await client.get(lang_url, headers=headers)
                if resp.status_code == 200:
                    metadata["languages"] = resp.json()
                    logger.info(f"✅ Langages: {list(metadata['languages'].keys())}")
        
        logger.info("✅ Collecte métadonnées LIGHT terminée")
        return metadata
    
    async def _generate_simple_answer(
        self,
        question: str,
        metadata: Dict[str, Any],
        repository: str,
        task_title: str
    ) -> str:
        """
        Génère une réponse simple basée uniquement sur les métadonnées GitHub.
        Pas de clone, pas d'analyse lourde.
        
        Args:
            question: La question posée
            metadata: Métadonnées GitHub collectées
            repository: Nom du repository (owner/repo)
            task_title: Titre de la tâche
            
        Returns:
            Réponse générée en texte
        """
        logger.info("🤖 Génération réponse LIGHT avec OpenAI...")
        
        import openai
        
        if not self.settings.openai_api_key:
            return "❌ Impossible de générer une réponse (API OpenAI non configurée)"
        
        client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key)
        
        repo_info = metadata.get("repository", {})
        readme_excerpt = metadata.get("readme", "Pas de README disponible")[:500]
        structure = metadata.get("structure", {})
        commits = metadata.get("recent_commits", [])
        languages = metadata.get("languages", {})
        
        context_text = f"""
📦 **Repository:** {repository}
📝 **Description:** {repo_info.get('description', 'Non renseignée')}
💻 **Langage principal:** {repo_info.get('language', 'Non spécifié')}
⭐ **Stars:** {repo_info.get('stars', 0)}
🔀 **Forks:** {repo_info.get('forks', 0)}

📋 **README (extrait):**
{readme_excerpt}

📁 **Structure racine:**
- Fichiers: {', '.join(structure.get('root_files', [])[:10])}
- Dossiers: {', '.join(structure.get('root_directories', [])[:10])}

💾 **Derniers commits:**
{self._format_commits(commits)}

🌐 **Langages du projet:**
{', '.join(languages.keys()) if languages else 'Non spécifié'}
"""
        
        system_prompt = """Tu es VyData, un assistant IA spécialisé dans l'analyse de projets GitHub.

Ta mission: Répondre RAPIDEMENT et PRÉCISÉMENT aux questions sur les repositories.

IMPORTANT:
- Réponds UNIQUEMENT avec les informations fournies
- Sois concis et factuel
- Si l'information n'est pas disponible, dis-le clairement
- N'invente AUCUNE information
- Indique si une analyse plus approfondie serait nécessaire

Format de réponse:
1. Réponse directe à la question
2. Informations pertinentes trouvées
3. Note si analyse approfondie recommandée"""

        user_prompt = f"""**Question:** {question}

**Contexte disponible:**
{context_text}

**Tâche:** {task_title}

Réponds à la question de manière concise en te basant UNIQUEMENT sur les informations ci-dessus."""

        try:
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            answer = response.choices[0].message.content
            logger.info(f"✅ Réponse générée: {len(answer)} caractères")
            
            return answer
            
        except Exception as e:
            logger.error(f"❌ Erreur génération réponse: {e}")
            return f"❌ Erreur lors de la génération de la réponse: {str(e)}"
    
    def _format_commits(self, commits: list) -> str:
        """Formate les commits pour l'affichage."""
        if not commits:
            return "Aucun commit récent"
        
        formatted = []
        for commit in commits[:3]:
            formatted.append(
                f"  • {commit['sha']}: {commit['message'][:60]} ({commit['author']})"
            )
        return "\n".join(formatted)

