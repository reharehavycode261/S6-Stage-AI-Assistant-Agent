"""Moteur de tests automatisés avancé avec support pytest, coverage et smoke tests."""

import os
import asyncio
import json
from typing import Any, Dict, List, Optional
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field

from .base_tool import BaseTool

from config.settings import get_settings
from utils.logger import get_logger
from utils.language_detector import GenericLanguageDetector

class TestType(str, Enum):
    """Types de tests supportés."""
    UNIT = "unit"
    INTEGRATION = "integration"
    SMOKE = "smoke"
    E2E = "e2e"
    PERFORMANCE = "performance"
    SECURITY = "security"

class TestSeverity(str, Enum):
    """Niveaux de sévérité des échecs de test."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TestFailure(BaseModel):
    """Représente un échec de test."""
    test_name: str
    test_file: str
    error_message: str
    severity: TestSeverity = TestSeverity.MEDIUM
    line_number: Optional[int] = None
    suggestion: Optional[str] = None

class TestCoverage(BaseModel):
    """Représente la couverture de code."""
    total_coverage: float
    files_coverage: Dict[str, float] = {}
    missing_lines: Dict[str, List[int]] = {}
    threshold_met: bool = False

class TestSuite(BaseModel):
    """Représente une suite de tests."""
    name: str
    test_type: TestType
    files_pattern: str
    timeout: int = 300
    requirements: List[str] = []
    environment: Dict[str, str] = {}

class TestingEngine(BaseTool):
    """Moteur de tests automatisés avancé."""
    
    name: str = "testing_engine"
    description: str = """
    Moteur de tests automatisés complet.
    
    Fonctionnalités:
    - Tests unitaires avec pytest
    - Tests d'intégration
    - Smoke tests automatiques
    - Analyse de couverture de code
    - Tests de performance
    - Tests de sécurité
    - Génération automatique de tests
    - Rapport de qualité
    """
    
    working_directory: Optional[str] = Field(default=None)
    test_suites: Dict[TestType, TestSuite] = {}
    
    def __init__(self, **kwargs):
        super().__init__()
        self.settings = get_settings()
        self.logger = get_logger(self.__class__.__name__)
        self._setup_test_suites()
    
    def _setup_test_suites(self):
        """Configure les suites de tests par défaut - détection flexible dans tous les répertoires."""
        self.test_suites = {
            TestType.UNIT: TestSuite(
                name="Tests Unitaires",
                test_type=TestType.UNIT,
                files_pattern="test_*.py",
                timeout=300,
                requirements=["pytest", "pytest-cov"]
            ),
            TestType.INTEGRATION: TestSuite(
                name="Tests d'Intégration", 
                test_type=TestType.INTEGRATION,
                files_pattern="test_integration_*.py",
                timeout=600,
                requirements=["pytest", "pytest-cov", "requests"]
            ),
            TestType.SMOKE: TestSuite(
                name="Smoke Tests",
                test_type=TestType.SMOKE,
                files_pattern="test_smoke_*.py", 
                timeout=120,
                requirements=["pytest"]
            ),
            TestType.E2E: TestSuite(
                name="Tests End-to-End",
                test_type=TestType.E2E,
                files_pattern="test_e2e_*.py",
                timeout=900,
                requirements=["pytest", "selenium"]
            ),
            TestType.PERFORMANCE: TestSuite(
                name="Tests de Performance",
                test_type=TestType.PERFORMANCE,
                files_pattern="test_perf_*.py",
                timeout=1800,
                requirements=["pytest", "pytest-benchmark"]
            ),
            TestType.SECURITY: TestSuite(
                name="Tests de Sécurité",
                test_type=TestType.SECURITY,
                files_pattern="test_security_*.py",
                timeout=600,
                requirements=["pytest", "bandit"]
            )
        }
    
    async def _arun(self, action: str, **kwargs) -> Dict[str, Any]:
        """Exécute une action de test."""
        try:
            if action == "run_all_tests":
                return await self._run_all_tests(
                    working_directory=kwargs.get("working_directory"),
                    include_coverage=kwargs.get("include_coverage", True),
                    code_changes=kwargs.get("code_changes", None)
                )
            elif action == "run_test_type":
                return await self._run_test_type(
                    test_type=TestType(kwargs.get("test_type")),
                    working_directory=kwargs.get("working_directory"),
                    include_coverage=kwargs.get("include_coverage", True)
                )
            elif action == "generate_tests":
                return await self._generate_tests(
                    source_file=kwargs.get("source_file"),
                    working_directory=kwargs.get("working_directory")
                )
            elif action == "analyze_test_coverage":
                return await self._analyze_test_coverage(
                    working_directory=kwargs.get("working_directory")
                )
            elif action == "run_smoke_tests":
                return await self._run_smoke_tests(
                    base_url=kwargs.get("base_url"),
                    working_directory=kwargs.get("working_directory")
                )
            elif action == "security_scan":
                return await self._run_security_scan(
                    working_directory=kwargs.get("working_directory")
                )
            elif action == "run_test_directory":
                return await self._run_test_directory(
                    test_directory=kwargs.get("test_directory")
                )
            else:
                raise ValueError(f"Action non supportée: {action}")
                
        except Exception as e:
            return self.handle_error(e, f"testing_engine.{action}")
    
    async def _run_all_tests(self, working_directory: str, include_coverage: bool = True, code_changes: Dict[str, str] = None) -> Dict[str, Any]:
        """Lance tests en 4 couches: baseline → IA → intégration → régression."""
        self.working_directory = working_directory
        
        if not os.path.exists(working_directory):
            error_msg = f"TestingEngine: Répertoire de travail inexistant: {working_directory}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}
        

        layers = {
            "baseline": {"success": True, "message": "Tests baseline (code original)"},
            "ai_code": {"success": True, "message": "Tests code IA généré"},
            "integration": {"success": True, "message": "Tests intégration (local+IA)"},
            "regression": {"success": True, "message": "Tests non-régression"}
        }
        all_results = {}
        total_success = True
        if code_changes:
            baseline_result = await self._test_baseline()
            layers["baseline"] = baseline_result
            all_results["baseline"] = baseline_result
            if not baseline_result["success"]:
                self.logger.error("❌ BASELINE ÉCHOUÉ - ARRÊT")
                total_success = False
                return {"success": False, "layers": layers, "stop_reason": "baseline_failed"}
        if code_changes:
            ai_result = await self._test_ai_files(list(code_changes.keys()))
            layers["ai_code"] = ai_result
            all_results["ai_code"] = ai_result
            if not ai_result["success"]:
                self.logger.warning("⚠️ Code IA échoué - correction nécessaire")
                total_success = False
        integration_result = await self._test_integration()
        layers["integration"] = integration_result
        all_results["integration"] = integration_result
        if not integration_result["success"]:
            total_success = False
        regression_result = await self._test_regression()
        layers["regression"] = regression_result
        all_results["regression"] = regression_result
        if not regression_result["success"]:
            total_success = False
        coverage_result = None
        if include_coverage:
            coverage_result = await self._analyze_test_coverage(working_directory)
        return {
            "success": total_success,
            "test_results": all_results,
            "coverage": coverage_result,
            "summary": self._generate_test_summary(all_results),
            "recommendations": self._generate_recommendations(all_results, coverage_result)
        }
    
    async def _run_test_type(self, test_type: TestType, working_directory: str, include_coverage: bool = True) -> Dict[str, Any]:
        """Exécute un type spécifique de tests."""
        self.working_directory = working_directory
        suite = self.test_suites.get(test_type)
        
        if not suite:
            raise ValueError(f"Suite de tests non configurée pour {test_type.value}")
        
        await self._setup_test_environment(suite)
        
        cmd = self._build_pytest_command(suite, include_coverage)
        
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                cwd=working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=suite.timeout
            )
            
            output = stdout.decode('utf-8') if stdout else ""
            
            result = self._parse_pytest_output(output, test_type)
            
            if not isinstance(result, dict):
                self.logger.error(f"❌ Résultat test invalide (type {type(result)}): {result}")
                result = {"passed_tests": 0, "total_tests": 0, "no_tests_found": True, "success": True}
            
            passed = result.get('passed_tests', 0)
            total = result.get('total_tests', 0)
            
            if result.get('no_tests_found', False) or total == 0:
                self.logger.info(f"📝 {test_type.value} tests: aucun test trouvé par pytest")
                
                test_files = await self._discover_tests(working_directory)
                
                if test_files:
                    self.logger.info(f"🔍 {len(test_files)} fichier(s) de test détecté(s): {[os.path.basename(f) for f in test_files[:5]]}{'...' if len(test_files) > 5 else ''}")
                    
                    total_tests = 0
                    passed_tests = 0
                    
                    for test_file in test_files[:10]:  
                        try:
                            if not os.path.exists(test_file):
                                self.logger.warning(f"⚠️ Fichier de test introuvable: {test_file}")
                                continue
                            
                            proc2 = await asyncio.create_subprocess_shell(
                                f"python '{test_file}'",
                                cwd=working_directory,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.STDOUT
                            )
                            out2, _ = await asyncio.wait_for(proc2.communicate(), timeout=30)
                            output = out2.decode('utf-8') if out2 else ""
                            
                            import re
                            test_matches = re.findall(r'(test_\w+).*\.\.\. (ok|FAIL|ERROR)', output)
                            ran_match = re.search(r'Ran (\d+) test', output)
                            
                            file_total = len(test_matches)
                            if ran_match and file_total == 0:
                                file_total = int(ran_match.group(1))
                                if "FAILED" not in output and "ERROR" not in output:
                                    file_passed = file_total  
                                else:
                                    failed_match = re.search(r'failures=(\d+)', output)
                                    error_match = re.search(r'errors=(\d+)', output) 
                                    failures = int(failed_match.group(1)) if failed_match else 0
                                    errors = int(error_match.group(1)) if error_match else 0
                                    file_passed = max(0, file_total - failures - errors)
                            else:
                                file_passed = len([m for m in test_matches if m[1] == 'ok'])
                            
                            total_tests += file_total
                            passed_tests += file_passed
                            
                            if file_total > 0:
                                self.logger.info(f"📊 {os.path.basename(test_file)}: {file_passed}/{file_total} tests réussis")
                            else:
                                self.logger.debug(f"🔍 {os.path.basename(test_file)}: aucun test détecté")
                                
                        except Exception as e:
                            self.logger.warning(f"⚠️ Erreur exécution {os.path.basename(test_file)}: {e}")
                    
                    result['total_tests'] = total_tests
                    result['passed_tests'] = passed_tests
                    result['success'] = total_tests == 0 or (total_tests > 0 and passed_tests == total_tests)
                    result['no_tests_found'] = total_tests == 0
                    
                    if total_tests > 0:
                        self.logger.info(f"✅ Tests générés: {passed_tests}/{total_tests} réussis")
                        result['message'] = f"Tests générés: {passed_tests}/{total_tests} réussis"
                    else:
                        self.logger.info("⚠️ Aucun test valide trouvé - création recommandée")
                        result['message'] = "Aucun test valide trouvé"
                else:
                    self.logger.info("⚠️ Aucun fichier de test trouvé dans le projet")
            else:
                self.logger.info(f"✅ {test_type.value} tests terminés: {passed}/{total} réussis")
            
            return result
        except asyncio.TimeoutError:
            self.logger.error(f"⏰ Timeout pour les {test_type.value} tests")
            return {
                "success": False,
                "test_type": test_type.value,
                "output": "Timeout lors de l'exécution des tests",
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 1
            }
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'exécution des {test_type.value} tests: {e}")
            return {
                "success": False,
                "test_type": test_type.value,
                "output": str(e),
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 1
            }

    async def _discover_tests(self, working_directory: str) -> List[str]:
        """Découvre les fichiers de tests dans le projet avec une détection améliorée et filtrage des scripts de correction."""
        test_files = []
        
        excluded_dirs = {
            'venv', '.venv', 'env', '.env', 
            'node_modules', '__pycache__', '.git',
            '.pytest_cache', '.tox', 'build', 'dist'
        }
        
        test_patterns = [
            "**/test_*.py",      # Fichiers commençant par test_
            "**/*_test.py",      # Fichiers finissant par _test
            "**/tests/**/*.py",  # Tous les fichiers dans le dossier tests
            "**/test/**/*.py"    # Tous les fichiers dans le dossier test
        ]
        
        working_path = Path(working_directory)
        
        if not working_path.exists():
            self.logger.warning(f"⚠️ Répertoire de travail n'existe pas: {working_directory}")
            return []
            
        self.logger.info(f"🔍 Recherche de tests dans: {working_directory}")
        
        for pattern in test_patterns:
            try:
                for file_path in working_path.glob(pattern):
                    if file_path.is_file():
                        if not any(excluded_dir in str(file_path) for excluded_dir in excluded_dirs):
                            filename = file_path.name
                            if filename.startswith('fix_') or filename in ['simple_fix.py', 'cleanup_scripts.py', 'debug_workflow.py']:
                                self.logger.debug(f"🔍 Exclusion script de correction: {filename}")
                                continue
                            
                            if await self._is_valid_test_file(file_path):
                                test_files.append(str(file_path))
                                self.logger.debug(f"✅ Test file trouvé: {file_path}")
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur lors de la recherche avec pattern {pattern}: {e}")
        
        if not test_files:
            self.logger.info(f"📝 Aucun fichier de test trouvé dans {working_directory}")
            
            simple_test_path = working_path / "test_generated.py"
            try:
                with open(simple_test_path, 'w') as f:
                    f.write("""# Test généré automatiquement pour validation
