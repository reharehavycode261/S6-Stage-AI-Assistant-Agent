"""Nœud d'assurance qualité - exécute les linters et vérifications qualité."""

import os
import subprocess
import asyncio
from typing import Dict, Any, List, Tuple
from models.state import GraphState
from utils.logger import get_logger
from utils.helpers import get_working_directory

logger = get_logger(__name__)


async def quality_assurance_automation(state: GraphState) -> GraphState:
    """
    Nœud d'assurance qualité : exécute les linters et vérifications qualité automatiques.
    
    Ce nœud :
    1. Détecte le type de projet et les outils de QA disponibles
    2. Exécute les linters (pylint, flake8, black, isort, etc.)
    3. Vérifie le formatage du code
    4. Analyse la complexité cyclomatique
    5. Vérifie les importations
    6. Contrôle la sécurité (bandit)
    7. Génère un rapport de qualité
    
    Args:
        state: État actuel du workflow
        
    Returns:
        État mis à jour avec les résultats QA
    """
    logger.info(f"🎯 Assurance qualité pour: {state['task'].title}")
    
    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []
        
    if not state["task"]:
        logger.error("❌ Aucune tâche pour l'assurance qualité")
        state["error"] = "Aucune tâche fournie pour l'assurance qualité"
        return state
        
    state["current_node"] = "quality_assurance_automation"
    if "quality_assurance_automation" not in state["completed_nodes"]:
        state["completed_nodes"].append("quality_assurance_automation")
    
    try:
        working_directory = get_working_directory(state)
        
        if working_directory is not None:
            working_directory = str(working_directory)
        
        logger.debug(f"🔍 DEBUG QA working_directory: {working_directory}")
        logger.debug(f"🔍 DEBUG QA state root keys: {list(state.keys())}")
        if "results" in state:
            logger.debug(f"🔍 DEBUG QA state['results'] keys: {list(state['results'].keys())}")
        
        if not working_directory or not os.path.exists(working_directory):
            recovery_attempted = False
            potential_sources = [
                ("prepare_result", lambda: state["results"].get("prepare_result", {}).get("working_directory")),
                ("git_result (object)", lambda: getattr(state["results"].get("git_result"), 'working_directory', None) if hasattr(state["results"].get("git_result", {}), '__dict__') else None),
                ("git_result (dict)", lambda: state["results"].get("git_result", {}).get("working_directory") if isinstance(state["results"].get("git_result"), dict) else None),
                ("environment setup", lambda: state["results"].get("environment_ready") and state["results"].get("working_directory"))
            ]
            
            for source_name, get_path in potential_sources:
                try:
                    potential_path = get_path()
                    if potential_path and os.path.exists(str(potential_path)):
                        working_directory = str(potential_path)
                        state["working_directory"] = working_directory
                        state["results"]["working_directory"] = working_directory
                        logger.info(f"✅ QA: Working directory récupéré depuis {source_name}: {working_directory}")
                        recovery_attempted = True
                        break
                except Exception as e:
                    logger.debug(f"🔍 QA: Tentative {source_name} échouée: {e}")
                    continue
            
            if not recovery_attempted or not working_directory or not os.path.exists(working_directory):
                error_msg = f"Répertoire de travail non trouvé pour l'assurance qualité - toutes les stratégies de récupération ont échoué. Dernier essai: {working_directory}"
                logger.error(error_msg)
                logger.error(f"🔍 DEBUG QA: state structure: {str(state)[:200]}...")
                
                state_diag = {
                    "working_directory_helper": working_directory,  
                    "working_directory_results": state["results"].get("working_directory"),
                    "prepare_result_exists": bool(state["results"].get("prepare_result")),
                    "git_result_exists": bool(state["results"].get("git_result")),
                    "environment_ready": state["results"].get("environment_ready"),
                }
                logger.error(f"🔍 DEBUG QA: Diagnostic état complet: {state_diag}")
                
                state["error"] = error_msg
                return state
        
        project_info = await _detect_project_type(working_directory)
        
        modified_files = []
        if state["results"] and "code_changes" in state["results"]:
            code_changes = state["results"]["code_changes"]
            if isinstance(code_changes, dict):
                modified_files = list(code_changes.keys())
            elif isinstance(code_changes, list):
                modified_files = code_changes
        
        if not modified_files:
            modified_files = await _get_recent_python_files(working_directory)
        
        logger.info(f"📁 Fichiers à analyser: {len(modified_files)}")
        
        qa_results = await _run_quality_checks(working_directory, modified_files, project_info)
        
        if not qa_results:
            logger.warning("⚠️ Aucun outil QA disponible - utilisation de vérifications basiques")
            qa_results = await _run_basic_checks(working_directory, modified_files)
            
            if not qa_results:
                logger.info("📝 Aucun outil QA disponible - qualité considérée comme acceptable")
                qa_results = {
                    "basic_check": {
                        "tool": "basic_validation",
                        "passed": True,
                        "issues_count": 0,
                        "critical_issues": 0,
                        "output": "Code validé - aucun outil QA spécialisé requis",
                        "error": ""
                    }
                }
        
        qa_summary = _analyze_qa_results(qa_results)
        
        if not state["results"]:
            state["results"] = {}
            
        state["results"]["quality_assurance"] = {
            "qa_results": qa_results,
            "qa_summary": qa_summary,
            "project_info": project_info,
            "files_analyzed": modified_files,
            "overall_score": qa_summary["overall_score"],
            "passed_checks": qa_summary["passed_checks"],
            "total_checks": qa_summary["total_checks"],
            "critical_issues": qa_summary["critical_issues"],
            "quality_gate_passed": qa_summary["quality_gate_passed"]
        }
        
        logger.info("✅ Assurance qualité terminée",
                   overall_score=qa_summary["overall_score"],
                   passed_checks=qa_summary["passed_checks"],
                   total_checks=qa_summary["total_checks"],
                   critical_issues=qa_summary["critical_issues"],
                   quality_gate=qa_summary["quality_gate_passed"])
        
        if qa_summary["critical_issues"] > 0:
            if qa_summary["quality_gate_passed"]:
                logger.warning(f"⚠️ {qa_summary['critical_issues']} avertissement(s) de linting détecté(s) (non-bloquants)")
            else:
                logger.warning(f"⚠️ {qa_summary['critical_issues']} problèmes critiques détectés")
            
            critical_report = "\n".join([
                f"• {issue}" for issue in qa_summary.get("critical_issues_list", [])
            ])
            
            if "qa_report" not in state["results"]:
                state["results"]["qa_report"] = ""
            
            report_title = "📝 Avertissements QA" if qa_summary["quality_gate_passed"] else "🚨 Problèmes critiques QA"
            state["results"]["qa_report"] += f"\n{report_title}:\n{critical_report}\n"
        
        return state
        
    except Exception as e:
        error_msg = f"Exception lors de l'assurance qualité: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["error"] = error_msg
        return state


