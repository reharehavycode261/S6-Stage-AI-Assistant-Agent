"""
Générateur d'instructions adaptatif pour la génération de code.

Ce module génère automatiquement des instructions spécifiques au langage
détecté, sans avoir besoin de les coder en dur pour chaque langage.
"""

from typing import Dict, Optional
from dataclasses import dataclass

from utils.language_detector import LanguageInfo
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CodeInstructions:
    """Instructions de génération de code pour un langage."""
    critical_rules: str          # Règles critiques (DOIS/NE DOIS PAS)
    file_structure: str          # Structure des fichiers attendue
    naming_conventions: str      # Conventions de nommage
    best_practices: str          # Bonnes pratiques
    common_pitfalls: str         # Pièges courants à éviter
    example_structure: str       # Exemple de structure de fichier


class AdaptiveInstructionGenerator:
    """
    Générateur adaptatif d'instructions de génération de code.
    
    Génère automatiquement des instructions pertinentes basées sur:
    - Le langage détecté
    - Les conventions du langage
    - La structure du projet
    - Les bonnes pratiques universelles
    """
    
    def generate_instructions(self, language_info: LanguageInfo) -> CodeInstructions:
        """
        Génère des instructions adaptées au langage détecté.
        
        Args:
            language_info: Informations sur le langage détecté
            
        Returns:
            CodeInstructions complètes pour ce langage
        """
        logger.info(f"📝 Génération instructions pour: {language_info.name}")
        
        # Générer chaque section
        critical_rules = self._generate_critical_rules(language_info)
        file_structure = self._generate_file_structure(language_info)
        naming_conventions = self._generate_naming_conventions(language_info)
        best_practices = self._generate_best_practices(language_info)
        common_pitfalls = self._generate_common_pitfalls(language_info)
        example_structure = self._generate_example_structure(language_info)
        
        return CodeInstructions(
            critical_rules=critical_rules,
            file_structure=file_structure,
            naming_conventions=naming_conventions,
            best_practices=best_practices,
            common_pitfalls=common_pitfalls,
            example_structure=example_structure
        )
    
    def _generate_critical_rules(self, lang_info: LanguageInfo) -> str:
        """Génère les règles critiques."""
        extensions = ", ".join([f"`*{ext}`" for ext in lang_info.primary_extensions])
        
        rules = f"""⚠️ RÈGLES CRITIQUES POUR {lang_info.name.upper()}:

1. **LANGAGE**: Tu DOIS générer UNIQUEMENT du code {lang_info.name}
   - NE génère JAMAIS de code dans un autre langage
   - Types de fichiers attendus: {extensions}

2. **EXTENSIONS**: Utilise UNIQUEMENT les extensions correctes
   - Extensions valides: {extensions}
   - ❌ NE PAS utiliser d'autres extensions

3. **STRUCTURE**: Respecte la structure de projet {lang_info.typical_structure}
"""
        
        # Ajouter build files si présents
        if lang_info.build_files:
            build_files = ", ".join([f"`{bf}`" for bf in lang_info.build_files])
            rules += f"""   - Fichiers de build détectés: {build_files}
   - Respecte la configuration de build existante

"""
        
        return rules.strip()
    
    def _generate_file_structure(self, lang_info: LanguageInfo) -> str:
        """Génère la structure de fichiers attendue."""
        structure = f"""📁 STRUCTURE DE FICHIERS {lang_info.name.upper()}:

Type de structure détectée: **{lang_info.typical_structure}**

"""
        
        # Instructions spécifiques selon le type détecté
        if "src/main" in lang_info.typical_structure or "src/test" in lang_info.typical_structure:
            # Structure Java/Maven/Gradle
            structure += """Structure Maven/Gradle standard:
```
src/
  ├── main/
  │   └── [langage]/    # Code principal
  └── test/
      └── [langage]/    # Tests
```

"""
        elif "src" in lang_info.typical_structure:
            # Structure générique avec src/
            structure += """Structure avec src/:
```
src/              # Code source
tests/ ou test/  # Tests (si applicable)
```

"""
        else:
            # Structure plate
            structure += """Structure plate détectée:
- Fichiers à la racine du projet
- Tests possiblement dans un dossier `tests/` ou `test/`

"""
        
        return structure.strip()
    
    def _generate_naming_conventions(self, lang_info: LanguageInfo) -> str:
        """Génère les conventions de nommage."""
        conventions = f"""📝 CONVENTIONS DE NOMMAGE {lang_info.name.upper()}:

"""
        
        # Utiliser les conventions détectées
        if lang_info.conventions:
            for key, value in lang_info.conventions.items():
                conventions += f"- **{key.replace('_', ' ').title()}**: {value}\n"
        else:
            # Conventions génériques
            conventions += """- Analyse le code existant pour identifier les conventions
- Reste cohérent avec les patterns du projet
- Utilise des noms descriptifs et clairs

"""
        
        return conventions.strip()
    
    def _generate_best_practices(self, lang_info: LanguageInfo) -> str:
        """Génère les bonnes pratiques."""
        practices = f"""✅ BONNES PRATIQUES {lang_info.name.upper()}:

1. **Cohérence**: Analyse le code existant et respecte son style
2. **Clarté**: Utilise des noms de variables/fonctions/classes descriptifs
3. **Documentation**: Ajoute des commentaires pour la logique complexe
4. **Tests**: Crée des tests si des fichiers de test existent dans le projet
5. **Build**: Ne modifie PAS les fichiers de build sans nécessité explicite
"""
        
        # Ajouter des pratiques spécifiques si build files détectés
        if lang_info.build_files:
            practices += f"""6. **Configuration**: Fichiers de build détectés ({', '.join(lang_info.build_files[:2])})
   - Respecte la configuration existante
   - Ne modifie que si explicitement requis

"""
        
        return practices.strip()
    
    def _generate_common_pitfalls(self, lang_info: LanguageInfo) -> str:
        """Génère les pièges courants à éviter."""
        pitfalls = f"""⚠️ PIÈGES À ÉVITER {lang_info.name.upper()}:

❌ **NE PAS**:
1. Générer du code dans un autre langage que {lang_info.name}
2. Utiliser des extensions incorrectes (seulement {', '.join(lang_info.primary_extensions)})
3. Ignorer la structure de projet existante ({lang_info.typical_structure})
4. Mélanger les conventions de nommage (reste cohérent)
5. Créer des fichiers dans des emplacements non-standard sans raison
"""
        
        # Avertissement spécifique pour confiance faible
        if lang_info.confidence < 0.7:
            pitfalls += f"""
⚠️ **ATTENTION**: Confiance de détection = {lang_info.confidence:.2f} (< 0.7)
- Vérifie doublement le langage en analysant les fichiers existants
- En cas de doute, demande des clarifications
"""
        
        return pitfalls.strip()
    
    def _generate_example_structure(self, lang_info: LanguageInfo) -> str:
        """Génère un exemple de structure de fichier."""
        ext = lang_info.primary_extensions[0] if lang_info.primary_extensions else ".txt"
        
        example = f"""📄 EXEMPLE DE STRUCTURE DE FICHIER {lang_info.name.upper()}:

Pour un fichier `Example{ext}`:

"""
        
        # Exemples adaptés selon structure typique
        if "src/main" in lang_info.typical_structure:
            example += f"""```
src/main/{lang_info.type_id}/com/example/Example{ext}
src/test/{lang_info.type_id}/com/example/ExampleTest{ext}
```

Avec packages/namespaces appropriés.
"""
        elif "src" in lang_info.typical_structure:
            example += f"""```
src/example{ext}
tests/test_example{ext}  (ou test/ExampleTest{ext})
```

Selon les conventions du projet.
"""
        else:
            example += f"""```
example{ext}           # Code principal
test_example{ext}      # Test correspondant
```

Structure plate, fichiers à la racine.
"""
        
        return example.strip()


