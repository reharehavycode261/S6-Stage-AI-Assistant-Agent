"""Outil GitHub pour la gestion des Pull Requests."""

import os
import subprocess
from datetime import datetime
from typing import Any, Dict, Optional
from github import Github, GithubException
from pydantic import Field

from .base_tool import BaseTool
from models.schemas import GitOperationResult, PullRequestInfo
from config.langsmith_config import langsmith_config


class GitHubTool(BaseTool):
    """Outil pour interagir avec l'API GitHub."""

    name: str = "github_tool"
    description: str = """
    Outil pour interagir avec GitHub.

    Fonctionnalités:
    - Créer des Pull Requests
    - Pousser des branches
    - Ajouter des commentaires
    - Gérer les labels et assignations
    """

    github_client: Optional[Github] = Field(default=None)
    repository: Optional[Any] = Field(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.github_client = Github(self.settings.github_token)

    async def _arun(self, action: str, **kwargs) -> Dict[str, Any]:
        """Exécute une action GitHub."""
        try:
            if action == "create_pull_request":
                return await self._create_pull_request(
                    repo_url=kwargs.get("repo_url"),
                    title=kwargs.get("title"),
                    body=kwargs.get("body"),
                    head_branch=kwargs.get("head_branch"),
                    base_branch=kwargs.get("base_branch", "main")
                )
            elif action == "push_branch":
                git_result = await self._push_branch(
                    working_directory=kwargs.get("working_directory"),
                    branch=kwargs.get("branch"),
                    repository_url=kwargs.get("repo_url")  # Paramètre optionnel
                )
                # Convertir GitOperationResult en dictionnaire
                return {
                    "success": git_result.success,
                    "message": git_result.message,
                    "branch": git_result.branch,
                    "commit_hash": git_result.commit_hash,
                    "error": git_result.error
                }
            elif action == "add_comment":
                return await self._add_comment(
                    repo_url=kwargs.get("repo_url"),
                    pr_number=kwargs.get("pr_number"),
                    comment=kwargs.get("comment")
                )
            elif action == "merge_pull_request":
                return await self._merge_pull_request(
                    repo_url=kwargs.get("repo_url"),
                    pr_number=kwargs.get("pr_number"),
                    commit_message=kwargs.get("commit_message"),
                    merge_method=kwargs.get("merge_method", "merge")
                )
            elif action == "delete_branch":
                return await self._delete_branch(
                    repo_url=kwargs.get("repo_url"),
                    branch=kwargs.get("branch")
                )
            else:
                raise ValueError(f"Action non supportée: {action}")

        except Exception as e:
            return self.handle_error(e, f"github_tool.{action}")

    async def _create_pull_request(self, repo_url: str, title: str, body: str,
                                   head_branch: str, base_branch: str = "main") -> Dict[str, Any]:
        """Crée une Pull Request sur GitHub."""
        try:
            repo_name = self._extract_repo_name(repo_url)
            self.logger.info(f"🔍 Tentative d'accès au repository: {repo_name}")

            try:
                repo = self.github_client.get_repo(repo_name)
            except GithubException as e:
                if e.status == 404:
                    return {
                        "success": False,
                        "error": f"Repository {repo_name} non trouvé ou token sans permissions (404). Vérifiez GITHUB_TOKEN et permissions."
                    }
                elif e.status == 401:
                    return {
                        "success": False,
                        "error": "Token GitHub invalide ou expiré (401). Vérifiez GITHUB_TOKEN."
                    }
                raise

            self.logger.info(f"✅ Repository accessible: {repo_name}")

            try:
                repo.get_branch(base_branch)
            except GithubException as e:
                if e.status == 404:
                    if base_branch == "main":
                        try:
                            repo.get_branch("master")
                            base_branch = "master"
                            self.logger.info(f"✅ Branche 'master' trouvée, utilisation comme base")
                        except GithubException:
                            return {
                                "success": False,
                                "error": f"Aucune branche base trouvée ('main' ou 'master')"
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"Branche de base '{base_branch}' inexistante. Vérifiez DEFAULT_BASE_BRANCH."
                        }
                else:
                    raise

            max_retries = 3
            retry_delay = 5  
            
            for attempt in range(max_retries):
                try:
                    repo.get_branch(head_branch)
                    self.logger.info(f"✅ Branche {head_branch} trouvée sur GitHub")
                    break
                except GithubException as e:
                    if e.status == 404:
                        if attempt < max_retries - 1:
                            self.logger.warning(f"⚠️ Branche {head_branch} pas encore visible (tentative {attempt + 1}/{max_retries}), attente {retry_delay}s...")
                            import asyncio
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            return {
                                "success": False,
                                "error": f"La branche {head_branch} n'existe pas sur GitHub après {max_retries} tentatives. Vérifiez que le push a réussi."
                            }
                    else:
                        raise

            head_ref = head_branch
            
            self.logger.info(f"🔨 Création PR: {head_ref} → {base_branch}")
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_ref,
                base=base_branch
            )

            pr_info = PullRequestInfo(
                number=pr.number,
                title=pr.title,
                url=pr.html_url,
                branch=head_branch,
                base_branch=base_branch,
                status="open",
                created_at=datetime.now()
            )

            self.log_operation(f"Création PR #{pr.number}", True, pr.html_url)

            if langsmith_config.client:
                try:
                    langsmith_config.client.create_run(
                        name=f"github_create_pr_{pr.number}",
                        run_type="tool",
                        inputs={
                            "repo_url": repo_url,
                            "title": title,
                            "head_branch": head_branch,
                            "base_branch": base_branch
                        },
                        outputs={
                            "success": True,
                            "number": pr.number,
                            "url": pr.html_url
                        },
                        extra={
                            "tool": "github",
                            "operation": "create_pull_request",
                            "repo_name": repo_name
                        }
                    )
                except Exception as e:
                    self.logger.warning(f"⚠️ Erreur LangSmith tracing: {e}")

            return {
                "success": True,
                "pr_info": pr_info.dict(),
                "url": pr.html_url,
                "number": pr.number
            }

        except GithubException as e:
            if e.status == 422 and "pull request already exists" in str(e):
                try:
                    existing_prs = repo.get_pulls(
                        state="open",
                        head=f"{repo.owner.login}:{head_branch}",
                        base=base_branch
                    )
                    if existing_prs.totalCount > 0:
                        existing_pr = existing_prs[0]
                        pr_info = PullRequestInfo(
                            number=existing_pr.number,
                            title=existing_pr.title,
                            url=existing_pr.html_url,
                            branch=head_branch,
                            base_branch=base_branch,
                            status=existing_pr.state,
                            created_at=datetime.now()
                        )

                        self.log_operation(f"PR existante trouvée #{existing_pr.number}", True)
                        return {
                            "success": True,
                            "pr_info": pr_info.dict(),
                            "url": existing_pr.html_url,
                            "number": existing_pr.number,
                            "message": "Pull Request existante utilisée"
                        }
                except Exception:
                    pass
            elif e.status == 404:
                return {
                    "success": False,
                    "error": f"Erreur 404 lors de création PR: {str(e)}. Vérifiez que la branche '{head_branch}' existe sur GitHub et que vous avez les permissions pour créer une PR sur ce repository.",
                    "operation": "création de la Pull Request",
                    "details": {
                        "repo_url": repo_url,
                        "head_branch": head_branch,
                        "base_branch": base_branch,
                        "status_code": 404
                    }
                }

            return self.handle_error(e, "création de la Pull Request")
        except Exception as e:
            return self.handle_error(e, "création de la Pull Request")

    async def _push_branch(self, working_directory: str, branch: str, repository_url: str = None) -> GitOperationResult:
        """
        Pousse une branche vers GitHub.
        
        Args:
            working_directory: Répertoire de travail Git
            branch: Nom de la branche à pousser
            repository_url: URL du repository GitHub (optionnel, utilisé si remote origin n'existe pas)
        """
        try:
            if not working_directory or not os.path.exists(working_directory):
                error_msg = f"Répertoire de travail invalide: {working_directory}"
                self.logger.error(f"❌ {error_msg}")
                return GitOperationResult(
                    success=False,
                    message=error_msg,
                    branch=branch,
                    error=error_msg
                )

            if not branch:
                error_msg = "Nom de branche manquant"
                self.logger.error(f"❌ {error_msg}")
                return GitOperationResult(
                    success=False,
                    message=error_msg,
                    branch=branch,
                    error=error_msg
                )

            git_dir = os.path.join(working_directory, '.git')
            if not os.path.exists(git_dir):
                error_msg = f"Le répertoire {working_directory} n'est pas un dépôt Git (pas de .git)"
                self.logger.error(f"❌ {error_msg}")
                return GitOperationResult(
                    success=False,
                    message=error_msg,
                    branch=branch,
                    error=error_msg
                )

            original_cwd = os.getcwd()
            self.logger.info(f"🔄 Changement de répertoire: {original_cwd} → {working_directory}")
            os.chdir(working_directory)

            try:
                github_token = self.settings.github_token
                
                
                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                has_changes = bool(status_result.stdout.strip())
                if not has_changes:
                    self.logger.warning("⚠️ Aucun changement détecté dans le repository")
                    return GitOperationResult(
                        success=False,
                        message="Aucun fichier modifié à pousser - vérifiez que l'implémentation a créé des fichiers",
                        branch=branch,
                        error="Échec implémentation: Aucun changement détecté par git status. L'IA n'a probablement pas créé/modifié de fichiers."
                    )
                
                add_result = subprocess.run(
                    ["git", "add", "."],
                    capture_output=True,
                    text=True,
                    check=True
                )

                status_after_add = subprocess.run(
                    ["git", "diff", "--cached", "--name-only"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                files_to_commit = status_after_add.stdout.strip()
                if not files_to_commit:
                    self.logger.error("❌ Aucun fichier à committer après git add")
                    return GitOperationResult(
                        success=False,
                        message="Aucun fichier à committer",
                        branch=branch,
                        error="Aucun fichier modifié après 'git add .' - l'implémentation a échoué"
                    )
                
                self.logger.info(f"📝 Fichiers à committer:\n{files_to_commit}")

                commit_result = subprocess.run(
                    ["git", "commit", "-m", f"Implémentation automatique - {branch}", "--allow-empty"],
                    capture_output=True,
                    text=True,
                    check=True
                )

                push_command = ["git", "push", "origin", branch]
                
                remote_check = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    capture_output=True,
                    text=True
                )
                
                if remote_check.returncode != 0:
                    self.logger.warning("⚠️ Aucun remote 'origin' configuré - création impossible sans URL repository")
                    
                    if hasattr(self, 'repository_url') and self.repository_url:
                        repo_url = self.repository_url
                    elif repository_url:
                        repo_url = repository_url
                    else:
                        return GitOperationResult(
                            success=False,
                            message="Impossible de pousser : pas de remote 'origin' et pas d'URL repository disponible",
                            branch=branch,
                            error="No such remote 'origin'"
                        )
                    
                    self.logger.info(f"📍 Ajout du remote origin: {repo_url}")
                    add_remote_result = subprocess.run(
                        ["git", "remote", "add", "origin", repo_url],
                        capture_output=True,
                        text=True
                    )
                    
                    if add_remote_result.returncode != 0:
                        return GitOperationResult(
                            success=False,
                            message=f"Erreur lors de l'ajout du remote origin: {add_remote_result.stderr}",
                            branch=branch,
                            error=add_remote_result.stderr
                        )
                    
                    self.logger.info("✅ Remote origin ajouté avec succès")
                
                if github_token:
                    remote_result = subprocess.run(
                        ["git", "remote", "get-url", "origin"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    remote_url = remote_result.stdout.strip()
                    if remote_url.startswith("https://github.com/"):
                        auth_url = remote_url.replace("https://github.com/", f"https://x-access-token:{github_token}@github.com/")
                        subprocess.run(
                            ["git", "remote", "set-url", "origin", auth_url],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        self.logger.info("✅ URL remote configurée avec authentification")
                    elif remote_url.startswith("git@github.com:"):
                        https_url = remote_url.replace("git@github.com:", "https://x-access-token:"+github_token+"@github.com/")
                        subprocess.run(
                            ["git", "remote", "set-url", "origin", https_url],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        self.logger.info("✅ URL remote convertie de SSH vers HTTPS avec authentification")
                
                push_result = subprocess.run(
                    push_command,
                    capture_output=True,
                    text=True
                )
                
                if push_result.returncode != 0:
                    error_output = push_result.stderr or push_result.stdout
                    
                    if "403" in error_output or "Permission" in error_output or "denied" in error_output:
                        detailed_error = f"""❌ Erreur de permissions GitHub (403):

{error_output}

🔧 Solutions possibles:
1. Vérifiez que votre GITHUB_TOKEN est valide et n'a pas expiré
2. Assurez-vous que le token a les permissions suivantes:
   - repo (accès complet aux repositories privés)
   - workflow (si vous modifiez des workflows)
3. Pour générer un nouveau token: https://github.com/settings/tokens
   - Sélectionnez "Personal access tokens" > "Tokens (classic)"
   - Cochez au minimum: repo, workflow
4. Mettez à jour GITHUB_TOKEN dans votre fichier .env

📋 Repository concerné: {remote_url}
"""
                        self.logger.error(detailed_error)
                        
                        return GitOperationResult(
                            success=False,
                            message="Erreur de permissions GitHub",
                            branch=branch,
                            error=detailed_error
                        )
                    
                    self.logger.error(f"❌ Erreur Git: {error_output}")
                    return GitOperationResult(
                        success=False,
                        message=f"Erreur lors du push",
                        branch=branch,
                        error=f"Erreur Git: {error_output}"
                    )

                commit_hash_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                commit_hash = commit_hash_result.stdout.strip()

                git_result = GitOperationResult(
                    success=True,
                    message=f"Branche {branch} poussée avec succès",
                    branch=branch,
                    commit_hash=commit_hash
                )

                self.log_operation(f"Push branche {branch}", True, commit_hash)
                return git_result

            finally:
                os.chdir(original_cwd)

        except subprocess.CalledProcessError as e:
            error_msg = f"Erreur Git: {e.stderr if e.stderr else e.stdout}"
            self.logger.error(f"❌ {error_msg}")
            self.logger.error(f"❌ Commande échouée: {' '.join(e.cmd)}")
            return GitOperationResult(
                success=False,
                message=error_msg,
                branch=branch,
                error=error_msg
            )
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"❌ Erreur inattendue lors du push: {error_msg}")
            return GitOperationResult(
                success=False,
                message=error_msg,
                branch=branch,
                error=error_msg
            )

    async def _add_comment(self, repo_url: str, pr_number: int, comment: str) -> Dict[str, Any]:
        """Ajoute un commentaire à une Pull Request."""
        try:
            repo_name = self._extract_repo_name(repo_url)
            repo = self.github_client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)

            comment_obj = pr.create_issue_comment(comment)

            self.log_operation(f"Commentaire ajouté PR #{pr_number}", True)

            return {
                "success": True,
                "comment_id": comment_obj.id,
                "comment_url": comment_obj.html_url
            }

        except Exception as e:
            return self.handle_error(e, f"ajout de commentaire à la PR #{pr_number}")

    async def _merge_pull_request(self, repo_url: str, pr_number: int, 
                                   commit_message: Optional[str] = None,
                                   merge_method: str = "merge") -> Dict[str, Any]:
        """
        Merge une Pull Request sur GitHub.
        
        Args:
            repo_url: URL du repository GitHub
            pr_number: Numéro de la PR à merger
            commit_message: Message de commit pour le merge (optionnel)
            merge_method: Méthode de merge ("merge", "squash", ou "rebase")
        
        Returns:
            Dictionnaire avec le résultat du merge
        """
        try:
            repo_name = self._extract_repo_name(repo_url)
            self.logger.info(f"🔀 Tentative de merge PR #{pr_number} sur {repo_name}")

            repo = self.github_client.get_repo(repo_name)
            
            pr = repo.get_pull(pr_number)
            
            if pr.mergeable is False:
                return {
                    "success": False,
                    "error": f"La PR #{pr_number} a des conflits et ne peut pas être mergée automatiquement",
                    "mergeable_state": pr.mergeable_state
                }
            
            if pr.merged:
                return {
                    "success": False,
                    "error": f"La PR #{pr_number} est déjà mergée",
                    "merged_at": pr.merged_at.isoformat() if pr.merged_at else None
                }
            
            if pr.state == "closed":
                return {
                    "success": False,
                    "error": f"La PR #{pr_number} est fermée sans être mergée"
                }
            
            if not commit_message:
                commit_message = f"Merge pull request #{pr_number}: {pr.title}"
            
            valid_methods = ["merge", "squash", "rebase"]
            if merge_method not in valid_methods:
                self.logger.warning(f"⚠️ Méthode de merge invalide '{merge_method}', utilisation de 'merge'")
                merge_method = "merge"
            
            self.logger.info(f"🔀 Merge PR #{pr_number} avec méthode: {merge_method}")
            merge_result = pr.merge(
                commit_message=commit_message,
                merge_method=merge_method
            )
            
            if merge_result.merged:
                self.logger.info(f"✅ PR #{pr_number} mergée avec succès - SHA: {merge_result.sha}")
                self.log_operation(f"PR #{pr_number} mergée", True)
                
                return {
                    "success": True,
                    "merged": True,
                    "sha": merge_result.sha,
                    "message": merge_result.message,
                    "pr_number": pr_number,
                    "pr_title": pr.title
                }
            else:
                error_msg = merge_result.message or "Merge échoué sans raison spécifique"
                self.logger.error(f"❌ Échec du merge PR #{pr_number}: {error_msg}")
                return {
                    "success": False,
                    "merged": False,
                    "error": error_msg
                }
        
        except GithubException as e:
            error_details = {
                "status_code": e.status,
                "message": str(e),
                "pr_number": pr_number
            }
            
            if e.status == 404:
                error_msg = f"PR #{pr_number} non trouvée ou repository inaccessible"
            elif e.status == 405:
                error_msg = f"PR #{pr_number} ne peut pas être mergée (conflits ou restrictions de branche)"
            elif e.status == 409:
                error_msg = f"PR #{pr_number} a des conflits de merge"
            else:
                error_msg = f"Erreur GitHub lors du merge: {str(e)}"
            
            self.logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "details": error_details
            }
        
        except Exception as e:
            return self.handle_error(e, f"merge de la PR #{pr_number}")

    async def _delete_branch(self, repo_url: str, branch: str) -> Dict[str, Any]:
        """
        Supprime une branche sur GitHub.
        
        Args:
            repo_url: URL du repository GitHub
            branch: Nom de la branche à supprimer
        
        Returns:
            Dictionnaire avec le résultat de la suppression
        """
        try:
            repo_name = self._extract_repo_name(repo_url)
            self.logger.info(f"🧹 Tentative de suppression de la branche '{branch}' sur {repo_name}")
            
            repo = self.github_client.get_repo(repo_name)
            
            ref_name = f"heads/{branch}"
            
            try:
                ref = repo.get_git_ref(ref_name)
                
                ref.delete()
                
                self.logger.info(f"✅ Branche '{branch}' supprimée avec succès")
                self.log_operation(f"Branche '{branch}' supprimée", True)
                
                return {
                    "success": True,
                    "message": f"Branche '{branch}' supprimée avec succès",
                    "branch": branch
                }
                
            except GithubException as ref_error:
                if ref_error.status == 404:
                    self.logger.warning(f"⚠️ Branche '{branch}' non trouvée (peut-être déjà supprimée)")
                    return {
                        "success": True,  # Considéré comme succès car objectif atteint
                        "message": f"Branche '{branch}' non trouvée (déjà supprimée?)",
                        "branch": branch,
                        "already_deleted": True
                    }
                else:
                    raise ref_error
        
        except GithubException as e:
            error_details = {
                "status_code": e.status,
                "message": str(e),
                "branch": branch
            }
            
            if e.status == 404:
                error_msg = f"Repository ou branche '{branch}' non trouvé(e)"
            elif e.status == 403:
                error_msg = f"Permissions insuffisantes pour supprimer la branche '{branch}'"
            elif e.status == 422:
                error_msg = f"Impossible de supprimer la branche '{branch}' (peut-être la branche par défaut?)"
            else:
                error_msg = f"Erreur GitHub lors de la suppression de la branche: {str(e)}"
            
            self.logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "details": error_details
            }
        
        except Exception as e:
            return self.handle_error(e, f"suppression de la branche '{branch}'")

    def _extract_repo_name(self, repo_url: str) -> str:
        """Extrait le nom du repository depuis une URL GitHub."""
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]

        if 'github.com/' in repo_url:
            parts = repo_url.split('github.com/')[-1]
            return parts
        else:
            raise ValueError(f"URL de repository invalide: {repo_url}")

    def cleanup(self):
        """Nettoie les ressources."""
        if hasattr(self, 'github_client'):
            pass
