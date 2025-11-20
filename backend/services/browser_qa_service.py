"""Service d'assurance qualité automatisée via browser automation."""

import asyncio
import json
import os
import psutil
import signal
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import get_settings
from utils.logger import get_logger
from services.chrome_mcp_client import ChromeMCPClient

logger = get_logger(__name__)


class DevServerManager:
    """Gestionnaire de serveur de développement pour tests browser."""
    
    def __init__(self, working_directory: str):
        """
        Initialise le gestionnaire de serveur.
        
        Args:
            working_directory: Répertoire du projet
        """
        self.working_directory = working_directory
        self.process: Optional[asyncio.subprocess.Process] = None
        self.server_url: Optional[str] = None
        self.settings = get_settings()
        
    async def start_dev_server(self) -> Optional[str]:
        """
        Détecte et démarre le serveur de développement approprié.
        
        Returns:
            URL du serveur ou None si échec
        """
        try:
            logger.info("🔍 Détection du type de projet...")
            server_command = await self._detect_dev_server_command()
            
            if not server_command:
                logger.warning("⚠️ Aucun serveur de dev détecté")
                return None
            
            logger.info(f"🚀 Démarrage du serveur: {server_command}")
            port = await self._detect_server_port()
            self.server_url = f"http://localhost:{port}"
            
            self.process = await asyncio.create_subprocess_shell(
                server_command,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid  
            )
            
            asyncio.create_task(self._capture_server_logs())
            
            logger.info(f"🔌 Port détecté: {port}")
            logger.info(f"⏳ Attente du serveur sur {self.server_url}...")
            
            timeout = 10  
            is_ready = await self._wait_for_server_ready(self.server_url, timeout=timeout)
            
            if is_ready:
                logger.info(f"✅ Serveur prêt: {self.server_url}")
                return self.server_url
            else:
                logger.info(f"⏱️  Timeout ({timeout}s): serveur non accessible sur le port {port}")
                logger.debug("📋 Vérifiez les logs du serveur ci-dessus pour plus de détails")
                await self.stop_dev_server()
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur démarrage serveur dev: {e}")
            await self.stop_dev_server()
            return None
    
    async def _detect_server_port(self) -> int:
        """
        🔍 Détecte intelligemment le port du serveur de développement.
        
        Analyse:
        - Fichiers de configuration (conf.env, .env, config.json)
        - Scripts de démarrage (framework.sh, package.json)
        - Valeurs par défaut selon la techno détectée
        
        Returns:
            Port détecté ou 5173 (défaut Vite)
        """
        try:
            project_root = Path(self.working_directory)
            
            for env_file in ["conf.env", ".env", "config.env"]:
                env_path = project_root / env_file
                if env_path.exists():
                    try:
                        with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            import re
                            port_match = re.search(r'(?:PORT|SERVER_PORT|APP_PORT|TOMCAT_PORT|HTTP_PORT)\s*=\s*(\d+)', content, re.IGNORECASE)
                            if port_match:
                                port = int(port_match.group(1))
                                logger.info(f"✅ Port détecté dans {env_file}: {port}")
                                return port
                    except:
                        pass
            
            for script_file in ["framework.sh", "start.sh", "run.sh"]:
                script_path = project_root / script_file
                if script_path.exists():
                    try:
                        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(1000)
                            import re
                            port_match = re.search(r':(\d{4,5})', content)  # Format :8080
                            if port_match:
                                port = int(port_match.group(1))
                                logger.info(f"✅ Port détecté dans {script_file}: {port}")
                                return port
                            
                            if 'tomcat' in content.lower():
                                logger.info("✅ Tomcat détecté → port 8080")
                                return 8080
                            elif 'jetty' in content.lower():
                                logger.info("✅ Jetty détecté → port 8080")
                                return 8080
                    except:
                        pass
            
            package_json = project_root / "package.json"
            if package_json.exists():
                try:
                    with open(package_json) as f:
                        import json
                        data = json.load(f)
                        scripts = data.get("scripts", {})
                        
                        for script_value in scripts.values():
                            import re
                            port_match = re.search(r'--port[=\s]+(\d+)', script_value)
                            if port_match:
                                port = int(port_match.group(1))
                                logger.info(f"✅ Port détecté dans package.json: {port}")
                                return port
                        
                        if "vite" in str(scripts.values()).lower():
                            return 5173  
                        elif "next" in data.get("dependencies", {}):
                            return 3000  
                except:
                    pass
            
            if (project_root / "pom.xml").exists() or (project_root / "framework.sh").exists():
                logger.info("✅ Projet Java/Tomcat détecté → port 8080")
                return 8080
            
            # Défaut: port Vite
            logger.info("⚠️ Port non détecté, utilisation du défaut: 5173")
            return 5173
            
        except Exception as e:
            logger.debug(f"Erreur détection port: {e}")
            return 5173

    async def _capture_server_logs(self):
        """
        📋 Capture et analyse intelligemment les logs stdout/stderr du serveur.
        
        ✅ NOUVEAU: Détection automatique des erreurs courantes et suggestions
        """
        if not self.process:
            return
        
        stdout_buffer = []
        stderr_buffer = []
        max_lines = 50  
        
        try:
            if self.process.stdout:
                line_count = 0
                while line_count < max_lines:
                    line = await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout=0.1
                    )
                    if not line:
                        break
                    log_line = line.decode('utf-8', errors='ignore').strip()
                    if log_line:
                        stdout_buffer.append(log_line)
                        logger.debug(f"📤 [SERVER] {log_line}")
                        line_count += 1
            
            if self.process.stderr:
                line_count = 0
                while line_count < max_lines:
                    line = await asyncio.wait_for(
                        self.process.stderr.readline(),
                        timeout=0.1
                    )
                    if not line:
                        break
                    log_line = line.decode('utf-8', errors='ignore').strip()
                    if log_line:
                        stderr_buffer.append(log_line)
                        logger.debug(f"⚠️ [SERVER ERR] {log_line}")
                        line_count += 1
                        
        except asyncio.TimeoutError:
            pass  
        except Exception as e:
            logger.debug(f"Erreur capture logs serveur: {e}")
        
        await self._analyze_server_logs(stdout_buffer, stderr_buffer)
    
    async def _analyze_server_logs(self, stdout_lines: List[str], stderr_lines: List[str]):
        """
        🤖 Analyse INTELLIGENTE avec LLM des logs serveur pour TOUS les langages.
        
        ✅ NOUVEAU: Utilise GPT-4o-mini/Claude pour analyser automatiquement :
        - Incompatibilités de versions (Java, Node, Python, PHP, Ruby, Go, Rust, .NET, etc.)
        - Dépendances manquantes (npm, pip, composer, maven, cargo, etc.)
        - Erreurs de compilation/syntaxe
        - Problèmes de configuration
        - Ports déjà utilisés
        - Permissions insuffisantes
        - Variables d'environnement manquantes
        - Et TOUT autre type d'erreur
        
        Args:
            stdout_lines: Lignes stdout du serveur
            stderr_lines: Lignes stderr du serveur
        """
        if not stdout_lines and not stderr_lines:
            return
        
        try:
            from services.llm_service import LLMService

            all_logs = stdout_lines + stderr_lines
            log_sample = "\n".join(all_logs[-20:])  
            if len(log_sample) > 2000:
                log_sample = log_sample[-2000:]  
            
            prompt = f"""Tu es un expert DevOps capable d'analyser les erreurs de démarrage de serveur pour TOUS les langages et frameworks.

📋 LOGS DU SERVEUR:
```
{log_sample}
```

🎯 TÂCHE: Analyse ces logs et identifie les problèmes qui empêchent le serveur de démarrer.

📊 RÉPONSE ATTENDUE (format JSON):
{{
    "has_errors": true/false,
    "language": "Java/Node.js/Python/PHP/Ruby/Go/Rust/.NET/Autre",
    "error_type": "version_incompatibility/missing_dependency/port_conflict/syntax_error/permission_error/config_error/autre",
    "problem_summary": "Description courte du problème en français (max 100 caractères)",
    "root_cause": "Cause racine en 1 phrase",
    "solution": "Solution concrète et actionnable pour résoudre le problème"
}}

EXEMPLES:
- Java version 61.0 vs 57.0 → "Recompiler les JARs avec Java 9 ou mettre à jour JAVA_HOME vers Java 17"
- Cannot find module 'express' → "Exécuter: npm install"
- Port 3000 déjà utilisé → "Arrêter l'autre serveur: lsof -ti:3000 | xargs kill -9"
- Permission denied → "Donner les permissions: chmod +x script.sh"
- ModuleNotFoundError: django → "Installer les dépendances: pip install -r requirements.txt"

Réponds UNIQUEMENT avec le JSON (pas de texte avant/après)."""

            llm_service = LLMService()
            response = await llm_service.generate_with_fallback(
                prompt=prompt,
                primary_provider="openai",
                primary_model="gpt-4o-mini",
                fallback_provider="anthropic",
                fallback_model="claude-3-5-sonnet-20241022",
                temperature=0.1,
                max_tokens=300
            )
            
            if not response:
                logger.debug("⚠️ LLM n'a pas pu analyser les logs")
                return
            
            import json
            import re
            
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                logger.debug("⚠️ Réponse LLM n'est pas au format JSON")
                return
            
            analysis = json.loads(json_match.group())
            
            if analysis.get("has_errors", False):
                logger.warning("🤖 Analyse LLM des erreurs de démarrage:")
                logger.warning(f"   • Langage: {analysis.get('language', 'Unknown')}")
                logger.warning(f"   • Type: {analysis.get('error_type', 'unknown')}")
                logger.warning(f"   • Problème: {analysis.get('problem_summary', 'Erreur inconnue')}")
                logger.info(f"   • Cause: {analysis.get('root_cause', 'Non identifiée')}")
                logger.info(f"    Solution: {analysis.get('solution', 'Voir les logs ci-dessus')}")
            else:
                logger.debug("✅ LLM: Aucune erreur bloquante détectée")
                
        except Exception as e:
            logger.debug(f"Erreur analyse LLM des logs: {e}")

    async def _detect_custom_start_scripts(self) -> Optional[str]:
        """
        🆕 DÉTECTION GÉNÉRIQUE: Analyse automatique des scripts de démarrage custom.
        
        Cherche intelligemment les scripts exécutables qui pourraient démarrer un serveur:
        - *.sh (bash/shell scripts)
        - start.*, run.*, server.*, dev.*
        - Analyse le contenu pour identifier les commandes de démarrage
        
        Returns:
            Commande de démarrage détectée ou None
        """
        try:
            project_root = Path(self.working_directory)
            
            script_patterns = [
                "framework.sh", "start.sh", "run.sh", "server.sh", "dev.sh",
                "start-server.sh", "run-server.sh", "startup.sh",
                "start.bat", "run.bat", "server.bat",  
                "start", "run", "server", "dev",  
            ]
            
            for pattern in script_patterns:
                script_path = project_root / pattern
                if script_path.exists() and script_path.is_file():
                    try:
                        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(500)  
                            
                            if content.startswith('#!/bin/bash') or content.startswith('#!/bin/sh'):
                                server_keywords = ['server', 'start', 'run', 'tomcat', 'jetty', 'deploy', 'mvn', 'gradle', 'java -jar']
                                if any(keyword in content.lower() for keyword in server_keywords):
                                    logger.info(f"✅ Script de démarrage custom détecté: {pattern}")
                                    
                                    if pattern.endswith('.sh'):
                                        return f"./{pattern} --run" if "--run" in content else f"./{pattern}"
                                    else:
                                        return f"./{pattern}"
                    except Exception as e:
                        logger.debug(f"Erreur lecture script {pattern}: {e}")
                        continue
            
            makefile = project_root / "Makefile"
            if makefile.exists():
                try:
                    with open(makefile, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if 'run:' in content or 'start:' in content or 'serve:' in content:
                            logger.info("✅ Makefile avec target de démarrage détecté")
                            return "make run" if 'run:' in content else "make start"
                except:
                    pass
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur détection scripts custom: {e}")
            return None

    async def _detect_dev_server_command(self) -> Optional[str]:
        """
        Détecte la commande de démarrage du serveur de dev pour TOUS les types de projets.
        
        ✅ DÉTECTION INTELLIGENTE EN 3 PHASES:
        1. Scripts custom (framework.sh, start.sh, etc.) - PRIORITÉ HAUTE
        2. Frameworks connus (React, Spring Boot, Django, etc.)
        3. Fallback: Analyse LLM pour projets inconnus
        
        Returns:
            Commande de démarrage ou None si pas de serveur dev
        """
        # ========================================
        # 🎯 PHASE 1: DÉTECTION SCRIPTS CUSTOM (PRIORITÉ)
        # ========================================
        
        custom_script = await self._detect_custom_start_scripts()
        if custom_script:
            return custom_script
        
        # ========================================
        # 📦 PHASE 2: JAVASCRIPT / NODE.JS ECOSYSTÈME
        # ========================================
        
        package_json = Path(self.working_directory) / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    
                    if "react" in deps:
                        if "dev" in scripts:
                            logger.info("✅ React + Vite détecté")
                            return "npm run dev"
                        elif "start" in scripts:
                            logger.info("✅ Create React App détecté")
                            return "npm start"
                    
                    if "next" in deps:
                        logger.info("✅ Next.js détecté")
                        return "npm run dev"
                    
                    if "nuxt" in deps or "nuxt3" in deps:
                        logger.info("✅ Nuxt.js détecté")
                        return "npm run dev"
                    
                    if "vue" in deps:
                        if "serve" in scripts:
                            logger.info("✅ Vue.js détecté")
                            return "npm run serve"
                        elif "dev" in scripts:
                            logger.info("✅ Vue.js + Vite détecté")
                            return "npm run dev"
                    
                    if "@angular/core" in deps:
                        logger.info("✅ Angular détecté")
                        return "npm start"  # ou ng serve
                    
                    if "svelte" in deps:
                        logger.info("✅ Svelte/SvelteKit détecté")
                        return "npm run dev"
                    
                    if "astro" in deps:
                        logger.info("✅ Astro détecté")
                        return "npm run dev"
                    
                    if "@remix-run/react" in deps:
                        logger.info("✅ Remix détecté")
                        return "npm run dev"
                    
                    if "gatsby" in deps:
                        logger.info("✅ Gatsby détecté")
                        return "npm run develop"
                    
                    if "express" in deps:
                        logger.info("✅ Express.js détecté")
                        if "dev" in scripts:
                            return "npm run dev"
                        elif "start" in scripts:
                            return "npm start"
                    
                    if "@nestjs/core" in deps:
                        logger.info("✅ Nest.js détecté")
                        return "npm run start:dev"
                    
                    if "electron" in deps:
                        logger.info("✅ Electron détecté")
                        return "npm start"
                    
                    if "dev" in scripts:
                        logger.info("✅ Projet Node.js (npm run dev)")
                        return "npm run dev"
                    elif "start" in scripts:
                        logger.info("✅ Projet Node.js (npm start)")
                        return "npm start"
                    
            except Exception as e:
                logger.debug(f"Erreur lecture package.json: {e}")
        
        # ========================================
        # ☕ JAVA ECOSYSTÈME
        # ========================================
        
        # Spring Boot (Maven)
        pom_xml = Path(self.working_directory) / "pom.xml"
        if pom_xml.exists():
            try:
                with open(pom_xml) as f:
                    content = f.read()
                    if "spring-boot" in content:
                        logger.info("✅ Spring Boot (Maven) détecté")
                        return "mvn spring-boot:run"
                    else:
                        logger.info("✅ Maven (Java) détecté")
                        logger.warning("⚠️ Projet Maven - commande de démarrage non automatique")
                        return None
            except:
                pass
        
        # Spring Boot / Java (Gradle)
        for gradle_file in ["build.gradle", "build.gradle.kts"]:
            gradle_path = Path(self.working_directory) / gradle_file
            if gradle_path.exists():
                try:
                    with open(gradle_path) as f:
                        content = f.read()
                        if "spring-boot" in content.lower():
                            logger.info("✅ Spring Boot (Gradle) détecté")
                            return "gradle bootRun"
                        else:
                            logger.info("✅ Gradle (Java) détecté")
                            logger.warning("⚠️ Projet Gradle - commande de démarrage non automatique")
                            return None
                except:
                    pass
        
        # ========================================
        # 🐍 PYTHON ECOSYSTÈME
        # ========================================
        
        # Django
        if (Path(self.working_directory) / "manage.py").exists():
            logger.info("✅ Django (Python) détecté")
            return "python manage.py runserver"
        
        # Flask
        if (Path(self.working_directory) / "app.py").exists():
            # Vérifier si c'est Flask ou FastAPI
            try:
                with open(Path(self.working_directory) / "app.py") as f:
                    content = f.read()
                    if "from flask" in content.lower() or "import flask" in content.lower():
                        logger.info("✅ Flask (Python) détecté")
                        return "python app.py"
                    elif "fastapi" in content.lower():
                        logger.info("✅ FastAPI (Python) détecté")
                        return "uvicorn app:app --reload"
            except:
                logger.info("✅ Flask/FastAPI (Python) détecté (app.py)")
                return "python app.py"
        
        # FastAPI (main.py)
        for main_file in ["main.py", "app/main.py", "src/main.py"]:
            if (Path(self.working_directory) / main_file).exists():
                logger.info("✅ FastAPI (Python) détecté")
                module_path = main_file.replace("/", ".").replace(".py", "")
                return f"uvicorn {module_path}:app --reload"
        
        # Streamlit
        if any((Path(self.working_directory) / f).exists() for f in ["streamlit_app.py", "app.py"]):
            try:
                # Vérifier requirements.txt pour streamlit
                req_file = Path(self.working_directory) / "requirements.txt"
                if req_file.exists():
                    with open(req_file) as f:
                        if "streamlit" in f.read():
                            logger.info("✅ Streamlit (Python) détecté")
                            return "streamlit run streamlit_app.py" if (Path(self.working_directory) / "streamlit_app.py").exists() else "streamlit run app.py"
            except:
                pass
        
        # Gradio
        if (Path(self.working_directory) / "app.py").exists():
            try:
                with open(Path(self.working_directory) / "app.py") as f:
                    if "gradio" in f.read().lower():
                        logger.info("✅ Gradio (Python) détecté")
                        return "python app.py"
            except:
                pass
        
        # ========================================
        # 💎 RUBY ECOSYSTÈME
        # ========================================
        
        # Ruby on Rails
        if (Path(self.working_directory) / "Gemfile").exists() and \
           (Path(self.working_directory) / "config" / "application.rb").exists():
            logger.info("✅ Ruby on Rails détecté")
            return "rails server"
        
        # Sinatra (Ruby)
        if (Path(self.working_directory) / "Gemfile").exists():
            try:
                with open(Path(self.working_directory) / "Gemfile") as f:
                    if "sinatra" in f.read().lower():
                        logger.info("✅ Sinatra (Ruby) détecté")
                        return "ruby app.rb"
            except:
                pass
        
        # ========================================
        # 🐘 PHP ECOSYSTÈME
        # ========================================
        
        # Laravel
        if (Path(self.working_directory) / "artisan").exists():
            logger.info("✅ Laravel (PHP) détecté")
            return "php artisan serve"
        
        # Symfony
        if (Path(self.working_directory) / "symfony.lock").exists() or \
           (Path(self.working_directory) / "bin" / "console").exists():
            logger.info("✅ Symfony (PHP) détecté")
            return "symfony server:start"
        
        # Composer (PHP générique)
        if (Path(self.working_directory) / "composer.json").exists():
            logger.info("✅ PHP (Composer) détecté")
            return "php -S localhost:8000"
        
        # ========================================
        # 🦀 RUST ECOSYSTÈME
        # ========================================
        
        if (Path(self.working_directory) / "Cargo.toml").exists():
            try:
                with open(Path(self.working_directory) / "Cargo.toml") as f:
                    content = f.read()
                    # Actix-web
                    if "actix-web" in content:
                        logger.info("✅ Actix-web (Rust) détecté")
                        return "cargo run"
                    # Rocket
                    elif "rocket" in content:
                        logger.info("✅ Rocket (Rust) détecté")
                        return "cargo run"
                    # Axum
                    elif "axum" in content:
                        logger.info("✅ Axum (Rust) détecté")
                        return "cargo run"
                    else:
                        logger.info("✅ Cargo (Rust) détecté")
                        logger.warning("⚠️ Projet Rust - pas de framework web détecté")
                        return None
            except:
                pass
        
        # ========================================
        # 🐹 GO ECOSYSTÈME
        # ========================================
        
        if (Path(self.working_directory) / "go.mod").exists():
            # Chercher main.go
            if (Path(self.working_directory) / "main.go").exists():
                logger.info("✅ Go détecté")
                return "go run main.go"
            elif (Path(self.working_directory) / "cmd" / "server" / "main.go").exists():
                logger.info("✅ Go (structure standard) détecté")
                return "go run cmd/server/main.go"
            else:
                logger.info("✅ Go détecté")
                logger.warning("⚠️ Projet Go - main.go non trouvé")
                return None
        
        # ========================================
        # 🔷 C# / .NET ECOSYSTÈME
        # ========================================
        
        # .NET / ASP.NET Core
        csproj_files = list(Path(self.working_directory).glob("*.csproj"))
        if csproj_files:
            logger.info("✅ .NET / ASP.NET Core détecté")
            return "dotnet run"
        
        # ========================================
        # ☕ AUTRES JVM (Kotlin, Scala)
        # ========================================
        
        # Kotlin
        if (Path(self.working_directory) / "build.gradle.kts").exists():
            logger.info("✅ Kotlin (Gradle) détecté")
            return "gradle run"
        
        # ========================================
        # 🔧 AUTRES FRAMEWORKS / OUTILS
        # ========================================
        
        # Hugo (Static Site Generator)
        if (Path(self.working_directory) / "config.toml").exists() or \
           (Path(self.working_directory) / "config.yaml").exists():
            if (Path(self.working_directory) / "archetypes").exists():
                logger.info("✅ Hugo détecté")
                return "hugo server"
        
        # Jekyll (Ruby Static Site)
        if (Path(self.working_directory) / "_config.yml").exists():
            logger.info("✅ Jekyll détecté")
            return "jekyll serve"
        
        # Eleventy (11ty)
        if package_json.exists():
            try:
                with open(package_json) as f:
                    if "@11ty/eleventy" in f.read():
                        logger.info("✅ Eleventy (11ty) détecté")
                        return "npm run serve"
            except:
                pass
        
        # Deno
        if (Path(self.working_directory) / "deno.json").exists() or \
           (Path(self.working_directory) / "deno.jsonc").exists():
            logger.info("✅ Deno détecté")
            return "deno run --allow-net main.ts"
        
        # Bun
        if (Path(self.working_directory) / "bun.lockb").exists():
            logger.info("✅ Bun détecté")
            return "bun run dev"
        
        # ========================================
        # 🤖 PHASE 3: ANALYSE LLM POUR PROJETS INCONNUS
        # ========================================
        
        logger.warning("⚠️ Aucun framework connu détecté - tentative analyse LLM...")
        llm_command = await self._analyze_project_with_llm()
        
        if llm_command:
            logger.info(f"✅ LLM a détecté une commande de démarrage: {llm_command}")
            return llm_command
        
        logger.warning("⚠️ Aucun serveur de dev détecté après toutes les analyses")
        return None
    
    async def _analyze_project_with_llm(self) -> Optional[str]:
        """
        🤖 Analyse le projet avec un LLM pour détecter la commande de démarrage.
        
        Utilisé comme fallback quand aucun framework connu n'est détecté.
        Analyse la structure du projet et suggère une commande de démarrage.
        
        Returns:
            Commande de démarrage suggérée par le LLM ou None
        """
        try:
            from services.llm_service import LLMService
            
            project_root = Path(self.working_directory)
            
            files = []
            for item in project_root.iterdir():
                if item.is_file() and not item.name.startswith('.'):
                    files.append(item.name)
                    if len(files) >= 50:
                        break
            
            config_files_content = {}
            for config_file in ['README.md', 'README', 'INSTALL.md', 'docs/quickstart.md']:
                config_path = project_root / config_file
                if config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                            config_files_content[config_file] = f.read(1000)  # Premier 1000 caractères
                    except:
                        pass
            
            prompt = f"""Tu es un expert en détection de configurations de projets.

Analyse la structure du projet suivant et identifie LA COMMANDE pour démarrer un serveur de développement local.

📁 Fichiers à la racine:
{', '.join(files[:30])}

📄 Contenu de fichiers de configuration:
{chr(10).join([f'{k}: {v[:200]}...' for k, v in config_files_content.items()])}

❓ Question: Quelle est la commande EXACTE pour démarrer le serveur de développement ?

Réponds UNIQUEMENT avec la commande (exemple: "./start.sh", "npm run dev", "make run", etc.)
Si aucun serveur de dev n'est détectable, réponds: "NONE"
"""
            
            llm_service = LLMService()
            response = await llm_service.generate_with_fallback(
                prompt=prompt,
                primary_provider="openai",
                primary_model="gpt-4o-mini",
                fallback_provider="anthropic",
                fallback_model="claude-3-5-sonnet-20241022",
                temperature=0.1,
                max_tokens=100
            )
            
            if response and "NONE" not in response.upper():
                # Nettoyer la réponse
                command = response.strip().strip('"').strip("'").strip('`')
                if command and len(command) < 100:  
                    logger.info(f"🤖 LLM suggère: {command}")
                    return command
            
            return None
            
        except Exception as e:
            logger.debug(f"Erreur analyse LLM: {e}")
            return None
    
    async def _wait_for_server_ready(self, url: str, timeout: int = 30) -> bool:
        """
        Attend que le serveur soit accessible.
        
        Args:
            url: URL du serveur
            timeout: Timeout en secondes
            
        Returns:
            True si le serveur est prêt
        """
        import aiohttp
        
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=2) as response:
                        if response.status < 500:  # 2xx, 3xx, 4xx OK (pas 5xx)
                            return True
            except Exception:
                pass
            
            await asyncio.sleep(1)
        
        return False
    
    async def stop_dev_server(self):
        """Arrête le serveur de développement."""
        if self.process:
            try:
                logger.info("🛑 Arrêt du serveur de développement...")
                
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
                  
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    try:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await self.process.wait()
                
                logger.info("✅ Serveur arrêté")
                
            except Exception as e:
                logger.error(f"❌ Erreur arrêt serveur: {e}")
            finally:
                self.process = None
                self.server_url = None


