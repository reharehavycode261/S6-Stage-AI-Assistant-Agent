"""
Module de détection générique des frameworks de test.

Ce module détecte automatiquement le framework de test approprié
pour n'importe quel langage de programmation.
"""

import json
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TestFrameworkInfo:
    """Informations sur un framework de test détecté."""
    name: str                       # Ex: "pytest", "jest", "junit"
    language: str                   # Langage associé
    confidence: float               # Score de confiance (0.0-1.0)
    test_file_pattern: str          # Pattern de nommage des tests
    test_file_extension: str        # Extension des fichiers de test
    import_statement: str           # Import/require du framework
    assertion_pattern: str          # Pattern d'assertion
    runner_command: str             # Commande pour lancer les tests


class TestFrameworkPattern:
    """Pattern de détection pour un framework de test."""
    
    def __init__(
        self,
        name: str,
        language: str,
        config_files: List[str],
        dependency_keys: List[str],
        test_patterns: List[str],
        file_pattern: str,
        extension: str,
        import_statement: str,
        assertion_pattern: str,
        runner_command: str
    ):
        self.name = name
        self.language = language
        self.config_files = config_files
        self.dependency_keys = dependency_keys
        self.test_patterns = test_patterns
        self.file_pattern = file_pattern
        self.extension = extension
        self.import_statement = import_statement
        self.assertion_pattern = assertion_pattern
        self.runner_command = runner_command


# ✅ BASE DE CONNAISSANCES: Frameworks de test connus
KNOWN_TEST_FRAMEWORKS = [
    # Python
    TestFrameworkPattern(
        name="pytest",
        language="python",
        config_files=["pytest.ini", "pyproject.toml", "setup.cfg"],
        dependency_keys=["pytest"],
        test_patterns=["test_*.py", "*_test.py"],
        file_pattern="test_{module}.py",
        extension=".py",
        import_statement="import pytest",
        assertion_pattern="assert",
        runner_command="pytest"
    ),
    TestFrameworkPattern(
        name="unittest",
        language="python",
        config_files=[],
        dependency_keys=["unittest"],
        test_patterns=["test_*.py", "*_test.py"],
        file_pattern="test_{module}.py",
        extension=".py",
        import_statement="import unittest",
        assertion_pattern="self.assert",
        runner_command="python -m unittest"
    ),
    
    # JavaScript/TypeScript
    TestFrameworkPattern(
        name="jest",
        language="javascript",
        config_files=["jest.config.js", "jest.config.ts", "jest.config.json"],
        dependency_keys=["jest", "@jest/globals"],
        test_patterns=["*.test.js", "*.spec.js", "*.test.ts", "*.spec.ts"],
        file_pattern="{module}.test.js",
        extension=".js",
        import_statement="import { test, expect } from '@jest/globals';",
        assertion_pattern="expect(...).toBe(...)",
        runner_command="npm test"
    ),
    TestFrameworkPattern(
        name="jest",
        language="typescript",
        config_files=["jest.config.js", "jest.config.ts", "jest.config.json"],
        dependency_keys=["jest", "@jest/globals", "@types/jest"],
        test_patterns=["*.test.ts", "*.spec.ts"],
        file_pattern="{module}.test.ts",
        extension=".ts",
        import_statement="import { test, expect } from '@jest/globals';",
        assertion_pattern="expect(...).toBe(...)",
        runner_command="npm test"
    ),
    TestFrameworkPattern(
        name="mocha",
        language="javascript",
        config_files=[".mocharc.json", ".mocharc.js", ".mocharc.yml"],
        dependency_keys=["mocha", "chai"],
        test_patterns=["*.test.js", "*.spec.js"],
        file_pattern="{module}.spec.js",
        extension=".js",
        import_statement="const { expect } = require('chai');",
        assertion_pattern="expect(...).to.equal(...)",
        runner_command="npm test"
    ),
    TestFrameworkPattern(
        name="vitest",
        language="typescript",
        config_files=["vitest.config.ts", "vitest.config.js"],
        dependency_keys=["vitest"],
        test_patterns=["*.test.ts", "*.spec.ts"],
        file_pattern="{module}.test.ts",
        extension=".ts",
        import_statement="import { describe, it, expect } from 'vitest';",
        assertion_pattern="expect(...).toBe(...)",
        runner_command="npm test"
    ),
    
    # Java
    TestFrameworkPattern(
        name="junit5",
        language="java",
        config_files=["pom.xml", "build.gradle"],
        dependency_keys=["junit-jupiter", "junit-platform"],
        test_patterns=["*Test.java"],
        file_pattern="{Module}Test.java",
        extension=".java",
        import_statement="import org.junit.jupiter.api.Test;",
        assertion_pattern="Assertions.assert",
        runner_command="mvn test"
    ),
    TestFrameworkPattern(
        name="junit4",
        language="java",
        config_files=["pom.xml", "build.gradle"],
        dependency_keys=["junit:junit:4"],
        test_patterns=["*Test.java"],
        file_pattern="{Module}Test.java",
        extension=".java",
        import_statement="import org.junit.Test;",
        assertion_pattern="Assert.assert",
        runner_command="mvn test"
    ),
    
    # Go
    TestFrameworkPattern(
        name="testing",
        language="go",
        config_files=["go.mod"],
        dependency_keys=[],  # Built-in
        test_patterns=["*_test.go"],
        file_pattern="{module}_test.go",
        extension=".go",
        import_statement="import \"testing\"",
        assertion_pattern="t.Error(...)",
        runner_command="go test"
    ),
    
    # Rust
    TestFrameworkPattern(
        name="cargo-test",
        language="rust",
        config_files=["Cargo.toml"],
        dependency_keys=[],  # Built-in
        test_patterns=["*_test.rs", "tests/*.rs"],
        file_pattern="{module}_test.rs",
        extension=".rs",
        import_statement="#[cfg(test)]",
        assertion_pattern="assert_eq!(...)",
        runner_command="cargo test"
    ),
    
    # C#
    TestFrameworkPattern(
        name="nunit",
        language="csharp",
        config_files=["*.csproj"],
        dependency_keys=["NUnit", "nunit"],
        test_patterns=["*Tests.cs", "*Test.cs"],
        file_pattern="{Module}Tests.cs",
        extension=".cs",
        import_statement="using NUnit.Framework;",
        assertion_pattern="Assert.That(...)",
        runner_command="dotnet test"
    ),
    TestFrameworkPattern(
        name="xunit",
        language="csharp",
        config_files=["*.csproj"],
        dependency_keys=["xunit", "xUnit"],
        test_patterns=["*Tests.cs", "*Test.cs"],
        file_pattern="{Module}Tests.cs",
        extension=".cs",
        import_statement="using Xunit;",
        assertion_pattern="Assert.Equal(...)",
        runner_command="dotnet test"
    ),
    
    # Ruby
    TestFrameworkPattern(
        name="rspec",
        language="ruby",
        config_files=[".rspec", "spec/spec_helper.rb"],
        dependency_keys=["rspec"],
        test_patterns=["*_spec.rb"],
        file_pattern="{module}_spec.rb",
        extension=".rb",
        import_statement="require 'rspec'",
        assertion_pattern="expect(...).to eq(...)",
        runner_command="rspec"
    ),
    TestFrameworkPattern(
        name="minitest",
        language="ruby",
        config_files=["test/test_helper.rb"],
        dependency_keys=["minitest"],
        test_patterns=["test_*.rb", "*_test.rb"],
        file_pattern="test_{module}.rb",
        extension=".rb",
        import_statement="require 'minitest/autorun'",
        assertion_pattern="assert_equal(...)",
        runner_command="ruby -Itest"
    ),
    
    # PHP
    TestFrameworkPattern(
        name="phpunit",
        language="php",
        config_files=["phpunit.xml", "phpunit.xml.dist"],
        dependency_keys=["phpunit/phpunit"],
        test_patterns=["*Test.php"],
        file_pattern="{Module}Test.php",
        extension=".php",
        import_statement="use PHPUnit\\Framework\\TestCase;",
        assertion_pattern="$this->assert",
        runner_command="vendor/bin/phpunit"
    ),
]


