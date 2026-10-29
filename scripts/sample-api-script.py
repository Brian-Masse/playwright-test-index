import os
import posixpath
from pathlib import Path

from api.github_gateway import GitHubGateway
from models.playwright_test import PlaywrightTest
from models.repo_ref import RepoRef
from repo.on_disk_repo_manager import OnDiskRepoManager
from repo.repo_reader import RepoReader
from repo.repo_writer import RepoWriter
from repo.test_collector import PlaywrightTestCollector

GITHUB_URL_PREFIX: str = "https://github.com/"
TOKEN_ENV_VAR: str = "GITHUB_TOKEN"
ROOT_DIR: str = ""


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

        disk_manager = OnDiskRepoManager()
        disk_manager.initialize_workspace()

        writer = RepoWriter()
        test_paths = reader.get_playwright_test_paths(repo=repo)
        test_dirs: list[str] = sorted(
            {posixpath.dirname(path) for path in test_paths} - {ROOT_DIR}
        )

        try:
            repo_dir: Path = disk_manager.request_new_dir(repo=repo)
            writer.clone(repo=repo, destination=repo_dir, include_dirs=test_dirs)

            collector = PlaywrightTestCollector.with_default_extractors()
            tests: list[PlaywrightTest] = collector.collect_tests(
                repo=repo, repo_dir=repo_dir, test_paths=test_paths
            )
        finally:
            disk_manager.prune_dir(repo=repo)

    for test in tests:
        print(
            f"{test.test_path}:{test.source.start_line}-{test.source.end_line}  {test.source.title}"
        )
    print(f"{len(tests)} tests from {len(test_paths)} files in {full_name}.")


# MARK: main
def main() -> None:

    # basic_positive_repo_check()
    extract_and_print_tests()


if __name__ == "__main__":
    main()
