"""
Service de détection de la langue naturelle d'un projet (FR/EN/ES/etc.).

Ce service analyse le projet pour déterminer la langue de communication technique:
- README, documentation
- Commentaires dans le code
- Messages de commit existants

Cette langue sera utilisée pour :
- Générer les PR descriptions
- Écrire les messages de commit
- Créer les fichiers README/docs

⚠️ À ne pas confondre avec:
- Langue de programmation (Python, Java, etc.) → utils/language_detector.py
- Langue du message utilisateur → semantic_search_service.py
"""

import asyncio
import re
import subprocess
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path

from openai import AsyncOpenAI
from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class ProjectLanguageInfo:
    """Information sur la langue naturelle du projet."""
    language_code: str
    language_name: str
    confidence: float
    detection_sources: List[str]
    sample_texts: List[str]


class ProjectLanguageDetectorService:
    """
    Service de détection de la langue naturelle d'un projet.
    
    Analyse:
    - README.md, README.txt
    - CONTRIBUTING.md, CODE_OF_CONDUCT.md
    - Commentaires dans les fichiers de code
    - Messages de commit existants (via git log)
    """
    
    LANGUAGE_NAMES = {
        'fr': 'Français',
        'en': 'English',
        'es': 'Español',
        'de': 'Deutsch',
        'it': 'Italiano',
        'pt': 'Português',
        'zh': '中文',
        'ja': '日本語',
        'ru': 'Русский',
        'ar': 'العربية'
    }
    
    # Templates PR supprimés - génération dynamique via LLM pour toutes les langues sauf anglais
    
    def __init__(self):
        """Initialise le service."""
        self._openai_client: Optional[AsyncOpenAI] = None
    
    def _get_openai_client(self) -> AsyncOpenAI:
        """Récupère ou crée le client OpenAI."""
        if self._openai_client is None:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY non configurée")
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client
    
    async def detect_project_language(
        self,
        working_directory: str,
        repository_url: Optional[str] = None
    ) -> ProjectLanguageInfo:
        """
        Détecte la langue naturelle du projet.
        
        Args:
            working_directory: Répertoire du projet
            repository_url: URL du repository (optionnel)
            
        Returns:
            ProjectLanguageInfo avec la langue détectée
        """
        logger.info(f"🌍 Détection de la langue naturelle du projet: {working_directory}")
        
        detection_sources = []
        sample_texts = []
        
        readme_text = await self._extract_readme_text(working_directory)
        if readme_text:
            detection_sources.append("README")
            sample_texts.append(readme_text[:500])
        
        code_comments = await self._extract_code_comments(working_directory)
        if code_comments:
            detection_sources.append("code_comments")
            sample_texts.extend(code_comments[:3])
        
        commit_messages = await self._extract_commit_messages(working_directory)
        if commit_messages:
            detection_sources.append("git_commits")
            sample_texts.extend(commit_messages[:3])
        
        if not sample_texts:
            logger.warning("⚠️ Aucune source de texte trouvée, langue par défaut: anglais")
            return ProjectLanguageInfo(
                language_code='en',
                language_name='English',
                confidence=0.3,
                detection_sources=['default'],
                sample_texts=[]
            )
        
        detected_lang = await self._detect_language_with_llm(sample_texts)
        
        lang_name = self.LANGUAGE_NAMES.get(detected_lang, 'English')
        confidence = 0.9 if len(detection_sources) >= 2 else 0.7
        
        logger.info(f"✅ Langue du projet détectée: {lang_name} ({detected_lang}) - confiance: {confidence:.2f}")
        logger.info(f"   Sources: {', '.join(detection_sources)}")
        
        return ProjectLanguageInfo(
            language_code=detected_lang,
            language_name=lang_name,
            confidence=confidence,
            detection_sources=detection_sources,
            sample_texts=sample_texts[:5]
        )
    
    async def _extract_readme_text(self, working_directory: str) -> Optional[str]:
        """Extrait le texte du README."""
        readme_files = ['README.md', 'README.txt', 'README', 'readme.md', 'Readme.md']
        
        for readme_file in readme_files:
            readme_path = Path(working_directory) / readme_file
            if readme_path.exists():
                try:
                    text = readme_path.read_text(encoding='utf-8', errors='ignore')
                    text = re.sub(r'```[\s\S]*?```', '', text)  # Enlever code blocks
                    text = re.sub(r'`[^`]+`', '', text)  # Enlever inline code
                    text = re.sub(r'http[s]?://\S+', '', text)  # Enlever URLs
                    text = re.sub(r'\n+', '\n', text).strip()
                    
                    if len(text) > 100:
                        logger.debug(f"✅ README trouvé: {readme_file}")
                        return text[:2000]
                except Exception as e:
                    logger.debug(f"⚠️ Erreur lecture {readme_file}: {e}")
        
        return None
    
    async def _extract_code_comments(self, working_directory: str, max_files: int = 10) -> List[str]:
        """Extrait les commentaires des fichiers de code."""
        comments = []
        
        code_extensions = ['.py', '.js', '.ts', '.java', '.go', '.rs', '.php', '.rb', '.cs']
        
        try:
            code_files = []
            for ext in code_extensions:
                code_files.extend(list(Path(working_directory).rglob(f'*{ext}'))[:max_files])
            
            for code_file in code_files[:max_files]:
                try:
                    content = code_file.read_text(encoding='utf-8', errors='ignore')
                    
                    multiline_comments = re.findall(r'/\*[\s\S]*?\*/|"""[\s\S]*?"""', content)
                    single_comments = re.findall(r'(?://|#)\s*(.+)$', content, re.MULTILINE)
                    
                    for comment in multiline_comments + single_comments:
                        clean_comment = comment.strip().replace('/*', '').replace('*/', '').replace('"""', '').strip()
                        if len(clean_comment) > 20:
                            comments.append(clean_comment[:200])
                            
                        if len(comments) >= 10:
                            break
                    
                    if len(comments) >= 10:
                        break
                        
                except Exception as e:
                    logger.debug(f"⚠️ Erreur lecture {code_file}: {e}")
                    continue
        
        except Exception as e:
            logger.debug(f"⚠️ Erreur extraction commentaires: {e}")
        
        return comments
    
    async def _extract_commit_messages(self, working_directory: str, max_commits: int = 10) -> List[str]:
        """Extrait les messages de commit récents."""
        commit_messages = []
        
        try:
            import subprocess
            
            result = subprocess.run(
                ['git', 'log', f'-{max_commits}', '--pretty=format:%s'],
                cwd=working_directory,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                messages = result.stdout.strip().split('\n')
                for msg in messages:
                    if len(msg) > 10:
                        commit_messages.append(msg[:200])
                
                logger.debug(f"✅ {len(commit_messages)} messages de commit extraits")
        
        except Exception as e:
            logger.debug(f"⚠️ Erreur extraction commits: {e}")
        
        return commit_messages
    
    async def _detect_language_with_llm(self, sample_texts: List[str]) -> str:
        """Détecte la langue des textes avec le LLM."""
        try:
            client = self._get_openai_client()
            
            combined_text = '\n\n---\n\n'.join(sample_texts[:5])[:1500]
            
            system_prompt = """Tu es un expert en détection de langues naturelles.
Analyse les textes fournis (documentation, commentaires, commits) et retourne UNIQUEMENT le code ISO 639-1 (2 lettres) de la langue principale utilisée.

Codes possibles: fr, en, es, de, it, pt, zh, ja, ru, ar, nl, pl, tr, ko, hi, sv, no, da, fi

Réponds UNIQUEMENT avec les 2 lettres du code langue."""

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Textes du projet:\n\n{combined_text}"}
                ],
                temperature=0.0,
                max_tokens=5
            )
            
            detected_lang = response.choices[0].message.content.strip().lower()
            
            if len(detected_lang) == 2 and detected_lang.isalpha():
                return detected_lang
            else:
                logger.warning(f"⚠️ Réponse LLM invalide: '{detected_lang}' - fallback sur 'en'")
                return 'en'
        
        except Exception as e:
            logger.warning(f"⚠️ Erreur détection langue par LLM: {e} - fallback sur 'en'")
            return 'en'
    
    async def get_monday_reply_template(self, user_language: str, project_language: str) -> Dict[str, str]:
        """
        Génère les templates pour répondre à l'utilisateur dans Monday.com.
        Génère DYNAMIQUEMENT via LLM pour N'IMPORTE QUELLE langue (sauf anglais en cache).
        GARANTIT de toujours retourner un dictionnaire valide (jamais None).
        
        Args:
            user_language: Langue du message de l'utilisateur
            project_language: Langue du projet
            
        Returns:
            Dictionnaire avec les templates de réponses (JAMAIS None)
        """
        # Template anglais uniquement comme référence (cache rapide)
        english_template = {
            'workflow_started': '🚀 Workflow started! Processing your request...',
            'pr_created': '✅ Pull Request created successfully!',
            'pr_merged': 'PR merged',
            'error': '❌ An error occurred',
            'validation_request': '🤝 Human validation required',
            'response_header': '🤖 **VyData Response**',
            'question_label': 'Question',
            'task_label': 'Task',
            'task_completed': 'Task Completed Successfully',
            'task_partial': 'Task Partially Completed',
            'task_failed': 'Task Failed',
            'automatic_response_note': 'This is an automatic response. For actions requiring code modifications, use a command.',
            'workflow_progress': 'Workflow progress',
            'environment_configured': 'Environment configured',
            'modified_files': 'Modified files',
            'no_modified_files': 'No modified files detected',
            'implementation_success': 'Implementation completed successfully',
            'implementation_failed': 'Implementation failed',
            'tests_passed': 'Tests executed successfully',
            'tests_errors': 'Tests executed with errors',
            'no_tests': 'No tests executed',
            'pr_not_created': 'Pull Request not created',
            'validation_instructions': """**Reply to this update with**:
• **'yes'** or **'validate'** → Automatic merge ✅
• **'no [instructions]'** → Relaunch with modifications (max 3) 🔄
• **'abandon'** or **'stop'** → End workflow ⛔

**Rejection example with instructions**:
"No, adjust file X and find another alternative with tests"

⏰ *Timeout: 60 minutes*"""
        }
        
        if user_language == 'en':
            return english_template
        
        # Pour toutes les autres langues, générer dynamiquement via LLM
        try:
            logger.info(f"🤖 Génération dynamique du template Monday.com pour: {user_language}")
            result = await self._generate_monday_template_with_llm(user_language)
            
            # GARANTIE: Si result est None ou vide, retourner l'anglais
            if not result or not isinstance(result, dict):
                logger.error(f"⚠️ Template invalide retourné pour {user_language}, fallback anglais")
                return english_template
            
            return result
        except Exception as e:
            logger.error(f"❌ Exception critique get_monday_reply_template pour {user_language}: {e}")
            logger.warning("⚠️ Fallback anglais d'urgence")
            return english_template
    
    async def get_pr_template(self, language_code: str) -> Dict[str, str]:
        """
        Récupère le template de PR pour une langue donnée.
        Génère DYNAMIQUEMENT via LLM pour N'IMPORTE QUELLE langue (sauf anglais en cache).
        
        Args:
            language_code: Code ISO 639-1 (fr, en, es, etc.)
            
        Returns:
            Dictionnaire avec les templates de sections PR
        """
        # Template anglais uniquement comme référence (cache rapide)
        if language_code == 'en':
            return {
                'title_prefix': 'feat',
                'auto_pr_header': '## 🤖 Automatically generated Pull Request',
                'task_section': '### 📋 Task',
                'description_section': '### 📝 Description',
                'changes_section': '### 🔧 Changes made',
                'modified_files': 'Modified files',
                'tests_section': '### ✅ Tests',
                'validation_section': '### ✅ Validation',
                'validated_text': 'Code validated and approved by the team',
                'footer': 'PR automatically created by AI-Agent'
            }
        
        # Pour toutes les autres langues, générer dynamiquement via LLM
        logger.info(f"🤖 Génération dynamique du template PR pour: {language_code}")
        return await self._generate_pr_template_with_llm(language_code)
    
    
    async def _generate_pr_template_with_llm(self, language_code: str) -> Dict[str, str]:
        """
        Génère un template de PR dans n'importe quelle langue via LLM.
        
        Args:
            language_code: Code ISO 639-1 de la langue cible
            
        Returns:
            Dictionnaire avec les templates de sections PR
        """
        import json
        
        try:
            client = self._get_openai_client()
            
            example_dict = {
                "title_prefix": "feat",
                "auto_pr_header": "## 🤖 Pull Request générée automatiquement",
                "task_section": "### 📋 Tâche",
                "description_section": "### 📝 Description",
                "changes_section": "### 🔧 Changements apportés",
                "modified_files": "Fichiers modifiés",
                "tests_section": "### ✅ Tests",
                "validation_section": "### ✅ Validation",
                "validated_text": "Code validé et approuvé par l'équipe",
                "footer": "PR créée automatiquement par AI-Agent"
            }
            
            example_template = json.dumps(example_dict, indent=2, ensure_ascii=False)
            
            language_name = self.LANGUAGE_NAMES.get(language_code, language_code.upper())
            
            system_prompt = f"""Tu es un expert en traduction technique pour GitHub Pull Requests.
Génère un template de PR en {language_name}.

RÈGLES CRITIQUES:
1. Réponds UNIQUEMENT avec un objet JSON valide
2. PAS de texte avant ou après le JSON
3. PAS de markdown (```json)
4. Traduis UNIQUEMENT les valeurs, PAS les clés
5. Garde TOUS les emojis (🤖, 📋, 📝, 🔧, ✅)
6. NE TRADUIS PAS "feat" dans title_prefix
7. Style: Professionnel et concis"""

            user_prompt = f"""Traduis ce template en {language_name} ({language_code}).
IMPORTANT: Réponds UNIQUEMENT avec le JSON, rien d'autre.

Template de référence:
{example_template}"""

            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.2,
                        max_tokens=800,
                        response_format={"type": "json_object"}
                    )
                    
                    template_json = response.choices[0].message.content.strip()
                    
                    if template_json.startswith('```'):
                        template_json = template_json.replace('```json', '').replace('```', '').strip()
                    
                    template = json.loads(template_json)
                    
                    required_fields = ['title_prefix', 'auto_pr_header', 'task_section']
                    missing_fields = [f for f in required_fields if f not in template]
                    
                    if missing_fields:
                        logger.warning(f"⚠️ Champs manquants dans le template PR LLM: {missing_fields}")
                        if attempt < max_retries - 1:
                            logger.info(f"🔄 Retry {attempt + 2}/{max_retries}...")
                            continue
                    
                    logger.info(f"✅ Template PR généré pour {language_name} ({language_code})")
                    return template
                    
                except json.JSONDecodeError as je:
                    logger.error(f"❌ Erreur parsing JSON PR (tentative {attempt + 1}/{max_retries}): {je}")
                    if attempt < max_retries - 1:
                        logger.info(f"🔄 Retry {attempt + 2}/{max_retries}...")
                        continue
                    raise
            
            raise Exception(f"Échec génération template PR après {max_retries} tentatives")
            
        except Exception as e:
            logger.error(f"❌ Erreur génération template PR via LLM: {e}")
            logger.warning(f"⚠️ Fallback vers anglais pour langue {language_code}")
            return {
                "title_prefix": "feat",
                "auto_pr_header": "## 🤖 Automatically generated Pull Request",
                "task_section": "### 📋 Task",
                "description_section": "### 📝 Description",
                "changes_section": "### 🔧 Changes made",
                "modified_files": "Modified files",
                "tests_section": "### ✅ Tests",
                "validation_section": "### ✅ Validation",
                "validated_text": "Code validated and approved by the team",
                "footer": "PR automatically created by AI-Agent"
            }
    
    async def _generate_monday_template_with_llm(self, language_code: str) -> Dict[str, str]:
        """
        Génère un template de messages Monday.com dans n'importe quelle langue via LLM.
        
        Args:
            language_code: Code ISO 639-1 de la langue cible
            
        Returns:
            Dictionnaire avec les templates de messages
        """
        import json
        
        try:
            client = self._get_openai_client()
            
            example_dict = {
                "workflow_started": "🚀 Workflow démarré ! Je traite votre demande...",
                "pr_created": "✅ Pull Request créée avec succès !",
                "pr_merged": "PR fusionnée",
                "error": "❌ Une erreur est survenue",
                "validation_request": "🤝 Validation humaine requise",
                "response_header": "🤖 **Réponse VyData**",
                "question_label": "Question",
                "task_label": "Tâche",
                "task_completed": "Tâche Complétée avec Succès",
                "task_partial": "Tâche Partiellement Complétée",
                "task_failed": "Tâche Échouée",
                "automatic_response_note": "Ceci est une réponse automatique. Pour une action nécessitant des modifications de code, utilisez une commande.",
                "workflow_progress": "Progression du workflow",
                "environment_configured": "Environnement configuré",
                "modified_files": "Fichiers modifiés",
                "no_modified_files": "Aucun fichier modifié détecté",
                "implementation_success": "Implémentation terminée avec succès",
                "implementation_failed": "Implémentation échouée",
                "tests_passed": "Tests exécutés avec succès",
                "tests_errors": "Tests exécutés avec des erreurs",
                "no_tests": "Aucun test exécuté",
                "pr_not_created": "Pull Request non créée",
                "validation_instructions": """**Répondez à cette update avec**:
• **'oui'** ou **'valide'** → Merge automatique ✅
• **'non [instructions]'** → Relance avec modifications (max 3) 🔄
• **'abandonne'** ou **'stop'** → Fin du workflow ⛔

**Exemple de rejet avec instructions**:
"Non, ajuste le fichier X et trouve une autre alternative avec des tests"

⏰ *Timeout: 60 minutes*"""
            }
            
            example_template = json.dumps(example_dict, indent=2, ensure_ascii=False)
            
            language_name = self.LANGUAGE_NAMES.get(language_code, language_code.upper())
            
            system_prompt = f"""Tu es un expert en traduction technique pour applications de gestion de projet.
Génère des templates de messages Monday.com en {language_name}.

RÈGLES CRITIQUES:
1. Réponds UNIQUEMENT avec un objet JSON valide
2. PAS de texte avant ou après le JSON
3. PAS de markdown (```json)
4. Traduis UNIQUEMENT les valeurs, PAS les clés
5. Garde TOUS les emojis (🚀, ✅, ❌, 🤝, ⚠️, 🔄, ⛔)
6. Garde la structure exacte avec retours à la ligne (\\n)
7. Style: Professionnel mais amical"""

            user_prompt = f"""Traduis ce template en {language_name} ({language_code}).
IMPORTANT: Réponds UNIQUEMENT avec le JSON, rien d'autre.

Template de référence:
{example_template}"""

            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.2,
                        max_tokens=1500,
                        response_format={"type": "json_object"}
                    )
                    
                    template_json = response.choices[0].message.content.strip()
                    
                    if template_json.startswith('```'):
                        template_json = template_json.replace('```json', '').replace('```', '').strip()
                    
                    template = json.loads(template_json)
                    
                    required_fields = ['validation_request', 'validation_instructions', 'workflow_progress']
                    missing_fields = [f for f in required_fields if f not in template]
                    
                    if missing_fields:
                        logger.warning(f"⚠️ Champs manquants dans le template LLM: {missing_fields}")
                        if attempt < max_retries - 1:
                            logger.info(f"🔄 Retry {attempt + 2}/{max_retries}...")
                            continue
                    
                    logger.info(f"✅ Template Monday.com généré pour {language_name} ({language_code})")
                    return template
                    
                except json.JSONDecodeError as je:
                    logger.error(f"❌ Erreur parsing JSON (tentative {attempt + 1}/{max_retries}): {je}")
                    if attempt < max_retries - 1:
                        logger.info(f"🔄 Retry {attempt + 2}/{max_retries}...")
                        continue
                    raise
            
            raise Exception(f"Échec génération template après {max_retries} tentatives")
            
        except Exception as e:
            logger.error(f"❌ Erreur génération template Monday via LLM: {e}")
            logger.warning(f"⚠️ Fallback vers anglais pour langue {language_code}")
            return {
                'validation_request': 'Human validation required',
                'validation_instructions': """**Reply to this update with**:
• **'yes'** or **'validate'** → Automatic merge ✅
• **'no [instructions]'** → Relaunch with modifications (max 3) 🔄
• **'abandon'** or **'stop'** → End workflow ⛔

**Rejection example with instructions**:
"No, adjust file X and find another alternative with tests"

⏰ *Timeout: 60 minutes*""",
                'workflow_progress': 'Workflow progress',
                'environment_configured': 'Environment configured',
                'modified_files': 'Modified files',
                'no_modified_files': 'No modified files detected',
                'implementation_success': 'Implementation completed successfully',
                'implementation_failed': 'Implementation failed',
                'tests_passed': 'Tests executed successfully',
                'tests_errors': 'Tests executed with errors',
                'no_tests': 'No tests executed',
                'pr_not_created': 'Pull Request not created',
                'pr_merged': 'PR merged',
                'question_label': 'Question',
                'task_label': 'Task',
                'task_completed': 'Task Completed Successfully',
                'task_partial': 'Task Partially Completed',
                'task_failed': 'Task Failed',
                'workflow_started': '🚀 Workflow started! Processing your request...',
                'pr_created': '✅ Pull Request created successfully!',
                'error': '❌ An error occurred',
                'response_header': '🤖 **VyData Response**',
                'automatic_response_note': 'This is an automatic response. For actions requiring code modifications, use a command.'
            }


project_language_detector = ProjectLanguageDetectorService()

