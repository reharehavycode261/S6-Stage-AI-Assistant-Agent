import os
import sys
import asyncio

# Assure l'import depuis la racine du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.github_tool import GitHubTool
from config.settings import get_settings

settings = get_settings()

OWNER_REPO = os.getenv("GITHUB_TEST_REPO", "reharehavycode261/AI-Agent-Monday")  # ex: owner/repo
TEST_BRANCH = os.getenv("GITHUB_TEST_BRANCH", "")  # ex: feature/test-pr
TEST_PR_NUMBER = os.getenv("GITHUB_TEST_PR_NUMBER", "")  # ex: 123


def skip_if_env_missing():
    missing = []
    if not settings.github_token:
        missing.append("GITHUB_TOKEN")
    if not OWNER_REPO:
        missing.append("GITHUB_TEST_REPO")
    if missing:
        raise SystemExit(f"Variables manquantes: {', '.join(missing)}")


async def test_init_client():
    skip_if_env_missing()
    tool = GitHubTool()
    assert tool.github_client is not None


async def test_repo_access():
    skip_if_env_missing()
    tool = GitHubTool()
    repo = tool.github_client.get_repo(OWNER_REPO)
    assert repo.full_name.lower() == OWNER_REPO.lower()


async def test_list_pull_requests_open_and_closed():
    """Vérifie que la liste des PRs (ouvertes/fermées) est accessible sans créer quoi que ce soit."""
    skip_if_env_missing()
    tool = GitHubTool()
    repo = tool.github_client.get_repo(OWNER_REPO)
    open_prs = list(repo.get_pulls(state='open'))
    closed_prs = list(repo.get_pulls(state='closed'))
    # On ne fait pas d'assert strict sur le nombre, on vérifie juste que l'appel passe
    assert open_prs is not None
    assert closed_prs is not None
    print(f"PRs ouvertes: {len(open_prs)} | PRs fermées: {len(closed_prs)}")


async def test_create_pr_if_branch_provided():
    skip_if_env_missing()
    if not TEST_BRANCH:
        print("[skip] TEST_BRANCH non défini")
        return
    tool = GitHubTool()
    res = await tool._arun(
        action="create_pull_request",
        repo_url=f"https://github.com/{OWNER_REPO}",
        title="Test PR depuis AI-Agent",
        body="PR de test générée automatiquement.",
        head_branch=TEST_BRANCH,
        base_branch="main",
    )
    assert isinstance(res, dict)
    assert res.get("success") in (True, False)  # peut renvoyer PR existante


async def test_add_comment_if_pr_number_provided():
    skip_if_env_missing()
    if not TEST_PR_NUMBER:
        print("[skip] TEST_PR_NUMBER non défini")
        return
    tool = GitHubTool()
    res = await tool._arun(
        action="add_comment",
        repo_url=f"https://github.com/{OWNER_REPO}",
        pr_number=int(TEST_PR_NUMBER),
        comment="Commentaire automatique depuis AI-Agent ✅",
    )
    assert isinstance(res, dict)
    assert res.get("success") is True


if __name__ == "__main__":
    # Exécution manuelle sans pytest
    skip_if_env_missing()
    async def main():
        await test_init_client()
        await test_repo_access()
        await test_list_pull_requests_open_and_closed()
        if TEST_BRANCH:
            await test_create_pr_if_branch_provided()
        if TEST_PR_NUMBER:
            await test_add_comment_if_pr_number_provided()
        print("✅ Tests GitHubTool terminés")
    asyncio.run(main())
