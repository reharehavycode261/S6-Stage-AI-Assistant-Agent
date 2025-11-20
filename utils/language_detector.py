"""
Module de détection automatique et générique du langage de programmation.

Ce module détecte automatiquement le langage d'un projet en analysant:
- Les extensions de fichiers
- Les fichiers de configuration/build
- Les métadonnées du projet
"""

import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from collections import Counter

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LanguageInfo:
    """Informations sur un langage de programmation détecté."""
    name: str                           # Ex: "Java", "Python", "JavaScript"
    type_id: str                        # Ex: "java", "python", "javascript"
    confidence: float                   # Score de confiance (0.0-1.0)
    file_count: int                     # Nombre de fichiers détectés
    primary_extensions: List[str]       # Extensions principales trouvées
    build_files: List[str]              # Fichiers de build trouvés
    typical_structure: str              # Structure typique du projet
    conventions: Dict[str, str]         # Conventions de nommage


class LanguagePattern:
    """Patterns de détection pour un langage."""
    
    def __init__(
        self,
        name: str,
        type_id: str,
        extensions: List[str],
        build_files: List[str],
        config_files: List[str],
        typical_dirs: List[str],
        weight_multiplier: float = 1.0
    ):
        self.name = name
        self.type_id = type_id
        self.extensions = extensions
        self.build_files = build_files
        self.config_files = config_files
        self.typical_dirs = typical_dirs
        self.weight_multiplier = weight_multiplier


# ✅ BASE DE CONNAISSANCES: Patterns pour les langages connus
KNOWN_LANGUAGE_PATTERNS = [
    LanguagePattern(
        name="Java",
        type_id="java",
        extensions=[".java"],
        build_files=["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"],
        config_files=["application.properties", "application.yml", "application.yaml"],
        typical_dirs=["src/main/java", "src/test/java"],
        weight_multiplier=1.5
    ),
    LanguagePattern(
        name="Python",
        type_id="python",
        extensions=[".py"],
        build_files=["setup.py", "pyproject.toml", "Pipfile"],
        config_files=["requirements.txt", "poetry.lock", "Pipfile.lock"],
        typical_dirs=["tests", "src"],
        weight_multiplier=1.5
    ),
    LanguagePattern(
        name="JavaScript",
        type_id="javascript",
        extensions=[".js", ".jsx", ".mjs", ".cjs"],
        build_files=["package.json"],
        config_files=["webpack.config.js", ".babelrc", ".eslintrc"],
        typical_dirs=["src", "lib", "dist"],
        weight_multiplier=1.3
    ),
    LanguagePattern(
        name="TypeScript",
        type_id="typescript",
        extensions=[".ts", ".tsx"],
        build_files=["tsconfig.json", "package.json"],
        config_files=["tsconfig.build.json", "tslint.json"],
        typical_dirs=["src", "dist"],
        weight_multiplier=1.4
    ),
    LanguagePattern(
        name="Go",
        type_id="go",
        extensions=[".go"],
        build_files=["go.mod"],
        config_files=["go.sum"],
        typical_dirs=["cmd", "pkg", "internal"],
        weight_multiplier=1.5
    ),
    LanguagePattern(
        name="Rust",
        type_id="rust",
        extensions=[".rs"],
        build_files=["Cargo.toml"],
        config_files=["Cargo.lock"],
        typical_dirs=["src", "tests"],
        weight_multiplier=1.5
    ),
    LanguagePattern(
        name="C++",
        type_id="cpp",
        extensions=[".cpp", ".cc", ".cxx", ".hpp", ".h"],
        build_files=["CMakeLists.txt", "Makefile"],
        config_files=["configure.ac", "meson.build"],
        typical_dirs=["src", "include"],
        weight_multiplier=1.2
    ),
    LanguagePattern(
        name="C",
        type_id="c",
        extensions=[".c", ".h"],
        build_files=["Makefile", "CMakeLists.txt"],
        config_files=["configure.ac"],
        typical_dirs=["src", "include"],
        weight_multiplier=1.2
    ),
    LanguagePattern(
        name="C#",
        type_id="csharp",
        extensions=[".cs"],
        build_files=[".csproj", ".sln"],
        config_files=["appsettings.json", "web.config"],
        typical_dirs=["Controllers", "Models", "Views"],
        weight_multiplier=1.4
    ),
    LanguagePattern(
        name="Ruby",
        type_id="ruby",
        extensions=[".rb"],
        build_files=["Gemfile"],
        config_files=["Gemfile.lock", "Rakefile"],
        typical_dirs=["lib", "spec"],
        weight_multiplier=1.3
    ),
    LanguagePattern(
        name="PHP",
        type_id="php",
        extensions=[".php"],
        build_files=["composer.json"],
        config_files=["composer.lock", "php.ini"],
        typical_dirs=["src", "vendor"],
        weight_multiplier=1.3
    ),
    LanguagePattern(
        name="Kotlin",
        type_id="kotlin",
        extensions=[".kt", ".kts"],
        build_files=["build.gradle.kts", "pom.xml"],
        config_files=["settings.gradle.kts"],
        typical_dirs=["src/main/kotlin", "src/test/kotlin"],
        weight_multiplier=1.4
    ),
    LanguagePattern(
        name="Swift",
        type_id="swift",
        extensions=[".swift"],
        build_files=["Package.swift"],
        config_files=["Podfile", "Cartfile"],
        typical_dirs=["Sources", "Tests"],
        weight_multiplier=1.4
    ),
]