def generate_instructions_for_language(language_info: LanguageInfo) -> str:
    """
    Fonction utilitaire pour générer des instructions formatées en texte.
    
    Args:
        language_info: Informations sur le langage détecté
        
    Returns:
        Instructions complètes formatées en texte
        
    Example:
        >>> from utils.language_detector import detect_language
        >>> lang_info = detect_language(["Main.java", "pom.xml"])
        >>> instructions = generate_instructions_for_language(lang_info)
        >>> print(instructions)
    """
    generator = AdaptiveInstructionGenerator()
    instructions = generator.generate_instructions(language_info)
    
    # Formater en texte complet
    text = f"""
# INSTRUCTIONS DE GÉNÉRATION DE CODE - {language_info.name.upper()}

**Langage détecté**: {language_info.name} (confiance: {language_info.confidence:.2f})
**Extensions**: {', '.join(language_info.primary_extensions)}
**Structure**: {language_info.typical_structure}

---

{instructions.critical_rules}

---

{instructions.file_structure}

---

{instructions.naming_conventions}

---

{instructions.best_practices}

---

{instructions.common_pitfalls}

---

{instructions.example_structure}

---

## 🎯 OBJECTIF PRINCIPAL

Génère du code {language_info.name} de haute qualité qui:
1. Respecte STRICTEMENT toutes les règles ci-dessus
2. S'intègre naturellement dans le projet existant
3. Suit les conventions et bonnes pratiques du langage
4. Est maintenable et compréhensible

**RAPPEL FINAL**: Tout le code doit être en **{language_info.name}** avec les extensions **{', '.join(language_info.primary_extensions)}** UNIQUEMENT.
"""
    
    return text.strip()


