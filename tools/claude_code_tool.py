"""Outil Claude Code SDK pour l'écriture et la modification de code."""

import asyncio
import os
import tempfile
import subprocess
import time
import shutil
from datetime import datetime
from typing import Any, Dict, Optional, List, Union, Tuple
from pydantic import Field
from anthropic import Client
from openai import OpenAI

from .base_tool import BaseTool
from models.schemas import TestResult
from config.langsmith_config import langsmith_config


class ClaudeCodeTool(BaseTool):
    """Outil pour l'écriture et la modification de code avec Anthropic Claude (fallback OpenAI)."""
    
    name: str = "claude_code_tool"
    description: str = """
    Outil pour écrire, modifier et tester du code.
    Utilise Anthropic Claude comme provider principal avec fallback automatique vers OpenAI.
    
    Fonctionnalités:
    - Lire des fichiers de code
    - Écrire/modifier des fichiers
    - Exécuter des commandes système
    - Lancer des tests
    - Analyser des erreurs
    """
    
    anthropic_client: Optional[Client] = Field(default=None)
    openai_client: Optional[OpenAI] = Field(default=None)
    working_directory: Optional[str] = Field(default=None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.anthropic_client = Client(api_key=self.settings.anthropic_api_key)
        if self.settings.openai_api_key:
            self.openai_client = OpenAI(api_key=self.settings.openai_api_key)
        else:
            self.openai_client = None
    
    def _call_llm_with_fallback(self, prompt: str, max_tokens: int = 4000) -> Tuple[str, str, Dict]:
        """
        Appelle le LLM avec fallback automatique Anthropic → OpenAI.
        
        Returns:
            Tuple[content, provider_used, metadata]
        """
        try:
            self.logger.info("🚀 Tentative avec Anthropic...")
            start_time = time.time()
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            latency_ms = int((time.time() - start_time) * 1000)
            
            content = response.content[0].text.strip()
            
            metadata = {
                "provider": "anthropic",
                "model": "claude-3-5-sonnet-20241022",
                "latency_ms": latency_ms,
                "input_tokens": response.usage.input_tokens if hasattr(response, 'usage') else 0,
                "output_tokens": response.usage.output_tokens if hasattr(response, 'usage') else 0,
                "cost_per_input_token": 0.000003,
                "cost_per_output_token": 0.000015
            }
            
            self.logger.info(f"✅ Anthropic réussi ({latency_ms}ms)")
            return content, "anthropic", metadata
            
        except Exception as e:
            self.logger.warning(f"⚠️ Anthropic échoué: {e}")
            
            if self.openai_client:
                try:
                    self.logger.info("🔄 Fallback vers OpenAI...")
                    start_time = time.time()
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o",
                        max_tokens=max_tokens,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    latency_ms = int((time.time() - start_time) * 1000)
                    
                    content = response.choices[0].message.content.strip()
                    
                    metadata = {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "latency_ms": latency_ms,
                        "input_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') else 0,
                        "output_tokens": response.usage.completion_tokens if hasattr(response, 'usage') else 0,
                        "cost_per_input_token": 0.000005,
                        "cost_per_output_token": 0.000015
                    }
                    
                    self.logger.info(f"✅ OpenAI fallback réussi ({latency_ms}ms)")
                    return content, "openai", metadata
                    
                except Exception as e2:
                    self.logger.error(f"❌ OpenAI fallback échoué: {e2}")
                    raise Exception(f"Anthropic et OpenAI ont échoué. Anthropic: {e}, OpenAI: {e2}")
            else:
                self.logger.error("❌ Pas de fallback OpenAI disponible (clé manquante)")
                raise Exception(f"Anthropic échoué et pas de fallback OpenAI: {e}")
    
    async def _arun(self, action: str, **kwargs) -> Dict[str, Any]:
        """Exécute une action avec Claude Code."""
        try:
            if action == "read_file":
                return await self._read_file(kwargs.get("file_path"), kwargs.get("required", True))
            elif action == "write_file":
                return await self._write_file(
                    kwargs.get("file_path"), 
                    kwargs.get("content")
                )
            elif action == "modify_file":
                return await self._modify_file(
                    kwargs.get("file_path"),
                    kwargs.get("description"),
                    kwargs.get("context", {})
                )
            elif action == "execute_command":
                return await self._execute_command(kwargs.get("command"), cwd=kwargs.get("cwd"))
            elif action == "run_tests":
                return await self._run_tests(kwargs.get("test_command", "npm test"), cwd=kwargs.get("cwd"))
            elif action == "setup_environment":
                return await self._setup_environment(
                    kwargs.get("repo_url"), 
                    kwargs.get("branch"),
                    is_reactivation=kwargs.get("is_reactivation", False),  
                    source_branch=kwargs.get("source_branch", "main")  
                )
            else:
                raise ValueError(f"Action non supportée: {action}")
                
        except Exception as e:
            return self.handle_error(e, f"claude_code_tool.{action}")
    
    async def _read_file(self, file_path: str, required: bool = True) -> Dict[str, Any]:
        """Lit le contenu d'un fichier."""
        try:
            if not isinstance(file_path, str):
                error_msg = f"file_path doit être une string, reçu {type(file_path)}: {file_path}"
                self.logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "file_path": str(file_path),
                    "file_exists": False,
                    "optional": False
                }
            
            full_path = self._get_full_path(file_path)
            
            if not os.path.exists(full_path):
                optional_config_files = {
                    "package.json", "setup.py", "requirements.txt", "pyproject.toml",
                    ".env", ".gitignore", "README.md", "CHANGELOG.md", "LICENSE",
                    "pytest.ini", "tox.ini", ".flake8", "mypy.ini", ".pylintrc"
                }
                
                is_optional = (
                    not required or 
                    file_path in optional_config_files or
                    any(opt_file in file_path.lower() for opt_file in optional_config_files)
                )
                
                if is_optional:
                    self.logger.debug(f"📝 Fichier de configuration {file_path} absent - normal selon le type de projet")
                    self.log_operation(f"Vérification fichier {file_path}", True, "Fichier absent (optionnel)")
                else:
                    self.log_operation(f"Lecture fichier {file_path}", False, "Fichier non trouvé")
                
                return {
                    "success": False,
                    "error": f"Fichier non trouvé: {file_path}",
                    "file_path": file_path,
                    "file_exists": False,
                    "optional": is_optional
                }
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.log_operation(f"Lecture fichier {file_path}", True)
            return {
                "success": True,
                "content": content,
                "file_path": file_path,
                "file_exists": True
            }
        except Exception as e:
            return self.handle_error(e, f"lecture du fichier {file_path}")
    
    async def _write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Écrit du contenu dans un fichier."""
        try:
            full_path = self._get_full_path(file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.log_operation(f"Écriture fichier {file_path}", True)
            return {
                "success": True,
                "file_path": file_path,
                "bytes_written": len(content.encode('utf-8'))
            }
        except Exception as e:
            return self.handle_error(e, f"écriture du fichier {file_path}")
    
    async def _modify_file(self, file_path: str, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Modifie un fichier existant avec l'aide de Claude."""
        try:
            current_content_result = await self._read_file(file_path)
            if not current_content_result["success"]:
                return current_content_result
            
            current_content = current_content_result["content"]
            
            prompt = f"""
Tu es un développeur expert. Tu dois modifier le fichier suivant selon la description fournie.

Fichier: {file_path}
Contenu actuel:
```
{current_content}
```

Description de la modification à effectuer:
{description}

Contexte supplémentaire:
{context}

Réponds UNIQUEMENT avec le nouveau contenu complet du fichier, sans explication.
"""
            
            new_content, provider_used, metadata = self._call_llm_with_fallback(prompt, max_tokens=4000)
            
            latency_ms = metadata.get("latency_ms", 0)
            input_tokens = metadata.get("input_tokens", 0)
            output_tokens = metadata.get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens
            
            cost_per_input = metadata.get("cost_per_input_token", 0)
            cost_per_output = metadata.get("cost_per_output_token", 0)
            estimated_cost = (input_tokens * cost_per_input) + (output_tokens * cost_per_output)
            
            token_usage = {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens
            }
            
            workflow_id = context.get("workflow_id", "unknown")
            task_id = context.get("task_id", "unknown")
            
            from services.cost_monitoring_service import cost_monitor
            from services.monitoring_service import monitoring_dashboard
            await cost_monitor.log_ai_usage(
                workflow_id=workflow_id,
                task_id=task_id,
                provider=provider_used,
                model=metadata.get("model"),
                operation="modify_file",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimated_cost,
                success=True
            )
            
            if langsmith_config.client:
                try:
                    langsmith_config.client.create_run(
                        name=f"{provider_used}_modify_file_{file_path.split('/')[-1]}",
                        run_type="llm",
                        inputs={
                            "file_path": file_path,
                            "description": description,
                            "prompt_tokens": input_tokens,
                            "completion_tokens": output_tokens
                        },
                        outputs={
                            "success": True,
                            "estimated_cost": estimated_cost,
                            "content_length": len(new_content)
                        },
                        session_name=context.get("langsmith_session"),
                        extra={
                            "model": metadata.get("model"),
                            "provider": provider_used,
                            "workflow_id": workflow_id
                        }
                    )
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")
            
            run_step_id = context.get("run_step_id")
            if run_step_id:
                await monitoring_dashboard.save_ai_interaction(
                    run_step_id=run_step_id,
                    provider=provider_used,
                    model_name=metadata.get("model"), 
                    prompt=prompt,
                    response=new_content,
                    token_usage=token_usage,
                    latency_ms=latency_ms
                )
            
            write_result = await self._write_file(file_path, new_content)
            if write_result["success"]:
                self.log_operation(f"Modification fichier {file_path}", True, 
                                 metadata={"tokens": total_tokens, "cost": estimated_cost})
                write_result["modification_description"] = description
                write_result["tokens_used"] = total_tokens
                write_result["estimated_cost"] = estimated_cost
            
            return write_result
            
        except Exception as e:
            return self.handle_error(e, f"modification du fichier {file_path}")
    
    async def _execute_command(self, command: str, cwd: str = None) -> Dict[str, Any]:
        """Exécute une commande système avec gestion améliorée des timeouts."""
        try:
            cwd = cwd or self.working_directory or os.getcwd()
            
            timeout = self._get_command_timeout(command)
            
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            success = result.returncode == 0
            self.log_operation(f"Commande: {command}", success, 
                             f"Code: {result.returncode}")
            
            return {
                "success": success,
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timeout_used": timeout
            }
            
        except subprocess.TimeoutExpired:
            return self.handle_error(
                TimeoutError(f"Commande expirée après {timeout}s"), 
                f"exécution de la commande: {command}"
            )
        except Exception as e:
            return self.handle_error(e, f"exécution de la commande: {command}")
    
    def _get_command_timeout(self, command: str) -> int:
        """Détermine le timeout approprié selon le type de commande."""
        if "git clone" in command:
            return 1800  
        elif "git" in command:
            return 600  
        elif any(install_cmd in command for install_cmd in ["npm install", "pip install", "yarn install"]):
            return 900  
        else:
            return 300  
    
    async def _execute_command_with_retry(self, command: str, max_retries: int = 2, cwd: str = None) -> Dict[str, Any]:
        last_result = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt  
                    self.logger.info(f"⏱️ Attente de {wait_time}s avant retry {attempt}/{max_retries}")
                    await asyncio.sleep(wait_time)
                
                result = await self._execute_command(command, cwd=cwd)
                
                if result["success"]:
                    if attempt > 0:
                        self.logger.info(f"✅ Commande réussie après {attempt} retry(s)")
                    return result
                else:
                    last_result = result
                    if attempt < max_retries:
                        self.logger.warning(f"⚠️ Échec tentative {attempt + 1}/{max_retries + 1}: {result.get('stderr', 'Erreur inconnue')}")
                    
            except Exception as e:
                last_result = {"success": False, "error": str(e), "command": command}
                if attempt < max_retries:
                    self.logger.warning(f"⚠️ Exception tentative {attempt + 1}/{max_retries + 1}: {str(e)}")
        
        self.logger.error(f"❌ Échec définitif après {max_retries + 1} tentatives")
        return last_result or {"success": False, "error": "Échec inconnu", "command": command}
    
    async def _run_tests(self, test_command: str, cwd: str = None) -> Dict[str, Any]:
        """Lance les tests et retourne le résultat structuré."""
        start_time = time.time()
        
        try:
            result = await self._execute_command(test_command, cwd=cwd or self.working_directory)
            duration = time.time() - start_time
            
            test_result_dict = {
                "success": result["success"],
                "test_type": "automated",
                "exit_code": result["exit_code"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "duration": duration,
                "test_command": test_command
            }
            
            self.log_operation("Tests", test_result_dict["success"], 
                             metadata={"duration": duration, "test_command": test_command})
            return test_result_dict
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Erreur lors des tests: {e}")
            return {
                "success": False,
                "test_type": "error",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration": duration,
                "test_command": test_command
            }
    
    async def _setup_environment(self, repo_url: str, branch: str, is_reactivation: bool = False, source_branch: str = "main") -> Dict[str, Any]:
        """
        Configure l'environnement de travail avec gestion avancée des dépendances.
        
        Args:
            repo_url: URL du repository Git
            branch: Nom de la branche à créer pour le travail
            is_reactivation: Si True, clone depuis source_branch (main) au lieu de créer une branche vide
            source_branch: Branche source pour la réactivation (défaut: 'main')
        """
        try:
            current_working_dir_path = self.working_directory
            
            if not current_working_dir_path or not os.path.exists(str(current_working_dir_path)):
                try:
                    self.working_directory = tempfile.mkdtemp(prefix="ai_agent_")
                    self.logger.info(f"📁 Répertoire de travail créé: {self.working_directory}")
                except Exception as e:
                    self.working_directory = "/tmp/ai_agent_fallback"
                    os.makedirs(self.working_directory, exist_ok=True)
                    self.logger.warning(f"⚠️ Fallback répertoire: {self.working_directory} (erreur tempfile: {e})")
            else:
                self.logger.info(f"📁 Répertoire de travail existant réutilisé: {self.working_directory}")
            
            if not os.path.exists(self.working_directory):
                os.makedirs(self.working_directory, exist_ok=True)
            
            if is_reactivation:
                self.logger.info(f"🔄 RÉACTIVATION DÉTECTÉE - Clone depuis {source_branch} (dernière version)")
            else:
                self.logger.info(f"🆕 Premier workflow - Création branche {branch}")
            
            await self._run_git_diagnostics()
            
            if repo_url and repo_url.strip():
                cleaned_url = self._clean_repository_url(repo_url)
                if cleaned_url != repo_url:
                    self.logger.info(f"🧹 URL repository nettoyée: '{repo_url[:50]}...' → '{cleaned_url}'")
                    repo_url = cleaned_url
            
            self.logger.info(f"📥 Clonage du repository: {repo_url}")
            clone_success = False
            clone_result = {"success": False, "stderr": "Aucune tentative effectuée"} 
            
            if not repo_url or not repo_url.strip():
                self.logger.warning("⚠️ Aucune URL de repository fournie - création d'un workspace vide")
            elif not self._is_valid_git_url(repo_url):
                self.logger.warning(f"⚠️ URL repository invalide après nettoyage: {repo_url} - création d'un workspace vide")
            else:
                await self._prepare_clean_workspace()
                
                clone_attempts = [
                    (f"git clone --depth 1 {repo_url} .", "Clonage superficiel rapide"),
                    (f"git clone {repo_url} .", "Clonage complet"),
                    (f"git -c http.sslVerify=false clone --depth 1 {repo_url} .", "SSL désactivé + superficiel"),
                    (f"git -c http.version=HTTP/1.1 clone --depth 1 {repo_url} .", "HTTP/1.1 + superficiel"),
                    (f"git -c http.postBuffer=524288000 clone --depth 1 {repo_url} .", "Buffer élevé + superficiel")
                ]
                
                for i, (clone_cmd, description) in enumerate(clone_attempts, 1):
                    self.logger.info(f"🔄 Tentative {i}/{len(clone_attempts)} - {description}")
                    
                    clone_result = await self._execute_command(clone_cmd, cwd=self.working_directory)
                    
                    if clone_result["success"]:
                        verification_result = await self._verify_clone_success()
                        if verification_result:
                            clone_success = True
                            self.logger.info(f"✅ Clonage réussi à la tentative {i} ({description})")
                            break
                        else:
                            self.logger.warning(f"⚠️ Clonage incomplet à la tentative {i}")
                    else:
                        self.logger.warning(f"❌ Échec tentative {i}: {clone_result.get('stderr', 'Erreur inconnue')}")

                    if i < len(clone_attempts):
                        await self._clean_failed_clone()
                        await asyncio.sleep(i * 2)  
            
            if not clone_success:
                self.logger.warning("⚠️ Clonage échoué - création d'un workspace vide")
                await self._create_minimal_workspace(branch)
            else:
                if is_reactivation:
                    self.logger.info(f"🔄 [RÉACTIVATION] Checkout de {source_branch} (dernière version)")
                    
                    checkout_source_result = await self._execute_command(
                        f"git checkout {source_branch} || git checkout main || git checkout master", 
                        cwd=self.working_directory
                    )
                    
                    if checkout_source_result["success"]:
                        pull_result = await self._execute_command(f"git pull origin {source_branch}", cwd=self.working_directory)
                        if pull_result["success"]:
                            self.logger.info(f"✅ Dernière version de {source_branch} récupérée")
                        else:
                            self.logger.warning(f"⚠️ Pull échoué, utilisation version locale de {source_branch}")
                        
                        self.logger.info(f"🌿 Création branche de réactivation: {branch}")
                        checkout_new_result = await self._execute_command(
                            f"git checkout -b {branch}", 
                            cwd=self.working_directory
                        )
                        
                        if checkout_new_result["success"]:
                            self.logger.info(f"✅ Branche de réactivation {branch} créée depuis {source_branch}")
                        else:
                            self.logger.error(f"❌ Échec création branche {branch}")
                    else:
                        self.logger.error(f"❌ Impossible de checkout {source_branch}")
                        
                else:
                    self.logger.info(f"🌿 Création ou récupération de la branche: {branch}")
                    checkout_result = await self._execute_command(f"git checkout -b {branch} || git checkout {branch}", cwd=self.working_directory)
                    
                    if not checkout_result["success"]:
                        self.logger.warning(f"⚠️ Impossible de gérer la branche {branch} - utilisation de master/main")
                        default_branch_result = await self._execute_command("git branch --show-current", cwd=self.working_directory)
                        if default_branch_result["success"]:
                            current_branch = default_branch_result["stdout"].strip()
                            self.logger.info(f"📝 Utilisation de la branche existante: {current_branch}")
            
            dependency_installed = await self._install_dependencies()
            
            await self._ensure_basic_structure()
            
            if not self.working_directory or not os.path.exists(self.working_directory):
                self.logger.error(f"❌ Working directory invalide avant retour: {self.working_directory}")
                return {
                    "success": False,
                    "error": f"Working directory invalide: {self.working_directory}",
                    "working_directory": None
                }
            
            return {
                "success": True,  
                "working_directory": self.working_directory,
                "branch": branch,
                "repo_url": repo_url,
                "clone_success": clone_success,
                "dependencies_installed": dependency_installed,
                "fallback_mode": not clone_success,
                "is_reactivation": is_reactivation,  
                "source_branch": source_branch if is_reactivation else None  
            }
            
        except Exception as e:
            self.logger.error(f"❌ Exception dans setup_environment: {e}")
            
            emergency_workspace = "/tmp/ai_agent_emergency"
            try:
                os.makedirs(emergency_workspace, exist_ok=True)
                self.working_directory = emergency_workspace
                
                return {
                    "success": True,  
                    "working_directory": emergency_workspace,
                    "branch": branch,
                    "repo_url": repo_url,
                    "clone_success": False,
                    "dependencies_installed": False,
                    "emergency_mode": True,
                    "error": str(e)
                }
            except Exception as fatal_error:
                return self.handle_error(fatal_error, "configuration de l'environnement")

    async def _create_essential_log_files(self):
        """Crée les fichiers de log essentiels souvent recherchés par le debug."""
        log_files = {
            "error.log": "# Log des erreurs\n# Créé automatiquement par AI-Agent\n\n",
            "debug.log": "# Log de debug\n# Créé automatiquement par AI-Agent\n\n", 
            "test.log": "# Log des tests\n# Créé automatiquement par AI-Agent\n\n",
            ".pytest_cache/README.md": "# Cache pytest\nCe dossier contient le cache de pytest\n"
        }
        
        for log_file, content in log_files.items():
            file_path = os.path.join(self.working_directory, log_file)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.logger.debug(f"📝 Créé: {log_file}")
    
    async def _create_dependency_failure_log(self, lang_name: str, install_result: Dict[str, Any]):
        """Crée un log d'échec d'installation des dépendances pour diagnostic."""
        failure_log = f"""# Échec installation dépendances - {lang_name}
Date: {datetime.now().isoformat()}
Commande: {install_result.get('command', 'N/A')}
Code sortie: {install_result.get('exit_code', 'N/A')}

## Erreur:
{install_result.get('stderr', 'Aucune erreur capturée')}

## Sortie:
{install_result.get('stdout', 'Aucune sortie capturée')}
"""
        
        log_path = os.path.join(self.working_directory, f"dependency_failure_{lang_name.lower().replace(' ', '_')}.log")
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(failure_log)
    
    async def _create_minimal_requirements(self):
        """Crée un requirements.txt minimal si aucun fichier de dépendance n'existe."""
        req_path = os.path.join(self.working_directory, "requirements.txt")
        
        if not os.path.exists(req_path):
            minimal_reqs = """# Requirements générés automatiquement par AI-Agent
# Ajoutez vos dépendances ici

# Dépendances de base communes
requests>=2.25.0
pytest>=6.0.0
black>=21.0.0
flake8>=3.8.0
"""
            with open(req_path, 'w', encoding='utf-8') as f:
                f.write(minimal_reqs)
            self.logger.info("📝 Créé requirements.txt minimal")
    
    async def _ensure_project_structure(self):
        """S'assure que les dossiers essentiels existent."""
        essential_dirs = [
            "tests", "test", "__pycache__", ".pytest_cache",
            "logs", "tmp", "temp", "build", "dist"
        ]
        
        for dir_name in essential_dirs:
            dir_path = os.path.join(self.working_directory, dir_name)
            os.makedirs(dir_path, exist_ok=True)
    
    async def _ensure_gitignore(self):
        """Crée un .gitignore minimal s'il n'existe pas."""
        gitignore_path = os.path.join(self.working_directory, ".gitignore")
        
        if not os.path.exists(gitignore_path):
            gitignore_content = """# AI-Agent generated .gitignore

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.env
venv/
env/
*.egg-info/
dist/
build/

# Tests
.pytest_cache/
.coverage
htmlcov/
.tox/

# Logs
*.log
logs/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Dependencies
node_modules/
"""
            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write(gitignore_content)
            self.logger.info("📝 Créé .gitignore minimal")
    
    async def _create_minimal_workspace(self, branch: str):
        """Crée un workspace minimal quand le clonage échoue."""
        self.logger.info("🔧 Création d'un workspace minimal...")
        
        try:
            await self._execute_command("git init", cwd=self.working_directory)
            await self._execute_command(f"git checkout -b {branch}", cwd=self.working_directory)
            self.logger.info(f"✅ Workspace git minimal créé avec branche {branch}")
        except:
            self.logger.warning("⚠️ Impossible d'initialiser git - workspace sans version")
        
        basic_files = {
            "README.md": f"# Workspace AI-Agent\n\nBranche: {branch}\nCréé automatiquement\n",
            "main.py": "# Fichier principal\nprint('Hello AI-Agent')\n",
            ".gitignore": "__pycache__/\n*.pyc\n.env\nnode_modules/\n"
        }
        
        for filename, content in basic_files.items():
            file_path = os.path.join(self.working_directory, filename)
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            except:
                pass  
    
    async def _install_dependencies(self) -> bool:
        """Installe les dépendances de manière robuste."""
        install_commands = [
            ("pip install -r requirements.txt", "requirements.txt"),
            ("npm install --silent", "package.json"),
            ("pip install -e .", "setup.py"),
        ]
        
        dependency_installed = False
        for cmd, dependency_file in install_commands:
            file_path = os.path.join(self.working_directory, dependency_file)
            if os.path.exists(file_path):
                self.logger.info(f"📦 Installation: {cmd}")
                install_result = await self._execute_command(cmd, cwd=self.working_directory)
                if install_result["success"]:
                    dependency_installed = True
                else:
                    self.logger.warning(f"⚠️ Échec: {cmd}")
        
        return dependency_installed
    
    async def _ensure_basic_structure(self):
        """Assure une structure de projet de base."""
        basic_dirs = ["src", "tests", "docs"]
        for dir_name in basic_dirs:
            dir_path = os.path.join(self.working_directory, dir_name)
            os.makedirs(dir_path, exist_ok=True)
    
    def _get_full_path(self, file_path: str) -> str:
        """Retourne le chemin complet d'un fichier."""
        if os.path.isabs(file_path):
            return file_path
        
        working_dir = getattr(self, 'working_directory', None)
        if hasattr(working_dir, 'default'):
            working_dir = working_dir.default
        
        base_dir = working_dir or os.getcwd()
        return os.path.join(base_dir, file_path) 

    async def _run_git_diagnostics(self):
        """Effectue des diagnostics Git préliminaires."""
        try:
            git_version_result = await self._execute_command("git --version")
            if git_version_result["success"]:
                self.logger.info(f"✅ Git disponible: {git_version_result['stdout'].strip()}")
            else:
                self.logger.warning("⚠️ Git non disponible ou non fonctionnel")
                return
            
            config_checks = [
                ("user.name", "git config --global user.name"),
                ("user.email", "git config --global user.email")
            ]
            
            for config_name, config_cmd in config_checks:
                result = await self._execute_command(config_cmd)
                if result["success"] and result["stdout"].strip():
                    self.logger.debug(f"✅ Config {config_name}: {result['stdout'].strip()}")
                else:
                    self.logger.info(f"📝 Configuration Git manquante: {config_name}")
                    if config_name == "user.name":
                        await self._execute_command("git config --global user.name 'AI-Agent'")
                    elif config_name == "user.email":
                        await self._execute_command("git config --global user.email 'ai-agent@smartelia.com'")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors des diagnostics Git: {e}")

    def _clean_repository_url(self, url: str) -> str:
        """
        Nettoie et extrait l'URL du repository depuis différents formats.
        
        Gère les cas comme :
        - "GitHub - user/repo - https://github.com/user/repo"
        - "https://github.com/user/repo"
        - "git@github.com:user/repo"
        """
        if not url or not isinstance(url, str):
            return ""
        
        import re
        url = url.strip()
        
        https_match = re.search(r'(https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?)', url, re.IGNORECASE)
        if https_match:
            clean_url = https_match.group(1)
            if clean_url.endswith('.git'):
                clean_url = clean_url[:-4]
            self.logger.debug(f"🧹 URL nettoyée: '{url}' → '{clean_url}'")
            return clean_url
        
        ssh_match = re.search(r'(git@github\.com:[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?)', url, re.IGNORECASE)
        if ssh_match:
            ssh_url = ssh_match.group(1)
            ssh_to_https = re.sub(r'git@github\.com:([^/]+)/([^.]+)(?:\.git)?', r'https://github.com/\1/\2', ssh_url)
            self.logger.debug(f"🧹 URL SSH → HTTPS: '{url}' → '{ssh_to_https}'")
            return ssh_to_https
        
        if re.match(r'^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/?$', url, re.IGNORECASE):
            return url
        
        self.logger.warning(f"⚠️ Impossible d'extraire une URL valide depuis: '{url}'")
        return url  
    
    def _is_valid_git_url(self, url: str) -> bool:
        """Valide si une URL est un repository Git valide."""
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        valid_patterns = [
            r'^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?/?$',
            r'^git@github\.com:[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?$',
            r'^https://gitlab\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?/?$',
            r'^https://bitbucket\.org/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?/?$'
        ]
        
        import re
        for pattern in valid_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        
        return False

    async def _prepare_clean_workspace(self):
        """Prépare un workspace propre pour le clonage."""
        try:
            if os.path.exists(self.working_directory):
                for item in os.listdir(self.working_directory):
                    if not item.startswith('.'):
                        item_path = os.path.join(self.working_directory, item)
                        if os.path.isdir(item_path):
                            import shutil
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                self.logger.debug("🧹 Workspace nettoyé avant clonage")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors du nettoyage workspace: {e}")

    async def _verify_clone_success(self) -> bool:
        """Vérifie que le clonage Git s'est bien passé."""
        try:
            git_dir = os.path.join(self.working_directory, ".git")
            if not os.path.exists(git_dir):
                return False
            
            status_result = await self._execute_command("git status --porcelain", cwd=self.working_directory)
            if not status_result["success"]:
                return False
            
            files_result = await self._execute_command("find . -type f -not -path './.git/*' | head -5", cwd=self.working_directory)
            if files_result["success"] and files_result["stdout"].strip():
                self.logger.debug(f"✅ Repository contient des fichiers: {len(files_result['stdout'].strip().split())} fichiers trouvés")
                return True
            
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors de la vérification du clonage: {e}")
            return False

    async def _clean_failed_clone(self):
        """Nettoie les restes d'un clonage échoué."""
        try:
            if os.path.exists(self.working_directory):
                for item in os.listdir(self.working_directory):
                    item_path = os.path.join(self.working_directory, item)
                    if os.path.isdir(item_path):
                        import shutil
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                self.logger.debug("🧹 Nettoyage après échec de clonage")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors du nettoyage: {e}") 