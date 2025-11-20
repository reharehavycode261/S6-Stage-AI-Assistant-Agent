"""
Tests unitaires pour le générateur d'instructions adaptatif.
"""

import pytest
from utils.language_detector import LanguageInfo, detect_language
from utils.instruction_generator import (
    AdaptiveInstructionGenerator,
    CodeInstructions,
    generate_instructions_for_language,
    get_adaptive_prompt_supplement
)


class TestAdaptiveInstructionGenerator:
    """Tests pour AdaptiveInstructionGenerator."""
    
    def setup_method(self):
        """Initialisation avant chaque test."""
        self.generator = AdaptiveInstructionGenerator()
    
    # ========== Tests génération instructions complètes ==========
    
    def test_generate_instructions_for_java(self):
        """Test génération instructions pour Java."""
        lang_info = detect_language([
            "pom.xml",
            "src/main/java/Main.java",
            "src/test/java/MainTest.java"
        ])
        
        instructions = self.generator.generate_instructions(lang_info)
        
        assert isinstance(instructions, CodeInstructions)
        assert "JAVA" in instructions.critical_rules.upper()
        assert ".java" in instructions.critical_rules.lower()
        assert "src/main" in instructions.file_structure.lower() or "src/test" in instructions.file_structure.lower()
        assert instructions.naming_conventions
        assert instructions.best_practices
        assert instructions.common_pitfalls
        assert instructions.example_structure
    
    def test_generate_instructions_for_python(self):
        """Test génération instructions pour Python."""
        lang_info = detect_language([
            "requirements.txt",
            "main.py",
            "tests/test_main.py"
        ])
        
        instructions = self.generator.generate_instructions(lang_info)
        
        assert "PYTHON" in instructions.critical_rules.upper()
        assert ".py" in instructions.critical_rules.lower()
        assert instructions.file_structure
    
    def test_generate_instructions_for_javascript(self):
        """Test génération instructions pour JavaScript."""
        lang_info = detect_language([
            "package.json",
            "src/index.js",
            "src/utils.js"
        ])
        
        instructions = self.generator.generate_instructions(lang_info)
        
        assert "JAVASCRIPT" in instructions.critical_rules.upper()
        assert ".js" in instructions.critical_rules.lower()
    
    def test_generate_instructions_for_unknown_language(self):
        """Test génération instructions pour langage inconnu."""
        lang_info = LanguageInfo(
            name="MyCustomLang",
            type_id="mycustomlang",
            confidence=0.8,
            file_count=5,
            primary_extensions=[".mcl"],
            build_files=["build.mcl"],
            typical_structure="custom (src, tests)",
            conventions={"files": "snake_case"}
        )
        
        instructions = self.generator.generate_instructions(lang_info)
        
        assert "MYCUSTOMLANG" in instructions.critical_rules.upper()
        assert ".mcl" in instructions.critical_rules
        assert "build.mcl" in instructions.critical_rules
        assert "custom" in instructions.file_structure.lower()
    
    # ========== Tests sections individuelles ==========
    
    def test_critical_rules_contains_essentials(self):
        """Test que les règles critiques contiennent l'essentiel."""
        lang_info = detect_language(["Main.java"])
        instructions = self.generator.generate_instructions(lang_info)
        
        # Doit contenir:
        assert "RÈGLES CRITIQUES" in instructions.critical_rules
        assert "LANGAGE" in instructions.critical_rules
        assert "EXTENSIONS" in instructions.critical_rules
        assert "STRUCTURE" in instructions.critical_rules
        assert ".java" in instructions.critical_rules
    
    def test_file_structure_detects_maven_structure(self):
        """Test détection structure Maven/Gradle."""
        lang_info = detect_language([
            "pom.xml",
            "src/main/java/App.java",
            "src/test/java/AppTest.java"
        ])
        instructions = self.generator.generate_instructions(lang_info)
        
        assert "src/main" in instructions.file_structure.lower() or "maven" in instructions.file_structure.lower()
    
    def test_naming_conventions_uses_detected_conventions(self):
        """Test que les conventions détectées sont utilisées."""
        lang_info = detect_language(["main.py", "utils.py"])
        instructions = self.generator.generate_instructions(lang_info)
        
        # Python devrait avoir des conventions définies
        assert instructions.naming_conventions
        assert len(instructions.naming_conventions) > 50  # Au moins quelques lignes
    
    def test_best_practices_includes_common_practices(self):
        """Test que les bonnes pratiques incluent les pratiques communes."""
        lang_info = detect_language(["Main.java"])
        instructions = self.generator.generate_instructions(lang_info)
        
        # Pratiques universelles
        assert "Cohérence" in instructions.best_practices or "cohérence" in instructions.best_practices
        assert "Documentation" in instructions.best_practices or "documentation" in instructions.best_practices
    
    def test_common_pitfalls_warns_against_wrong_language(self):
        """Test que les pièges mettent en garde contre le mauvais langage."""
        lang_info = detect_language(["Main.java"])
        instructions = self.generator.generate_instructions(lang_info)
        
        assert "NE PAS" in instructions.common_pitfalls or "NE pas" in instructions.common_pitfalls
        assert "Java" in instructions.common_pitfalls
    
    def test_common_pitfalls_warns_when_low_confidence(self):
        """Test avertissement spécial pour confiance faible."""
        lang_info = LanguageInfo(
            name="TestLang",
            type_id="testlang",
            confidence=0.5,  # Confiance faible
            file_count=2,
            primary_extensions=[".test"],
            build_files=[],
            typical_structure="flat",
            conventions={}
        )
        instructions = self.generator.generate_instructions(lang_info)
        
        assert "ATTENTION" in instructions.common_pitfalls or "confiance" in instructions.common_pitfalls.lower()
        assert "0.5" in instructions.common_pitfalls or "0.50" in instructions.common_pitfalls
    
    def test_example_structure_adapts_to_project_type(self):
        """Test que l'exemple s'adapte au type de projet."""
        # Structure Maven
        lang_info_maven = detect_language([
            "pom.xml",
            "src/main/java/App.java"
        ])
        instructions_maven = self.generator.generate_instructions(lang_info_maven)
        
        assert "src/main" in instructions_maven.example_structure.lower()
        
        # Structure plate
        lang_info_flat = detect_language(["app.py", "utils.py"])
        instructions_flat = self.generator.generate_instructions(lang_info_flat)
        
        # Structure différente pour projet plat
        assert instructions_flat.example_structure != instructions_maven.example_structure
    
    # ========== Tests fonction utilitaire ==========
    
    def test_generate_instructions_for_language_utility(self):
        """Test de la fonction utilitaire."""
        lang_info = detect_language(["Main.java"])
        text = generate_instructions_for_language(lang_info)
        
        assert isinstance(text, str)
        assert len(text) > 500  # Devrait être substantiel
        assert "JAVA" in text.upper()
        assert "RÈGLES CRITIQUES" in text.upper()
        assert "STRUCTURE DE FICHIERS" in text.upper() or "STRUCTURE" in text.upper()
        assert "CONVENTIONS DE NOMMAGE" in text.upper() or "CONVENTIONS" in text.upper()
        assert "BONNES PRATIQUES" in text.upper() or "PRATIQUES" in text.upper()
        assert "PIÈGES À ÉVITER" in text.upper() or "PIÈGES" in text.upper()
        assert "EXEMPLE DE STRUCTURE" in text.upper() or "EXEMPLE" in text.upper()
        assert "OBJECTIF PRINCIPAL" in text.upper() or "OBJECTIF" in text.upper()
    
    def test_generate_instructions_includes_confidence(self):
        """Test que les instructions incluent le score de confiance."""
        lang_info = detect_language(["pom.xml", "Main.java"])
        text = generate_instructions_for_language(lang_info)
        
        assert "confiance:" in text.lower()
    
    def test_generate_instructions_includes_extensions(self):
        """Test que les instructions incluent les extensions."""
        lang_info = detect_language(["Main.java"])
        text = generate_instructions_for_language(lang_info)
        
        assert ".java" in text
        assert "Extensions" in text or "extensions" in text
    
    # ========== Tests supplément de prompt ==========
    
    def test_get_adaptive_prompt_supplement(self):
        """Test du supplément de prompt adaptatif."""
        lang_info = detect_language([
            "pom.xml",
            "src/main/java/Main.java"
        ])
        supplement = get_adaptive_prompt_supplement(lang_info)
        
        assert isinstance(supplement, str)
        assert len(supplement) > 100
        assert "Java" in supplement
        assert ".java" in supplement
        assert "RÈGLES IMPÉRATIVES" in supplement
        assert "VÉRIFICATION AVANT GÉNÉRATION" in supplement
    
    def test_prompt_supplement_condensed_format(self):
        """Test que le supplément est condensé (pour inclusion dans prompts)."""
        lang_info = detect_language(["Main.java"])
        supplement = get_adaptive_prompt_supplement(lang_info)
        
        # Devrait être plus court que les instructions complètes
        full_instructions = generate_instructions_for_language(lang_info)
        assert len(supplement) < len(full_instructions)
        
        # Mais contenir l'essentiel
        assert "Java" in supplement
        assert ".java" in supplement
    
    def test_prompt_supplement_includes_verification_questions(self):
        """Test que le supplément inclut des questions de vérification."""
        lang_info = detect_language(["main.py"])
        supplement = get_adaptive_prompt_supplement(lang_info)
        
        assert "❓" in supplement or "?" in supplement
        assert "Python" in supplement
    
    def test_prompt_supplement_handles_build_files(self):
        """Test que le supplément mentionne les build files si présents."""
        lang_info = detect_language([
            "pom.xml",
            "build.gradle",
            "Main.java"
        ])
        supplement = get_adaptive_prompt_supplement(lang_info)
        
        # Devrait mentionner au moins un build file
        assert "pom.xml" in supplement or "build.gradle" in supplement or "build" in supplement.lower()
    
    def test_prompt_supplement_handles_conventions(self):
        """Test que le supplément inclut les conventions si disponibles."""
        lang_info = detect_language(["main.py", "utils.py"])
        supplement = get_adaptive_prompt_supplement(lang_info)
        
        # Python a des conventions connues
        if lang_info.conventions:
            assert "Conventions" in supplement or "conventions" in supplement


