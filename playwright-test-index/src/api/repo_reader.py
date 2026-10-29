from models.repo_ref import RepoRef

from api.github_gateway import RepoFileAccess

PLAYWRIGHT_KEYWORD: str = "playwright"
ROOT_README_PATTERN: str = r"(?i)^readme(\.\w+)?$"
MARKDOWN_PATTERN: str = r"(?i)\.md$"
PLAYWRIGHT_CONFIG_PATTERN: str = r"^playwright\.config\.(ts|js|mjs|cjs)$"
PATH_SEPARATOR: str = "/"


# MARK: RepoReader
class RepoReader:
    """Read Playwright tests from a given repo."""

    def __init__(self, file_access: RepoFileAccess) -> None:
        self._file_access: RepoFileAccess = file_access

    # MARK: playwright_in_README
    def playwright_in_README(self, repo: RepoRef) -> bool:
        """Checks whether any of the README's mention playwright by name.
        Always checks the root README. If present, no further action is taken.
        If not, find all .md's and search for playwright there.
        """

        root_readme_paths: list[str] = [
            path
            for path in self._file_access.find_files(repo, ROOT_README_PATTERN)
            if PATH_SEPARATOR not in path
        ]
        if self._any_file_mentions_playwright(repo, root_readme_paths):
            return True

        markdown_paths: list[str] = [
            path
            for path in self._file_access.find_files(repo, MARKDOWN_PATTERN)
            if path not in root_readme_paths
        ]

        return self._any_file_mentions_playwright(repo, markdown_paths)

    # MARK: playwright_in_directory
    def playwright_in_directory(self, repo: RepoRef) -> bool:
        """Checks whether a playwright.config.{ts,js,mjs,cjs} file exists anywhere in the repo."""

        return len(self._file_access.find_files(repo, PLAYWRIGHT_CONFIG_PATTERN)) > 0

    # MARK: repo_has_playwright
    def repo_has_playwright(self, repo: RepoRef) -> bool:
        """Checks for playwright in READMEs or directories."""

        return self.playwright_in_directory(repo) or self.playwright_in_README(repo)

    def _any_file_mentions_playwright(self, repo: RepoRef, paths: list[str]) -> bool:
        return any(
            PLAYWRIGHT_KEYWORD
            in self._file_access.read_file_from_repo(repo, path).lower()
            for path in paths
        )

    # MARK: extract_tests_from_repo
    def extract_tests_from_repo(self, repo: RepoRef):
        pass
