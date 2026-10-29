import posixpath
import re

from api.github_gateway import RepoFileAccess
from models.repo_ref import RepoRef

PLAYWRIGHT_KEYWORD: str = "playwright"
ROOT_README_PATTERN: str = r"(?i)^readme(\.\w+)?$"
MARKDOWN_PATTERN: str = r"(?i)\.md$"
PLAYWRIGHT_CONFIG_PATTERN: str = r"^playwright\.config\.(ts|js|mjs|cjs)$"
PATH_SEPARATOR: str = "/"
CURRENT_DIR: str = "."
PARENT_DIR: str = ".."
IGNORED_DIR: str = "node_modules"

# Playwright's default testMatch and pytest's default python_files.
TS_TEST_FILE_PATTERN: str = r"\.(spec|test)\.[cm]?[jt]sx?$"
PYTHON_TEST_FILE_PATTERN: str = r"^(test_.*|.*_test)\.py$"

# Only plain string literals are read; computed values (e.g. path.join(...)) fall back to the config's directory.
TEST_DIR_PATTERN: re.Pattern[str] = re.compile(r"""\btestDir\s*:\s*(['"`])([^'"`$]+)\1""")


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

    # MARK: get_playwright_test_paths
    def get_playwright_test_paths(self, repo: RepoRef) -> list[str]:
        """Returns repo-relative paths of candidate Playwright test files, sorted.
        Paths are matched by name only; files must still be filtered by content after cloning.
        """

        test_paths: set[str] = set()

        for config_path in self._find_unignored_files(repo, PLAYWRIGHT_CONFIG_PATTERN):
            test_roots: list[str] = self._resolve_test_roots(repo, config_path)
            test_paths.update(
                path
                for path in self._find_unignored_files(repo, TS_TEST_FILE_PATTERN)
                if any(self._is_under(path, test_root) for test_root in test_roots)
            )

        test_paths.update(self._find_unignored_files(repo, PYTHON_TEST_FILE_PATTERN))

        return sorted(test_paths)

    def _resolve_test_roots(self, repo: RepoRef, config_path: str) -> list[str]:
        config_dir: str = posixpath.dirname(config_path)
        config_source: str = self._file_access.read_file_from_repo(repo, config_path)
        test_dirs: list[str] = [match[1] for match in TEST_DIR_PATTERN.findall(config_source)]

        test_roots: list[str] = [
            posixpath.normpath(posixpath.join(config_dir, test_dir)) for test_dir in test_dirs
        ]
        inside_repo_roots: list[str] = [
            root for root in test_roots if root.split(PATH_SEPARATOR)[0] != PARENT_DIR
        ]

        return inside_repo_roots or [config_dir]

    def _find_unignored_files(self, repo: RepoRef, pattern: str) -> list[str]:
        return [
            path
            for path in self._file_access.find_files(repo, pattern)
            if IGNORED_DIR not in path.split(PATH_SEPARATOR)
        ]

    @staticmethod
    def _is_under(path: str, directory: str) -> bool:
        if directory in ("", CURRENT_DIR):
            return True

        return path.startswith(directory + PATH_SEPARATOR)