class GenericLanguageDetector:
    """
    Détecteur générique de langage de programmation.
    
    Fonctionne en deux modes:
    1. Mode pattern-matching: Utilise la base de connaissances KNOWN_LANGUAGE_PATTERNS
    2. Mode discovery: Détecte automatiquement les langages inconnus par analyse
    """
    
    def __init__(self, patterns: Optional[List[LanguagePattern]] = None):
        """
        Initialise le détecteur.
        
        Args:
            patterns: Liste de patterns personnalisés (optionnel)
        """
        self.patterns = patterns or KNOWN_LANGUAGE_PATTERNS
        
    def detect_from_files(self, files: List[str]) -> LanguageInfo:
        """
        Détecte le langage principal à partir d'une liste de fichiers.
        
        Args:
            files: Liste des chemins de fichiers du projet
            
        Returns:
            LanguageInfo avec les informations du langage détecté
        """
        if not files:
            return self._create_unknown_language_info()
        
        # Étape 1: Essayer la détection par patterns connus
        known_result = self._detect_with_known_patterns(files)
        
        # Si confiance suffisante, retourner
        if known_result.confidence >= 0.7:
            logger.info(f"✅ Langage détecté (patterns connus): {known_result.name} "
                       f"(confiance: {known_result.confidence:.2f})")
            return known_result
        
        # Étape 2: Détection générique par discovery
        logger.info("🔍 Confiance insuffisante avec patterns connus, activation du mode discovery...")
        discovery_result = self._detect_with_discovery(files)
        
        # Combiner les résultats
        if discovery_result.confidence > known_result.confidence:
            logger.info(f"✅ Langage détecté (discovery): {discovery_result.name} "
                       f"(confiance: {discovery_result.confidence:.2f})")
            return discovery_result
        else:
            return known_result
    
    def _detect_with_known_patterns(self, files: List[str]) -> LanguageInfo:
        """Détection basée sur les patterns connus."""
        # ✅ AMÉLIORATION: Filtrer les fichiers vendor/assets avant analyse
        filtered_files = [f for f in files if not self._should_exclude_path(f)]
        logger.debug(f"🔍 Fichiers après filtrage: {len(filtered_files)}/{len(files)}")
        
        scores: Dict[str, float] = {}
        details: Dict[str, Dict] = {}
        
        for pattern in self.patterns:
            score = 0.0
            file_count = 0
            found_extensions = []
            found_build_files = []
            found_dirs = []
            
            # Compter les fichiers par extension
            for file in filtered_files:
                file_lower = file.lower()
                
                # Vérifier extensions
                for ext in pattern.extensions:
                    if file_lower.endswith(ext):
                        score += 1.0 * pattern.weight_multiplier
                        file_count += 1
                        if ext not in found_extensions:
                            found_extensions.append(ext)
                        break
                
                # Vérifier build files (poids fort)
                for build_file in pattern.build_files:
                    if build_file.lower() in file_lower:
                        score += 10.0 * pattern.weight_multiplier
                        found_build_files.append(build_file)
                
                # Vérifier config files (poids moyen)
                for config_file in pattern.config_files:
                    if config_file.lower() in file_lower:
                        score += 3.0 * pattern.weight_multiplier
                
                # Vérifier structure typique
                for typical_dir in pattern.typical_dirs:
                    if typical_dir.lower() in file_lower:
                        score += 2.0 * pattern.weight_multiplier
                        if typical_dir not in found_dirs:
                            found_dirs.append(typical_dir)
            
            scores[pattern.type_id] = score
            details[pattern.type_id] = {
                "pattern": pattern,
                "file_count": file_count,
                "extensions": found_extensions,
                "build_files": found_build_files,
                "dirs": found_dirs
            }
        
        # Trouver le meilleur score
        if not scores or max(scores.values()) == 0:
            return self._create_unknown_language_info()
        
        best_type_id = max(scores, key=scores.get)
        best_score = scores[best_type_id]
        best_details = details[best_type_id]
        pattern = best_details["pattern"]
        
        # Calculer la confiance
        total_score = sum(scores.values())
        confidence = best_score / total_score if total_score > 0 else 0.0
        
        # Ajuster confiance selon les indicateurs
        if best_details["build_files"]:
            confidence = min(1.0, confidence + 0.2)  # Boost si build files trouvés
        
        logger.debug(f"📊 Scores: {scores}")
        logger.debug(f"🏆 Meilleur: {pattern.name} avec score {best_score}")
        
        return LanguageInfo(
            name=pattern.name,
            type_id=pattern.type_id,
            confidence=confidence,
            file_count=best_details["file_count"],
            primary_extensions=best_details["extensions"],
            build_files=best_details["build_files"],
            typical_structure=self._infer_structure(best_details["dirs"]),
            conventions=self._get_conventions_for_language(pattern.type_id)
        )
    
    def _should_exclude_path(self, file_path: str) -> bool:
        """Vérifie si un chemin doit être exclu de l'analyse."""
        path_lower = file_path.lower()
        
        # ✅ AMÉLIORATION: Exclusions plus complètes pour vendor/assets/node_modules
        exclude_patterns = [
            '/node_modules/',
            '/vendor/',
            '/assets/vendor/',
            '/src/assets/vendor/',
            '/public/vendor/',
            '/dist/',
            '/build/',
            '/.git/',
            '/venv/',
            '/__pycache__/',
            '/target/',
            '/out/',
            '/bin/',
        ]
        
        return any(pattern in path_lower for pattern in exclude_patterns)
    
    def _detect_with_discovery(self, files: List[str]) -> LanguageInfo:
        """
        Détection générique par discovery (pour langages inconnus).
        
        Analyse les extensions et patterns pour détecter un langage
        même s'il n'est pas dans KNOWN_LANGUAGE_PATTERNS.
        """
        # ✅ AMÉLIORATION: Filtrer les fichiers vendor/assets avant analyse
        filtered_files = [f for f in files if not self._should_exclude_path(f)]
        logger.debug(f"🔍 Fichiers après filtrage: {len(filtered_files)}/{len(files)}")
        
        # Extraire toutes les extensions
        extensions = []
        for file in filtered_files:
            ext = Path(file).suffix.lower()
            if ext and len(ext) <= 5:  # Extensions valides
                extensions.append(ext)
        
        if not extensions:
            return self._create_unknown_language_info()
        
        # Compter les extensions
        ext_counter = Counter(extensions)
        most_common = ext_counter.most_common(3)
        
        if not most_common:
            return self._create_unknown_language_info()
        
        # Extension dominante
        dominant_ext, count = most_common[0]
        total_files = len(extensions)
        confidence = count / total_files if total_files > 0 else 0.0
        
        # Essayer de deviner le nom du langage
        language_name = self._guess_language_name(dominant_ext, files)
        type_id = language_name.lower().replace(" ", "_")
        
        logger.info(f"🔍 Discovery: Extension dominante {dominant_ext} "
                   f"({count}/{total_files} fichiers) → {language_name}")
        
        return LanguageInfo(
            name=language_name,
            type_id=type_id,
            confidence=min(0.8, confidence),  # Cap à 0.8 pour discovery
            file_count=count,
            primary_extensions=[ext for ext, _ in most_common],
            build_files=self._find_build_files(filtered_files),
            typical_structure=self._analyze_directory_structure(filtered_files),
            conventions=self._infer_conventions(dominant_ext, filtered_files)
        )
    
    def _guess_language_name(self, extension: str, files: List[str]) -> str:
        """Devine le nom du langage à partir de l'extension."""
        # Mapping extension → langage pour extensions communes
        common_mappings = {
            ".py": "Python",
            ".java": "Java",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".go": "Go",
            ".rs": "Rust",
            ".cpp": "C++",
            ".c": "C",
            ".cs": "C#",
            ".rb": "Ruby",
            ".php": "PHP",
            ".kt": "Kotlin",
            ".swift": "Swift",
            ".scala": "Scala",  # ✅ Déjà présent
            ".sc": "Scala",     # ✅ Extension alternative pour Scala
            ".sbt": "Scala",    # ✅ Fichiers build Scala
            ".dart": "Dart",
            ".lua": "Lua",
            ".pl": "Perl",
            ".r": "R",
            ".jl": "Julia",
            ".ex": "Elixir",
            ".exs": "Elixir",
            ".clj": "Clojure",
            ".hs": "Haskell",
            ".erl": "Erlang",
            ".ml": "OCaml",
            ".vim": "VimScript",
            ".sh": "Shell",
            ".bash": "Shell",
            ".ps1": "PowerShell",
            ".vb": "Visual Basic",
            ".groovy": "Groovy",
            ".f90": "Fortran",
            ".f95": "Fortran",
            ".m": "Objective-C",
            ".mm": "Objective-C++",
        }
        
        if extension in common_mappings:
            return common_mappings[extension]
        
        # Sinon, utiliser l'extension comme nom (ex: .xyz → XYZ)
        return extension[1:].upper() if extension else "Unknown"
    
    def _find_build_files(self, files: List[str]) -> List[str]:
        """Trouve les fichiers de build/configuration dans la liste."""
        build_patterns = [
            "makefile", "cmake", "gradle", "maven", "pom.xml",
            "package.json", "cargo.toml", "go.mod", "setup.py",
            "build.xml", "build.gradle", "project.clj"
        ]
        
        found = []
        for file in files:
            file_lower = file.lower()
            for pattern in build_patterns:
                if pattern in file_lower:
                    found.append(Path(file).name)
                    break
        
        return found
    
    def _analyze_directory_structure(self, files: List[str]) -> str:
        """Analyse la structure de répertoires du projet."""
        dirs = set()
        for file in files:
            parts = Path(file).parts
            if len(parts) > 1:
                # Ajouter les 2 premiers niveaux
                dirs.add(parts[0])
                if len(parts) > 2:
                    dirs.add(f"{parts[0]}/{parts[1]}")
        
        if not dirs:
            return "flat"
        
        common_dirs = ["src", "test", "tests", "lib", "bin", "dist", "build"]
        found_common = [d for d in dirs if any(c in d.lower() for c in common_dirs)]
        
        if found_common:
            return f"structured ({', '.join(sorted(found_common)[:3])})"
        return "custom"
    
    def _infer_structure(self, dirs: List[str]) -> str:
        """Infère la structure typique à partir des répertoires trouvés."""
        if not dirs:
            return "standard"
        return f"standard ({', '.join(dirs[:3])})"
    
    def _infer_conventions(self, extension: str, files: List[str]) -> Dict[str, str]:
        """Infère les conventions de nommage."""
        # Analyser quelques noms de fichiers pour détecter les patterns
        sample_files = [Path(f).stem for f in files[:20] if f.endswith(extension)]
        
        has_underscores = any("_" in name for name in sample_files)
        has_camel_case = any(re.search(r'[a-z][A-Z]', name) for name in sample_files)
        
        if has_camel_case and not has_underscores:
            naming = "camelCase/PascalCase"
        elif has_underscores and not has_camel_case:
            naming = "snake_case"
        else:
            naming = "mixed"
        
        return {
            "file_naming": naming,
            "detected_from": "file_analysis"
        }
    
    def _get_conventions_for_language(self, type_id: str) -> Dict[str, str]:
        """Retourne les conventions de nommage pour un langage connu."""
        conventions_map = {
            "java": {"classes": "PascalCase", "methods": "camelCase", "files": "PascalCase"},
            "python": {"classes": "PascalCase", "functions": "snake_case", "files": "snake_case"},
            "javascript": {"classes": "PascalCase", "functions": "camelCase", "files": "camelCase"},
            "typescript": {"classes": "PascalCase", "functions": "camelCase", "files": "camelCase"},
            "go": {"exported": "PascalCase", "private": "camelCase", "files": "snake_case"},
            "rust": {"types": "PascalCase", "functions": "snake_case", "files": "snake_case"},
            "cpp": {"classes": "PascalCase", "functions": "camelCase", "files": "snake_case"},
            "csharp": {"classes": "PascalCase", "methods": "PascalCase", "files": "PascalCase"},
            "ruby": {"classes": "PascalCase", "methods": "snake_case", "files": "snake_case"},
            "php": {"classes": "PascalCase", "methods": "camelCase", "files": "PascalCase"},
        }
        return conventions_map.get(type_id, {"default": "mixed"})
    
    def _create_unknown_language_info(self) -> LanguageInfo:
        """Crée un LanguageInfo pour un langage non détecté."""
        return LanguageInfo(
            name="Unknown",
            type_id="unknown",
            confidence=0.0,
            file_count=0,
            primary_extensions=[],
            build_files=[],
            typical_structure="unknown",
            conventions={}
        )


def detect_language(files: List[str]) -> LanguageInfo:
    """
    Fonction utilitaire pour détecter le langage principal d'un projet.
    
    Args:
        files: Liste des fichiers du projet
        
    Returns:
        LanguageInfo avec les informations détectées
        
    Example:
        >>> files = ["src/Main.java", "pom.xml", "src/test/Test.java"]
        >>> lang = detect_language(files)
        >>> print(f"{lang.name} (confiance: {lang.confidence:.2f})")
        Java (confiance: 0.95)
    """
    detector = GenericLanguageDetector()
    return detector.detect_from_files(files)

