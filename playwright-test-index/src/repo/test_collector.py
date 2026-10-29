import warnings
from pathlib import Path
from typing import Self

from models.playwright_test import PlaywrightTest, PlaywrightTestSource
from models.repo_ref import RepoRef

from repo.extractor import (
    FILE_ENCODING,
    PythonTestExtractor,
    TestExtractor,
    TypeScriptTestExtractor,
)

PLAYWRIGHT_KEYWORD: str = "playwright"
PYTHON_SUFFIX: str = ".py"
TYPESCRIPT_SUFFIXES: tuple[str, ...] = (
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
)


# MARK: PlaywrightTestCollector
class PlaywrightTestCollector:
    """Turns the test files of a cloned repo into PlaywrightTest records using per-extension extractors."""

    def __init__(self, extractors_by_suffix: dict[str, TestExtractor]) -> None:
        self._extractors_by_suffix: dict[str, TestExtractor] = extractors_by_suffix

    # MARK: with_default_extractors
    @classmethod
    def with_default_extractors(cls) -> Self:
        """Creates a collector that handles Python and TypeScript/JavaScript test files."""

        typescript_extractor: TestExtractor = TypeScriptTestExtractor()
        extractors_by_suffix: dict[str, TestExtractor] = {
            PYTHON_SUFFIX: PythonTestExtractor(),
            **{suffix: typescript_extractor for suffix in TYPESCRIPT_SUFFIXES},
        }

        return cls(extractors_by_suffix)

    # MARK: collect_tests
    def collect_tests(
        self, repo: RepoRef, repo_dir: Path, test_paths: list[str]
    ) -> list[PlaywrightTest]:
        """Extracts every test from the given repo-relative paths inside `repo_dir`.
        Files that are missing, unsupported, unparseable, or Python files not mentioning playwright are skipped with a warning.
        """

        tests: list[PlaywrightTest] = []

        for test_path in test_paths:
            tests.extend(
                PlaywrightTest(repo=repo, test_path=test_path, source=source)
                for source in self._extract_file(repo_dir / test_path)
            )

        return tests

    def _extract_file(self, file_path: Path) -> list[PlaywrightTestSource]:
        extractor: TestExtractor | None = self._extractors_by_suffix.get(file_path.suffix)

        if extractor is None:
            warnings.warn(f"No extractor for {file_path.suffix} files: {file_path}.")
            return []
        if not file_path.is_file():
            warnings.warn(f"Test file missing from checkout: {file_path}.")
            return []
        if file_path.suffix == PYTHON_SUFFIX and not self._mentions_playwright(file_path):
            return []

        try:
            return extractor.extract_tests(file_path)
        except SyntaxError as error:
            warnings.warn(f"Could not parse {file_path}: {error}.")
            return []

    @staticmethod
    def _mentions_playwright(file_path: Path) -> bool:
        # pytest test files are matched by name only, so drop those unrelated to Playwright.
        file_text: str = file_path.read_text(encoding=FILE_ENCODING, errors="replace")

        return PLAYWRIGHT_KEYWORD in file_text.lower()
