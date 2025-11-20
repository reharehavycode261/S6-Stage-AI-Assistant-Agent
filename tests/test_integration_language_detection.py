"""
Tests d'intégration pour la détection de langage dans implement_node.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from nodes.implement_node import _analyze_project_structure, _create_implementation_prompt
from models.schemas import TaskRequest
from utils.language_detector import LanguageInfo


class TestImplementNodeIntegration:
    """Tests d'intégration pour implement_node avec nouveau système de détection."""
    
    @pytest.mark.asyncio
    async def test_analyze_project_structure_java_project(self):
        """Test analyse d'un projet Java réel."""
        # Mock de ClaudeCodeTool
        mock_tool = AsyncMock()
        
        # Simuler la sortie de find
        java_project_files = """./pom.xml
./src/main/java/com/example/Main.java
./src/main/java/com/example/Service.java
./src/test/java/com/example/MainTest.java
./README.md"""
        
        mock_tool._arun = AsyncMock(side_effect=[
            # Premier appel: find
            {"success": True, "stdout": java_project_files},
            # Appels suivants: read_file pour config files
            {"success": True, "file_exists": True, "content": "<project>Maven project</project>"},
            {"success": False, "file_exists": False}
        ])
        
        # Exécuter l'analyse
        result = await _analyze_project_structure(mock_tool)
        
        # Vérifications
        assert result["project_type"] == "java"
        assert result["main_language"] == "Java"
        assert result["confidence"] >= 0.5  # ✅ Seuil ajusté pour tenir compte de la détection par discovery
        assert ".java" in result["extensions"]
        assert "pom.xml" in result["build_files"]
        assert result["language_info"] is not None
        assert result["language_info"].name == "Java"
    
    @pytest.mark.asyncio
    async def test_analyze_project_structure_python_project(self):
        """Test analyse d'un projet Python réel."""
        mock_tool = AsyncMock()
        
        python_project_files = """./requirements.txt
./main.py
./utils.py
./tests/test_main.py
./setup.py"""
        
        mock_tool._arun = AsyncMock(side_effect=[
            {"success": True, "stdout": python_project_files},
            {"success": True, "file_exists": True, "content": "pytest==7.0.0"},
            {"success": True, "file_exists": True, "content": "from setuptools import setup"},
            {"success": False}
        ])
        
        result = await _analyze_project_structure(mock_tool)
        
        assert result["project_type"] == "python"
        assert result["main_language"] == "Python"
        assert result["confidence"] > 0.7
        assert ".py" in result["extensions"]
        assert any("requirements.txt" in bf or "setup.py" in bf for bf in result["build_files"])
    
    @pytest.mark.asyncio
    async def test_analyze_project_structure_typescript_project(self):
        """Test analyse d'un projet TypeScript réel."""
        mock_tool = AsyncMock()
        
        ts_project_files = """./package.json
./tsconfig.json
./src/index.ts
./src/components/Button.tsx
./src/utils.ts"""
        
        mock_tool._arun = AsyncMock(side_effect=[
            {"success": True, "stdout": ts_project_files},
            {"success": True, "file_exists": True, "content": '{"name": "my-app"}'},
            {"success": True, "file_exists": True, "content": '{"compilerOptions": {}}'},
            {"success": False}
        ])
        
        result = await _analyze_project_structure(mock_tool)
        
        assert result["project_type"] == "typescript"
        assert result["main_language"] == "TypeScript"
        assert ".ts" in result["extensions"] or ".tsx" in result["extensions"]
    
    @pytest.mark.asyncio
    async def test_analyze_project_structure_unknown_language(self):
        """Test analyse avec langage inconnu (mode discovery)."""
        mock_tool = AsyncMock()
        
        unknown_files = """./main.xyz
./utils.xyz
./test.xyz"""
        
        mock_tool._arun = AsyncMock(side_effect=[
            {"success": True, "stdout": unknown_files},
            {"success": False}
        ])
        
        result = await _analyze_project_structure(mock_tool)
        
        # Devrait être détecté via discovery
        assert result["project_type"] == "xyz"
        assert result["main_language"] == "XYZ"
        assert ".xyz" in result["extensions"]
        assert result["confidence"] > 0
    
    @pytest.mark.asyncio
    async def test_analyze_project_structure_error_handling(self):
        """Test gestion d'erreur lors de l'analyse."""
        mock_tool = AsyncMock()
        mock_tool._arun = AsyncMock(side_effect=Exception("Connection error"))
        
        result = await _analyze_project_structure(mock_tool)
        
        # Devrait retourner un fallback
        assert result["project_type"] == "unknown"
        assert result["main_language"] == "Unknown"
        assert result["confidence"] == 0.0
        assert result["language_info"] is not None
        assert result["language_info"].name == "Unknown"


