# -*- coding: utf-8 -*-
"""Détecteur intelligent de frameworks de test multi-langages.

Ce module utilise un LLM pour analyser un projet et déterminer automatiquement :
- Le langage du projet
- Le framework de test approprié
- Les commandes de test à exécuter
- Le format des fichiers de test à générer
"""

import os
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
from utils.logger import get_logger
from ai.llm.llm_factory import get_llm_with_fallback

logger = get_logger(__name__)


@dataclass
class TestFrameworkInfo:
    """Informations sur le framework de test détecté."""
    language: str  # java, python, javascript, typescript, go, rust, etc.
    framework: str  # junit, pytest, jest, mocha, go test, cargo test, etc.
    test_file_pattern: str  # Ex: *Test.java, test_*.py, *.test.js
    test_directory: str  # Ex: src/test, tests, __tests__
    test_command: str  # Commande pour exécuter les tests
    build_command: Optional[str]  # Commande de build si nécessaire
    dependencies: List[str]  # Dépendances nécessaires
    file_extension: str  # Extension des fichiers de test
    confidence: float  # Niveau de confiance (0.0 - 1.0)
    

class IntelligentTestDetector:
    """Détecteur intelligent de frameworks de test utilisant un LLM.
    
    Ce détecteur utilise l'IA en PREMIER pour analyser le projet de manière
    intelligente, sans règles hardcodées. Les patterns ne servent que de
    fallback en cas d'échec de l'IA.
    """
    
    # ⚠️ PATTERNS DE FALLBACK UNIQUEMENT (utilisés SI l'IA échoue)
    # L'IA détecte automatiquement les langages/frameworks sans ces règles
    LANGUAGE_INDICATORS = {
        "java": {
            "extensions": [".java"],
            "build_files": ["pom.xml", "build.gradle", "build.gradle.kts"],
            "test_dirs": ["src/test/java", "test", "tests"],
            "frameworks": {
                "junit5": {
                    "indicators": ["@Test", "org.junit.jupiter"],
                    "test_pattern": "*Test.java",
                    "command": "mvn test"
                },
                "junit4": {
                    "indicators": ["@Test", "org.junit.Test"],
                    "test_pattern": "*Test.java",
                    "command": "mvn test"
                },
                "testng": {
                    "indicators": ["@Test", "org.testng"],
                    "test_pattern": "*Test.java",
                    "command": "mvn test"
                }
            }
        },
        "python": {
            "extensions": [".py"],
            "build_files": ["setup.py", "pyproject.toml", "requirements.txt"],
            "test_dirs": ["tests", "test", "__tests__"],
            "frameworks": {
                "pytest": {
                    "indicators": ["pytest", "def test_", "@pytest"],
                    "test_pattern": "test_*.py",
                    "command": "python -m pytest"
                },
                "unittest": {
                    "indicators": ["unittest", "TestCase"],
                    "test_pattern": "test_*.py",
                    "command": "python -m unittest discover"
                }
            }
        },
        "javascript": {
            "extensions": [".js", ".jsx"],
            "build_files": ["package.json"],
            "test_dirs": ["tests", "test", "__tests__", "spec"],
            "frameworks": {
                "jest": {
                    "indicators": ["jest", "describe(", "it(", "test("],
                    "test_pattern": "*.test.js",
                    "command": "npm test"
                },
                "mocha": {
                    "indicators": ["mocha", "describe(", "it("],
                    "test_pattern": "*.spec.js",
                    "command": "npm test"
                }
            }
        },
        "typescript": {
            "extensions": [".ts", ".tsx"],
            "build_files": ["package.json", "tsconfig.json"],
            "test_dirs": ["tests", "test", "__tests__", "spec"],
            "frameworks": {
                "jest": {
                    "indicators": ["jest", "describe(", "it(", "test("],
                    "test_pattern": "*.test.ts",
                    "command": "npm test"
                }
            }
        },
        "go": {
            "extensions": [".go"],
            "build_files": ["go.mod", "go.sum"],
            "test_dirs": [""],  # Tests dans le même répertoire
            "frameworks": {
                "gotest": {
                    "indicators": ["import \"testing\"", "func Test"],
                    "test_pattern": "*_test.go",
                    "command": "go test ./..."
                }
            }
        },
        "rust": {
            "extensions": [".rs"],
            "build_files": ["Cargo.toml"],
            "test_dirs": ["tests"],
            "frameworks": {
                "cargo": {
                    "indicators": ["#[test]", "#[cfg(test)]"],
                    "test_pattern": "*.rs",
                    "command": "cargo test"
                }
            }
        },
        "csharp": {
            "extensions": [".cs"],
            "build_files": ["*.csproj", "*.sln"],
            "test_dirs": ["Tests", "test", "tests"],
            "frameworks": {
                "xunit": {
                    "indicators": ["[Fact]", "[Theory]", "using Xunit"],
                    "test_pattern": "*Test.cs",
                    "command": "dotnet test"
                },
                "nunit": {
                    "indicators": ["[Test]", "using NUnit"],
                    "test_pattern": "*Test.cs",
                    "command": "dotnet test"
                }
            }
        },
        "php": {
            "extensions": [".php"],
            "build_files": ["composer.json"],
            "test_dirs": ["tests", "test"],
            "frameworks": {
                "phpunit": {
                    "indicators": ["PHPUnit", "TestCase", "public function test"],
                    "test_pattern": "*Test.php",
                    "command": "vendor/bin/phpunit"
                }
            }
        },
        "ruby": {
            "extensions": [".rb"],
            "build_files": ["Gemfile"],
            "test_dirs": ["test", "spec"],
            "frameworks": {
                "rspec": {
                    "indicators": ["describe", "it ", "expect("],
                    "test_pattern": "*_spec.rb",
                    "command": "bundle exec rspec"
                },
                "minitest": {
                    "indicators": ["require 'minitest'", "def test_"],
                    "test_pattern": "test_*.rb",
                    "command": "ruby -Itest"
                }
            }
        }
    }
    
    def __init__(self):
        """Initialise le détecteur avec un LLM."""
        self.llm = None
        self.use_anthropic = True
        try:
            # Tenter Anthropic en premier
            from ai.llm.llm_factory import get_llm
            try:
                self.llm = get_llm(
                    provider="anthropic",
                    model="claude-3-5-sonnet-20241022",
                    temperature=0.1,
                    max_tokens=2000
                )
                self.use_anthropic = True
                logger.info("✅ LLM Anthropic initialisé pour détection intelligente de tests")
            except:
                # Fallback sur OpenAI
                self.llm = get_llm(
                    provider="openai",
                    model="gpt-4",
                    temperature=0.1,
                    max_tokens=2000
                )
                self.use_anthropic = False
                logger.info("✅ LLM OpenAI initialisé pour détection intelligente de tests (fallback)")
        except Exception as e:
            logger.warning(f"⚠️ LLM non disponible, utilisation du mode fallback patterns: {e}")
    
    async def detect_test_framework(self, project_path: str) -> TestFrameworkInfo:
        """
        Détecte intelligemment le framework de test pour un projet.
        
        Args:
            project_path: Chemin vers le projet à analyser
            
        Returns:
            TestFrameworkInfo avec les détails du framework détecté
        """
        logger.info(f"🔍 Analyse intelligente du projet: {project_path}")
        
        # 1. Analyser la structure du projet
        project_analysis = self._analyze_project_structure(project_path)
        
        # 2. Si LLM disponible, l'utiliser pour une détection intelligente
        if self.llm:
            try:
                framework_info = await self._detect_with_llm(project_path, project_analysis)
                if framework_info.confidence >= 0.7:
                    logger.info(f"✅ Framework détecté par LLM: {framework_info.framework} ({framework_info.language})")
                    return framework_info
            except Exception as e:
                logger.warning(f"⚠️ Échec détection LLM: {e}, utilisation du fallback")
        
        # 3. Fallback: détection basée sur les patterns
        framework_info = self._detect_with_patterns(project_path, project_analysis)
        logger.info(f"✅ Framework détecté (patterns): {framework_info.framework} ({framework_info.language})")
        
        return framework_info
    
    def _analyze_project_structure(self, project_path: str) -> Dict[str, Any]:
        """Analyse la structure du projet (fichiers, répertoires, contenu)."""
        analysis = {
            "files": [],
            "directories": [],
            "build_files": [],
            "test_files": [],
            "language_stats": {},
            "sample_content": {}
        }
        
        try:
            # Lister les fichiers (limité pour performance)
            for root, dirs, files in os.walk(project_path):
                # Ignorer les répertoires courants
                dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'venv', '__pycache__', 'target', 'build']]
                
                rel_root = os.path.relpath(root, project_path)
                analysis["directories"].append(rel_root)
                
                for file in files[:100]:  # Limiter à 100 fichiers par répertoire
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, project_path)
                    
                    analysis["files"].append(rel_path)
                    
                    # Compter les extensions (ignorer les fichiers de config)
                    ext = Path(file).suffix
                    # Extensions à ignorer (fichiers de configuration, etc.)
                    ignored_extensions = {'.xml', '.json', '.yml', '.yaml', '.toml', '.txt', '.md', 
                                        '.conf', '.properties', '.ini', '.cfg'}
                    
                    if ext and ext.lower() not in ignored_extensions:
                        analysis["language_stats"][ext] = analysis["language_stats"].get(ext, 0) + 1
                        # Debug: log des fichiers importants
                        if ext in [".java", ".py", ".js", ".go", ".ts", ".rs"]:
                            logger.debug(f"  Fichier détecté: {rel_path} (ext: {ext})")
                    
                    # Identifier les fichiers de build
                    if file in ['pom.xml', 'build.gradle', 'package.json', 'Cargo.toml', 'go.mod', 'composer.json', 'Gemfile']:
                        analysis["build_files"].append(rel_path)
                        
                        # Lire le contenu des fichiers de build
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read(5000)  # Limiter à 5KB
                                analysis["sample_content"][rel_path] = content
                        except:
                            pass
                    
                    # Identifier les fichiers de test potentiels
                    if any(pattern in file.lower() for pattern in ['test', 'spec', '_test', '.test']):
                        analysis["test_files"].append(rel_path)
                        
                        # Lire un échantillon de contenu
                        if len(analysis["sample_content"]) < 3:  # Max 3 échantillons
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read(2000)  # Limiter à 2KB
                                    analysis["sample_content"][rel_path] = content
                            except:
                                pass
        
        except Exception as e:
            logger.error(f"Erreur analyse structure: {e}")
        
        return analysis
    
    async def _detect_with_llm(self, project_path: str, project_analysis: Dict[str, Any]) -> TestFrameworkInfo:
        """Utilise le LLM pour détecter INTELLIGEMMENT le framework de test.
        
        Cette méthode permet à l'IA d'analyser le projet sans règles hardcodées.
        L'IA peut détecter :
        - Un ou plusieurs langages (ex: Python + NextJS)
        - Projets monorepo, microservices, etc.
        - N'importe quel framework de test (même nouveaux/inconnus)
        - La meilleure stratégie de test adaptée au projet
        """
        
        # Préparer un contexte RICHE pour l'IA
        file_tree = self._build_file_tree(project_analysis)
        
        context = f"""Tu es un expert en analyse de projets logiciels et en frameworks de test.

🎯 MISSION: Analyse ce projet et détermine INTELLIGEMMENT la meilleure stratégie de test.

📂 STRUCTURE DU PROJET:
{file_tree}

📦 FICHIERS DE BUILD/CONFIG DÉTECTÉS:
{self._format_build_files(project_analysis['build_files'])}

📝 ÉCHANTILLONS DE CODE:
{self._format_samples_detailed(project_analysis['sample_content'])}

📊 STATISTIQUES:
- Total fichiers: {len(project_analysis['files'])}
- Extensions: {dict(list(project_analysis['language_stats'].items())[:15])}
- Répertoires: {len(project_analysis['directories'])}

🧠 TON ANALYSE DOIT:
1. Identifier TOUS les langages du projet (peut être un seul ou plusieurs)
2. Déterminer le type de projet (API REST, NextJS, microservice, monorepo, library, etc.)
3. Identifier quel est le langage PRINCIPAL pour les tests
4. Détecter automatiquement le framework de test utilisé ou recommandé
5. Générer les commandes de test ET de build adaptées au projet réel
6. Être capable de gérer des projets multi-langages (ex: Backend Python + Frontend NextJS)

⚠️ IMPORTANT:
- NE te limite PAS aux frameworks connus (pytest, jest, junit)
- Si le projet utilise un framework custom ou rare, détecte-le
- Pour les projets multi-langages, choisis le langage principal
- Base-toi sur les fichiers de config réels (package.json, pom.xml, etc.)
- Si c'est un projet sans outil de build (ex: Java simple), adapte la commande

🚨 RÈGLES CRITIQUES POUR LA COMMANDE DE TEST:
1. N'utilise QUE des outils de build/test STANDARDS (mvn, npm, pytest, cargo, go test)
2. NE référence JAMAIS de fichiers .jar, .so, .dll ou autres dépendances qui n'existent pas
3. Si le projet n'a PAS de pom.xml → N'utilise PAS "mvn"
4. Si le projet n'a PAS de package.json → N'utilise PAS "npm"
5. Si le projet n'a PAS de Cargo.toml → N'utilise PAS "cargo"
6. Pour Java sans Maven/Gradle → Utilise "echo 'Tests Java nécessitent Maven ou Gradle'"
7. Pour Node.js sans package.json → Utilise "echo 'Tests nécessitent package.json'"
8. PRIORITÉ: Une commande qui échoue proprement > Une commande qui référence des fichiers manquants

💡 EXEMPLES DE COMMANDES SÛRES:
- Projet NextJS AVEC package.json: "npm run test" ou "npm test"
- Projet Python AVEC requirements.txt: "pytest" ou "python -m pytest"
- Projet Java AVEC pom.xml: "mvn test"
- Projet Java SANS pom.xml: "echo 'Tests Java nécessitent Maven/Gradle. Projet non configuré.'"
- Projet Vue.js AVEC package.json: "npm run test:unit" ou "npm test"
- Projet Rust AVEC Cargo.toml: "cargo test"
- Monorepo: Commande du langage principal détecté

📋 RÉPONDS UNIQUEMENT AVEC CE JSON (sans markdown, sans texte avant/après):

{{
  "project_type": "description du type de projet (ex: 'NextJS fullstack app', 'Python REST API', 'Java library', etc.)",
  "languages": ["liste de TOUS les langages détectés, par ordre d'importance"],
  "primary_language": "langage principal pour les tests",
  "framework": "framework de test détecté ou recommandé",
  "test_file_pattern": "pattern des fichiers de test",
  "test_directory": "répertoire des tests détecté",
  "test_command": "commande EXACTE pour exécuter les tests basée sur les fichiers de config",
  "build_command": "commande de build si nécessaire (null sinon)",
  "file_extension": "extension des fichiers de test",
  "confidence": 0.95,
  "reasoning": "courte explication de ta détection (1-2 phrases)"
}}"""

        try:
            logger.info(f"🤖 Envoi de l'analyse au LLM ({'Anthropic' if self.use_anthropic else 'OpenAI'})...")
            
            try:
                response = await self.llm.ainvoke(context)
            except Exception as e:
                # Si Anthropic échoue, tenter OpenAI
                if self.use_anthropic:
                    logger.warning(f"⚠️ Anthropic échoué: {str(e)[:100]}, tentative avec OpenAI...")
                    from ai.llm.llm_factory import get_llm
                    openai_llm = get_llm(provider="openai", model="gpt-4", temperature=0.1)
                    response = await openai_llm.ainvoke(context)
                    logger.info("✅ Fallback OpenAI réussi")
                else:
                    raise
            
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"✅ Réponse LLM reçue: {response_text[:200]}...")
            
            # Nettoyer la réponse (supprimer markdown et texte superflu)
            response_text = response_text.strip()
            
            # Supprimer les blocs markdown
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                parts = response_text.split('```')
                response_text = parts[1] if len(parts) > 1 else parts[0]
            
            response_text = response_text.strip()
            
            # Parser le JSON
            result = json.loads(response_text)
            
            # Extraire le langage principal et normaliser (minuscules)
            primary_lang = result.get("primary_language") or result.get("language") or "unknown"
            primary_lang = primary_lang.lower().strip()  # Normaliser en minuscules
            
            # Normaliser aussi le framework
            framework = result.get("framework", "unknown").lower().replace(" ", "").strip()
            
            logger.info(f"🎯 Projet détecté: {result.get('project_type', 'unknown')}")
            logger.info(f"🔤 Langages: {result.get('languages', [primary_lang])}")
            logger.info(f"🧪 Framework: {framework}")
            logger.info(f"💭 Raisonnement: {result.get('reasoning', 'N/A')}")
            
            return TestFrameworkInfo(
                language=primary_lang,
                framework=framework,
                test_file_pattern=result.get("test_file_pattern", "test_*"),
                test_directory=result.get("test_directory", "tests"),
                test_command=result.get("test_command", ""),
                build_command=result.get("build_command"),
                dependencies=result.get("dependencies", []),
                file_extension=result.get("file_extension", ".test"),
                confidence=float(result.get("confidence", 0.9))
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur parsing JSON: {e}")
            logger.error(f"Réponse brute: {response_text}")
            raise
        except Exception as e:
            logger.error(f"❌ Erreur détection LLM: {e}")
            raise
    
    def _build_file_tree(self, project_analysis: Dict[str, Any]) -> str:
        """Construit une arborescence visuelle du projet."""
        files = project_analysis.get('files', [])[:30]  # Limiter à 30 fichiers
        
        if not files:
            return "❌ Aucun fichier détecté"
        
        tree_lines = ["```"]
        tree_lines.append("projet/")
        
        # Grouper par répertoire
        dirs = {}
        for file in files:
            parts = file.split('/')
            if len(parts) == 1:
                # Fichier à la racine
                if 'root' not in dirs:
                    dirs['root'] = []
                dirs['root'].append(file)
            else:
                # Fichier dans un répertoire
                dir_name = parts[0]
                if dir_name not in dirs:
                    dirs[dir_name] = []
                dirs[dir_name].append('/'.join(parts[1:]))
        
        # Afficher l'arborescence
        for dir_name, dir_files in list(dirs.items())[:10]:
            if dir_name == 'root':
                for file in dir_files[:5]:
                    tree_lines.append(f"├── {file}")
            else:
                tree_lines.append(f"├── {dir_name}/")
                for file in dir_files[:5]:
                    tree_lines.append(f"│   ├── {file}")
                if len(dir_files) > 5:
                    tree_lines.append(f"│   └── ... ({len(dir_files) - 5} more)")
        
        if len(dirs) > 10:
            tree_lines.append(f"└── ... ({len(dirs) - 10} more directories)")
        
        tree_lines.append("```")
        return '\n'.join(tree_lines)
    
    def _format_build_files(self, build_files: List[str]) -> str:
        """Formate les fichiers de build avec leur contenu partiel."""
        if not build_files:
            return "❌ Aucun fichier de build détecté"
        
        formatted = []
        for file in build_files[:5]:
            formatted.append(f"✅ {file}")
        
        if len(build_files) > 5:
            formatted.append(f"... et {len(build_files) - 5} autres")
        
        return '\n'.join(formatted)
    
    def _format_samples_detailed(self, samples: Dict[str, str]) -> str:
        """Formate les échantillons de code de manière détaillée."""
        if not samples:
            return "❌ Aucun échantillon de code disponible"
        
        formatted = []
        for path, content in list(samples.items())[:5]:
            formatted.append(f"\n📄 {path}:")
            formatted.append("```")
            formatted.append(content[:800])  # Plus de contenu pour l'IA
            formatted.append("```")
        
        return '\n'.join(formatted)
    
    def _format_samples(self, samples: Dict[str, str]) -> str:
        """Formate les échantillons de contenu pour le LLM (legacy)."""
        formatted = []
        for path, content in list(samples.items())[:3]:
            formatted.append(f"\n--- {path} ---\n{content[:500]}...")
        return '\n'.join(formatted) if formatted else "Aucun échantillon disponible"
    
    def _detect_with_patterns(self, project_path: str, project_analysis: Dict[str, Any]) -> TestFrameworkInfo:
        """Détection basée sur les patterns (fallback si LLM échoue)."""
        
        # Déterminer le langage dominant
        ext_counts = project_analysis["language_stats"]
        
        # Debug logging
        logger.info(f"🔍 Détection par patterns - extensions trouvées: {ext_counts}")
        logger.info(f"🔍 Fichiers de build: {project_analysis.get('build_files', [])}")
        
        if not ext_counts:
            logger.warning("⚠️ Aucune extension trouvée, utilisation du fallback par défaut")
            return self._get_default_framework()
        
        dominant_ext = max(ext_counts, key=ext_counts.get)
        logger.info(f"🔍 Extension dominante détectée: {dominant_ext}")
        
        # Mapper l'extension au langage
        ext_to_lang = {
            ".java": "java",
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".cs": "csharp",
            ".php": "php",
            ".rb": "ruby"
        }
        
        language = ext_to_lang.get(dominant_ext, "unknown")
        
        if language == "unknown" or language not in self.LANGUAGE_INDICATORS:
            return self._get_default_framework()
        
        lang_info = self.LANGUAGE_INDICATORS[language]
        
        # Détecter le framework en analysant les fichiers de build
        detected_framework = None
        for build_file_path, content in project_analysis["sample_content"].items():
            for framework_name, framework_info in lang_info["frameworks"].items():
                for indicator in framework_info["indicators"]:
                    if indicator in content:
                        detected_framework = framework_name
                        break
                if detected_framework:
                    break
            if detected_framework:
                break
        
        # Si aucun framework détecté, prendre le premier par défaut
        if not detected_framework:
            detected_framework = list(lang_info["frameworks"].keys())[0]
        
        framework_info = lang_info["frameworks"][detected_framework]
        
        # Détecter le répertoire de test
        test_dir = "tests"
        for test_dir_candidate in lang_info["test_dirs"]:
            if any(test_dir_candidate in d for d in project_analysis["directories"]):
                test_dir = test_dir_candidate
                break
        
        return TestFrameworkInfo(
            language=language,
            framework=detected_framework,
            test_file_pattern=framework_info["test_pattern"],
            test_directory=test_dir,
            test_command=framework_info["command"],
            build_command=None,
            dependencies=[],
            file_extension=dominant_ext,
            confidence=0.7
        )
    
    def _get_default_framework(self) -> TestFrameworkInfo:
        """Retourne un framework par défaut (Python/pytest)."""
        return TestFrameworkInfo(
            language="python",
            framework="pytest",
            test_file_pattern="test_*.py",
            test_directory="tests",
            test_command="python -m pytest",
            build_command=None,
            dependencies=["pytest"],
            file_extension=".py",
            confidence=0.5
        )
    
    def get_test_generation_template(self, framework_info: TestFrameworkInfo, file_to_test: str) -> str:
        """
        Génère un template de test approprié pour le framework détecté.
        
        Args:
            framework_info: Informations sur le framework
            file_to_test: Fichier à tester
            
        Returns:
            Template de test adapté au framework
        """
        templates = {
            "junit5": self._get_junit5_template,
            "junit4": self._get_junit4_template,
            "pytest": self._get_pytest_template,
            "jest": self._get_jest_template,
            "gotest": self._get_gotest_template,
            "cargo": self._get_cargo_template
        }
        
        template_func = templates.get(framework_info.framework, self._get_generic_template)
        return template_func(file_to_test)
    
    def _get_junit5_template(self, file_to_test: str) -> str:
        """Template JUnit 5."""
        class_name = Path(file_to_test).stem
        return f"""import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import static org.junit.jupiter.api.Assertions.*;

public class {class_name}Test {{
    
    private {class_name} instance;
    
    @BeforeEach
    public void setUp() {{
        instance = new {class_name}();
    }}
    
    @Test
    public void testBasicFunctionality() {{
        assertNotNull(instance, "{class_name} instance should not be null");
    }}
    
    // TODO: Ajouter des tests spécifiques
}}"""
    
    def _get_junit4_template(self, file_to_test: str) -> str:
        """Template JUnit 4."""
        class_name = Path(file_to_test).stem
        return f"""import org.junit.Test;
import org.junit.Before;
import static org.junit.Assert.*;

public class {class_name}Test {{
    
    private {class_name} instance;
    
    @Before
    public void setUp() {{
        instance = new {class_name}();
    }}
    
    @Test
    public void testBasicFunctionality() {{
        assertNotNull("{class_name} instance should not be null", instance);
    }}
    
    // TODO: Ajouter des tests spécifiques
}}"""
    
    def _get_pytest_template(self, file_to_test: str) -> str:
        """Template pytest."""
        module_name = Path(file_to_test).stem
        return f'''"""Tests pour {module_name}"""
import pytest

def test_{module_name}_exists():
    """Test que le module existe."""
    import {module_name}
    assert {module_name} is not None

# TODO: Ajouter des tests spécifiques
'''
    
    def _get_jest_template(self, file_to_test: str) -> str:
        """Template Jest."""
        module_name = Path(file_to_test).stem
        return f"""import {{ }} from './{module_name}';

describe('{module_name}', () => {{
  it('should exist', () => {{
    expect(true).toBe(true);
  }});
  
  // TODO: Ajouter des tests spécifiques
}});
"""
    
    def _get_gotest_template(self, file_to_test: str) -> str:
        """Template Go testing."""
        return """package main

import "testing"

func TestBasic(t *testing.T) {
    // TODO: Ajouter des tests spécifiques
}
"""
    
    def _get_cargo_template(self, file_to_test: str) -> str:
        """Template Cargo (Rust)."""
        return """#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn it_works() {
        // TODO: Ajouter des tests spécifiques
    }
}
"""
    
    def _get_generic_template(self, file_to_test: str) -> str:
        """Template générique."""
        return f"""// Tests pour {file_to_test}
// TODO: Implémenter les tests
"""

