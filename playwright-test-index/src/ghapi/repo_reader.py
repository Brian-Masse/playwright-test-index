from models.language import Language
from models.repo_ref import RepoRef

from ghapi.dependency_detector import DependencyDetector, detector_for
from ghapi.github_gateway import RepoFileAccess

PLAYWRIGHT_KEYWORD: str = "playwright"
ROOT_README_PATTERN: str = r"(?i)^readme(\.\w+)?$"
MARKDOWN_PATTERN: str = r"(?i)\.md$"
PLAYWRIGHT_CONFIG_PATTERN: str = r"^playwright\.config\.(ts|js|mjs|cjs)$"
PATH_SEPARATOR: str = "/"
ROOT_TEST_DIRS: tuple[str, ...] = ("tests", "e2e")


# MARK: RepoReader
class RepoReader:
    """Answers independent yes/no questions about whether a remote repo uses Playwright."""

    def __init__(self, file_access: RepoFileAccess) -> None:
        self._file_access: RepoFileAccess = file_access

    # MARK: has_playwright_config
    def has_playwright_config(self, repo: RepoRef) -> bool:
        """Checks whether a playwright.config.{ts,js,mjs,cjs} file exists anywhere in the repo."""

        return len(self._file_access.find_files(repo, PLAYWRIGHT_CONFIG_PATTERN)) > 0

    # MARK: has_playwright_in_readme
    def has_playwright_in_readme(self, repo: RepoRef) -> bool:
        """Checks whether any Markdown file mentions playwright by name.
        The root README is read first; other .md files are read only if it does not mention playwright.
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

    # MARK: has_root_test_dir
    def has_root_test_dir(self, repo: RepoRef) -> bool:
        """Checks whether a `tests` or `e2e` directory exists at the repo root."""

        return any(
            self._file_access.check_dir_exists_in_repo(repo, test_dir)
            for test_dir in ROOT_TEST_DIRS
        )

    # MARK: has_playwright_dependency
    def has_playwright_dependency(self, repo: RepoRef, language: Language) -> bool:
        """Checks whether the package manifests for `language` declare a Playwright package."""

        detector: DependencyDetector = detector_for(language, self._file_access)

        return detector.has_playwright_dependency(repo)

    # MARK: has_playwright_dependency_in_any_language
    def has_playwright_dependency_in_any_language(self, repo: RepoRef) -> bool:
        """Checks whether the package manifests of any supported Language declare a Playwright package."""

        # Languages sharing a package manager (TypeScript, JavaScript) map to the same detector
        # type, so dedupe to avoid re-reading the same manifests.
        detectors_by_type: dict[type, DependencyDetector] = {}
        for language in Language:
            detector: DependencyDetector = detector_for(language, self._file_access)
            detectors_by_type.setdefault(type(detector), detector)

        return any(
            detector.has_playwright_dependency(repo)
            for detector in detectors_by_type.values()
        )

    def _any_file_mentions_playwright(self, repo: RepoRef, paths: list[str]) -> bool:
        return any(
            PLAYWRIGHT_KEYWORD
            in self._file_access.read_file_from_repo(repo, path).lower()
            for path in paths
        )