class GenericTestFrameworkDetector:
    """Détecteur générique de framework de test."""
    
    def __init__(self):
        self.patterns = KNOWN_TEST_FRAMEWORKS
    
    def detect_framework(
        self, 
        working_directory: str, 
        language: str
    ) -> Optional[TestFrameworkInfo]:
        """
        Détecte le framework de test pour un langage donné.
        
        Args:
            working_directory: Répertoire du projet
            language: Langage de programmation
            
        Returns:
            TestFrameworkInfo ou None si non détecté
        """
        logger.debug(f"🔍 Détection framework de test pour {language}")
        
        # Filtrer par langage
        language_patterns = [p for p in self.patterns if p.language == language]
        
        if not language_patterns:
            logger.warning(f"⚠️ Aucun framework connu pour {language}")
            return self._create_generic_framework(language)
        
        # Chercher le framework le plus probable
        best_pattern = None
        best_score = 0
        
        for pattern in language_patterns:
            score = self._calculate_score(pattern, working_directory)
            logger.debug(f"  {pattern.name}: score={score}")
            
            if score > best_score:
                best_score = score
                best_pattern = pattern
        
        if best_pattern and best_score > 0:
            confidence = min(1.0, best_score / 10.0)
            logger.info(f"✅ Framework détecté: {best_pattern.name} (confiance: {confidence:.2f})")
            
            return TestFrameworkInfo(
                name=best_pattern.name,
                language=best_pattern.language,
                confidence=confidence,
                test_file_pattern=best_pattern.file_pattern,
                test_file_extension=best_pattern.extension,
                import_statement=best_pattern.import_statement,
                assertion_pattern=best_pattern.assertion_pattern,
                runner_command=best_pattern.runner_command
            )
        
        # Fallback sur le premier pattern pour ce langage
        logger.info(f"ℹ️ Utilisation du framework par défaut pour {language}")
        fallback = language_patterns[0]
        
        return TestFrameworkInfo(
            name=fallback.name,
            language=fallback.language,
            confidence=0.5,
            test_file_pattern=fallback.file_pattern,
            test_file_extension=fallback.extension,
            import_statement=fallback.import_statement,
            assertion_pattern=fallback.assertion_pattern,
            runner_command=fallback.runner_command
        )
    
    def _calculate_score(self, pattern: TestFrameworkPattern, directory: str) -> float:
        """Calcule un score pour un pattern donné."""
        score = 0.0
        work_path = Path(directory)
        
        # Vérifier les fichiers de configuration (+5 points)
        for config_file in pattern.config_files:
            if (work_path / config_file).exists():
                score += 5.0
                logger.debug(f"    ✓ Config trouvé: {config_file}")
        
        # Vérifier les dépendances dans les fichiers de build (+3 points)
        score += self._check_dependencies(work_path, pattern)
        
        # Vérifier les fichiers de test existants (+2 points)
        score += self._check_test_files(work_path, pattern)
        
        return score
    
    def _check_dependencies(self, work_path: Path, pattern: TestFrameworkPattern) -> float:
        """Vérifie si les dépendances du framework sont présentes."""
        score = 0.0
        
        # Pour Python: requirements.txt, pyproject.toml
        if pattern.language == "python":
            for dep_file in ["requirements.txt", "pyproject.toml", "setup.py"]:
                dep_path = work_path / dep_file
                if dep_path.exists():
                    try:
                        content = dep_path.read_text()
                        for dep_key in pattern.dependency_keys:
                            if dep_key.lower() in content.lower():
                                score += 3.0
                                logger.debug(f"    ✓ Dépendance trouvée: {dep_key} dans {dep_file}")
                                break
                    except Exception:
                        pass
        
        # Pour JS/TS: package.json
        elif pattern.language in ["javascript", "typescript"]:
            package_json = work_path / "package.json"
            if package_json.exists():
                try:
                    data = json.loads(package_json.read_text())
                    all_deps = {
                        **data.get("dependencies", {}),
                        **data.get("devDependencies", {})
                    }
                    for dep_key in pattern.dependency_keys:
                        if dep_key in all_deps:
                            score += 3.0
                            logger.debug(f"    ✓ Dépendance trouvée: {dep_key}")
                            break
                except Exception:
                    pass
        
        # Pour Java: pom.xml ou build.gradle
        elif pattern.language == "java":
            for build_file in ["pom.xml", "build.gradle"]:
                build_path = work_path / build_file
                if build_path.exists():
                    try:
                        content = build_path.read_text()
                        for dep_key in pattern.dependency_keys:
                            if dep_key in content:
                                score += 3.0
                                logger.debug(f"    ✓ Dépendance trouvée: {dep_key} dans {build_file}")
                                break
                    except Exception:
                        pass
        
        return score
    
    def _check_test_files(self, work_path: Path, pattern: TestFrameworkPattern) -> float:
        """Vérifie si des fichiers de test existent avec le pattern."""
        score = 0.0
        
        # Chercher des fichiers correspondant aux patterns
        for test_pattern in pattern.test_patterns:
            # Simplifier le pattern pour la recherche
            if "*" in test_pattern:
                search_pattern = test_pattern.replace("*", "")
                
                # Chercher dans le répertoire de travail
                for path in work_path.rglob(f"*{search_pattern}"):
                    if path.is_file():
                        score += 2.0
                        logger.debug(f"    ✓ Fichier de test trouvé: {path.name}")
                        break
        
        return score
    
    def _create_generic_framework(self, language: str) -> TestFrameworkInfo:
        """Crée un framework générique pour un langage inconnu."""
        logger.info(f"ℹ️ Création framework générique pour {language}")
        
        return TestFrameworkInfo(
            name=f"{language}-test",
            language=language,
            confidence=0.3,
            test_file_pattern="test_{module}",
            test_file_extension=f".{language}",
            import_statement=f"// Test framework for {language}",
            assertion_pattern="assert",
            runner_command=f"# Run tests for {language}"
        )


def detect_test_framework(working_directory: str, language: str) -> Optional[TestFrameworkInfo]:
    """
    Fonction utilitaire pour détecter le framework de test.
    
    Args:
        working_directory: Répertoire du projet
        language: Langage de programmation
        
    Returns:
        TestFrameworkInfo détecté
        
    Example:
        >>> framework = detect_test_framework("/path/to/project", "python")
        >>> print(f"{framework.name} - {framework.test_file_pattern}")
        pytest - test_{module}.py
    """
    detector = GenericTestFrameworkDetector()
    return detector.detect_framework(working_directory, language)