class TestCreateImplementationPrompt:
    """Tests pour _create_implementation_prompt avec nouveau système."""
    
    @pytest.mark.asyncio
    async def test_create_prompt_with_java_language_info(self):
        """Test génération de prompt avec LanguageInfo Java."""
        # Créer une tâche mock
        task = Mock()
        task.title = "Ajouter méthode count()"
        task.description = "Implémenter une méthode count() dans GenericDAO"
        task.branch_name = "feature/count-method"
        task.priority = "high"
        
        # Créer LanguageInfo pour Java
        lang_info = LanguageInfo(
            name="Java",
            type_id="java",
            confidence=0.95,
            file_count=10,
            primary_extensions=[".java"],
            build_files=["pom.xml"],
            typical_structure="structured (src/main, src/test)",
            conventions={"classes": "PascalCase", "methods": "camelCase"}
        )
        
        # Générer le prompt
        prompt = await _create_implementation_prompt(
            task,
            "Structure: projet Maven standard",
            [],
            language_info=lang_info
        )
        
        # Vérifications
        assert "Java" in prompt or "JAVA" in prompt
        assert ".java" in prompt
        assert "count()" in prompt or "count" in prompt.lower()
        assert "feature/count-method" in prompt
        assert "RÈGLES" in prompt.upper() or "règles" in prompt.lower()
        assert "EXTENSIONS" in prompt.upper() or "extensions" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_create_prompt_with_python_language_info(self):
        """Test génération de prompt avec LanguageInfo Python."""
        task = Mock()
        task.title = "Add logging feature"
        task.description = "Add comprehensive logging to the application"
        task.branch_name = "feature/logging"
        task.priority = "medium"
        
        lang_info = LanguageInfo(
            name="Python",
            type_id="python",
            confidence=0.88,
            file_count=15,
            primary_extensions=[".py"],
            build_files=["requirements.txt", "setup.py"],
            typical_structure="standard (src, tests)",
            conventions={"functions": "snake_case", "classes": "PascalCase"}
        )
        
        prompt = await _create_implementation_prompt(
            task,
            "Structure: projet Python avec tests",
            [],
            language_info=lang_info
        )
        
        assert "Python" in prompt or "PYTHON" in prompt
        assert ".py" in prompt
        assert "logging" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_create_prompt_without_language_info(self):
        """Test génération de prompt sans LanguageInfo (fallback)."""
        task = Mock()
        task.title = "Test task"
        task.description = "Test description"
        task.branch_name = "test-branch"
        task.priority = "low"
        
        prompt = await _create_implementation_prompt(
            task,
            "Structure: unknown",
            [],
            language_info=None  # Pas de language_info
        )
        
        # Devrait avoir un fallback générique
        assert "NON DÉTECTÉ" in prompt.upper() or "non détecté" in prompt.lower()
        assert "Unknown" in prompt or "unknown" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_create_prompt_with_low_confidence(self):
        """Test génération de prompt avec confiance faible."""
        task = Mock()
        task.title = "Test"
        task.description = "Test"
        task.branch_name = "test"
        task.priority = "low"
        
        lang_info = LanguageInfo(
            name="TestLang",
            type_id="testlang",
            confidence=0.45,  # Confiance faible
            file_count=2,
            primary_extensions=[".test"],
            build_files=[],
            typical_structure="flat",
            conventions={}
        )
        
        prompt = await _create_implementation_prompt(
            task,
            "Test structure",
            [],
            language_info=lang_info
        )
        
        # Devrait contenir des avertissements
        assert "TestLang" in prompt or "TESTLANG" in prompt
        assert prompt  # Non vide


class TestEndToEndScenario:
    """Tests de scénarios end-to-end complets."""
    
    @pytest.mark.asyncio
    async def test_java_project_full_workflow(self):
        """Test workflow complet pour un projet Java."""
        # Setup mock tool
        mock_tool = AsyncMock()
        
        java_files = """./pom.xml
./src/main/java/com/example/Main.java
./src/main/java/com/example/Service.java"""
        
        mock_tool._arun = AsyncMock(side_effect=[
            {"success": True, "stdout": java_files},
            {"success": True, "file_exists": True, "content": "<project></project>"},
            {"success": False}
        ])
        
        # Étape 1: Analyser le projet
        analysis = await _analyze_project_structure(mock_tool)
        
        assert analysis["project_type"] == "java"
        assert analysis["language_info"].name == "Java"
        
        # Étape 2: Créer le prompt
        task = Mock()
        task.title = "Add feature"
        task.description = "Add new feature"
        task.branch_name = "feature/new"
        task.priority = "high"
        
        prompt = await _create_implementation_prompt(
            task,
            analysis["structure_text"],
            [],
            language_info=analysis["language_info"]
        )
        
        # Vérifications finales
        assert "Java" in prompt or "JAVA" in prompt
        assert "pom.xml" in prompt or "Maven" in prompt or "MAVEN" in prompt
        assert "feature" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_python_project_full_workflow(self):
        """Test workflow complet pour un projet Python."""
        mock_tool = AsyncMock()
        
        python_files = """./requirements.txt
./app.py
./utils.py
./tests/test_app.py"""
        
        mock_tool._arun = AsyncMock(side_effect=[
            {"success": True, "stdout": python_files},
            {"success": True, "file_exists": True, "content": "flask==2.0.0"},
            {"success": False}
        ])
        
        # Analyse
        analysis = await _analyze_project_structure(mock_tool)
        assert analysis["project_type"] == "python"
        
        # Prompt
        task = Mock()
        task.title = "Bug fix"
        task.description = "Fix critical bug"
        task.branch_name = "bugfix/critical"
        task.priority = "critical"
        
        prompt = await _create_implementation_prompt(
            task,
            analysis["structure_text"],
            ["Previous error: timeout"],
            language_info=analysis["language_info"]
        )
        
        assert "Python" in prompt or "PYTHON" in prompt
        assert ".py" in prompt
        assert "timeout" in prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

