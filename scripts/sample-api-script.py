import os
from pathlib import Path

from ghapi.github_gateway import GitHubGateway
from models.repo_ref import RepoRef
from repo.on_disk_repo_manager import OnDiskRepoManager
from repo.repo_reader import RepoReader
from repo.repo_writer import RepoWriter

GITHUB_URL_PREFIX: str = "https://github.com/"
TOKEN_ENV_VAR: str = "GITHUB_TOKEN"
ROOT_DIR: str = ""
GIT_URL_SUFFIX: str = ".git"
PLAYWRIGHT_KEYWORD: str = "playwright"
TOP_REPO_COUNT: int = 50


# MARK: get_repo
def get_repo(url: str) -> None:
    """Clones the repo at `url` at its latest commit and prints its RepoRef and clone location."""

    full_name: str = (
        url.removeprefix(GITHUB_URL_PREFIX).rstrip("/").removesuffix(GIT_URL_SUFFIX)
    )

    with GitHubGateway.from_token(os.environ[TOKEN_ENV_VAR]) as gateway:
        repo: RepoRef = gateway.resolve_commit(gateway.get_repo(full_name))

    disk_manager: OnDiskRepoManager = OnDiskRepoManager()
    disk_manager.initialize_workspace()

    repo_dir: Path = disk_manager.request_new_dir(repo=repo)
    RepoWriter().clone(repo=repo, destination=repo_dir)

    print(f"{repo!r}")
    print(f"# Cloned to {repo_dir}")


# MARK: basic_positive_repo_check
def basic_positive_repo_check() -> None:

    repo_url: str = "https://github.com/AutomationPanda/playwright-python-tutorial"
    full_name: str = repo_url.removeprefix(GITHUB_URL_PREFIX)

    with GitHubGateway.from_token(os.environ[TOKEN_ENV_VAR]) as gateway:
        repo: RepoRef = gateway.get_repo(full_name)

        reader: RepoReader = RepoReader(gateway)
        has_playwright: bool = reader.repo_has_playwright(repo)

    assert has_playwright, f"{full_name} was not detected as a Playwright repo."
    print(f"PASS: {full_name} uses Playwright.")


# MARK: clean_repo_clones
def clean_repo_clones() -> None:
    """Deletes every local clone by removing the whole workspace."""

    disk_manager: OnDiskRepoManager = OnDiskRepoManager()

    # Initializing first makes cleanup safe to run when no workspace exists yet.
    disk_manager.initialize_workspace()
    disk_manager.deinitialize_workspace()


# MARK: extract_and_print_tests()
def extract_and_print_tests() -> None:

    repo_url: str = "https://github.com/microsoft/playwright-examples"
    full_name: str = repo_url.removeprefix(GITHUB_URL_PREFIX)

    with GitHubGateway.from_token(os.environ[TOKEN_ENV_VAR]) as gateway:
        repo: RepoRef = gateway.get_repo(full_name)

        reader: RepoReader = RepoReader(gateway)

        has_playwright: bool = reader.repo_has_playwright(repo)

        if not has_playwright:
            return

        repo = gateway.resolve_commit(repo)
        print(repo.url)

    #     disk_manager = OnDiskRepoManager()
    #     disk_manager.initialize_workspace()

    #     writer = RepoWriter()
    #     test_paths = reader.get_playwright_test_paths(repo=repo)
    #     test_dirs: list[str] = sorted(
    #         {posixpath.dirname(path) for path in test_paths} - {ROOT_DIR}
    #     )

    #     try:
    #         repo_dir: Path = disk_manager.request_new_dir(repo=repo)
    #         writer.clone(repo=repo, destination=repo_dir, include_dirs=test_dirs)

    #         collector = PlaywrightTestCollector.with_default_extractors()
    #         tests: list[PlaywrightTest] = collector.collect_tests(
    #             repo=repo, repo_dir=repo_dir, test_paths=test_paths
    #         )
    #     finally:
    #         disk_manager.prune_dir(repo=repo)

    # for test in tests:
    #     print(
    #         f"{test.test_path}:{test.source.start_line}-{test.source.end_line}  {test.source.title}"
    #     )
    # print(f"{len(tests)} tests from {len(test_paths)} files in {full_name}.")


# MARK: list_top_playwright_repos
def list_top_playwright_repos() -> None:
    """Fetches the most-starred GitHub repositories using Playwright and prints them, ranked."""

    with GitHubGateway.from_token(os.environ[TOKEN_ENV_VAR]) as gateway:
        repos: list[RepoRef] = gateway.get_repos(
            keywords=[PLAYWRIGHT_KEYWORD], limit=TOP_REPO_COUNT
        )

    for rank, repo in enumerate(repos, start=1):
        print(f"{rank:>2}. {repo.stars:>7} stars  {repo.full_name}")

    print(f"{len(repos)} repositories using Playwright.")


# MARK: main
def main() -> None:
    """Fetches and prints the top 50 most-starred GitHub repositories using Playwright."""

    list_top_playwright_repos()


if __name__ == "__main__":
    main()
