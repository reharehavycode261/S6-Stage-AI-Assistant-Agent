"""
Explorateur approfondi de repository pour comprendre le code avant génération.

✅ AMÉLIORATION MAJEURE: Phase d'exploration obligatoire avant toute génération de code.
"""

import os
import re
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from utils.logger import get_logger

logger = get_logger(__name__)


class RepositoryExplorer:
    """
    Explore un repository en profondeur pour construire un contexte riche.
    
    Cette classe est CRITIQUE pour la qualité du code généré:
    - Lit le code existant
    - Identifie les patterns et conventions
    - Comprend l'architecture
    - Construit un contexte pour l'IA
    """
    
    def __init__(self, working_directory: str):
        self.working_directory = Path(working_directory)
        self.logger = logger
    
    async def explore_for_task(
        self,
        task_description: str,
        files_mentioned: Optional[List[str]] = None,
        max_files_to_read: int = 15
    ) -> Dict[str, Any]:
        """
        Explore le repository de manière ciblée pour une tâche spécifique.
        
        ✅ STRATÉGIE D'EXPLORATION:
        1. Identifier les fichiers pertinents à la tâche
        2. Lire leur contenu complet
        3. Analyser les patterns et conventions
        4. Construire un contexte riche
        
        Args:
            task_description: Description de la tâche
            files_mentioned: Fichiers mentionnés dans la tâche
            max_files_to_read: Nombre max de fichiers à lire (15 par défaut)
            
        Returns:
            Dict avec le contexte complet du repository
        """
        self.logger.info(f"🔍 Exploration approfondie du repository pour: {task_description[:100]}...")
        
        context = {
            "files_read": [],
            "code_samples": {},
            "patterns_detected": [],
            "conventions": {},
            "architecture_insights": [],
            "dependencies": [],
            "related_files": []
        }
        
        relevant_files = await self._identify_relevant_files(
            task_description,
            files_mentioned,
            max_files_to_read
        )
        
        self.logger.info(f"📋 {len(relevant_files)} fichiers identifiés comme pertinents")
        
        for file_path in relevant_files:
            try:
                content = await self._read_file_safely(file_path)
                if content:
                    context["files_read"].append(str(file_path))
                    context["code_samples"][str(file_path)] = content
                    self.logger.info(f"✅ Lu: {file_path} ({len(content)} caractères)")
            except Exception as e:
                self.logger.warning(f"⚠️ Impossible de lire {file_path}: {e}")
        
        if context["code_samples"]:
            patterns = self._analyze_code_patterns(context["code_samples"])
            context["patterns_detected"] = patterns["patterns"]
            context["conventions"] = patterns["conventions"]
            
            self.logger.info(f"🎯 {len(patterns['patterns'])} patterns détectés")
        
        architecture = self._identify_architecture(context["code_samples"])
        context["architecture_insights"] = architecture
        
        dependencies = self._extract_dependencies(context["code_samples"])
        context["dependencies"] = dependencies
        
        related = await self._find_related_files(relevant_files)
        context["related_files"] = related
        
        self.logger.info(f"✅ Exploration terminée: {len(context['files_read'])} fichiers analysés")
        
        return context
    
    async def _identify_relevant_files(
        self,
        task_description: str,
        files_mentioned: Optional[List[str]],
        max_files: int
    ) -> List[Path]:
        """
        Identifie les fichiers pertinents pour la tâche.
        
        ✅ STRATÉGIE:
        1. Fichiers mentionnés explicitement
        2. Fichiers dans les mêmes répertoires
        3. Fichiers avec noms similaires
        4. Fichiers de configuration/build
        """
        relevant = set()
        
        if files_mentioned:
            for file_path in files_mentioned:
                full_path = self.working_directory / file_path
                if full_path.exists():
                    relevant.add(full_path)
                    self.logger.info(f"📌 Fichier mentionné ajouté: {file_path}")
        
        keywords = self._extract_keywords_from_task(task_description)
        self.logger.info(f"🔑 Mots-clés extraits: {', '.join(keywords[:5])}")
        
        all_files = []
        for ext in ['.py', '.js', '.ts', '.java', '.go', '.rb', '.php', '.jsx', '.tsx']:
            try:
                all_files.extend(self.working_directory.rglob(f"*{ext}"))
            except Exception as e:
                self.logger.warning(f"Erreur scan {ext}: {e}")
        
        for file_path in all_files[:200]:  # Limiter la recherche
            if self._is_relevant_file(file_path, keywords):
                relevant.add(file_path)
                if len(relevant) >= max_files:
                    break
        
        if len(relevant) == 0 and all_files:
            self.logger.info("📝 Aucun fichier trouvé par mots-clés, ajout des fichiers source principaux")
            for file_path in all_files[:max_files]:
                if not self._is_test_or_excluded(file_path):
                    relevant.add(file_path)
                    if len(relevant) >= max_files:
                        break
        
        config_files = [
            'package.json', 'requirements.txt', 'pom.xml', 'build.gradle',
            'Cargo.toml', 'go.mod', 'composer.json', 'Gemfile'
        ]
        
        for config_file in config_files:
            config_path = self.working_directory / config_file
            if config_path.exists():
                relevant.add(config_path)
        
        return list(relevant)[:max_files]
    
    def _extract_keywords_from_task(self, task_description: str) -> List[str]:
        """Extrait les mots-clés importants de la description de tâche."""
        # Nettoyer et tokenizer
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', task_description.lower())
        
        # Filtrer les mots communs
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her',
            'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how',
            'add', 'create', 'update', 'delete', 'implement', 'modify', 'change'
        }
        
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        
        return list(dict.fromkeys(keywords))[:20]
    
    def _is_test_or_excluded(self, file_path: Path) -> bool:
        """Vérifie si un fichier est un test ou doit être exclu."""
        path_str = str(file_path).lower()
        
        exclusions = [
            'node_modules', 'venv', '__pycache__', '.git', 'dist', 'build',
            'test_', '_test', '.spec.', '.test.', 'tests/'
        ]
        
        return any(exclude in path_str for exclude in exclusions)
    
    def _is_relevant_file(self, file_path: Path, keywords: List[str]) -> bool:
        """Détermine si un fichier est pertinent pour la tâche."""
        if self._is_test_or_excluded(file_path):
            return False
        
        path_str = str(file_path).lower()
        file_name = file_path.stem.lower()
        
        for keyword in keywords:
            if keyword in file_name or keyword in path_str:
                return True
        
        return False
    
    async def _read_file_safely(self, file_path: Path, max_size: int = 50000) -> Optional[str]:
        """
        Lit un fichier de manière sécurisée avec limite de taille.
        
        Args:
            file_path: Chemin du fichier
            max_size: Taille maximale en caractères (50KB par défaut)
            
        Returns:
            Contenu du fichier ou None si erreur
        """
        try:
            if not file_path.exists():
                return None
            
            size = file_path.stat().st_size
            if size > max_size:
                self.logger.warning(f"⚠️ Fichier {file_path} trop grand ({size} bytes), lecture partielle")
                # Lire seulement le début
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read(max_size)
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        
        except Exception as e:
            self.logger.warning(f"Erreur lecture {file_path}: {e}")
            return None
    
    def _analyze_code_patterns(self, code_samples: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyse les patterns et conventions dans le code existant.
        
        ✅ DÉTECTION:
        - Conventions de nommage
        - Patterns architecturaux
        - Style de code
        - Imports courants
        """
        patterns = []
        conventions = {}
        
        # Analyser chaque fichier
        all_code = "\n".join(code_samples.values())
        
        # 1. Convention de nommage
        if re.search(r'function\s+[a-z][a-zA-Z0-9]*', all_code):
            conventions["naming"] = "camelCase"
            patterns.append("Convention camelCase pour les fonctions")
        elif re.search(r'def\s+[a-z][a-z0-9_]*', all_code):
            conventions["naming"] = "snake_case"
            patterns.append("Convention snake_case pour les fonctions")
        
        # 2. Style de classes
        if 'class ' in all_code:
            if re.search(r'class\s+[A-Z][a-zA-Z0-9]*', all_code):
                patterns.append("Classes en PascalCase")
        
        # 3. Patterns d'imports
        imports = re.findall(r'^import\s+(\w+)', all_code, re.MULTILINE)
        imports.extend(re.findall(r'^from\s+(\w+)', all_code, re.MULTILINE))
        
        if imports:
            conventions["common_imports"] = list(set(imports))[:10]
            patterns.append(f"Imports courants: {', '.join(list(set(imports))[:5])}")
        
        # 4. Patterns d'architecture
        if 'async def' in all_code or 'await ' in all_code:
            patterns.append("Architecture asynchrone détectée")
            conventions["async"] = True
        
        if 'interface ' in all_code or 'implements ' in all_code:
            patterns.append("Utilisation d'interfaces")
        
        if '@' in all_code and ('decorator' in all_code or 'annotation' in all_code):
            patterns.append("Utilisation de décorateurs/annotations")
        
        return {
            "patterns": patterns,
            "conventions": conventions
        }
    
    def _identify_architecture(self, code_samples: Dict[str, str]) -> List[str]:
        """Identifie l'architecture du projet."""
        insights = []
        
        all_code = "\n".join(code_samples.values())
        file_paths = list(code_samples.keys())
        
        # Détecter MVC
        if any('controller' in path.lower() for path in file_paths):
            insights.append("Architecture MVC détectée (contrôleurs présents)")
        
        if any('model' in path.lower() for path in file_paths):
            insights.append("Couche Model présente")
        
        if any('view' in path.lower() or 'template' in path.lower() for path in file_paths):
            insights.append("Couche View présente")
        
        # Détecter patterns
        if 'Repository' in all_code or 'repository' in all_code.lower():
            insights.append("Pattern Repository détecté")
        
        if 'Service' in all_code and 'service' in all_code.lower():
            insights.append("Architecture en couches (Services)")
        
        return insights
    
    def _extract_dependencies(self, code_samples: Dict[str, str]) -> List[str]:
        """Extrait les dépendances du code."""
        dependencies = set()
        
        for content in code_samples.values():
            # Python imports
            imports = re.findall(r'^(?:from|import)\s+([\w.]+)', content, re.MULTILINE)
            dependencies.update(imports)
        
        return list(dependencies)[:20]
    
    async def _find_related_files(self, files: List[Path]) -> List[str]:
        """Trouve les fichiers liés (même répertoire, imports, etc.)."""
        related = set()
        
        for file_path in files:
            # Fichiers dans le même répertoire
            try:
                siblings = list(file_path.parent.glob(f"*{file_path.suffix}"))
                related.update(str(s) for s in siblings[:5])
            except Exception:
                pass
        
        return list(related)[:10]
    
    def build_context_summary(self, exploration_result: Dict[str, Any]) -> str:
        """
        Construit un résumé textuel du contexte pour l'IA.
        
        ✅ FORMAT OPTIMISÉ pour la génération de code de qualité.
        """
        summary = "## 📚 CONTEXTE DU REPOSITORY (CODE RÉEL ANALYSÉ)\n\n"
        
        # 1. Fichiers analysés
        files_count = len(exploration_result.get("files_read", []))
        summary += f"### Fichiers analysés: {files_count}\n\n"
        
        if exploration_result.get("files_read"):
            summary += "**Fichiers pertinents lus:**\n"
            for f in exploration_result["files_read"][:10]:
                summary += f"- `{f}`\n"
            summary += "\n"
        
        # 2. Patterns détectés
        if exploration_result.get("patterns_detected"):
            summary += "### ✅ Patterns et conventions détectés:\n\n"
            for pattern in exploration_result["patterns_detected"]:
                summary += f"- {pattern}\n"
            summary += "\n"
        
        # 3. Conventions de code
        if exploration_result.get("conventions"):
            summary += "### 📏 Conventions de code à respecter:\n\n"
            conv = exploration_result["conventions"]
            
            if "naming" in conv:
                summary += f"- **Nommage**: {conv['naming']}\n"
            
            if "common_imports" in conv:
                summary += f"- **Imports courants**: {', '.join(conv['common_imports'][:5])}\n"
            
            if "async" in conv:
                summary += "- **Asynchrone**: Utiliser async/await\n"
            
            summary += "\n"
        
        # 4. Architecture
        if exploration_result.get("architecture_insights"):
            summary += "### 🏗️ Architecture du projet:\n\n"
            for insight in exploration_result["architecture_insights"]:
                summary += f"- {insight}\n"
            summary += "\n"
        
        # 5. Exemples de code
        if exploration_result.get("code_samples"):
            summary += "### 💻 EXEMPLES DE CODE EXISTANT (à respecter):\n\n"
            
            for file_path, content in list(exploration_result["code_samples"].items())[:3]:
                summary += f"**Fichier: `{file_path}`** (extrait):\n```\n"
                # Prendre les 500 premiers caractères
                extract = content[:500].strip()
                summary += extract
                if len(content) > 500:
                    summary += "\n... (tronqué)"
                summary += "\n```\n\n"
        
        summary += "⚠️ **IMPORTANT**: Le code que tu génères DOIT respecter ces patterns et conventions!\n"
        
        return summary

