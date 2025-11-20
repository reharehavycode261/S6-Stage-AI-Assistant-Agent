# -*- coding: utf-8 -*-
"""Tests unitaires pour IntelligentTestDetector."""

import pytest
import tempfile
import os
from pathlib import Path
from utils.intelligent_test_detector import IntelligentTestDetector, TestFrameworkInfo


class TestIntelligentTestDetector:
    """Tests pour le détecteur intelligent de frameworks de test."""
    
    @pytest.fixture
    def detector(self):
        """Fixture pour créer un détecteur."""
        return IntelligentTestDetector()
    
    @pytest.fixture
    def temp_java_project(self):
        """Crée un projet Java temporaire."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Créer un fichier pom.xml
            pom_path = Path(tmpdir) / "pom.xml"
            pom_path.write_text("""<?xml version="1.0"?>
<project>
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
        </dependency>
    </dependencies>
</project>""")
            
            # Créer un fichier Java
            src_dir = Path(tmpdir) / "src" / "main" / "java"
            src_dir.mkdir(parents=True)
            (src_dir / "Main.java").write_text("""
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello");
    }
}
""")
            
            # Créer un test
            test_dir = Path(tmpdir) / "src" / "test" / "java"
            test_dir.mkdir(parents=True)
            (test_dir / "MainTest.java").write_text("""
import org.junit.jupiter.api.Test;
public class MainTest {
    @Test
    public void testMain() {}
}
""")
            
            yield tmpdir
    
    @pytest.fixture
    def temp_python_project(self):
        """Crée un projet Python temporaire."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Créer requirements.txt
            req_path = Path(tmpdir) / "requirements.txt"
            req_path.write_text("pytest>=7.0.0\n")
            
            # Créer un module Python
            (Path(tmpdir) / "main.py").write_text("""
def hello():
    return "Hello"
""")
            
            # Créer un test
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            (test_dir / "test_main.py").write_text("""
import pytest
def test_hello():
    assert True
""")
            
            yield tmpdir
    
    def test_detector_initialization(self, detector):
        """Test que le détecteur s'initialise correctement."""
        assert detector is not None
        assert detector.LANGUAGE_INDICATORS is not None
        assert "java" in detector.LANGUAGE_INDICATORS
        assert "python" in detector.LANGUAGE_INDICATORS
    
    def test_analyze_project_structure(self, detector, temp_java_project):
        """Test l'analyse de la structure d'un projet."""
        analysis = detector._analyze_project_structure(temp_java_project)
        
        assert "files" in analysis
        assert "directories" in analysis
        assert "build_files" in analysis
        assert "language_stats" in analysis
        
        # Vérifier qu'on a détecté pom.xml
        assert any("pom.xml" in f for f in analysis["build_files"])
        
        # Vérifier qu'on a compté les fichiers .java
        assert ".java" in analysis["language_stats"]
    
    @pytest.mark.asyncio
    async def test_detect_java_project_with_patterns(self, detector, temp_java_project):
        """Test la détection d'un projet Java avec patterns."""
        framework_info = await detector.detect_test_framework(temp_java_project)
        
        assert framework_info.language == "java"
        assert framework_info.framework in ["junit5", "junit4"]
        assert "Test.java" in framework_info.test_file_pattern
        assert "test" in framework_info.test_command.lower()
        assert framework_info.confidence >= 0.5
    
    @pytest.mark.asyncio
    async def test_detect_python_project_with_patterns(self, detector, temp_python_project):
        """Test la détection d'un projet Python avec patterns."""
        framework_info = await detector.detect_test_framework(temp_python_project)
        
        assert framework_info.language == "python"
        assert framework_info.framework in ["pytest", "unittest"]
        assert "test_" in framework_info.test_file_pattern
        assert "pytest" in framework_info.test_command or "unittest" in framework_info.test_command
        assert framework_info.confidence >= 0.5
    
    def test_get_test_generation_template_java(self, detector):
        """Test la génération de template pour Java."""
        framework_info = TestFrameworkInfo(
            language="java",
            framework="junit5",
            test_file_pattern="*Test.java",
            test_directory="src/test/java",
            test_command="mvn test",
            build_command=None,
            dependencies=[],
            file_extension=".java",
            confidence=0.9
        )
        
        template = detector.get_test_generation_template(framework_info, "MyClass.java")
        
        assert "import org.junit.jupiter.api.Test" in template
        assert "MyClassTest" in template
        assert "@Test" in template
    
    def test_get_test_generation_template_python(self, detector):
        """Test la génération de template pour Python."""
        framework_info = TestFrameworkInfo(
            language="python",
            framework="pytest",
            test_file_pattern="test_*.py",
            test_directory="tests",
            test_command="python -m pytest",
            build_command=None,
            dependencies=["pytest"],
            file_extension=".py",
            confidence=0.9
        )
        
        template = detector.get_test_generation_template(framework_info, "my_module.py")
        
        assert "import pytest" in template
        assert "test_" in template
    
    def test_language_indicators_completeness(self, detector):
        """Test que tous les langages ont les bonnes infos."""
        for lang, info in detector.LANGUAGE_INDICATORS.items():
            assert "extensions" in info
            assert "build_files" in info
            assert "test_dirs" in info
            assert "frameworks" in info
            assert len(info["frameworks"]) > 0
            
            for framework_name, framework_info in info["frameworks"].items():
                assert "indicators" in framework_info
                assert "test_pattern" in framework_info
                assert "command" in framework_info
    
    def test_default_framework(self, detector):
        """Test le framework par défaut."""
        default = detector._get_default_framework()
        
        assert default.language == "python"
        assert default.framework == "pytest"
        assert default.confidence == 0.5


@pytest.mark.asyncio
async def test_integration_full_detection():
    """Test d'intégration complet de la détection."""
    detector = IntelligentTestDetector()
    
    # Créer un petit projet de test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Ajouter quelques fichiers Python
        (Path(tmpdir) / "app.py").write_text("print('hello')")
        (Path(tmpdir) / "test_app.py").write_text("def test_app(): pass")
        
        # Détecter
        result = await detector.detect_test_framework(tmpdir)
        
        # Vérifications basiques
        assert result is not None
        assert result.language in detector.LANGUAGE_INDICATORS
        assert result.test_command != ""
        assert result.confidence > 0


def test_parse_framework_output():
    """Test du parsing de sortie de tests."""
    from nodes.test_node import _parse_framework_output
    
    # Test JUnit
    junit_output = """
Tests run: 10, Failures: 2, Errors: 0, Skipped: 0
BUILD SUCCESS
"""
    result = _parse_framework_output(junit_output, "junit5")
    assert result["passed"] == 8
    assert result["failed"] == 2
    
    # Test pytest
    pytest_output = """
===== 5 passed, 1 failed in 2.5s =====
"""
    result = _parse_framework_output(pytest_output, "pytest")
    assert result["passed"] == 5
    assert result["failed"] == 1
    
    # Test Jest
    jest_output = """
Tests: 3 passed, 1 failed, 4 total
"""
    result = _parse_framework_output(jest_output, "jest")
    assert result["passed"] == 3
    assert result["failed"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