class TestInstructionsQuality:
    """Tests de qualité des instructions générées."""
    
    def test_instructions_are_comprehensive(self):
        """Test que les instructions sont complètes."""
        lang_info = detect_language(["pom.xml", "Main.java"])
        text = generate_instructions_for_language(lang_info)
        
        # Toutes les sections essentielles doivent être présentes
        required_sections = [
            "RÈGLES CRITIQUES",
            "STRUCTURE DE FICHIERS",
            "CONVENTIONS DE NOMMAGE",
            "BONNES PRATIQUES",
            "PIÈGES À ÉVITER",
            "EXEMPLE DE STRUCTURE",
            "OBJECTIF PRINCIPAL"
        ]
        
        for section in required_sections:
            assert section in text, f"Section manquante: {section}"
    
    def test_instructions_are_language_specific(self):
        """Test que les instructions sont spécifiques au langage."""
        # Générer pour Java
        java_info = detect_language(["Main.java"])
        java_text = generate_instructions_for_language(java_info)
        
        # Générer pour Python
        python_info = detect_language(["main.py"])
        python_text = generate_instructions_for_language(python_info)
        
        # Les instructions doivent être différentes
        assert java_text != python_text
        assert ".java" in java_text
        assert ".java" not in python_text
        assert ".py" in python_text
        assert ".py" not in java_text
    
    def test_instructions_provide_actionable_guidance(self):
        """Test que les instructions fournissent des directives actionnables."""
        lang_info = detect_language(["Main.java"])
        text = generate_instructions_for_language(lang_info)
        
        # Doit contenir des directives d'action
        action_words = ["DOIS", "NE PAS", "Utilise", "Respecte", "Crée", "Analyse"]
        has_actions = any(word in text for word in action_words)
        assert has_actions
    
    def test_instructions_include_examples(self):
        """Test que les instructions incluent des exemples."""
        lang_info = detect_language(["Main.java"])
        text = generate_instructions_for_language(lang_info)
        
        # Devrait avoir une section d'exemple
        assert "EXEMPLE" in text.upper()
        assert "```" in text  # Code block