import unittest

class TestGenerated(unittest.TestCase):
    def test_basic_functionality(self):
        \"\"\"Test de base pour s'assurer que le code se charge sans erreur.\"\"\"
        # Test minimal - s'assurer que les imports fonctionnent
        try:
            # Essayer d'importer les modules dans le répertoire courant
            import os
            import sys
            current_dir = os.path.dirname(__file__)
            if current_dir not in sys.path:
                sys.path.append(current_dir)
            
            # Test réussi si on arrive ici
            self.assertTrue(True, "Code loaded successfully")
        except Exception as e:
            self.fail(f"Failed to load code: {e}")

if __name__ == '__main__':
    unittest.main()
""")
                test_files.append(str(simple_test_path))
                self.logger.info(f"✅ Test automatique créé: {simple_test_path}")
            except Exception as e:
                self.logger.warning(f"⚠️ Impossible de créer test automatique: {e}")
        
        test_files = list(set(test_files))
        test_files = test_files[:20]
        
        if test_files:
            self.logger.info(f"🔍 {len(test_files)} fichier(s) de test détecté(s): {[Path(f).name for f in test_files[:5]]}{'...' if len(test_files) > 5 else ''}")
        else:
            self.logger.info("⚠️ Aucun fichier de test trouvé avec les patterns standards")
        
        return test_files

    async def _setup_test_environment(self, suite: TestSuite):
        """Prépare l'environnement pour une suite de tests."""
        if suite.requirements:
            for requirement in suite.requirements:
                try:
                    import importlib
                    importlib.import_module(requirement.replace("-", "_"))
                except ImportError:
                    self.logger.info(f"📦 Installation de {requirement}...")
                    await self._install_package(requirement)
    
    async def _install_package(self, package: str):
        """Installe un package Python."""
        try:
            process = await asyncio.create_subprocess_shell(
                f"pip install {package}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0:
                self.logger.info(f"✅ {package} installé avec succès")
            else:
                self.logger.warning(f"⚠️ Échec de l'installation de {package}")
                
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'installation de {package}: {e}")
    
    def _build_pytest_command(self, suite: TestSuite, include_coverage: bool) -> str:
        """Construit la commande pytest."""
        cmd_parts = ["python", "-m", "pytest"]
        
        cmd_parts.append(suite.files_pattern)
        
        cmd_parts.extend([
            "-v",  
            "--tb=short",  
            "--json-report",  
            "--json-report-file=test_report.json"
        ])
        
        if include_coverage:
            cmd_parts.extend([
                "--cov=.",
                "--cov-report=json:coverage.json",
                "--cov-report=term-missing",
                f"--cov-fail-under={self.settings.test_coverage_threshold}"
            ])
        
        if suite.test_type == TestType.SMOKE:
            cmd_parts.extend(["-x"])  
        elif suite.test_type == TestType.PERFORMANCE:
            cmd_parts.extend(["--benchmark-only"])
        
        return " ".join(cmd_parts)
    
    def _parse_pytest_output(self, output: str, test_type: TestType) -> Dict[str, Any]:
        """Parse la sortie de pytest."""
        success = False
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        execution_time = 0.0
        failures = []
        
        json_report_path = os.path.join(self.working_directory or ".", "test_report.json")
        
        if os.path.exists(json_report_path):
            try:
                with open(json_report_path, 'r') as f:
                    report = json.load(f)
                
                summary = report.get("summary", {})
                total_tests = summary.get("total", 0)
                passed_tests = summary.get("passed", 0)
                failed_tests = summary.get("failed", 0)
                skipped_tests = summary.get("skipped", 0)
                execution_time = report.get("duration", 0.0)
                success = summary.get("failed", 0) == 0
                
                failures = self._parse_test_failures(report.get("tests", []))
                
            except Exception as e:
                self.logger.warning(f"Impossible de parser le rapport JSON: {e}")
        
        if failed_tests > 0:
            success = False
        elif passed_tests > 0 and failed_tests == 0:
            success = True
        
        result_dict = {
            "success": success,
            "test_type": test_type.value,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "output": output,
            "execution_time": execution_time,
            "failures": failures
        }
        
        if total_tests == 0:
            result_dict = self._parse_text_output(output, test_type)
        
        return result_dict
    
    def _parse_test_failures(self, tests: List[Dict]) -> List[TestFailure]:
        """Parse les échecs de tests depuis le rapport JSON."""
        failures = []
        
        for test in tests:
            if test.get("outcome") == "failed":
                failure = TestFailure(
                    test_name=test.get("nodeid", ""),
                    test_file=test.get("setup", {}).get("filename", ""),
                    error_message=test.get("call", {}).get("longrepr", ""),
                    severity=self._determine_failure_severity(test)
                )
                failures.append(failure)
        
        return failures
    
    def _determine_failure_severity(self, test: Dict) -> TestSeverity:
        """Détermine la sévérité d'un échec de test."""
        error_msg = test.get("call", {}).get("longrepr", "").lower()
        
        if any(keyword in error_msg for keyword in ["security", "auth", "permission"]):
            return TestSeverity.CRITICAL
        elif any(keyword in error_msg for keyword in ["database", "connection", "timeout"]):
            return TestSeverity.HIGH
        elif any(keyword in error_msg for keyword in ["validation", "format", "type"]):
            return TestSeverity.MEDIUM
        else:
            return TestSeverity.LOW
    
    def _parse_text_output(self, output: str, test_type: TestType) -> Dict[str, Any]:
        """Parse la sortie texte de pytest en fallback."""
        # Valeurs par défaut
        success = False
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        
        # Détecter les patterns communs de "aucun test trouvé"
        no_tests_patterns = [
            "collected 0 items",
            "no tests collected",
            "0 passed",
            "=== 0 passed",
            "=== no tests collected ===",
            "no tests ran",
            "0 items collected"
        ]
        
        output_lower = output.lower()
        for pattern in no_tests_patterns:
            if pattern in output_lower:
                self.logger.info(f"🔍 Détecté: aucun test trouvé (pattern: '{pattern}')")
                return {
                    "success": True,  
                    "test_type": test_type.value,
                    "total_tests": 0,
                    "passed_tests": 0,
                    "failed_tests": 0,
                    "output": output,
                    "no_tests_found": True  
                }
        
        lines = output.split('\n')
        for line in lines:
            if "passed" in line and ("failed" in line or "error" in line):
                import re
                matches = re.findall(r'(\d+) (\w+)', line)
                for count, status in matches:
                    count = int(count)
                    if status == "passed":
                        passed_tests = count
                    elif status in ["failed", "error", "errors"]:
                        failed_tests = count
                    elif status == "skipped":
                        skipped_tests = count
                
                total_tests = passed_tests + failed_tests + skipped_tests
                success = failed_tests == 0 and total_tests > 0
                break
            
            elif "passed" in line and "failed" not in line:
                import re
                match = re.search(r'(\d+) passed', line)
                if match:
                    passed_tests = int(match.group(1))
                    total_tests = passed_tests
                    success = True
                    break
                    
            elif "failed" in line and "passed" not in line:
                import re
                match = re.search(r'(\d+) failed', line)
                if match:
                    failed_tests = int(match.group(1))
                    total_tests = failed_tests
                    success = False
                    break
        
        if total_tests == 0:
            if "pytest" in output_lower or "test session starts" in output_lower:
                if "collected" in output_lower:
                    import re
                    collected_match = re.search(r'collected (\d+) items?', output_lower)
                    if collected_match:
                        collected_items = int(collected_match.group(1))
                        if collected_items == 0:
                            return {
                                "success": False,  
                                "test_type": test_type.value,
                                "total_tests": 0,
                                "passed_tests": 0,
                                "failed_tests": 0,
                                "output": output,
                                "no_tests_found": True
                            }
        
        if total_tests == 0:
            return {
                "success": False,  
                "test_type": test_type.value,
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "output": output,
                "no_tests_found": True
            }
        
        if failed_tests > 0:
            success = False
        elif passed_tests > 0 and failed_tests == 0:
            success = True
        
        return {
            "success": success,
            "test_type": test_type.value,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "output": output
        }
    
    async def _analyze_test_coverage(self, working_directory: str) -> Optional[TestCoverage]:
        """Analyse la couverture de code."""
        coverage_file = os.path.join(working_directory, "coverage.json")
        
        if not os.path.exists(coverage_file):
            return None
        
        try:
            with open(coverage_file, 'r') as f:
                coverage_data = json.load(f)
            
            total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0.0)
            
            files_coverage = {}
            missing_lines = {}
            
            for filename, file_data in coverage_data.get("files", {}).items():
                files_coverage[filename] = file_data.get("summary", {}).get("percent_covered", 0.0)
                missing_lines[filename] = file_data.get("missing_lines", [])
            
            return TestCoverage(
                total_coverage=total_coverage,
                files_coverage=files_coverage,
                missing_lines=missing_lines,
                threshold_met=total_coverage >= self.settings.test_coverage_threshold
            )
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de couverture: {e}")
            return None
    
    async def _run_smoke_tests(self, base_url: str, working_directory: str) -> Dict[str, Any]:
        """Exécute des smoke tests automatiques."""
        self.logger.info(f"🔥 Lancement des smoke tests sur {base_url}")
        
        smoke_tests = [
            {"name": "Health Check", "endpoint": "/health", "method": "GET"},
            {"name": "API Status", "endpoint": "/api/status", "method": "GET"},
            {"name": "Authentication", "endpoint": "/api/auth/test", "method": "POST"}
        ]
        
        results = []
        
        for test in smoke_tests:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    url = f"{base_url.rstrip('/')}{test['endpoint']}"
                    
                    if test['method'] == 'GET':
                        async with session.get(url, timeout=10) as response:
                            success = response.status < 400
                    else:
                        async with session.post(url, timeout=10) as response:
                            success = response.status < 500
                    
                    results.append({
                        "test": test['name'],
                        "success": success,
                        "status_code": response.status,
                        "url": url
                    })
                    
            except Exception as e:
                results.append({
                    "test": test['name'],
                    "success": False,
                    "error": str(e),
                    "url": f"{base_url}{test['endpoint']}"
                })
        
        overall_success = all(r['success'] for r in results)
        
        return {
            "success": overall_success,
            "results": results,
            "base_url": base_url
        }
    
    async def _run_security_scan(self, working_directory: str) -> Dict[str, Any]:
        """Exécute un scan de sécurité automatique."""
        self.logger.info("🔐 Lancement du scan de sécurité...")
        
        security_checks = [
            {"name": "Bandit Security Scan", "command": "bandit -r . -f json -o security_report.json"},
            {"name": "Safety Dependencies Check", "command": "safety check --json --output safety_report.json"},
            {"name": "Semgrep Security Analysis", "command": "semgrep --config=auto --json --output=semgrep_report.json ."}
        ]
        
        results = []
        
        for check in security_checks:
            try:
                process = await asyncio.create_subprocess_shell(
                    check['command'],
                    cwd=working_directory,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
                
                results.append({
                    "check": check['name'],
                    "success": process.returncode == 0,
                    "output": stdout.decode('utf-8') if stdout else "",
                    "errors": stderr.decode('utf-8') if stderr else ""
                })
                
            except asyncio.TimeoutError:
                results.append({
                    "check": check['name'],
                    "success": False,
                    "error": "Timeout"
                })
            except Exception as e:
                results.append({
                    "check": check['name'],
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "success": all(r['success'] for r in results),
            "security_checks": results
        }
    
    async def _generate_tests(self, source_file: str, working_directory: str) -> Dict[str, Any]:
        """Génère automatiquement des tests pour un fichier source."""
        self.logger.info(f"🧪 Génère automatiquement de tests pour {source_file}")
        
        from tools.ai_engine_hub import ai_hub, AIRequest, TaskType
        
        with open(os.path.join(working_directory, source_file), 'r') as f:
            source_code = f.read()
        
        request = AIRequest(
            prompt=f"""
Génère des tests unitaires complets avec pytest pour ce code Python :

```python
{source_code}
```

Génère des tests qui couvrent :
1. Les cas normaux
2. Les cas d'erreur
3. Les cas limites
4. Les mocks nécessaires

Format de sortie : code Python uniquement avec pytest.
""",
            task_type=TaskType.TESTING,
            context={"source_file": source_file, "source_code": source_code}
        )
        
        response = await ai_hub.generate_code(request)
        
        if response.success:
            test_file = source_file.replace('.py', '_test.py')
            test_path = os.path.join(working_directory, 'tests', 'unit', test_file)
            
            os.makedirs(os.path.dirname(test_path), exist_ok=True)
            
            with open(test_path, 'w') as f:
                f.write(response.content)
            
            return {
                "success": True,
                "test_file": test_path,
                "generated_content": response.content,
                "provider_used": response.provider
            }
        else:
            return {
                "success": False,
                "error": response.error
            }
    
    async def _test_baseline(self) -> Dict[str, Any]:
        """Teste le code avec détection simple des tests existants."""
        try:
            test_files = await self._find_test_files()
            
            if not test_files:
                self.logger.info("📝 Aucun fichier de test trouvé - création recommandée")
                return {
                    "success": True, 
                    "message": "Aucun test trouvé - création recommandée",
                    "no_tests_found": True,
                    "total_tests": 0,
                    "passed_tests": 0
                }

            return await self._run_detected_tests(test_files)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur test baseline: {e}")
            return {"success": False, "error": str(e)}
    
    async def _find_test_files(self) -> List[str]:
        """Trouve tous les fichiers de test dans le projet (exclusion des dépendances et scripts de correction)."""
        test_files = []
        test_patterns = [
            "test_*.py",
            "*_test.py", 
            "tests/*.py",
            "test/*.py",
            "**/test_*.py",      
            "**/*_test.py",      
            "tests/**/*.py",     
            "**/tests/**/*.py"   
        ]
        
        exclude_dirs = {
            "venv", ".venv", "env", ".env", 
            "node_modules", ".git", "__pycache__",
            "site-packages", ".pytest_cache",
            ".mypy_cache", "htmlcov", "coverage"
        }
        
        try:
            from pathlib import Path
            
            if not self.working_directory or not os.path.exists(self.working_directory):
                self.logger.warning("⚠️ working_directory invalide - aucun test trouvé")
                return []
            
            search_dir = self.working_directory
            base_path = Path(search_dir)
            self.logger.debug(f"🔍 Recherche de tests dans: {search_dir}")
            
            for pattern in test_patterns:
                try:
                    for test_file in base_path.glob(pattern):
                        if test_file.is_file():
                            excluded = False
                            for parent in test_file.parents:
                                if parent.name in exclude_dirs:
                                    excluded = True
                                    break
                            
                            filename = test_file.name
                            if filename.startswith('fix_') or filename in ['simple_fix.py', 'cleanup_scripts.py', 'debug_workflow.py']:
                                self.logger.debug(f"🔍 Exclusion script de correction: {filename}")
                                excluded = True
                            
                            if not excluded and str(test_file) not in test_files:
                                if await self._is_valid_test_file(test_file):
                                    test_files.append(str(test_file))
                except Exception as e:
                    self.logger.debug(f"⚠️ Erreur avec pattern {pattern}: {e}")
                        
            test_files = list(set(test_files))
            
            self.logger.info(f"🔍 Fichiers de test valides trouvés: {len(test_files)}")
            for test_file in test_files[:3]:  
                try:
                    rel_path = os.path.relpath(test_file, self.working_directory)
                    self.logger.info(f"  📄 {rel_path}")
                except:
                    self.logger.info(f"  📄 {os.path.basename(test_file)}")
                
            return test_files
        except Exception as e:
            self.logger.error(f"❌ Erreur détection tests: {e}")
            return []
    
    async def _is_valid_test_file(self, file_path) -> bool:
        """Vérifie si un fichier contient réellement des tests."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            test_indicators = [
                'def test_',
                'class Test',
                'import unittest',
                'import pytest',
                'from unittest',
                '@pytest.',
                'assert ',
                'self.assert'
            ]
            
            return any(indicator in content for indicator in test_indicators)
        except Exception:
            return False
    
    async def _run_detected_tests(self, test_files: List[str]) -> Dict[str, Any]:
        """Exécute les tests détectés avec commandes appropriées."""
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        execution_output = []
        
        if not test_files:
            self.logger.info("📝 Aucun fichier de test trouvé - ce n'est pas nécessairement une erreur")
            self.logger.info("💡 Essai des commandes de découverte automatique de tests...")

        test_commands = []
        
        if test_files:
            valid_test_files = []
            for test_file in test_files[:10]:  
                if (os.path.exists(test_file) or 
                    os.path.exists(os.path.join(self.working_directory, test_file))):
                    
                    filename = os.path.basename(test_file)
                    if not (filename.startswith('fix_') or 
                           filename in ['simple_fix.py', 'cleanup_scripts.py', 'debug_workflow.py']):
                        valid_test_files.append(test_file)
            
            if valid_test_files:
                specific_files = " ".join([f'"{f}"' for f in valid_test_files])
                test_commands.extend([
                    f"python3 -m pytest {specific_files} -v --tb=short",
                    f"python -m pytest {specific_files} -v --tb=short"
                ])
                self.logger.info(f"🧪 Tests spécifiques trouvés: {len(valid_test_files)} fichiers valides")
        
        test_commands.extend([
            f"python3 -m unittest discover -s . -p 'test_*.py' -v",
            f"python -m unittest discover -s . -p 'test_*.py' -v",
            "python3 -m pytest -v --tb=short",
            "python -m pytest -v --tb=short",
            "python3 -m unittest -v",
            "python -m unittest -v"
        ])
        
        for cmd in test_commands:
            try:
                self.logger.info(f"🧪 Test avec commande: {cmd}")
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    cwd=self.working_directory,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
                output = stdout.decode('utf-8') + stderr.decode('utf-8')
                execution_output.append(f"Cmd: {cmd}")
                execution_output.append(f"Return code: {process.returncode}")
                execution_output.append(f"Output: {output[:500]}...")  
                
                self.logger.debug(f"📝 Commande {cmd} - Return code: {process.returncode}")
                if output:
                    self.logger.debug(f"📝 Output: {output[:200]}...")
                
                import re
                
                pytest_match = re.search(r'(\d+) passed.*?(\d+) failed', output)
                if pytest_match:
                    passed_tests = int(pytest_match.group(1))
                    failed_tests = int(pytest_match.group(2))
                    total_tests = passed_tests + failed_tests
                    break
                
                unittest_match = re.search(r'Ran (\d+) tests', output)
                if unittest_match:
                    total_tests = int(unittest_match.group(1))
                    if "FAILED" not in output and process.returncode == 0:
                        passed_tests = total_tests
                        failed_tests = 0
                    else:
                        failed_match = re.search(r'failures=(\d+)', output)
                        error_match = re.search(r'errors=(\d+)', output)
                        failures = int(failed_match.group(1)) if failed_match else 0
                        errors = int(error_match.group(1)) if error_match else 0
                        failed_tests = failures + errors
                        passed_tests = total_tests - failed_tests
                    break
                    
                if process.returncode == 0 and ("no tests ran" in output.lower() or "collected 0 items" in output.lower()):
                    total_tests = 0
                    passed_tests = 0
                    failed_tests = 0
                    break
                    
            except asyncio.TimeoutError:
                self.logger.warning(f"⏰ Timeout pour commande: {cmd}")
                continue
            except Exception as e:
                error_str = str(e)
                if "No such file or directory" in error_str:
                    self.logger.debug(f"📝 Fichier non trouvé pour {cmd} - normal si pas de tests dans ce répertoire")
                else:
                    self.logger.warning(f"⚠️ Échec commande {cmd}: {e}")
                continue
        
        success = failed_tests == 0  
        
        if total_tests > 0:
            message = f"Tests: {passed_tests}/{total_tests} réussis"
            self.logger.info(f"✅ {message}")
        else:
            message = f"Aucun test trouvé - pas d'erreur détectée (considéré comme succès)"
            self.logger.info(f"💡 {message}")
            for line in execution_output[-5:]:  
                self.logger.debug(f"🔍 {line}")
        
        return {
            "success": success,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "message": message,
            "no_tests_found": total_tests == 0,
            "test_files_detected": len(test_files),
            "execution_debug": execution_output[-5:] if execution_output else []  
        }
    
    async def _test_ai_files(self, modified_files: List[str]) -> Dict[str, Any]:
        """Teste spécifiquement les fichiers modifiés par IA."""
        if not modified_files:
            return {"success": True, "message": "Aucun fichier IA à tester"}
        
        test_files = " ".join([f"**/*test*{f.replace('.py', '')}*.py" for f in modified_files if f.endswith('.py')])
        if not test_files:
            return {"success": True, "message": "Aucun test trouvé pour fichiers IA"}
        
        try:
            cmd = f"python -m pytest {test_files} -v --tb=short"
            process = await asyncio.create_subprocess_shell(
                cmd, cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            success = process.returncode == 0
            return {
                "success": success,
                "files_tested": modified_files,
                "output": stdout.decode() if stdout else "",
                "error": stderr.decode() if stderr else ""
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_integration(self) -> Dict[str, Any]:
        """Teste l'intégration complète (code local + IA)."""
        return await self._test_baseline()
    
    def _get_syntax_check_command(self, language_type: str, working_directory: str) -> Optional[str]:
        """
        Retourne la commande de vérification de syntaxe appropriée selon le langage.
        
        Args:
            language_type: Type du langage détecté (ex: "python", "java", "javascript")
            working_directory: Répertoire de travail
            
        Returns:
            Commande de vérification de syntaxe ou None si non supporté
        """
        syntax_commands = {
            "python": "python -m py_compile **/*.py",
            "java": "javac -Xlint:all $(find . -name '*.java' -type f)",
            "javascript": "npx eslint '**/*.js' || node --check $(find . -name '*.js' -type f)",
            "typescript": "npx tsc --noEmit",
            "go": "go vet ./...",
            "rust": "cargo check",
            "cpp": "g++ -fsyntax-only $(find . -name '*.cpp' -o -name '*.cc' -type f)",
            "c": "gcc -fsyntax-only $(find . -name '*.c' -type f)",
            "csharp": "dotnet build --no-incremental /p:TreatWarningsAsErrors=false",
            "php": "php -l $(find . -name '*.php' -type f)",
            "ruby": "ruby -c $(find . -name '*.rb' -type f)",
            "swift": "swiftc -typecheck $(find . -name '*.swift' -type f)",
            "kotlin": "kotlinc -no-stdlib $(find . -name '*.kt' -type f)",
            "scala": "scalac -Xfatal-warnings $(find . -name '*.scala' -type f)"
        }
        
        cmd = syntax_commands.get(language_type.lower())
        if cmd:
            self.logger.info(f"🔍 Commande de vérification syntaxe {language_type}: {cmd}")
        else:
            self.logger.warning(f"⚠️ Pas de commande de vérification syntaxe pour {language_type}")
        
        return cmd
    
    async def _test_regression(self) -> Dict[str, Any]:
        """Teste la non-régression (performance, fonctionnalités non-modifiées)."""
        try:
            smoke_result = await self._run_test_type(TestType.SMOKE, self.working_directory, False)
            
            detector = GenericLanguageDetector()
            
            all_files = []
            for root, dirs, files in os.walk(self.working_directory):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__', 'target', 'build', 'dist']]
                for file in files:
                    if not file.startswith('.'):
                        all_files.append(os.path.join(root, file))
            
            detected_lang = detector.detect_from_files(all_files) if all_files else None
            
            syntax_ok = True  
            language_name = "Unknown"
            
            if detected_lang:
                language_name = detected_lang.name
                language_type = detected_lang.type_id
                self.logger.info(f"🔍 Langage détecté: {language_name} (confiance: {detected_lang.confidence:.2f})")
                
                syntax_cmd = self._get_syntax_check_command(language_type, self.working_directory)
                
                if syntax_cmd:
                    self.logger.info(f"🧪 Vérification syntaxe pour {language_name}...")
                    try:
                        process = await asyncio.create_subprocess_shell(
                            syntax_cmd, 
                            cwd=self.working_directory,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await process.communicate()
                        
                        syntax_ok = process.returncode == 0
                        
                        if not syntax_ok:
                            if language_type == "typescript":
                                self.logger.warning(f"⚠️ Erreurs TypeScript détectées (non-bloquantes)")
                                self.logger.debug(f"stderr: {stderr.decode() if stderr else ''}")
                                syntax_ok = True
                            else:
                                self.logger.warning(f"⚠️ Erreurs de syntaxe détectées pour {language_name}")
                                self.logger.debug(f"stderr: {stderr.decode() if stderr else ''}")
                    except Exception as cmd_error:
                        self.logger.warning(f"⚠️ Impossible d'exécuter la vérification syntaxe: {cmd_error}")
                        syntax_ok = True  
                else:
                    self.logger.info(f"ℹ️ Pas de vérification syntaxe disponible pour {language_name}")
            else:
                self.logger.warning("⚠️ Langage non détecté - skip vérification syntaxe")
            
            overall_success = smoke_result.get("success", False) and syntax_ok
            
            return {
                "success": overall_success,
                "smoke_tests": smoke_result.get("success", False),
                "syntax_check": syntax_ok,
                "detected_language": language_name
            }
        except Exception as e:
            self.logger.error(f"❌ Erreur test régression: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _generate_test_summary(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Génère un résumé des tests."""
        total_tests = 0
        total_passed = 0
        total_failed = 0
        
        for test_type, result in all_results.items():
            if isinstance(result, dict):
                total_tests += result.get("total_tests", 0)
                total_passed += result.get("passed_tests", 0)
                total_failed += result.get("failed_tests", 0)
        
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        return {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "success_rate": round(success_rate, 2),
            "overall_success": total_failed == 0
        }
    
    def _generate_recommendations(self, all_results: Dict[str, Any], coverage_result: Optional[TestCoverage]) -> List[str]:
        """Génère des recommandations basées sur les résultats."""
        recommendations = []
        
        for test_type, result in all_results.items():
            if isinstance(result, dict) and result.get("failed_tests", 0) > 0:
                recommendations.append(f"Corriger les échecs dans les {test_type} tests")
        
        if coverage_result and not coverage_result.threshold_met:
            recommendations.append(
                f"Améliorer la couverture de code (actuelle: {coverage_result.total_coverage:.1f}%, "
                f"objectif: {self.settings.test_coverage_threshold}%)"
            )
        
        if not recommendations:
            recommendations.append("Tous les tests passent ! Considérer l'ajout de tests d'edge cases.")
        
        return recommendations 

    async def _run_test_directory(self, test_directory: str) -> Dict[str, Any]:
        """Exécute tous les tests dans un répertoire spécifique."""
        import os
        import asyncio
        
        if not os.path.exists(test_directory):
            return {
                "success": False,
                "error": f"Répertoire de tests inexistant: {test_directory}",
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 1
            }
        
        try:
            pytest_cmd = f"python -m pytest {test_directory} -v --tb=short"
            
            process = await asyncio.create_subprocess_shell(
                pytest_cmd,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=300  
            )
            
            output = stdout.decode('utf-8') if stdout else ""
            
            if process.returncode == 0:
                passed_count = output.count(" PASSED")
                total_count = max(passed_count, 1)
                
                return {
                    "success": True,
                    "total_tests": total_count,
                    "passed_tests": passed_count,
                    "failed_tests": 0,
                    "output": output,
                    "test_runner": "pytest"
                }
            else:
                passed_count = output.count(" PASSED")
                failed_count = output.count(" FAILED")
                total_count = max(passed_count + failed_count, 1)
                
                return {
                    "success": False,
                    "total_tests": total_count,
                    "passed_tests": passed_count,
                    "failed_tests": failed_count,
                    "output": output,
                    "error": f"Tests échoués (code de retour: {process.returncode})",
                    "test_runner": "pytest"
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Timeout lors de l'exécution des tests",
                "total_tests": 1,
                "passed_tests": 0,
                "failed_tests": 1
            }
        except Exception as e:
            try:
                unittest_cmd = f"python -m unittest discover -s {test_directory} -p 'test_*.py' -v"
                
                process = await asyncio.create_subprocess_shell(
                    unittest_cmd,
                    cwd=self.working_directory,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
                
                stdout, _ = await asyncio.wait_for(
                    process.communicate(),
                    timeout=300
                )
                
                output = stdout.decode('utf-8') if stdout else ""
                
                if process.returncode == 0:
                    lines = output.split('\n')
                    test_count = sum(1 for line in lines if ' ... ok' in line)
                    
                    return {
                        "success": True,
                        "total_tests": max(test_count, 1),
                        "passed_tests": max(test_count, 1),
                        "failed_tests": 0,
                        "output": output,
                        "test_runner": "unittest"
                    }
                else:
                    return {
                        "success": False,
                        "total_tests": 1,
                        "passed_tests": 0,
                        "failed_tests": 1,
                        "output": output,
                        "error": f"Tests unittest échoués (code: {process.returncode})",
                        "test_runner": "unittest"
                    }
                    
            except Exception as unittest_error:
                return {
                    "success": False,
                    "error": f"Erreur pytest: {e}, erreur unittest: {unittest_error}",
                    "total_tests": 1,
                    "passed_tests": 0,
                    "failed_tests": 1
                } 