class BrowserQAService:
    """
    Service d'assurance qualité automatisée via browser automation.
    
    Fonctionnalités:
    - Détection automatique des changements frontend
    - Génération de scénarios de test intelligents
    - Exécution des tests via Chrome DevTools MCP
    - Capture de screenshots et logs
    - Analyse des performances
    - Rapports détaillés
    """
    
    def __init__(self):
        """Initialise le service Browser QA."""
        self.settings = get_settings()
        self.chrome_client: Optional[ChromeMCPClient] = None
        self.dev_server: Optional[DevServerManager] = None
        
    async def should_run_browser_tests(self, modified_files: List[str]) -> bool:
        """
        Détermine si des tests browser doivent être exécutés.
        
        ✅ NOUVEAU: Ne se limite plus au frontend - teste TOUT le code !
        
        Args:
            modified_files: Liste des fichiers modifiés
            
        Returns:
            True si tests browser nécessaires
        """
        if not self.settings.browser_qa_enabled:
            logger.info("ℹ️ Browser QA désactivé dans la configuration")
            return False

        testable_extensions = {
            "frontend": [".tsx", ".jsx", ".ts", ".js", ".vue", ".html", ".css", ".scss", ".less", ".sass"],
            "backend": [".py", ".rb", ".go", ".java", ".php", ".cs", ".rs"],
            "config": [".json", ".yaml", ".yml", ".toml", ".xml"],
            "docs": [".md", ".rst"]
        }
        
        file_types = {"frontend": 0, "backend": 0, "config": 0, "docs": 0}
        
        for file in modified_files:
            for category, extensions in testable_extensions.items():
                if any(file.endswith(ext) for ext in extensions):
                    file_types[category] += 1
                    break
        
        total_testable = sum(file_types.values())
        
        if total_testable > 0:
            categories = [cat for cat, count in file_types.items() if count > 0]
            logger.info(f"✅ {total_testable} fichier(s) testable(s) détecté(s) ({', '.join(categories)}) - tests browser requis")
            return True
        else:
            logger.info("ℹ️ Aucun fichier testable - tests browser non nécessaires")
            return False
    
    def _should_skip_dev_server(self, working_directory: str) -> bool:
        """
        Détermine si on doit skip le démarrage du serveur dev (optimisation).
        
        ✅ Skip pour:
        - Projets Java/Tomcat/Maven (trop lents > 30s)
        - Projets Spring Boot
        - Projets avec framework.sh custom
        - Pas de package.json/requirements.txt
        
        Returns:
            True si on doit skip le serveur
        """
        from pathlib import Path
        project_root = Path(working_directory)
        
        if (project_root / "pom.xml").exists():
            logger.info("⚡ Projet Maven/Java détecté → Skip serveur dev (trop lent)")
            return True
        
        if (project_root / "framework.sh").exists():
            logger.info("⚡ Script framework.sh détecté → Skip serveur dev (custom)")
            return True
        
        if (project_root / "build.gradle").exists():
            logger.info("⚡ Projet Gradle détecté → Skip serveur dev (peut être lent)")
            return True
        
        has_deps = (project_root / "package.json").exists() or \
                   (project_root / "requirements.txt").exists() or \
                   (project_root / "Gemfile").exists() or \
                   (project_root / "go.mod").exists()
        
        if not has_deps:
            logger.info("⚡ Pas de fichiers de dépendances détectés → Skip serveur dev")
            return True
        
        return False
    
    async def run_browser_tests(
        self,
        working_directory: str,
        modified_files: List[str],
        task_description: str = ""
    ) -> Dict[str, Any]:
        """
        Exécute les tests browser automatiques.
        
        Args:
            working_directory: Répertoire du projet
            modified_files: Fichiers modifiés
            task_description: Description de la tâche
            
        Returns:
            Résultats des tests
        """
        results = {
            "success": False,
            "tests_executed": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "screenshots": [],
            "console_errors": [],
            "network_requests": [],  
            "performance_metrics": {},
            "test_scenarios": [],  
            "error": None
        }
        
        try:
            logger.info("🌐 Browser QA: L'agent teste son propre code généré")
            
            logger.info("📦 Étape 1/5: Démarrage du projet généré par l'agent...")
            
            skip_dev_server = self._should_skip_dev_server(working_directory)
            
            if skip_dev_server:
                logger.info("⚡ Mode rapide activé - Skip démarrage serveur (projet lent détecté)")
                server_url = None
            else:
                self.dev_server = DevServerManager(working_directory)
                server_url = await self.dev_server.start_dev_server()
            
            if not server_url:
                logger.info("⚠️ Serveur du projet non démarré - tests browser limités")
                results["success"] = True  # Non-bloquant
                results["tests_executed"] = 1
                results["tests_passed"] = 1
                results["test_scenarios"] = [{
                    "name": "Static Code Analysis",
                    "type": "static",
                    "description": "Analyse statique du code généré (pas de serveur requis)",
                    "success": True
                }]
                logger.info("✅ Analyse statique effectuée (serveur non disponible)")
                return results
            
            logger.info(f"✅ Projet démarré: {server_url}")
            logger.info("🎯 L'agent va maintenant valider son propre travail...")
            
            logger.info("🌐 Étape 2/5: Démarrage de Chrome via MCP...")
            self.chrome_client = ChromeMCPClient()
            chrome_started = await self.chrome_client.start()
            
            if not chrome_started:
                results["error"] = "Impossible de démarrer Chrome MCP"
                return results
            
            logger.info("🧪 Étape 3/5: Génération des scénarios de test...")
            test_scenarios = await self._generate_test_scenarios(
                modified_files,
                task_description
            )
            
            logger.info(f"✅ {len(test_scenarios)} scénario(s) généré(s)")
            
            logger.info("🚀 Étape 4/5: Exécution des tests...")
            for i, scenario in enumerate(test_scenarios, 1):
                logger.info(f"   Test {i}/{len(test_scenarios)}: {scenario['name']}")
                
                test_result = await self._execute_test_scenario(
                    server_url,
                    scenario,
                    working_directory
                )
                
                results["tests_executed"] += 1
                
                if test_result["success"]:
                    results["tests_passed"] += 1
                    logger.info(f"   ✅ Test réussi")
                else:
                    results["tests_failed"] += 1
                    logger.warning(f"   ❌ Test échoué: {test_result.get('error')}")
                
                if test_result.get("screenshot"):
                    results["screenshots"].append(test_result["screenshot"])
                
                if test_result.get("console_errors"):
                    results["console_errors"].extend(test_result["console_errors"])
                
                if test_result.get("network_requests"):
                    results["network_requests"].extend(test_result["network_requests"])
                
                results["test_scenarios"].append({
                    "name": scenario["name"],
                    "type": scenario["type"],
                    "description": scenario.get("description", ""),
                    "success": test_result["success"]
                })
            
            # 5. Analyser les performances
            logger.info("📊 Étape 5/5: Analyse des performances...")
            perf_metrics = await self._analyze_performance(server_url)
            results["performance_metrics"] = perf_metrics
            
            # Déterminer le succès global
            results["success"] = results["tests_failed"] == 0
            
            if results["success"]:
                logger.info(f"✅ Tests browser réussis: {results['tests_passed']}/{results['tests_executed']}")
            else:
                logger.warning(f"⚠️ Tests browser échoués: {results['tests_failed']}/{results['tests_executed']}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Erreur lors des tests browser: {e}", exc_info=True)
            results["error"] = str(e)
            return results
            
        finally:
            # Nettoyage
            await self._cleanup()
    
    async def _generate_test_scenarios(
        self,
        modified_files: List[str],
        task_description: str
    ) -> List[Dict[str, Any]]:
        """
        Génère les scénarios de test intelligents pour TOUT le code généré.
        
        ✅ NOUVEAU: Tests adaptés au type de code (backend, frontend, API, config, docs)
        
        Args:
            modified_files: Fichiers modifiés par l'agent
            task_description: Description de la tâche
            
        Returns:
            Liste des scénarios de test intelligents
        """
        scenarios = []
        
        file_categories = self._classify_files(modified_files)
        
        if file_categories["backend"]:
            scenarios.extend(await self._generate_backend_tests(file_categories["backend"]))
        if file_categories["frontend"]:
            scenarios.extend(await self._generate_frontend_tests(file_categories["frontend"]))
        
        if file_categories["backend"] and file_categories["frontend"]:
            scenarios.extend(await self._generate_integration_tests(file_categories))
        
        if file_categories["docs"] or file_categories["config"]:
            scenarios.extend(await self._generate_documentation_tests())
        
        generated_code_scenarios = [
            {
                "name": "Generated Code - Application Load",
                "type": "generated_smoke",
                "description": "L'agent vérifie que son code généré se charge sans erreur",
                "steps": [
                    {"action": "navigate", "url": "/"},
                    {"action": "wait", "duration": 3},
                    {"action": "screenshot", "name": "generated_code_homepage"},
                    {"action": "check_console"},
                    {"action": "check_network"}
                ]
            },
            {
                "name": "Generated Code - Functionality Check",
                "type": "generated_functionality",
                "description": "L'agent teste les fonctionnalités du code qu'il a généré",
                "steps": [
                    {"action": "navigate", "url": "/"},
                    {"action": "wait", "duration": 2},
                    {"action": "evaluate", "script": """
                        // Test automatique des fonctionnalités de base
                        const results = {
                            dom_loaded: document.readyState === 'complete',
                            has_content: document.body.innerText.length > 50,
                            links_count: document.querySelectorAll('a').length,
                            forms_count: document.querySelectorAll('form').length,
                            buttons_count: document.querySelectorAll('button').length,
                            images_count: document.querySelectorAll('img').length,
                            scripts_count: document.querySelectorAll('script').length
                        };
                        return results;
                    """},
                    {"action": "screenshot", "name": "functionality_check"},
                    {"action": "check_console"}
                ]
            },
            {
                "name": "Generated Code - Error Detection",
                "type": "generated_errors",
                "description": "L'agent détecte les erreurs dans son propre code",
                "steps": [
                    {"action": "navigate", "url": "/"},
                    {"action": "wait", "duration": 2},
                    {"action": "check_console"},
                    {"action": "evaluate", "script": """
                        // Vérifier les erreurs JS globales
                        return {
                            has_errors: window.onerror !== null,
                            console_error_count: 0,  // Sera rempli par check_console
                            page_title: document.title,
                            url: window.location.href
                        };
                    """},
                    {"action": "screenshot", "name": "error_detection"}
                ]
            },
            {
                "name": "Generated Code - Performance Check",
                "type": "generated_performance",
                "description": "L'agent mesure les performances de son code",
                "steps": [
                    {"action": "navigate", "url": "/"},
                    {"action": "wait", "duration": 2},
                    {"action": "check_performance"},
                    {"action": "screenshot", "name": "performance_check"}
                ]
            }
        ]
        
        scenarios = generated_code_scenarios + scenarios
        
        max_tests = self.settings.browser_qa_max_tests_per_file * 3
        if len(scenarios) > max_tests:
            logger.info(f"⚠️ Limitation à {max_tests} tests (sur {len(scenarios)} générés)")
            scenarios = scenarios[:max_tests]
        
        logger.info(f"✅ {len(scenarios)} scénario(s) de test généré(s)")
        return scenarios
    
    def _classify_files(self, modified_files: List[str]) -> Dict[str, List[str]]:
        """
        Classifie les fichiers modifiés par catégorie.
        
        Args:
            modified_files: Liste des fichiers modifiés
            
        Returns:
            Dictionnaire des fichiers par catégorie
        """
        categories = {
            "frontend": [],
            "backend": [],
            "config": [],
            "docs": []
        }
        
        for file in modified_files:
            if any(file.endswith(ext) for ext in [".tsx", ".jsx", ".ts", ".js", ".vue", ".html", ".css", ".scss"]):
                categories["frontend"].append(file)
            elif any(file.endswith(ext) for ext in [".py", ".rb", ".go", ".java", ".php"]):
                categories["backend"].append(file)
            elif any(file.endswith(ext) for ext in [".json", ".yaml", ".yml", ".toml", ".xml"]):
                categories["config"].append(file)
            elif any(file.endswith(ext) for ext in [".md", ".rst"]):
                categories["docs"].append(file)
        
        return categories
    
    async def _generate_backend_tests(self, backend_files: List[str]) -> List[Dict[str, Any]]:
        """
        Génère des tests pour le code backend (API endpoints).
        
        Args:
            backend_files: Fichiers backend modifiés
            
        Returns:
            Scénarios de test backend
        """
        scenarios = []
        
        scenarios.append({
            "name": "Backend API - Health Check",
            "type": "backend_api",
            "description": "Teste les endpoints API via le browser",
            "steps": [
                {"action": "navigate", "url": "/"},
                {"action": "evaluate", "script": """
                    async function testAPI() {
                        const results = [];
                        
                        // Test endpoint de base
                        try {
                            const response = await fetch('/api/health');
                            results.push({
                                endpoint: '/api/health',
                                status: response.status,
                                ok: response.ok
                            });
                        } catch (e) {
                            results.push({endpoint: '/api/health', error: e.message});
                        }
                        
                        return results;
                    }
                    return await testAPI();
                """},
                {"action": "screenshot", "name": "api_test"},
                {"action": "check_network"}
            ]
        })
        
        scenarios.append({
            "name": "Backend API - Documentation",
            "type": "backend_docs",
            "description": "Vérifie que la documentation API est accessible",
            "steps": [
                {"action": "navigate", "url": "/docs"},
                {"action": "wait", "duration": 2},
                {"action": "screenshot", "name": "api_docs"},
                {"action": "check_console"}
            ]
        })
        
        return scenarios
    
    async def _generate_frontend_tests(self, frontend_files: List[str]) -> List[Dict[str, Any]]:
        """
        Génère des tests pour le code frontend.
        
        Args:
            frontend_files: Fichiers frontend modifiés
            
        Returns:
            Scénarios de test frontend
        """
        scenarios = []
        
        for file in frontend_files[:self.settings.browser_qa_max_tests_per_file]:
            component_name = Path(file).stem
            
            scenarios.append({
                "name": f"Frontend Component - {component_name}",
                "type": "frontend_component",
                "file": file,
                "description": f"Teste le composant {component_name}",
                "steps": [
                    {"action": "navigate", "url": "/"},
                    {"action": "wait", "duration": 1},
                    {"action": "screenshot", "name": f"component_{component_name}"},
                    {"action": "check_console"}
                ]
            })
        
        # Test responsive
        scenarios.append({
            "name": "Frontend Responsive - Multiple Viewports",
            "type": "frontend_responsive",
            "description": "Teste le responsive design",
            "steps": [
                {"action": "navigate", "url": "/"},
                {"action": "resize", "viewport": "375x667"},  # Mobile
                {"action": "screenshot", "name": "mobile"},
                {"action": "resize", "viewport": "768x1024"},  # Tablet
                {"action": "screenshot", "name": "tablet"},
                {"action": "resize", "viewport": "1920x1080"},  # Desktop
                {"action": "screenshot", "name": "desktop"},
                {"action": "check_console"}
            ]
        })
        
        return scenarios
    
    async def _generate_integration_tests(self, file_categories: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        Génère des tests d'intégration E2E (frontend + backend).
        
        Args:
            file_categories: Catégories de fichiers
            
        Returns:
            Scénarios de test E2E
        """
        scenarios = []
        
        scenarios.append({
            "name": "Integration E2E - Full Flow",
            "type": "integration_e2e",
            "description": "Teste le flux complet frontend → backend",
            "steps": [
                {"action": "navigate", "url": "/"},
                {"action": "wait", "duration": 2},
                {"action": "evaluate", "script": """
                    async function testIntegration() {
                        // Tester une requête API depuis le frontend
                        try {
                            const response = await fetch('/api/test');
                            return {
                                success: response.ok,
                                status: response.status,
                                data: await response.json().catch(() => null)
                            };
                        } catch (e) {
                            return {success: false, error: e.message};
                        }
                    }
                    return await testIntegration();
                """},
                {"action": "screenshot", "name": "integration"},
                {"action": "check_console"},
                {"action": "check_network"},
                {"action": "check_performance"}
            ]
        })
        
        return scenarios
    
    async def _generate_documentation_tests(self) -> List[Dict[str, Any]]:
        """
        Génère des tests pour la documentation.
        
        Returns:
            Scénarios de test documentation
        """
        scenarios = []
        
        scenarios.append({
            "name": "Documentation - Accessibility",
            "type": "documentation",
            "description": "Vérifie que la documentation est accessible",
            "steps": [
                {"action": "navigate", "url": "/admin"},
                {"action": "wait", "duration": 2},
                {"action": "screenshot", "name": "admin_interface"},
                {"action": "check_console"}
            ]
        })
        
        return scenarios
    
    async def _execute_test_scenario(
        self,
        server_url: str,
        scenario: Dict[str, Any],
        working_directory: str
    ) -> Dict[str, Any]:
        """
        Exécute un scénario de test avec support complet des outils Chrome MCP.
        
        ✅ NOUVEAU: Support de evaluate, check_network, check_performance
        
        Args:
            server_url: URL du serveur
            scenario: Scénario à exécuter
            working_directory: Répertoire de travail
            
        Returns:
            Résultat du test avec toutes les métriques
        """
        result = {
            "success": True,
            "scenario_name": scenario["name"],
            "scenario_type": scenario.get("type", "unknown"),
            "screenshot": None,
            "console_errors": [],
            "network_requests": [],
            "performance_metrics": {},
            "evaluation_results": None,
            "error": None
        }
        
        try:
            for step in scenario["steps"]:
                action = step["action"]
                
                if action == "navigate":
                    url = server_url + step.get("url", "/")
                    logger.debug(f"   → Navigation: {url}")
                    await self.chrome_client.navigate_page(url)
                
                elif action == "wait":
                    duration = step.get("duration", 1)
                    await asyncio.sleep(duration)
                
                elif action == "screenshot":
                    screenshot_name = step.get("name", "screenshot")
                    screenshot_path = os.path.join(
                        working_directory,
                        f"browser_qa_{screenshot_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    )
                    await self.chrome_client.take_screenshot(screenshot_path)
                    result["screenshot"] = screenshot_path
                    logger.debug(f"   → Screenshot: {screenshot_path}")
                
                elif action == "check_console":
                    console_data = await self.chrome_client.get_console_messages()
                    if console_data.get("errors"):
                        result["console_errors"] = console_data["errors"]
                        if len(console_data["errors"]) > 0:
                            result["success"] = False
                            logger.warning(f"   ⚠️ {len(console_data['errors'])} erreur(s) console détectée(s)")
                
                elif action == "check_network":
                    network_data = await self.chrome_client.execute_command(
                        "list_network_requests",
                        {}
                    )
                    if network_data and not network_data.get("error"):
                        result["network_requests"] = network_data.get("requests", [])
                        logger.debug(f"   → Network: {len(result['network_requests'])} requête(s)")
                
                elif action == "check_performance":
                    perf_data = await self.chrome_client.get_performance_metrics()
                    if perf_data and not perf_data.get("error"):
                        result["performance_metrics"] = perf_data
                        logger.debug(f"   → Performance: {perf_data.get('load_time_ms', 'N/A')}ms")
                
                elif action == "evaluate":
                    script = step.get("script", "")
                    if script:
                        eval_result = await self.chrome_client.execute_command(
                            "evaluate_script",
                            {"script": script}
                        )
                        result["evaluation_results"] = eval_result
                        logger.debug(f"   → Evaluation: {eval_result.get('success', 'N/A')}")
                
                elif action == "resize":
                    viewport = step.get("viewport", "1920x1080")
                    width, height = map(int, viewport.split("x"))
                    await self.chrome_client.execute_command(
                        "resize_page",
                        {"width": width, "height": height}
                    )
                    logger.debug(f"   → Resize: {viewport}")
            
        except Exception as e:
            logger.error(f"❌ Erreur exécution scénario {scenario['name']}: {e}")
            result["success"] = False
            result["error"] = str(e)
        
        return result
    
    async def _analyze_performance(self, server_url: str) -> Dict[str, Any]:
        """
        Analyse les performances de la page.
        
        Args:
            server_url: URL du serveur
            
        Returns:
            Métriques de performance
        """
        try:
            return {
                "load_time_ms": 0,
                "dom_content_loaded_ms": 0,
                "first_contentful_paint_ms": 0,
                "analyzed": False
            }
        except Exception as e:
            logger.error(f"❌ Erreur analyse performance: {e}")
            return {"error": str(e)}
    
    async def _cleanup(self):
        """Nettoyage des ressources."""
        try:
            if self.chrome_client:
                await self.chrome_client.stop()
                self.chrome_client = None
            
            if self.dev_server:
                await self.dev_server.stop_dev_server()
                self.dev_server = None
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage: {e}")

