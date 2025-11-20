"""
Service de réponse directe pour les questions informatives (Type 1).

Ce service:
- Génère des réponses à des questions sur le projet
- Analyse le contexte du projet (code, structure, technologies)
- Poste la réponse directement dans Monday.com
- N'utilise PAS le workflow complet (pas de PR, pas de validation humaine)
"""

from typing import Dict, Any, Optional
from utils.logger import get_logger
from config.settings import get_settings
from services.github_context_enricher import github_context_enricher
import openai

logger = get_logger(__name__)
settings = get_settings()


class AgentResponseService:
    """
    Service pour générer et poster des réponses informatives.
    
    Flux AMÉLIORÉ:
    1. Recevoir une question
    2. EXPLORER LE PROJET COMPLET:
       - Clone le repository (prepare_environment)
       - Analyse la structure, le code, les technologies (analyze_requirements)
    3. Générer une réponse enrichie avec OpenAI basée sur l'exploration
    4. Poster la réponse dans Monday.com
    
    IMPORTANT: 
    - Exécute prepare_environment et analyze_requirements pour avoir le contexte complet
    - S'arrête AVANT implémentation (pas de modifications)
    - S'arrête AVANT validation humaine
    """
    
    def __init__(self):
        """Initialise le service de réponse."""
        self.openai_client = None
        if settings.openai_api_key:
            self.openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        else:
            logger.warning("⚠️ OpenAI API key non configurée - Réponses désactivées")
        
        from services.github import GitHubInformationOrchestrator, GitHubCollectorConfig
        self.github_orchestrator = GitHubInformationOrchestrator(settings.github_token)
        
        self.github_config = GitHubCollectorConfig(
            limit_prs=3,
            limit_issues=5,
            limit_commits=5,
            limit_branches=5,
            limit_releases=3,
            limit_contributors=5,
            limit_labels=10,
            limit_milestones=3,
            include_pr_files=False,
            include_commit_files=False,
            include_closed_issues=False,
            include_all_branches=False
        )
    
    async def generate_and_post_response(
        self,
        question: str,
        task_context: Dict[str, Any],
        monday_item_id: str,
        task: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Génère une réponse à une question et la poste dans Monday.com.
        
        NOUVEAU FLUX:
        1. Explorer le projet complet via ProjectExplorationService
           - Clone le repository (prepare_environment)
           - Analyse complète (analyze_requirements)
        2. Générer une réponse enrichie avec OpenAI basée sur l'exploration réelle
        3. Poster la réponse dans Monday.com
        
        Args:
            question: Question posée par l'utilisateur
            task_context: Contexte de la tâche (titre, description, statut, etc.)
            monday_item_id: ID de l'item Monday.com où poster la réponse
            task: Objet Task pour l'exploration (optionnel)
            
        Returns:
            Résultat de l'opération avec la réponse générée
        """
        logger.info(f"💬 Génération réponse pour question: '{question[:50]}...'")
        
        if not self.openai_client:
            error_msg = "OpenAI API non configurée - impossible de générer une réponse"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        
        try:
            project_context = await self._explore_project_full(question, task_context, task)
            
            response_text = await self._generate_response(question, task_context, project_context)
            
            logger.info(f"✅ Réponse générée: {len(response_text)} caractères")
            
            creator_name = None
            if task:
                if isinstance(task, dict):
                    creator_name = task.get('creator_name')
                elif hasattr(task, 'creator_name'):
                    creator_name = task.creator_name
            
            user_language = task_context.get('user_language', 'en')
            project_language = task_context.get('project_language', 'en')
            
            post_result = await self._post_response_to_monday(
                response_text=response_text,
                monday_item_id=monday_item_id,
                original_question=question,
                creator_name=creator_name,
                user_language=user_language,
                project_language=project_language
            )
            
            if post_result.get("success"):
                logger.info(f"✅ Réponse postée dans Monday.com: item {monday_item_id}")
                return {
                    "success": True,
                    "response_text": response_text,
                    "monday_update_id": post_result.get("update_id"),
                    "message": "Réponse générée et postée avec succès",
                    "project_explored": project_context.get("success", False)
                }
            else:
                logger.error(f"❌ Échec post réponse Monday.com: {post_result.get('error')}")
                return {
                    "success": False,
                    "error": f"Échec post Monday.com: {post_result.get('error')}",
                    "response_text": response_text  
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur génération réponse: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Erreur génération réponse: {str(e)}"
            }
    
    async def _explore_project_full(
        self, 
        question: str, 
        task_context: Dict[str, Any],
        task: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Explore le projet complet via les nœuds du workflow.
        
        Exécute:
        - prepare_environment: Clone le repo, setup l'environnement
        - analyze_requirements: Analyse complète du code, structure, technologies
        
        N'exécute PAS:
        - Nœud d'implémentation (pas de modifications)
        - Nœud de tests
        - Nœud de PR
        - Nœud de validation humaine
        
        Args:
            question: Question de l'utilisateur
            task_context: Contexte de la tâche
            task: Objet Task (optionnel, chargé si non fourni)
            
        Returns:
            Contexte enrichi du projet avec analyse complète
        """
        logger.info("="*80)
        logger.info("🔍 DÉBUT EXPLORATION COMPLÈTE DU PROJET")
        logger.info("="*80)
        logger.info(f"❓ Question: '{question[:100]}...'")
        logger.info(f"📦 Task fourni: {'Oui' if task else 'Non'}")
        logger.info("="*80)
        
        try:
            if not task:
                logger.info("⏳ Task non fourni - chargement depuis la base...")
                task = await self._load_task_from_context(task_context)
                if not task:
                    logger.error("="*80)
                    logger.error("❌ ÉCHEC CHARGEMENT TASK - FALLBACK ANALYSE BASIQUE")
                    logger.error("="*80)
                    logger.warning("⚠️ Impossible de charger la tâche - fallback analyse basique")
                    return await self._analyze_project_context_basic(task_context)
                else:
                    logger.info(f"✅ Task chargée avec succès: {task.get('title', 'N/A')}")
            else:
                logger.info(f"✅ Task déjà fournie: {task.get('title', 'N/A') if isinstance(task, dict) else task}")
            
            logger.info("🚀 Lancement ProjectExplorationService...")
            from services.project_exploration_service import project_exploration_service
            
            exploration_result = await project_exploration_service.explore_project_for_question(
                task=task,
                question=question,
                task_context=task_context
            )
            
            logger.info("="*80)
            logger.info("📊 RÉSULTAT EXPLORATION")
            logger.info("="*80)
            logger.info(f"✅ Succès: {exploration_result.get('success')}")
            if not exploration_result.get("success"):
                logger.error(f"❌ Erreur: {exploration_result.get('error')}")
                logger.error(f"📍 Phase: {exploration_result.get('phase')}")
            logger.info("="*80)
            
            if exploration_result.get("success"):
                logger.info("✅✅✅ Exploration complète du projet TERMINÉE AVEC SUCCÈS")
                project_context = exploration_result.get("project_context", {})
                
                logger.info(f"📊 Technologies détectées: {project_context.get('technologies', [])}")
                logger.info(f"📁 Fichiers analysés: {len(project_context.get('file_structure', []))}")
                logger.info(f"🔗 Repository: {project_context.get('repository_url', 'N/A')}")
                
                project_context.update({
                    "title": task_context.get("title", ""),
                    "description": task_context.get("description", ""),
                    "repository_url": task_context.get("repository_url", ""),
                    "exploration_successful": True
                })
                
                github_context = await self._enrich_with_github_info(
                    question=question,
                    repository_url=project_context.get("repository_url")
                )
                if github_context:
                    project_context["github_info"] = github_context
                    logger.info(f"✅ Contexte enrichi avec informations GitHub")
                
                return project_context
            else:
                error = exploration_result.get("error", "Erreur inconnue")
                logger.error("="*80)
                logger.error("❌ EXPLORATION INCOMPLÈTE OU ÉCHOUÉE")
                logger.error("="*80)
                logger.warning(f"⚠️ Exploration incomplète: {error}")
                logger.info("📋 Tentative utilisation contexte partiel...")
                
                partial_context = exploration_result.get("partial_context", {})
                if partial_context:
                    logger.info("✅ Contexte partiel disponible - utilisation")
                    partial_context.update({
                        "title": task_context.get("title", ""),
                        "description": task_context.get("description", ""),
                        "exploration_successful": False,
                        "exploration_error": error
                    })
                    return partial_context
                else:
                    logger.warning("⚠️ Aucun contexte partiel - fallback analyse basique")
                    return await self._analyze_project_context_basic(task_context)
                    
        except Exception as e:
            logger.error(f"❌ Erreur exploration projet: {e}", exc_info=True)
            logger.info("📋 Fallback: analyse basique sans exploration")
            return await self._analyze_project_context_basic(task_context)
    
    async def _load_task_from_context(self, task_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Charge les données de la tâche depuis le contexte.
        
        Args:
            task_context: Contexte de la tâche
            
        Returns:
            Dictionnaire avec les données de la tâche ou None
        """
        try:
            from services.database_persistence_service import db_persistence
            
            logger.info("="*80)
            logger.info("📥 CHARGEMENT TASK DEPUIS CONTEXTE")
            logger.info("="*80)
            logger.info(f"📋 Clés disponibles dans task_context: {list(task_context.keys())}")
            
            task_id = task_context.get("tasks_id")
            if not task_id:
                logger.error("❌ tasks_id NON TROUVÉ dans task_context")
                logger.error(f"📦 task_context complet: {task_context}")
                return None
            
            logger.info(f"🔍 Chargement tâche ID: {task_id}")
            
            task_data = await db_persistence.get_task_by_id(task_id)
            if not task_data:
                logger.error(f"❌ Tâche {task_id} NON TROUVÉE en base de données")
                return None
            
            logger.info(f"✅ Tâche {task_id} chargée avec succès")
            logger.info(f"📋 Titre: {task_data.get('title', 'N/A')}")
            logger.info(f"🔗 Repository: {task_data.get('repository_url', 'N/A')}")
            logger.info("="*80)
            
            return task_data
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement tâche: {e}", exc_info=True)
            return None
    
    async def _detect_github_question(self, question: str) -> bool:
        """
        Détecte si la question concerne des informations GitHub via un LLM.
        
        Args:
            question: Question de l'utilisateur
            
        Returns:
            True si c'est une question GitHub, False sinon
        """
        from ai.chains.github_question_detection_chain import detect_github_question
        
        logger.info("🔍 Détection question GitHub via LLM...")
        
        try:
            analysis = await detect_github_question(
                question=question,
                provider="anthropic",
                fallback_to_openai=True
            )
            
            if analysis.is_github_question:
                logger.info(f"✅ Question GitHub détectée (confiance: {analysis.confidence:.2f})")
                logger.info(f"   Raisonnement: {analysis.reasoning}")
            else:
                logger.info(f"ℹ️  Question NON-GitHub - Analyse du code suffira (confiance: {analysis.confidence:.2f})")
                logger.info(f"   Raisonnement: {analysis.reasoning}")
            
            return analysis.is_github_question
        
        except Exception as e:
            logger.error(f"❌ Erreur détection question GitHub: {e}", exc_info=True)
            return False
    
    async def _enrich_with_github_info(
        self,
        question: str,
        repository_url: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Enrichit le contexte avec TOUTES les informations GitHub disponibles via l'orchestrateur OO.
        Le LLM décidera ensuite quelles informations utiliser pour répondre.
        
        NOUVELLE ARCHITECTURE ORIENTÉE OBJET:
        - Utilise GitHubInformationOrchestrator
        - Collecte automatique de toutes les données (PRs, Issues, Commits, Branches, Releases, etc.)
        - Format automatique pour le LLM
        - Extensible facilement avec de nouveaux collecteurs
        
        Args:
            question: Question de l'utilisateur
            repository_url: URL du repository GitHub
            
        Returns:
            Contexte GitHub complet ou None si pas pertinent
        """
        if not repository_url:
            return None
        
        # Détecter si la question concerne GitHub via LLM
        is_github_question = await self._detect_github_question(question)
        
        if not is_github_question:
            return None
        
        logger.info("="*80)
        logger.info("📦 ORCHESTRATEUR GITHUB - COLLECTE COMPLÈTE (OO)")
        logger.info("="*80)
        logger.info("ℹ️  Architecture: Collecteurs orientés objet extensibles")
        logger.info("ℹ️  Stratégie: Récupérer TOUTES les infos, le LLM choisira")
        
        try:
            collected_data = await self.github_orchestrator.collect_all(
                repository_url=repository_url,
                config=self.github_config,
                collectors=None  
            )
            
            if not collected_data.get("success"):
                logger.error(f"❌ Échec collecte GitHub: {collected_data.get('error')}")
                return None
            
            github_context = collected_data.get("data", {})
            
            successful_collectors = [
                key for key, value in github_context.items()
                if value.get("success", False)
            ]
            
            logger.info(f"✅ Contexte GitHub complet récupéré:")
            logger.info(f"   - Collecteurs réussis: {len(successful_collectors)}/{len(github_context)}")
            logger.info(f"   - Types de données: {', '.join(successful_collectors)}")
            logger.info("="*80)
            
            return github_context if github_context else None
        
        except Exception as e:
            logger.error(f"❌ Erreur orchestrateur GitHub: {e}", exc_info=True)
            return None
    
    async def _analyze_project_context_basic(self, task_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyse basique du contexte sans exploration complète (fallback).
        
        Args:
            task_context: Contexte de la tâche
            
        Returns:
            Contexte enrichi basique du projet
        """
        logger.debug("🔍 Analyse basique du contexte du projet (sans exploration)...")
        
        repository_url = task_context.get("repository_url")
        title = task_context.get("title", "")
        description = task_context.get("description", "")
        
        context = {
            "has_repository": bool(repository_url),
            "repository_url": repository_url,
            "title": title,
            "description": description,
            "technologies": [],
            "file_structure": None,
            "exploration_successful": False,
            "exploration_mode": "basic"
        }
        
        technologies = self._detect_technologies(description)
        context["technologies"] = technologies
        
        logger.debug(f"📋 Technologies détectées (basique): {technologies}")
        
        return context
    
    def _detect_technologies(self, text: str) -> list:
        """
        Détecte les technologies mentionnées dans le texte.
        
        Args:
            text: Texte à analyser (description, titre, etc.)
            
        Returns:
            Liste des technologies détectées
        """
        if not text:
            return []
        
        text_lower = text.lower()
        
        tech_keywords = {
            "python": "Python",
            "java": "Java",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "react": "React",
            "vue": "Vue.js",
            "angular": "Angular",
            "django": "Django",
            "flask": "Flask",
            "fastapi": "FastAPI",
            "spring": "Spring",
            "node": "Node.js",
            "express": "Express.js",
            "postgres": "PostgreSQL",
            "mysql": "MySQL",
            "mongodb": "MongoDB",
            "redis": "Redis",
            "docker": "Docker",
            "kubernetes": "Kubernetes",
            "aws": "AWS",
            "azure": "Azure",
            "gcp": "Google Cloud",
        }
        
        detected = []
        for keyword, tech_name in tech_keywords.items():
            if keyword in text_lower:
                detected.append(tech_name)
        
        return detected
    
    async def _generate_response(
        self,
        question: str,
        task_context: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> str:
        """
        Génère une réponse à la question avec OpenAI.
        
        ✅ OPTIMISÉ: Détecte automatiquement les questions GitHub et récupère les vraies données.
        
        Args:
            question: Question de l'utilisateur
            task_context: Contexte de la tâche
            project_context: Contexte du projet analysé
            
        Returns:
            Texte de la réponse
        """
        if self._is_greeting(question):
            logger.info("👋 Salutation détectée - Réponse formatée spéciale")
            user_language = task_context.get('user_language', 'en')
            return await self._get_greeting_response(user_language)
        
        github_data = None
        
        if project_context.get("github_info"):
            logger.info("♻️  Réutilisation des données GitHub déjà collectées (évite double collecte)")
            github_data = github_context_enricher.extract_github_data({"success": True, "data": project_context["github_info"]})
            logger.info(f"✅ Données structurées (cache): {list(github_data.keys())}")
        else:
            needs_github = await self._detect_github_question(question)
            
            if needs_github and task_context.get("repository_url"):
                logger.info(f"🔍 Question GitHub détectée pour {task_context.get('repository_url')}")
                
                orchestrator_result = await self._fetch_github_raw(
                    question,
                    task_context.get("repository_url"),
                    task_context.get("repository_name"),
                    task_context.get("default_branch", "main")
                )
                
                if orchestrator_result and orchestrator_result.get("success"):
                    github_data = github_context_enricher.extract_github_data(orchestrator_result)
                    logger.info(f"✅ Données structurées: {list(github_data.keys())}")
                else:
                    logger.warning("⚠️ Aucune données GitHub récupérée")
        
        prompt = self._create_response_prompt(
            question, 
            task_context, 
            project_context,
            github_data=github_data
        )
        
        logger.debug(f"🤖 Génération réponse avec OpenAI ({len(prompt)} caractères de prompt)")
        
        user_language = task_context.get('user_language', 'en')
        system_prompt = await self._get_system_prompt_for_language(user_language)
        
        response = await self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,  
            max_tokens=1500
        )
        
        response_text = response.choices[0].message.content.strip()
        
        logger.info(f"✅ Réponse générée: {len(response_text)} caractères")
        
        return response_text
    
    async def _get_greeting_response(self, language_code: str) -> str:
        """
        Génère dynamiquement une réponse de salutation dans N'IMPORTE QUELLE langue via LLM.
        
        Args:
            language_code: Code langue ISO 639-1 (2 lettres)
            
        Returns:
            Message de salutation multilingue
        """
        try:
            from services.project_language_detector import project_language_detector
            
            language_name = project_language_detector.LANGUAGE_NAMES.get(
                language_code, 
                language_code.upper()
            )
            
            logger.info(f"👋 Génération message de salutation pour: {language_name} ({language_code})")
            
            # Template de référence en anglais
            reference_greeting = """Hello! 👋 I'm **VyData**, your AI development assistant.

I can help you with:

💬 **Answering your questions** about your project
- Explain code and architecture
- Analyze technology choices
- Provide information on Git history

🔍 **Analyzing code** in depth
- Project structure
- Dependencies and technologies used
- Commits, branches and pull requests

🛠️ **Implementing new features**
- Add complete features
- Create components and services
- Follow best practices

🐛 **Fixing bugs**
- Identify and resolve issues
- Optimize performance
- Improve code quality

📋 **Creating Pull Requests** automatically
- Clean and tested code
- Complete documentation
- Ready for code review

How can I help you today? 😊"""
            
            # Si c'est l'anglais, retourner directement
            if language_code == 'en':
                return reference_greeting
            
            # Sinon, générer via LLM
            system_prompt = f"""Tu es un expert en traduction pour assistants IA.
Traduis le message de salutation suivant en {language_name}.

RÈGLES CRITIQUES:
1. Garde EXACTEMENT la même structure avec les sections
2. Garde TOUS les emojis (👋, 💬, 🔍, 🛠️, 🐛, 📋, 😊)
3. Traduis le contenu de manière naturelle et engageante
4. Conserve le ton professionnel mais amical
5. Adapte les salutations au contexte culturel (tutoiement/vouvoiement)
6. Réponds UNIQUEMENT avec la traduction, sans commentaire"""

            user_prompt = f"""Traduis ce message de salutation en {language_name} ({language_code}):

{reference_greeting}

IMPORTANT: Réponds UNIQUEMENT avec la traduction du message, rien d'autre."""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            translated_greeting = response.choices[0].message.content.strip()
            
            logger.info(f"✅ Message de salutation généré pour {language_name} ({len(translated_greeting)} caractères)")
            
            return translated_greeting
            
        except Exception as e:
            logger.error(f"❌ Erreur génération salutation: {e}")
            logger.warning(f"⚠️ Fallback vers anglais")
            # Fallback en anglais
            return """Hello! 👋 I'm **VyData**, your AI development assistant.

I can help you with:

💬 **Answering your questions** about your project
- Explain code and architecture
- Analyze technology choices
- Provide information on Git history

🔍 **Analyzing code** in depth
- Project structure
- Dependencies and technologies used
- Commits, branches and pull requests

🛠️ **Implementing new features**
- Add complete features
- Create components and services
- Follow best practices

🐛 **Fixing bugs**
- Identify and resolve issues
- Optimize performance
- Improve code quality

📋 **Creating Pull Requests** automatically
- Clean and tested code
- Complete documentation
- Ready for code review

How can I help you today? 😊"""
    
    async def _get_system_prompt_for_language(self, language_code: str) -> str:
        """
        Génère dynamiquement le prompt système dans N'IMPORTE QUELLE langue via LLM.
        
        Args:
            language_code: Code langue ISO 639-1 (2 lettres)
            
        Returns:
            Prompt système dans la bonne langue
        """
        try:
            from services.project_language_detector import project_language_detector
            
            language_name = project_language_detector.LANGUAGE_NAMES.get(
                language_code, 
                language_code.upper()
            )
            
            logger.info(f"🤖 Génération prompt système pour la langue: {language_name} ({language_code})")
            
            # Template de référence en anglais
            reference_prompt = """You are VyData, an AI assistant expert in software development.
You answer questions about development projects in a way that is:
- Clear and concise
- Technical but accessible
- Based on REAL data when available
- Honest (if you don't know, say so)
- Professional and friendly

Response format:
- Start with an appropriate emoji (💡, 📋, 🔍, etc.)
- Use the REAL DATA provided (commits, PRs, structure)
- Structure your response with bullets or numbers if needed
- End with an offer of additional help if relevant"""
            
            # Si c'est l'anglais, retourner directement
            if language_code == 'en':
                return reference_prompt
            
            # Sinon, générer via LLM
            system_prompt = f"""Tu es un expert en traduction technique pour assistants IA de développement.
Traduis le prompt système suivant en {language_name}.

RÈGLES CRITIQUES:
1. Garde EXACTEMENT la même structure et les mêmes sections
2. Garde TOUS les emojis (💡, 📋, 🔍)
3. Traduis le contenu de manière naturelle et fluide
4. Conserve le ton professionnel mais amical
5. Réponds UNIQUEMENT avec la traduction, sans commentaire"""

            user_prompt = f"""Traduis ce prompt système en {language_name} ({language_code}):

{reference_prompt}

IMPORTANT: Réponds UNIQUEMENT avec la traduction du prompt, rien d'autre."""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            translated_prompt = response.choices[0].message.content.strip()
            
            logger.info(f"✅ Prompt système généré pour {language_name} ({len(translated_prompt)} caractères)")
            
            return translated_prompt
            
        except Exception as e:
            logger.error(f"❌ Erreur génération prompt système: {e}")
            logger.warning(f"⚠️ Fallback vers anglais")
            # Fallback en anglais
            return """You are VyData, an AI assistant expert in software development.
You answer questions about development projects in a way that is:
- Clear and concise
- Technical but accessible
- Based on REAL data when available
- Honest (if you don't know, say so)
- Professional and friendly

Response format:
- Start with an appropriate emoji (💡, 📋, 🔍, etc.)
- Use the REAL DATA provided (commits, PRs, structure)
- Structure your response with bullets or numbers if needed
- End with an offer of additional help if relevant"""
    
    async def _fetch_github_raw(
        self,
        question: str,
        repository_url: str,
        repository_name: str,
        default_branch: str = "main"
    ) -> Dict[str, Any]:
        """
        ✅ NOUVELLE MÉTHODE: Récupère les données BRUTES de l'orchestrateur.
        Sans extraction intermédiaire - laisse l'enricher OO gérer tout.
        
        Args:
            question: Question pour déterminer quels collecteurs activer
            repository_url: URL du repository
            repository_name: Nom du repository
            default_branch: Branche par défaut
            
        Returns:
            Résultat brut de l'orchestrateur GitHub
        """
        try:
            question_lower = question.lower()

            collectors_needed = []
            if any(word in question_lower for word in ["commit", "dernier", "last", "historique"]):
                collectors_needed.append("commits")
            if any(word in question_lower for word in ["pull request", "pr", "merge"]):
                collectors_needed.append("pull_requests")
            if any(word in question_lower for word in ["structure", "fichiers", "files", "arborescence"]):
                collectors_needed.append("repository")
            
            if not collectors_needed:
                collectors_needed = ["repository", "commits", "pull_requests"]
            
            logger.info(f"📥 Collecte GitHub: {collectors_needed}")
            
            result = await self.github_orchestrator.collect_all(
                repository_url=repository_url,
                config=self.github_config
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération GitHub raw: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _is_greeting(self, question: str) -> bool:
        """
        Détecte si le message est une salutation.
        
        Args:
            question: Question à analyser
            
        Returns:
            True si c'est une salutation
        """
        question_lower = question.lower().strip()
        
        greetings = [
            "hello", "hi", "hey", "bonjour", "salut", "bonsoir",
            "good morning", "good afternoon", "good evening",
            "yo", "sup", "wassup"
        ]
        
        if len(question_lower.split()) <= 3:
            return any(greeting in question_lower for greeting in greetings)
        
        return False
    
    async def _detect_github_question(self, question: str) -> bool:
        """
        ✅ OPTIMISÉ: Détection rapide des questions nécessitant GitHub.
        
        Args:
            question: Question à analyser
            
        Returns:
            True si la question nécessite des données GitHub
        """
        question_lower = question.lower()
        
        github_keywords = [
            "commit", "pull request", "pr", "branch", "branche",
            "dernier", "last", "structure", "fichiers", "files",
            "historique", "history", "contributor", "contributeur"
        ]
        
        return any(keyword in question_lower for keyword in github_keywords)
    
    async def _fetch_github_data(
        self,
        question: str,
        repository_url: str,
        repository_name: str,
        default_branch: str = "main"
    ) -> Dict[str, Any]:
        """
        ✅ OPTIMISÉ: Récupère les données GitHub réelles selon la question.
        
        Args:
            question: Question pour cibler les données nécessaires
            repository_url: URL du repository
            repository_name: Nom du repository (owner/repo)
            default_branch: Branche par défaut
            
        Returns:
            Dict avec les données GitHub pertinentes
        """
        try:
            question_lower = question.lower()
            
            collectors_needed = []
            
            if any(word in question_lower for word in ["commit", "dernier", "last", "historique"]):
                collectors_needed.append("commits")
                
            if any(word in question_lower for word in ["pull request", "pr", "merge"]):
                collectors_needed.append("pull_requests")
                
            if any(word in question_lower for word in ["structure", "fichiers", "files", "arborescence", "organisation"]):
                collectors_needed.append("repository")
            
            if not collectors_needed:
                collectors_needed = ["repository", "commits", "pull_requests"]
            
            logger.info(f"📥 Collecte GitHub: {collectors_needed}")
            
            result = await self.github_orchestrator.collect_all(
                repository_url=repository_url,
                config=self.github_config
            )
            
            if not result.get("success"):
                logger.warning(f"⚠️ Collecte GitHub échouée: {result.get('error')}")
                return {}
            
            github_data = result.get("data", {})
            
            formatted_data = {}
            
            if "commits" in github_data:
                commits_dict = github_data["commits"]
                commits_list = commits_dict.get("data", []) if isinstance(commits_dict, dict) else commits_dict
                if commits_list:
                    formatted_data["commits"] = commits_list[:10]
                    formatted_data["last_commit"] = commits_list[0]
            
            if "pull_requests" in github_data:
                prs_dict = github_data["pull_requests"]
                prs_list = prs_dict.get("data", []) if isinstance(prs_dict, dict) else prs_dict
                if prs_list:
                    formatted_data["pull_requests"] = prs_list[:5]
                    formatted_data["last_pr"] = prs_list[0]
            
            if "repository" in github_data:
                formatted_data["repository"] = github_data["repository"]
            
            logger.info(f"✅ Données GitHub récupérées: {list(formatted_data.keys())}")
            return formatted_data
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération GitHub: {e}", exc_info=True)
            return {}
    
    def _create_response_prompt(
        self,
        question: str,
        task_context: Dict[str, Any],
        project_context: Dict[str, Any],
        github_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Crée le prompt pour générer la réponse basé sur l'exploration complète.
        
        Args:
            question: Question de l'utilisateur
            task_context: Contexte de la tâche
            project_context: Contexte du projet (avec exploration complète si disponible)
            
        Returns:
            Prompt formaté
        """
        technologies_str = ", ".join(project_context.get("technologies", [])) or "Non spécifié"
        exploration_successful = project_context.get("exploration_successful", False)
        
        has_github_data = github_data and len(github_data) > 0
        
        if exploration_successful or has_github_data:
            analysis_summary = project_context.get("analysis_summary", "Analyse disponible")
            file_structure = project_context.get("file_structure", [])
            dependencies = project_context.get("dependencies", [])
            structured_analysis = project_context.get("structured_analysis", {})
            
            file_count = len(file_structure)
            candidate_files = structured_analysis.get("candidate_files", []) if structured_analysis else []
            implementation_approach = structured_analysis.get("implementation_approach", "N/A") if structured_analysis else "N/A"
            
            main_files_str = "\n".join([f"  - {f}" for f in file_structure[:10]]) if file_structure else "  Aucun fichier détecté"
            if len(file_structure) > 10:
                main_files_str += f"\n  ... et {len(file_structure) - 10} autres fichiers"
            
            github_section = ""
            
            if github_data:
                github_section = github_context_enricher.format_for_llm_prompt(
                    github_data,
                    include_detailed=True
                )
                logger.debug(f"📦 Section GitHub formatée: {len(github_section)} caractères")
            elif project_context.get("github_info"):
                github_info = project_context.get("github_info", {})
                github_section = "\n\n" + self.github_orchestrator.format_for_llm(
                    collected_data={"success": True, "data": github_info},
                    collectors=None
                )
            
            prompt = f"""Question de l'utilisateur:
"{question}"

Contexte du projet (ANALYSE COMPLÈTE EFFECTUÉE):
- Titre de la tâche: {task_context.get('title', 'N/A')}
- Description: {task_context.get('description', 'N/A')[:300]}...
- Repository: {project_context.get('repository_url', 'N/A')}
- Technologies détectées: {technologies_str}
- Fichiers analysés: {file_count} fichier(s)
- Dépendances: {len(dependencies)} dépendance(s) identifiée(s)

Structure du projet:
{main_files_str}

Analyse du projet:
{analysis_summary[:1000]}{'...' if len(analysis_summary) > 1000 else ''}

{github_section if github_section else ''}

{github_context_enricher.build_instruction_section(bool(github_section))}

Réponds de manière claire, précise et factuelle en utilisant DIRECTEMENT les données ci-dessus."""
        else:
            error = project_context.get("exploration_error", "")
            
            prompt = f"""Question de l'utilisateur:
"{question}"

Contexte du projet (ANALYSE LIMITÉE):
- Titre de la tâche: {task_context.get('title', 'N/A')}
- Description: {task_context.get('description', 'N/A')[:300]}...
- Technologies détectées: {technologies_str}
- Statut actuel: {task_context.get('internal_status', 'N/A')}

Note: L'analyse complète du projet n'a pas pu être effectuée{f' ({error})' if error else ''}.
Base ta réponse sur les informations disponibles et indique clairement les limitations."""
        
        return prompt.strip()
    
    async def _post_response_to_monday(
        self,
        response_text: str,
        monday_item_id: str,
        original_question: str,
        creator_name: Optional[str] = None,
        user_language: str = 'en',
        project_language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Poste la réponse dans Monday.com avec template multilingue.
        
        Args:
            response_text: Texte de la réponse à poster
            monday_item_id: ID de l'item Monday.com
            original_question: Question originale (pour le contexte)
            creator_name: Nom du créateur du ticket (pour tagging)
            user_language: Langue de l'utilisateur (détectée automatiquement)
            project_language: Langue du projet
            
        Returns:
            Résultat de l'opération
        """
        logger.info(f"📤 Post réponse dans Monday.com: item {monday_item_id} (langue: {user_language})")
        
        try:
            from tools.monday_tool import MondayTool
            from utils.monday_comment_formatter import MondayCommentFormatter
            from services.project_language_detector import project_language_detector
            
            templates = await project_language_detector.get_monday_reply_template(
                user_language=user_language,
                project_language=project_language
            )
            
            # SÉCURITÉ: Vérification pour garantir que templates n'est JAMAIS None
            if not templates or not isinstance(templates, dict):
                logger.error(f"❌ CRITIQUE: templates invalide dans agent_response_service ! Type: {type(templates)}")
                templates = {
                    'response_header': '🤖 **VyData Response**',
                    'question_label': 'Question',
                    'automatic_response_note': 'This is an automatic response. For actions requiring code modifications, use a command.'
                }
            
            creator_tag = ""
            if creator_name:
                creator_tag = MondayCommentFormatter.format_creator_tag(creator_name)
                if creator_tag:
                    creator_tag = f"{creator_tag} "  
            
            question_without_mention = original_question.replace("@vydata", "").replace("@VyData", "").strip()
            
            response_header = templates.get('response_header', '🤖 **VyData Response**')
            question_label = templates.get('question_label', 'Question')
            automatic_response_note = templates.get('automatic_response_note', 
                'This is an automatic response. For actions requiring code modifications, use a command.')
            
            formatted_message = f"""{creator_tag}{response_header}

> {question_label}: {question_without_mention[:100]}{'...' if len(question_without_mention) > 100 else ''}

{response_text}

---
*{automatic_response_note}*
"""
            
            monday_tool = MondayTool()
            
            result = await monday_tool._arun(
                action="post_update",
                item_id=monday_item_id,
                update_text=formatted_message
            )
            
            if isinstance(result, dict) and result.get("success"):
                logger.info(f"✅ Réponse postée avec succès dans Monday.com")
                return {
                    "success": True,
                    "update_id": result.get("update_id")
                }
            else:
                error_msg = result.get("error", "Erreur inconnue") if isinstance(result, dict) else "Format de réponse invalide"
                logger.error(f"❌ Échec post Monday.com: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur post réponse Monday.com: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

agent_response_service = AgentResponseService()

