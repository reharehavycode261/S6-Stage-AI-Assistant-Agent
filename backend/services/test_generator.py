"""Service de génération automatique de tests intelligents via IA."""

import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from utils.logger import get_logger
from ai.llm.llm_factory import get_default_llm_with_fallback
from utils.language_detector import KNOWN_LANGUAGE_PATTERNS
from utils.test_framework_detector import detect_test_framework, TestFrameworkInfo

logger = get_logger(__name__)


class TestGeneratorService:
    """Service de génération de tests automatiques intelligents."""
    
    def __init__(self):
        """Initialise le générateur de tests avec un modèle LLM."""
        self.llm = get_default_llm_with_fallback(temperature=0.3)
    
    async def generate_tests_for_files(
        self, 
        modified_files: Dict[str, str], 
        working_directory: str,
        requirements: Optional[str] = None,
        framework_info: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Génère des tests pour les fichiers modifiés.
        
        Args:
            modified_files: Dict des fichiers modifiés {path: content}
            working_directory: Répertoire de travail
            requirements: Description des requirements (optionnel)
            framework_info: Informations sur le framework de test détecté (optionnel)
            
        Returns:
            Dict contenant les tests générés et les métadonnées
        """
        if framework_info:
            logger.info(f"🧪 Génération de tests {framework_info.framework} ({framework_info.language}) pour {len(modified_files)} fichiers")
        else:
            logger.info(f"🧪 Génération de tests pour {len(modified_files)} fichiers")
        
        generated_tests = {}
        test_metadata = {
            "total_files": len(modified_files),
            "tests_generated": 0,
            "skipped_files": [],
            "errors": []
        }
        
        for file_path, file_content in modified_files.items():
            try:
                if self._is_test_file(file_path):
                    logger.debug(f"⏭️ Ignorer fichier de test existant: {file_path}")
                    test_metadata["skipped_files"].append(file_path)
                    continue
                
                language = self._detect_language(file_path)
                if not language:
                    logger.warning(f"⚠️ Langage non détecté pour {file_path}")
                    test_metadata["skipped_files"].append(file_path)
                    continue
                
                framework_info = detect_test_framework(working_directory, language)
                
                if not framework_info:
                    logger.warning(f"⚠️ Framework non supporté pour {file_path}")
                    test_metadata["skipped_files"].append(file_path)
                    continue
                
                logger.info(f"🤖 Génération test IA pour {file_path} ({language}/{framework_info.name})")
                test_content = await self._generate_test_with_ai(
                    file_path=file_path,
                    file_content=file_content,
                    framework_info=framework_info,
                    requirements=requirements
                )
                
                if test_content:
                    test_file_path = self._get_test_file_path(file_path, framework_info)
                    generated_tests[test_file_path] = test_content
                    test_metadata["tests_generated"] += 1
                    logger.info(f"✅ Test généré: {test_file_path}")
                else:
                    test_metadata["errors"].append(f"Échec génération test pour {file_path}")
                    
            except Exception as e:
                error_msg = f"Erreur génération test pour {file_path}: {e}"
                logger.error(f"❌ {error_msg}")
                test_metadata["errors"].append(error_msg)
        
        return {
            "generated_tests": generated_tests,
            "metadata": test_metadata,
            "success": test_metadata["tests_generated"] > 0
        }
    
    async def _generate_test_with_ai(
        self,
        file_path: str,
        file_content: str,
        framework_info: TestFrameworkInfo,
        requirements: Optional[str] = None
    ) -> Optional[str]:
        """Génère un test intelligent avec l'IA avec fallback automatique."""
        
        prompt = await self._build_test_generation_prompt(
            file_path=file_path,
            file_content=file_content,
            framework_info=framework_info,
            requirements=requirements
        )
        
        try:
            response = await self.llm.ainvoke(prompt)
            test_content = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            test_content = self._clean_generated_test(test_content, framework_info.language)
            
            if not self._validate_test_content(test_content, framework_info):
                logger.warning(f"⚠️ Test généré invalide pour {file_path}")
                return await self._generate_template_test(file_path, file_content, framework_info)
            
            return test_content
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "credit balance" in error_str or "anthropic" in error_str:
                logger.warning(f"⚠️ Erreur Anthropic pour {file_path}, tentative avec fallback OpenAI...")
                try:
                    from ai.llm.llm_factory import get_llm
                    openai_llm = get_llm(provider="openai", temperature=0.3)
                    response = await openai_llm.ainvoke(prompt)
                    test_content = response.content.strip() if hasattr(response, 'content') else str(response).strip()
                    
                    test_content = self._clean_generated_test(test_content, framework_info.language)
                    if not self._validate_test_content(test_content, framework_info):
                        logger.warning(f"⚠️ Test OpenAI invalide pour {file_path}, utilisation template")
                        return await self._generate_template_test(file_path, file_content, framework_info)
                    
                    logger.info(f"✅ Test généré avec succès via OpenAI fallback pour {file_path}")
                    return test_content
                    
                except Exception as e2:
                    logger.error(f"❌ Erreur OpenAI fallback pour {file_path}: {e2}")
                    return await self._generate_template_test(file_path, file_content, framework_info)
            else:
                logger.error(f"❌ Erreur génération IA pour {file_path}: {e}")
                return await self._generate_template_test(file_path, file_content, framework_info)
    
    async def _build_test_generation_prompt(
        self,
        file_path: str,
        file_content: str,
        framework_info: TestFrameworkInfo,
        requirements: Optional[str] = None
    ) -> str:
        """Construit le prompt pour la génération de tests via IA."""
        
        extracted_items = await self._extract_testable_items(file_content, framework_info.language)
        
        prompt = f"""Tu es un expert en tests unitaires pour {framework_info.language} utilisant {framework_info.name}.

Génère des tests complets et pertinents pour le fichier suivant:

**Fichier**: {file_path}

**Code**:
```{framework_info.language}
{file_content[:2000]}  # Limiter la taille pour éviter les timeouts
```

**Éléments à tester**:
{extracted_items}

**Framework de test**: {framework_info.name}
**Import statement**: {framework_info.import_statement}
**Assertion pattern**: {framework_info.assertion_pattern}
**Test file pattern**: {framework_info.test_file_pattern}

"""
        
        if requirements:
            prompt += f"""
**Requirements du projet**:
{requirements[:500]}

"""
        
        prompt += f"""
**Instructions**:
1. Crée des tests {framework_info.name} complets et professionnels
2. Utilise EXACTEMENT ce pattern d'import: {framework_info.import_statement}
3. Utilise EXACTEMENT ce pattern d'assertion: {framework_info.assertion_pattern}
4. Teste TOUTES les fonctions et classes publiques
5. Inclus des tests positifs ET négatifs (edge cases)
6. Ajoute des assertions claires et descriptives
7. Utilise les meilleures pratiques {framework_info.name}
8. Inclus des mocks/stubs si nécessaire
9. Teste les cas d'erreur avec les exceptions appropriées
10. Ajoute des docstrings/commentaires explicatifs

**Format de sortie**:
Retourne UNIQUEMENT le code du fichier de test, sans markdown, sans explications.
Le code doit être directement exécutable.
Extension attendue: {framework_info.test_file_extension}

Commence le fichier de test maintenant:
"""
        
        return prompt
    
    async def _extract_testable_items(self, file_content: str, language: str) -> str:
        """✨ Extrait les fonctions/classes testables du code (UNIVERSEL avec LLM)."""
        try:
            from ai.llm.llm_factory import get_llm
            import json
            
            prompt = f"""Analyse ce code {language} et liste les éléments testables (publics uniquement).

CODE:
```{language}
{file_content[:1500]}
```

INSTRUCTIONS:
- Liste les classes publiques
- Liste les fonctions/méthodes publiques
- Ignore les éléments privés/internes
- Format: JSON simple

RÉPONDS UNIQUEMENT AVEC CE JSON (sans markdown):
{{
  "classes": ["Class1", "Class2"],
  "functions": ["func1", "func2"]
}}"""

            llm = get_llm(provider="openai", model="gpt-4o-mini", temperature=0)
            response = await llm.ainvoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            response_text = response_text.strip()
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                parts = response_text.split('```')
                response_text = parts[1] if len(parts) > 1 else parts[0]
            
            result = json.loads(response_text.strip())
            
            items = []
            if result.get("classes"):
                items.append(f"- Classes: {', '.join(result['classes'][:10])}")
            if result.get("functions"):
                items.append(f"- Fonctions: {', '.join(result['functions'][:15])}")
            
            return '\n'.join(items) if items else "- Aucun élément public détecté"
            
        except Exception as e:
            logger.debug(f"Extraction LLM échouée, fallback regex: {e}")
            
            classes = re.findall(r'\b(?:class|struct|interface)\s+(\w+)', file_content, re.IGNORECASE)
            functions = re.findall(r'\b(?:def|function|func|fn|pub fn|void|int|string|async)\s+(\w+)\s*\(', file_content, re.IGNORECASE)
            
            public_functions = [f for f in functions if not f.startswith('_') and f[0].isupper() or not f.startswith('_')]
            
            items = []
            if classes:
                items.append(f"- Classes: {', '.join(list(set(classes))[:10])}")
            if public_functions:
                items.append(f"- Fonctions: {', '.join(list(set(public_functions))[:15])}")
            
            return '\n'.join(items) if items else "- Éléments détectés (regex basique)"
    
    def _clean_generated_test(self, test_content: str, language: str) -> str:
        """Nettoie le test généré par l'IA."""
        
        test_content = re.sub(r'^```\w*\n', '', test_content)
        test_content = re.sub(r'\n```$', '', test_content)
        test_content = test_content.strip()
        
        return test_content
    
    def _validate_test_content(self, test_content: str, framework_info: TestFrameworkInfo) -> bool:
        """Valide que le test généré contient des assertions."""
        
        assertion_pattern = framework_info.assertion_pattern
        
        keywords = re.findall(r'\b\w+\b', assertion_pattern)
        
        if not keywords:
            keywords = ['assert']
        
        for keyword in keywords:
            pattern = rf'\b{re.escape(keyword)}\b'
            if re.search(pattern, test_content, re.IGNORECASE):
                return True
        
        logger.warning(f"⚠️ Aucune assertion trouvée dans le test généré (framework: {framework_info.name})")
        return False
    
    async def _generate_template_test(
        self,
        file_path: str,
        file_content: str,
        framework_info: TestFrameworkInfo
    ) -> str:
        """Génère un test basique générique (fallback)."""
        
        return await self._get_generic_template(file_path, file_content, framework_info)
    
    async def _get_generic_template(
        self,
        file_path: str,
        file_content: str,
        framework_info: TestFrameworkInfo
    ) -> str:
        """
        ✨ Template générique UNIVERSEL basé sur LLM.
        Fonctionne pour N'IMPORTE QUEL langage/framework.
        """
        
        module_name = Path(file_path).stem
        language = framework_info.language
        framework = framework_info.name
        
        try:
            from ai.llm.llm_factory import get_llm
            
            prompt = f"""Génère un template de test BASIQUE et GÉNÉRIQUE pour ce fichier.

FICHIER: {file_path}
LANGAGE: {language}
FRAMEWORK: {framework}
IMPORTS: {framework_info.import_statement}
ASSERTION: {framework_info.assertion_pattern}

CODE (extrait):
```{language}
{file_content[:800]}
```

INSTRUCTIONS:
1. Génère UN test basique fonctionnel
2. Utilise le format du framework: {framework}
3. Inclus les imports nécessaires
4. Ajoute des commentaires TODO pour compléter
5. N'invente PAS de fonctions qui n'existent pas
6. Garde-le SIMPLE (10-20 lignes max)

RÉPONDS UNIQUEMENT AVEC LE CODE DU TEST (pas de markdown, pas d'explication):"""

            llm = get_llm(provider="openai", model="gpt-4o-mini", temperature=0.2)
            response = await llm.ainvoke(prompt)
            test_code = response.content if hasattr(response, 'content') else str(response)
            
            test_code = test_code.strip()
            if '```' in test_code:
                parts = test_code.split('```')
                for part in parts:
                    if language.lower() in part.lower() or 'code' in part.lower():
                        continue
                    if part.strip() and not part.startswith(language):
                        test_code = part.strip()
                        break
            
            logger.info(f"✅ Template LLM généré pour {language}/{framework}")
            return test_code
            
        except Exception as e:
            logger.warning(f"⚠️ Génération LLM template échouée, fallback basique: {e}")
            
        header = f"""/**
 * Tests pour {file_path}
 * Langage: {language} | Framework: {framework}
 * Généré automatiquement - À compléter
 */

"""
        imports = f"{framework_info.import_statement}\n\n"
        
        assertion_keyword = framework_info.assertion_pattern.split('(')[0].strip()
        
        body = f"""
// Test basique généré automatiquement pour {module_name}
// Framework: {framework} | Langage: {language}
// TODO: Compléter avec des tests spécifiques

function test_basic() {{
    // Exemple d'assertion: {framework_info.assertion_pattern}
    // TODO: Ajouter vos tests ici
    {assertion_keyword}(true);  // Test placeholder
}}
"""
        
        return header + imports + body
    
    def _is_test_file(self, file_path: str) -> bool:
        """Vérifie si le fichier est déjà un fichier de test."""
        
        test_patterns = [
            r'test_.*\.py$',
            r'.*_test\.py$',
            r'.*\.test\.(js|ts|jsx|tsx)$',
            r'.*\.spec\.(js|ts|jsx|tsx)$',
            r'tests?/.*\.py$',
            r'__tests__/.*\.(js|ts|jsx|tsx)$'
        ]
        
        return any(re.search(pattern, file_path) for pattern in test_patterns)
    
    def _detect_language(self, file_path: str) -> Optional[str]:
        """
        Détecte le langage basé sur l'extension du fichier.
        Utilise KNOWN_LANGUAGE_PATTERNS au lieu d'un dictionnaire codé en dur.
        """
        
        ext = Path(file_path).suffix.lower()
        
        if not ext:
            return None
        
        for pattern in KNOWN_LANGUAGE_PATTERNS:
            if ext in pattern.extensions:
                return pattern.type_id
        
        logger.debug(f"Extension {ext} non reconnue dans les patterns connus")
        return None
    
    def _get_test_file_path(self, source_file: str, framework_info: TestFrameworkInfo) -> str:
        """
        Génère le chemin du fichier de test basé sur TestFrameworkInfo.
        Utilise le pattern de nommage du framework détecté.
        """
        
        source_path = Path(source_file)
        module_name = source_path.stem
        
        test_file_pattern = framework_info.test_file_pattern

        test_name = test_file_pattern.replace("{module}", module_name)
        test_name = test_name.replace("{Module}", module_name)
        
        return str(source_path.parent / test_name)
    
    async def write_test_files(
        self,
        generated_tests: Dict[str, str],
        working_directory: str
    ) -> Dict[str, Any]:
        """Écrit les fichiers de test générés sur le disque."""
        
        results = {
            "files_written": [],
            "errors": []
        }
        
        for test_file_path, test_content in generated_tests.items():
            try:
                full_path = Path(working_directory) / test_file_path
                
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(test_content)
                
                results["files_written"].append(str(full_path))
                logger.info(f"✅ Fichier de test écrit: {full_path}")
                
            except Exception as e:
                error_msg = f"Erreur écriture {test_file_path}: {e}"
                logger.error(f"❌ {error_msg}")
                results["errors"].append(error_msg)
        
        return results