def get_adaptive_prompt_supplement(language_info: LanguageInfo) -> str:
    """
    Génère un supplément de prompt adaptatif pour l'implémentation.
    
    Version condensée pour inclusion dans les prompts d'implémentation.
    
    Args:
        language_info: Informations sur le langage détecté
        
    Returns:
        Texte condensé pour supplément de prompt
    """
    extensions_str = ", ".join([f"`*{ext}`" for ext in language_info.primary_extensions])
    
    supplement = f"""
## ⚠️ TYPE DE PROJET DÉTECTÉ

**Langage**: {language_info.name} (confiance: {language_info.confidence:.1%})
**Extensions valides**: {extensions_str}
**Structure**: {language_info.typical_structure}

### RÈGLES IMPÉRATIVES:
1. ✅ Génère UNIQUEMENT du code **{language_info.name}**
2. ✅ Utilise UNIQUEMENT les extensions: {extensions_str}
3. ✅ Respecte la structure: {language_info.typical_structure}
4. ❌ NE génère JAMAIS de code dans un autre langage
"""
    
    if language_info.build_files:
        supplement += f"""5. ℹ️  Fichiers de build détectés: {', '.join([f"`{bf}`" for bf in language_info.build_files[:3]])}
"""
    
    if language_info.conventions:
        conv_summary = ", ".join([f"{k}={v}" for k, v in list(language_info.conventions.items())[:2]])
        supplement += f"""6. 📝 Conventions: {conv_summary}
"""
    
    supplement += f"""
### VÉRIFICATION AVANT GÉNÉRATION:
Avant de générer du code, demande-toi:
- ❓ Est-ce que je génère bien du **{language_info.name}** ?
- ❓ Les extensions sont-elles correctes ({extensions_str}) ?
- ❓ La structure respecte-t-elle le projet ({language_info.typical_structure}) ?

Si la réponse à l'une de ces questions est NON, ARRÊTE et corrige.
"""
    
    return supplement.strip()