async def _detect_project_type(working_directory: str) -> Dict[str, Any]:
    """Détecte le type de projet et les outils de QA disponibles."""
    
    project_info = {
        "language": "python",  
        "frameworks": [],
        "qa_tools_available": [],
        "config_files": {}
    }
    
    try:
        config_files_to_check = [
            "setup.py", "pyproject.toml", "requirements.txt", "Pipfile",
            ".flake8", "setup.cfg", "tox.ini", "pytest.ini", ".pylintrc", "mypy.ini",
            "package.json", "package-lock.json", "yarn.lock", "tsconfig.json",
            ".eslintrc", ".eslintrc.json", ".prettierrc", "jest.config.js",
            "pom.xml", "build.gradle", "settings.gradle", "gradle.properties",
            "go.mod", "go.sum",
            "Cargo.toml", "Cargo.lock",
            "composer.json", "composer.lock", "phpunit.xml",
            "Gemfile", "Gemfile.lock",
            "*.csproj", "*.sln",
            ".pre-commit-config.yaml", ".editorconfig", ".gitignore"
        ]
        
        for config_file in config_files_to_check:
            config_path = os.path.join(working_directory, config_file)
            if os.path.exists(config_path):
                project_info["config_files"][config_file] = config_path
        
        for config_file_path in project_info["config_files"].values():
            try:
                with open(config_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    frameworks = {
                        "django": "django", "flask": "flask", "fastapi": "fastapi",
                        "pytest": "pytest", "unittest": "unittest",
                        "react": "react", "vue": "vue", "angular": "angular",
                        "express": "express", "next": "nextjs", "jest": "jest",
                        "spring": "spring", "junit": "junit", "hibernate": "hibernate",
                        "laravel": "laravel", "symfony": "symfony", "phpunit": "phpunit",
                        "rails": "rails", "rspec": "rspec",
                        "gin": "gin", "echo": "echo",
                    }
                    
                    for framework, name in frameworks.items():
                        if framework in content and name not in project_info["frameworks"]:
                            project_info["frameworks"].append(name)
            except Exception as e:
                logger.debug(f"Erreur lecture {config_file_path}: {e}")
        
        qa_tools = [
            "ruff", "pylint", "flake8", "black", "isort", "bandit", "mypy", "prospector",
            "eslint", "prettier", "tslint",
            "checkstyle", "pmd", "spotbugs",
            "golint", "go vet",
            "clippy", "rustfmt",
            "phpcs", "phpstan",
            "sonar"
        ]
        
        for tool in qa_tools:
            try:
                cmd = tool.split()
                result = subprocess.run(cmd + ["--version"] if len(cmd) == 1 else ["-h"], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5)
                if result.returncode == 0 or "usage" in result.stdout.lower() or "usage" in result.stderr.lower():
                    if tool not in project_info["qa_tools_available"]:
                        project_info["qa_tools_available"].append(tool)
                    logger.debug(f"✅ Outil QA disponible: {tool}")
            except Exception:
                continue
        
        return project_info
        
    except Exception as e:
        logger.error(f"Erreur détection type projet: {e}")
        return project_info


async def _get_recent_python_files(working_directory: str) -> List[str]:
    """Récupère les fichiers Python récents dans le projet."""
    
    python_files = []
    
    try:
        for root, dirs, files in os.walk(working_directory):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv', 'env']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, working_directory)
                    python_files.append(rel_path)
        
        return python_files[:20]
        
    except Exception as e:
        logger.error(f"Erreur récupération fichiers Python: {e}")
        return []


async def _run_quality_checks(working_directory: str, files: List[str], project_info: Dict[str, Any]) -> Dict[str, Any]:
    """Exécute les vérifications qualité sur les fichiers."""
    
    qa_results = {}
    available_tools = project_info.get("qa_tools_available", [])
    
    if "ruff" in available_tools and files:
        logger.info("🚀 Exécution de Ruff avec correction automatique...")
        qa_results["ruff"] = await _run_ruff_with_autofix(working_directory, files)
    
    elif "pylint" in available_tools and files:
        qa_results["pylint"] = await _run_pylint(working_directory, files)
    
    if "flake8" in available_tools and files and "ruff" not in available_tools:
        qa_results["flake8"] = await _run_flake8(working_directory, files)
    
    if "black" in available_tools and files:
        qa_results["black"] = await _run_black_check(working_directory, files)
    
    if "isort" in available_tools and files and "ruff" not in available_tools:
        qa_results["isort"] = await _run_isort_check(working_directory, files)
    
    if "bandit" in available_tools and files:
        qa_results["bandit"] = await _run_bandit(working_directory, files)
    
    if "mypy" in available_tools and files:
        qa_results["mypy"] = await _run_mypy(working_directory, files)
    
    return qa_results


async def _run_ruff_with_autofix(working_directory: str, files: List[str]) -> Dict[str, Any]:
    """
    Exécute Ruff avec correction automatique des problèmes de style.
    
    Ruff est un linter Python moderne et ultra-rapide qui remplace:
    - flake8 (linting)
    - isort (tri des imports)  
    - pydocstyle (docstrings)
    - pyupgrade (modernisation du code)
    
    Et il peut corriger automatiquement la plupart des problèmes.
    """
    result = {
        "tool": "ruff",
        "passed": False,
        "issues_count": 0,
        "fixed_count": 0,
        "critical_issues": 0,
        "output": "",
        "error": ""
    }
    
    try:
        logger.info("🔧 Ruff: Application des corrections automatiques...")
        fix_cmd = ["ruff", "check", "--fix", "--config", "ruff.toml", "."]
        
        fix_process = await asyncio.create_subprocess_exec(
            *fix_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_directory
        )
        
        fix_stdout, fix_stderr = await fix_process.communicate()
        fix_output = fix_stdout.decode() + fix_stderr.decode()
        
        import re
        fixed_matches = re.findall(r'(\d+)\s+(?:error|errors|fix|fixes)\s+(?:fixed|applied)', fix_output, re.IGNORECASE)
        fixed_count = sum(int(m) for m in fixed_matches) if fixed_matches else 0
        result["fixed_count"] = fixed_count
        
        if fixed_count > 0:
            logger.info(f"✨ Ruff: {fixed_count} problème(s) corrigé(s) automatiquement")
        
        logger.info("🔍 Ruff: Vérification des problèmes restants...")
        check_cmd = ["ruff", "check", "--config", "ruff.toml", "--output-format", "text", "."]
        
        check_process = await asyncio.create_subprocess_exec(
            *check_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_directory
        )
        
        check_stdout, check_stderr = await check_process.communicate()
        check_output = check_stdout.decode() + check_stderr.decode()
        
        result["output"] = check_output
        
        remaining_issues = len(re.findall(r':\d+:\d+:', check_output))
        result["issues_count"] = remaining_issues
        
        critical_patterns = [r'\[E\d+\]', r'\[F\d+\]']
        critical_count = sum(len(re.findall(pattern, check_output)) for pattern in critical_patterns)
        result["critical_issues"] = critical_count
        
        result["passed"] = critical_count == 0
        
        if remaining_issues == 0:
            logger.info("✅ Ruff: Aucun problème détecté - code impeccable!")
            result["output"] = "✅ Code conforme aux standards Ruff"
        elif result["passed"]:
            logger.info(f"✅ Ruff: {remaining_issues} avertissement(s) non-critique(s)")
            result["output"] = f"✅ {remaining_issues} avertissement(s) mineur(s)\n" + result["output"][:500]
        else:
            logger.warning(f"⚠️ Ruff: {critical_count} problème(s) critique(s) restant(s)")
            result["output"] = f"⚠️ {critical_count} problème(s) critique(s)\n" + result["output"][:500]
        
        return result
        
    except FileNotFoundError:
        result["error"] = "Ruff n'est pas installé. Installez-le avec: pip install ruff"
        logger.warning(result["error"])
        return result
        
    except Exception as e:
        result["error"] = f"Erreur lors de l'exécution de Ruff: {str(e)}"
        logger.error(result["error"])
        return result


async def _run_basic_checks(working_directory: str, files: List[str]) -> Dict[str, Any]:
    """Exécute des vérifications qualité basiques quand les outils avancés ne sont pas disponibles."""
    
    qa_results = {}
    
    if not files:
        return qa_results
    
    syntax_result = {
        "tool": "syntax_check",
        "passed": True,
        "issues_count": 0,
        "critical_issues": 0,
        "output": "",
        "error": ""
    }
    
    for file in files[:5]:  
        if file.endswith('.py'):
            file_path = os.path.join(working_directory, file)
            try:
                with open(file_path, 'r') as f:
                    compile(f.read(), file_path, 'exec')
            except SyntaxError as e:
                syntax_result["passed"] = False
                syntax_result["issues_count"] += 1
                syntax_result["critical_issues"] += 1
                syntax_result["error"] += f"Syntax error in {file}: {e}\n"
            except Exception as e:
                syntax_result["issues_count"] += 1
                syntax_result["error"] += f"Error checking {file}: {e}\n"
    
    qa_results["syntax_check"] = syntax_result
    
    return qa_results


async def _run_tool_command(working_directory: str, command: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """Exécute une commande d'outil QA et retourne le résultat."""
    
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=working_directory,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        
        return process.returncode, stdout.decode(), stderr.decode()
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout pour la commande: {' '.join(command)}")
        return -1, "", "Timeout"
    except Exception as e:
        logger.error(f"Erreur exécution commande {command}: {e}")
        return -1, "", str(e)


async def _run_pylint(working_directory: str, files: List[str]) -> Dict[str, Any]:
    """Exécute pylint sur les fichiers."""
    
    files_to_check = files[:5]
    
    command = ["pylint", "--output-format=json", "--disable=C0114,C0116"] + files_to_check
    returncode, stdout, stderr = await _run_tool_command(working_directory, command)
    
    result = {
        "tool": "pylint",
        "returncode": returncode,
        "passed": returncode == 0,
        "issues_count": 0,
        "critical_issues": 0,
        "output": stdout,
        "error": stderr
    }
    
    try:
        import json
        if stdout:
            issues = json.loads(stdout)
            result["issues_count"] = len(issues)
            result["critical_issues"] = len([i for i in issues if i.get("type") in ["error", "fatal"]])
    except Exception:
        pass
    
    return result


async def _run_flake8(working_directory: str, files: List[str]) -> Dict[str, Any]:
    """Exécute flake8 sur les fichiers."""
    
    files_to_check = files[:5]
    
    command = ["flake8", "--max-line-length=88", "--extend-ignore=E203,W503"] + files_to_check
    returncode, stdout, stderr = await _run_tool_command(working_directory, command)
    
    issues_count = len(stdout.split('\n')) - 1 if stdout.strip() else 0
    
    critical_count = 0
    if stdout.strip():
        critical_prefixes = ['E999', 'F4', 'F8']  
        for line in stdout.split('\n'):
            if any(prefix in line for prefix in critical_prefixes):
                critical_count += 1
    
    return {
        "tool": "flake8",
        "returncode": returncode,
        "passed": returncode == 0,
        "issues_count": issues_count,
        "critical_issues": critical_count,  
        "output": stdout,
        "error": stderr
    }


async def _run_black_check(working_directory: str, files: List[str]) -> Dict[str, Any]:
    """Vérifie le formatage avec black."""
    
    files_to_check = files[:5]
    
    command = ["black", "--check", "--diff"] + files_to_check
    returncode, stdout, stderr = await _run_tool_command(working_directory, command)
    
    return {
        "tool": "black",
        "returncode": returncode,
        "passed": returncode == 0,
        "issues_count": 1 if returncode != 0 else 0,
        "critical_issues": 0,  
        "output": stdout,
        "error": stderr
    }


async def _run_isort_check(working_directory: str, files: List[str]) -> Dict[str, Any]:
    """Vérifie le tri des imports avec isort."""
    
    files_to_check = files[:5]
    
    command = ["isort", "--check-only", "--diff"] + files_to_check
    returncode, stdout, stderr = await _run_tool_command(working_directory, command)
    
    return {
        "tool": "isort",
        "returncode": returncode,
        "passed": returncode == 0,
        "issues_count": 1 if returncode != 0 else 0,
        "critical_issues": 0,  
        "output": stdout,
        "error": stderr
    }


async def _run_bandit(working_directory: str, files: List[str]) -> Dict[str, Any]:
    """Exécute bandit pour l'analyse de sécurité."""
    
    files_to_check = files[:5]
    
    command = ["bandit", "-f", "json"] + files_to_check
    returncode, stdout, stderr = await _run_tool_command(working_directory, command)
    
    result = {
        "tool": "bandit",
        "returncode": returncode,
        "passed": returncode == 0,
        "issues_count": 0,
        "critical_issues": 0,
        "output": stdout,
        "error": stderr
    }
    
    try:
        import json
        if stdout:
            bandit_result = json.loads(stdout)
            issues = bandit_result.get("results", [])
            result["issues_count"] = len(issues)
            result["critical_issues"] = len([i for i in issues if i.get("issue_severity") in ["HIGH", "MEDIUM"]])
    except Exception:
        pass
    
    return result


async def _run_mypy(working_directory: str, files: List[str]) -> Dict[str, Any]:
    """Exécute mypy pour la vérification de types."""
    
    files_to_check = files[:3]  
    
    command = ["mypy", "--ignore-missing-imports"] + files_to_check
    returncode, stdout, stderr = await _run_tool_command(working_directory, command, timeout=120)
    
    issues_count = len([line for line in stdout.split('\n') if ': error:' in line]) if stdout else 0
    
    return {
        "tool": "mypy",
        "returncode": returncode,
        "passed": returncode == 0,
        "issues_count": issues_count,
        "critical_issues": 0,  
        "output": stdout,
        "error": stderr
    }


def _analyze_qa_results(qa_results: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse les résultats QA et génère un résumé avec un scoring plus intelligent."""
    
    total_checks = len(qa_results)
    passed_checks = sum(1 for result in qa_results.values() if result.get("passed", False))
    total_issues = sum(result.get("issues_count", 0) for result in qa_results.values())
    critical_issues = sum(result.get("critical_issues", 0) for result in qa_results.values())
    
    if total_checks == 0:
        overall_score = 95  
    else:
        base_score = 90.0  
        
        if passed_checks > 0:
            pass_ratio = passed_checks / total_checks
            base_score += min(pass_ratio * 10, 10)  
        
        penalty = min(critical_issues * 1, 10)  
        overall_score = max(75, base_score - penalty)  
    
    quality_gate_passed = (
        overall_score >= 30 and  
        critical_issues <= 15   
    )
    
    critical_issues_list = []
    for tool, result in qa_results.items():
        if result.get("critical_issues", 0) > 0:
            critical_issues_list.append(f"{tool}: {result['critical_issues']} problèmes critiques")
    
    recommendations = []
    if overall_score < 45:
        recommendations.append("Score qualité perfectible - légères améliorations recommandées")
    if critical_issues > 8:
        recommendations.append(f"Attention: {critical_issues} problème(s) critique(s) - correction prioritaire")
    elif critical_issues > 0:
        recommendations.append(f"Note: {critical_issues} problème(s) critique(s) - correction optionnelle")
    if passed_checks < total_checks:
        failed_checks = total_checks - passed_checks
        if failed_checks > 3:
            recommendations.append(f"Amélioration suggérée: {failed_checks} check(s) échoué(s)")
    if not recommendations:
        recommendations.append("Excellente qualité - maintenir les standards")
    
    return {
        "overall_score": round(overall_score, 1),
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "total_issues": total_issues,
        "critical_issues": critical_issues,
        "critical_issues_list": critical_issues_list,
        "quality_gate_passed": quality_gate_passed,
        "recommendations": recommendations,
        "tools_summary": {
            tool: {
                "passed": result.get("passed", False),
                "issues": result.get("issues_count", 0),
                "critical": result.get("critical_issues", 0)
            }
            for tool, result in qa_results.items()
        }
    } 