class TestEdgeCases:
    """Tests des cas limites."""
    
    def test_handles_language_with_no_conventions(self):
        """Test gestion d'un langage sans conventions définies."""
        lang_info = LanguageInfo(
            name="NewLang",
            type_id="newlang",
            confidence=0.9,
            file_count=3,
            primary_extensions=[".new"],
            build_files=[],
            typical_structure="flat",
            conventions={}  # Aucune convention
        )
        
        generator = AdaptiveInstructionGenerator()
        instructions = generator.generate_instructions(lang_info)
        
        # Ne devrait pas planter
        assert instructions.naming_conventions
        # Devrait avoir des instructions génériques
        assert "cohérent" in instructions.naming_conventions.lower()
    
    def test_handles_language_with_no_build_files(self):
        """Test gestion d'un langage sans build files."""
        lang_info = LanguageInfo(
            name="SimpleLang",
            type_id="simplelang",
            confidence=0.8,
            file_count=2,
            primary_extensions=[".sim"],
            build_files=[],  # Aucun build file
            typical_structure="flat",
            conventions={}
        )
        
        text = generate_instructions_for_language(lang_info)
        
        # Ne devrait pas planter
        assert text
        assert "SimpleLang" in text
    
    def test_handles_language_with_multiple_extensions(self):
        """Test gestion d'un langage avec plusieurs extensions."""
        lang_info = LanguageInfo(
            name="MultiExt",
            type_id="multiext",
            confidence=0.9,
            file_count=10,
            primary_extensions=[".ext1", ".ext2", ".ext3"],
            build_files=[],
            typical_structure="standard",
            conventions={}
        )
        
        text = generate_instructions_for_language(lang_info)
        
        # Toutes les extensions devraient être mentionnées
        assert ".ext1" in text
        assert ".ext2" in text
        assert ".ext3" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

