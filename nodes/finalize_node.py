"""Nœud de finalisation - pousse le code et crée la Pull Request."""

from typing import Dict, Any
from models.state import GraphState
from models.schemas import PullRequestInfo
from tools.github_tool import GitHubTool
from utils.logger import get_logger
from utils.helpers import get_working_directory, validate_working_directory, ensure_working_directory
from utils.persistence_decorator import with_persistence
from services.database_persistence_service import db_persistence
from services.command_deduplication_service import command_deduplication_service
from services.base_branch_resolver import get_base_branch_resolver  
from services.evaluation.agent_output_logger import AgentOutputLogger

logger = get_logger(__name__)


@with_persistence("finalize_pr")
async def finalize_pr(state: GraphState) -> GraphState:
    """
    Nœud de finalisation : pousse le code et crée la Pull Request.

    Ce nœud :
    1. Pousse les changements vers GitHub
    2. Crée une Pull Request
    3. Ajoute des informations détaillées à la PR
    4. Prépare la mise à jour Monday

    Args:
        state: État actuel du graphe

    Returns:
        État mis à jour avec les informations de la PR
    """
    logger.info(f"🚀 Finalisation pour: {state['task'].title}")

    from utils.error_handling import ensure_state_integrity
    ensure_state_integrity(state)

    if "results" not in state or not isinstance(state["results"], dict):
        state["results"] = {}

    if "ai_messages" not in state["results"]:
        state["results"]["ai_messages"] = []

    if "error_logs" not in state["results"]:
        state["results"]["error_logs"] = []

    state["results"]["current_status"] = "FINALIZING".lower()
    state["results"]["ai_messages"].append("Début de la finalisation...")

    try:
        logger.info("🔍 Récupération du répertoire de travail...")
        working_directory = get_working_directory(state)
        logger.info(f"🔍 Répertoire de travail récupéré: {working_directory}")

        if not validate_working_directory(working_directory, "finalize_node"):
            logger.warning("⚠️ Répertoire de travail invalide, tentative de récupération...")
            try:
                working_directory = ensure_working_directory(state, "finalize_node_")
                logger.info(f"📁 Répertoire de travail de secours créé: {working_directory}")
            except Exception as e:
                error_msg = f"Impossible de créer un répertoire de travail pour la finalisation: {e}"
                logger.error(f"❌ {error_msg}")
                state["results"]["error_logs"].append(error_msg)
                state["results"]["ai_messages"].append(f"❌ {error_msg}")
                state["results"]["current_status"] = "failed"
                return state

        logger.info(f"🔍 Répertoire de travail validé: {working_directory}")
        task = state["task"]
        
        repo_url = (
            state["results"].get("repository_url") or 
            getattr(task, 'repository_url', None) or 
            ""
        )
        git_branch = (
            state["results"].get("git_branch") or 
            getattr(task, 'git_branch', None) or 
            getattr(task, 'branch_name', None) or 
            ""
        )
        
        if repo_url and isinstance(repo_url, str):
            import re
            # Format Monday.com: "GitHub - user/repo - https://github.com/user/repo"
            https_match = re.search(r'(https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?)', repo_url)
            if https_match:
                cleaned_url = https_match.group(1)
                if cleaned_url.endswith('.git'):
                    cleaned_url = cleaned_url[:-4]
                if cleaned_url != repo_url:
                    logger.info(f"🧹 URL repository nettoyée pour finalize: '{repo_url[:50]}...' → '{cleaned_url}'")
                    repo_url = cleaned_url
                    state["results"]["repository_url"] = cleaned_url
        
        logger.info(f"🔍 Repository URL: {repo_url}")
        logger.info(f"🔍 Git branch: {git_branch}")

        validation_errors = []
        
        if not repo_url or not repo_url.strip():
            validation_errors.append("URL du repository non définie")
        
        if not git_branch or not git_branch.strip():
            validation_errors.append("Branche Git non définie")
        
        if not working_directory:
            validation_errors.append("Répertoire de travail non défini")
            
        modified_files = state["results"].get("modified_files", [])
        if not modified_files:
            logger.warning("⚠️ Aucun fichier modifié détecté dans results - tentative de détection avec Git...")
            
            if working_directory:
                try:
                    import subprocess
                    import os
                    original_cwd = os.getcwd()
                    os.chdir(working_directory)
                    
                    result = subprocess.run(
                        ["git", "status", "--porcelain"], 
                        capture_output=True, 
                        text=True, 
                        timeout=30
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        git_modified_files = []
                        for line in result.stdout.strip().split('\n'):
                            if line.strip():
                                status = line[:2]
                                filepath = line[3:]
                                git_modified_files.append(filepath)
                        
                        if git_modified_files:
                            logger.info(f"✅ {len(git_modified_files)} fichiers modifiés détectés avec Git: {git_modified_files[:3]}...")
                            state["results"]["modified_files"] = git_modified_files
                            modified_files = git_modified_files
                        else:
                            logger.warning("⚠️ Git status ne montre aucun fichier modifié")
                    else:
                        logger.warning("⚠️ Impossible d'exécuter git status")
                        
                    os.chdir(original_cwd)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erreur lors de la détection Git: {e}")
                    if 'original_cwd' in locals():
                        os.chdir(original_cwd)
            
            if not modified_files:
                logger.warning("⚠️ Aucun fichier modifié détecté même avec Git - continuons quand même")
        
        if validation_errors:
            error_msg = f"Prérequis manquants pour la finalisation: {', '.join(validation_errors)}"
            logger.warning(f"⚠️ {error_msg}")
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"⚠️ {error_msg}")
            
            state["results"]["current_status"] = "validation_warnings"
            state["results"]["pr_skipped"] = True
            state["results"]["pr_skip_reason"] = error_msg
            
            state["results"]["should_continue"] = True
            state["results"]["skip_github"] = True
            
            logger.info(f"⚠️ PR ignorée - passage à la validation humaine (workflow continue)")
            return state

        state["results"]["ai_messages"].append("🚀 Création de la Pull Request...")

        logger.info("🔍 Génération du contenu PR...")
        pr_title, pr_body = await _generate_pr_content(task, state)
        logger.info(f"🔍 PR title généré: {pr_title[:50]}...")

        logger.info("🔍 Initialisation GitHubTool...")
        github_tool = GitHubTool()

        try:
            try:
                import subprocess
                import os
                original_cwd = os.getcwd()
                os.chdir(working_directory)
                
                config_result = subprocess.run(
                    ["git", "config", "--list"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if config_result.returncode == 0:
                    logger.info("✅ Configuration Git vérifiée")
                
                os.chdir(original_cwd)
            except Exception as e:
                logger.warning(f"⚠️ Impossible de vérifier la config Git: {e}")
                if 'original_cwd' in locals():
                    os.chdir(original_cwd)

            push_result = await github_tool._push_branch(
                working_directory=working_directory,
                branch=git_branch,
                repository_url=repo_url  
            )
            logger.info(f"�� Résultat push reçu: {type(push_result)} - {push_result}")

            push_success = False
            if hasattr(push_result, 'success'):
                push_success = push_result.success
                error_msg = getattr(push_result, 'error', push_result.message) if not push_success else None
            elif isinstance(push_result, dict):
                push_success = push_result.get("success", False)
                error_msg = push_result.get("error", "Erreur lors du push") if not push_success else None
            else:
                error_msg = "Résultat push invalide"

            if not push_success:
                if error_msg and "Aucun changement détecté" in error_msg:
                    logger.warning("⚠️ Aucun changement local - vérification si la branche existe déjà sur le remote...")
                    try:
                        import subprocess
                        original_cwd_check = os.getcwd()
                        os.chdir(working_directory)
                        
                        check_result = subprocess.run(
                            ["git", "ls-remote", "--heads", "origin", git_branch],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        os.chdir(original_cwd_check)
                        
                        if check_result.returncode == 0 and check_result.stdout.strip():
                            logger.info(f"✅ La branche {git_branch} existe déjà sur le remote")
                            logger.info("💡 Les fichiers ont été poussés pendant l'implémentation - continuons avec la PR")
                            push_success = True  
                        else:
                            logger.error(f"❌ La branche n'existe pas sur le remote et pas de changements locaux")
                            raise Exception(f"Échec push: {error_msg}")
                    except Exception as check_error:
                        logger.error(f"❌ Impossible de vérifier l'existence de la branche: {check_error}")
                        if 'original_cwd_check' in locals():
                            os.chdir(original_cwd_check)
                        raise Exception(f"Échec push: {error_msg}")
                else:
                    raise Exception(f"Échec push: {error_msg}")

            if push_success:
                logger.info(f"✅ Branche {git_branch} poussée avec succès (ou déjà présente sur le remote)")

            resolver = get_base_branch_resolver()
            monday_base_branch = getattr(task, 'base_branch', None)
            
            base_branch = await resolver.resolve_base_branch(
                task=task,
                repository_url=repo_url,
                monday_base_branch=monday_base_branch
            )
            
            logger.info(f"🎯 Branche de base résolue: {base_branch} pour PR")

            pr_result = await github_tool._arun(
                action="create_pull_request",
                repo_url=repo_url,
                head_branch=git_branch,
                base_branch=base_branch,  
                title=pr_title,
                body=pr_body
            )

            if pr_result and pr_result.get("success"):
                pr_info_dict = pr_result.get("pr_info")
                
                if not pr_info_dict:
                    raise ValueError("Données PR manquantes dans la réponse")
                
                required_fields = ["number", "url"]
                missing_fields = [field for field in required_fields if field not in pr_info_dict]
                
                if missing_fields:
                    raise ValueError(f"Champs PR manquants: {missing_fields}")
                
                if not isinstance(pr_info_dict["number"], int) or pr_info_dict["number"] <= 0:
                    raise ValueError(f"Numéro PR invalide: {pr_info_dict['number']}")
                
                if not isinstance(pr_info_dict["url"], str) or not pr_info_dict["url"].startswith('http'):
                    raise ValueError(f"URL PR invalide: {pr_info_dict['url']}")

                try:
                    pr_info = PullRequestInfo(**pr_info_dict)
                except Exception as schema_error:
                    raise ValueError(f"Erreur création objet PullRequestInfo: {schema_error}")

                state["results"]["pr_info"] = pr_info
                state["results"]["pr_url"] = pr_info.url
                state["results"]["pr_number"] = pr_info.number
                state["results"]["ai_messages"].append(f"✅ PR créée: #{pr_info.number} - {pr_info.url}")
                state["results"]["last_operation_result"] = f"PR créée: {pr_info.url}"

                logger.info(f"✅ PR créée avec succès - #{pr_info.number}: {pr_info.url}")
                
                try:
                    interaction_logger = AgentOutputLogger()
                    interaction_logger.log_agent_interaction(
                        monday_update_id=f"pr_{state['task'].monday_item_id}_{state.get('db_task_id', 'unknown')}",
                        monday_item_id=state['task'].monday_item_id,
                        input_text=state['task'].description or state['task'].title,
                        agent_output=f"PR #{pr_info.number} créée avec succès sur la branche {git_branch}. Titre: {pr_title}. URL: {pr_info.url}",
                        interaction_type='pr',
                        duration_seconds=state.get("results", {}).get("total_duration", 0.0),
                        success=True,
                        metadata={"pr_title": pr_title, "pr_body": pr_body[:200]},
                        repository_url=repo_url,
                        branch_name=git_branch,
                        pr_number=str(pr_info.number),
                        pr_url=pr_info.url,
                        assigned_to=getattr(state['task'], 'assignee', None),
                        creator_name=getattr(state['task'], 'creator_name', None)
                    )
                    logger.info(f"📊 Interaction PR loggée dans Excel")
                except Exception as log_error:
                    logger.warning(f"⚠️ Erreur logging interaction PR: {log_error}")
                
                try:
                    task_id = state.get("db_task_id")
                    task_run_id = state.get("db_run_id")
                    
                    if task_id and task_run_id:
                        await db_persistence.create_pull_request(
                            task_id=int(task_id),  
                            task_run_id=int(task_run_id),  
                            github_pr_number=pr_info.number,
                            github_pr_url=pr_info.url,
                            pr_title=pr_title,
                            pr_description=pr_body,
                            head_sha=None,  
                            base_branch="main",
                            feature_branch=git_branch
                        )
                        logger.info(f"💾 Pull request sauvegardée en base de données")
                    else:
                        logger.warning(f"⚠️ Impossible de sauvegarder la PR en base: task_id={task_id}, task_run_id={task_run_id}")
                except Exception as db_error:
                    logger.error(f"❌ Erreur sauvegarde PR en base: {db_error}")

                try:
                    metadata = state.get("metadata", {})
                    semantic_hash = metadata.get("semantic_hash")
                    
                    if semantic_hash:
                        await command_deduplication_service.initialize()
                        updated = await command_deduplication_service.update_command_pr_url(
                            semantic_hash=semantic_hash,
                            pr_url=pr_info.url
                        )
                        if updated:
                            logger.info(f"✅ URL PR mise à jour dans Redis pour déduplication: {pr_info.url}")
                        else:
                            logger.debug(f"⚠️ Commande non trouvée dans Redis (peut-être pas une commande @vydata)")
                    else:
                        logger.debug("ℹ️ Pas de semantic_hash - pas une commande @vydata ou Redis non utilisé")
                except Exception as e:
                    logger.error(f"❌ Erreur mise à jour Redis PR URL: {e}")
                
            elif pr_result and not pr_result.get("success"):
                error_msg = pr_result.get("error", "Erreur lors de la création de PR")
                raise Exception(f"GitHub API error: {error_msg}")
            else:
                raise Exception("Aucune réponse de l'API GitHub pour la création de PR")

        except Exception as pr_error:
            error_msg = f"Exception lors de la création PR: {str(pr_error)}"
            state["results"]["error_logs"].append(error_msg)
            state["results"]["ai_messages"].append(f"❌ Exception PR: {error_msg}")
            logger.error(error_msg, exc_info=True)

        state["results"]["should_continue"] = True
        state["results"]["waiting_human_validation"] = True
        
        try:
            task_id = state.get("db_task_id")
            task_run_id = state.get("db_run_id")
            
            if task_id and task_run_id:
                started_at = state.get("started_at")
                total_duration = None
                if started_at:
                    from datetime import datetime, timezone
                    now_utc = datetime.now(timezone.utc)
                    if started_at.tzinfo is None:
                        started_at = started_at.replace(tzinfo=timezone.utc)
                    total_duration = int((now_utc - started_at).total_seconds())
                
                ai_calls = state.get("results", {}).get("total_ai_calls", 0)
                total_tokens = state.get("results", {}).get("total_tokens_used", 0)
                total_cost = state.get("results", {}).get("total_ai_cost", 0.0)
                
                test_results_list = state.get("results", {}).get("test_results", [])
                test_coverage = None
                if test_results_list:
                    last_test = test_results_list[-1]
                    if isinstance(last_test, dict):
                        test_coverage = last_test.get("coverage", None)
                
                retry_attempts = state.get("results", {}).get("debug_attempts", 0)
                
                code_lines = 0
                code_changes = state.get("results", {}).get("code_changes", {})
                for file_code in code_changes.values():
                    if isinstance(file_code, str):
                        code_lines += len(file_code.split('\n'))
                
                await db_persistence.record_performance_metrics(
                    task_id=task_id,
                    task_run_id=task_run_id,
                    total_duration_seconds=total_duration,
                    ai_processing_time_seconds=None,  
                    testing_time_seconds=None,  
                    total_ai_calls=ai_calls,
                    total_tokens_used=total_tokens,
                    total_ai_cost=total_cost,
                    test_coverage_final=test_coverage,
                    retry_attempts=retry_attempts
                )
                logger.info(f"💾 Métriques de performance enregistrées pour task_id={task_id}, run_id={task_run_id}")
            else:
                logger.warning(f"⚠️ Impossible d'enregistrer les métriques: task_id={task_id}, task_run_id={task_run_id}")
        except Exception as metrics_error:
            logger.error(f"❌ Erreur enregistrement métriques de performance: {metrics_error}")

        try:
            from config.langsmith_config import langsmith_config
            if langsmith_config._client is not None:
                logger.info("🧹 Nettoyage du client LangSmith pour éviter SIGSEGV")
                langsmith_config._client = None
        except Exception as cleanup_error:
            logger.warning(f"⚠️ Erreur nettoyage LangSmith: {cleanup_error}")

        return state

    except Exception as e:
        error_msg = f"Exception lors de la finalisation: {str(e)}"
        logger.error(error_msg, exc_info=True)

        state["results"]["error_logs"].append(error_msg)
        state["results"]["ai_messages"].append(f"❌ Exception: {error_msg}")
        state["results"]["last_operation_result"] = error_msg
        state["results"]["should_continue"] = True  
    logger.info("🏁 Finalisation terminée")
    return state


async def _generate_pr_content(task, state: Dict[str, Any]) -> tuple[str, str]:
    """Génère le titre et la description de la Pull Request."""

    is_reactivation = state.get("is_reactivation", False) or getattr(task, 'is_reactivation', False)
    reactivation_count = state.get("reactivation_count", 0)
    
    if is_reactivation and reactivation_count > 0:
        pr_title = f"[Réactivation {reactivation_count}] feat: {task.title}"
    else:
        pr_title = f"feat: {task.title}"

    display_id = task.monday_item_id if hasattr(task, 'monday_item_id') and task.monday_item_id else task.task_id
    
    reactivation_section = ""
    if is_reactivation and reactivation_count > 0:
        reactivation_context = state.get("reactivation_context") or getattr(task, 'reactivation_context', '')
        source_branch = state.get("source_branch", "main")
        reactivation_section = f"""
### 🔄 Réactivation #{reactivation_count}

Cette Pull Request est une **réactivation** du workflow original.
- **Clone depuis**: branche `{source_branch}` (dernière version)
- **Contexte de réactivation**: {reactivation_context[:200] if reactivation_context else 'N/A'}

"""
    
    pr_body = f"""## 🤖 Pull Request générée automatiquement
{reactivation_section}
### 📋 Tâche
**ID Monday.com**: {display_id}
**Titre**: {task.title}
**Priorité**: {task.priority}

### 📝 Description
{task.description}

### 🔧 Changements apportés
"""

    if state["results"].get("modified_files"):
        pr_body += "\n#### Fichiers modifiés:\n"
        for file_path in state["results"]["modified_files"]:
            pr_body += f"- `{file_path}`\n"

    if state["results"].get("test_results"):
        latest_test = state["results"]["test_results"][-1]

        if hasattr(latest_test, 'success'):
            test_success = latest_test.success
            test_command = getattr(latest_test, 'test_command', 'N/A')
        else:
            test_success = latest_test.get("success", False)
            test_command = latest_test.get("command", "N/A")

        if test_success:
            pr_body += f"\n### ✅ Tests\n- ✅ Tests passés avec `{test_command}`\n"
        else:
            pr_body += f"\n### ⚠️ Tests\n- ⚠️ Derniers tests: `{test_command}` (voir logs)\n"

    if state["results"].get("debug_attempts", 0) > 0:
        pr_body += (f"\n### 🔧 Debug\n- 🔧 {state['results'].get('debug_attempts', 0)} "
                    f"tentative(s) de correction effectuée(s)\n")

    if state["results"].get("error_logs"):
        recent_errors = state["results"]["error_logs"][-3:]
        pr_body += "\n### 📊 Informations de développement\n"
        pr_body += "<details><summary>Logs de développement (cliquer pour développer)</summary>\n\n"
        for error in recent_errors:
            pr_body += f"- {error}\n"
        pr_body += "\n</details>\n"

    pr_body += f"""
### 🎯 Prêt pour la revue
Cette Pull Request a été générée automatiquement par l'agent IA.
- ✅ Code implémenté selon les spécifications
- ✅ Tests validés
- ✅ Prêt pour la revue humaine

**Branche**: `{getattr(task, 'git_branch', 'N/A')}`
**Assigné**: {getattr(task, 'assignee', None) or 'Non assigné'}
"""

    return pr_title, pr_body


async def _generate_summary_comment(state: Dict[str, Any]) -> str:
    """Génère un commentaire de résumé pour la PR."""

    comment = "## 🤖 Résumé de l'implémentation automatique\n\n"

    comment += "### 📊 Statistiques\n"
    modified_files = len(state["results"].get("modified_files", []))
    test_results = state["results"].get("test_results", [])
    error_count = len(state["results"].get("error_logs", []))

    comment += f"- **Fichiers modifiés**: {modified_files}\n"
    comment += f"- **Tests exécutés**: {len(test_results)}\n"
    comment += f"- **Erreurs détectées**: {error_count}\n"

    return comment


def should_continue_to_update(state: Dict[str, Any]) -> bool:
    """Détermine si le workflow doit continuer vers la mise à jour Monday."""
    return True
