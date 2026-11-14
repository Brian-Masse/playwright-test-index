import json
import re
import warnings
from typing import Any, Protocol, assert_never

from models.language import Language
from models.repo_ref import RepoRef

from ghapi.github_gateway import RepoFileAccess

PATH_SEPARATOR: str = "/"
IGNORED_DIRS: frozenset[str] = frozenset({"node_modules", ".venv", "venv"})

PACKAGE_JSON_PATTERN: str = r"^package\.json$"
NPM_DEPENDENCY_FIELDS: tuple[str, ...] = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)
NPM_PLAYWRIGHT_PACKAGE: str = "playwright"
NPM_PLAYWRIGHT_PREFIXES: tuple[str, ...] = ("@playwright/", "playwright-")

PYTHON_MANIFEST_PATTERN: str = (
    r"^(requirements.*\.txt|pyproject\.toml|Pipfile|setup\.py|setup\.cfg)$"
)

# Matches `playwright` / `pytest-playwright` as a requirement name: at a line start
# (requirements.txt, Poetry and Pipfile tables) or opening a quoted string (PEP 621, setup.py).
PYTHON_PLAYWRIGHT_REQUIREMENT: re.Pattern[str] = re.compile(
    r"""(?im)(?:^\s*|["'])(?:pytest[-_.])?playwright(?=$|[\s\[<>=!~;,"'@])"""
)


# MARK: DependencyDetector
class DependencyDetector(Protocol):
    """Checks a repo's package manifests for a Playwright dependency."""

    def has_playwright_dependency(self, repo: RepoRef) -> bool:
        """Checks whether any manifest declares a Playwright package."""

        ...


# MARK: NpmDependencyDetector
class NpmDependencyDetector:
    """Detects Playwright packages declared in any package.json (JavaScript and TypeScript projects)."""

    def __init__(self, file_access: RepoFileAccess) -> None:
        self._file_access: RepoFileAccess = file_access

    # MARK: has_playwright_dependency
    def has_playwright_dependency(self, repo: RepoRef) -> bool:
        """Checks whether any package.json lists playwright, playwright-*, or an @playwright/* package.
        Unparseable package.json files are skipped with a warning.
        """

        return any(
            self._manifest_has_playwright(repo, path)
            for path in find_unignored_files(
                self._file_access, repo, PACKAGE_JSON_PATTERN
            )
        )

    def _manifest_has_playwright(self, repo: RepoRef, path: str) -> bool:
        try:
            manifest: Any = json.loads(
                self._file_access.read_file_from_repo(repo, path)
            )
        except json.JSONDecodeError as error:
            warnings.warn(f"Could not parse {repo.full_name}/{path}: {error}.")
            return False

        if not isinstance(manifest, dict):
            return False

        return any(
            self._is_playwright_package(package_name)
            for field in NPM_DEPENDENCY_FIELDS
            if isinstance(manifest.get(field), dict)
            for package_name in manifest[field]
        )

    @staticmethod
    def _is_playwright_package(package_name: str) -> bool:
        return (
            package_name == NPM_PLAYWRIGHT_PACKAGE
            or package_name.startswith(NPM_PLAYWRIGHT_PREFIXES)
        )


# MARK: PythonDependencyDetector
class PythonDependencyDetector:
    """Detects playwright or pytest-playwright in requirements*.txt, pyproject.toml, Pipfile, setup.py, or setup.cfg."""

    def __init__(self, file_access: RepoFileAccess) -> None:
        self._file_access: RepoFileAccess = file_access

    # MARK: has_playwright_dependency
    def has_playwright_dependency(self, repo: RepoRef) -> bool:
        """Checks whether any Python manifest names playwright or pytest-playwright as a requirement.
        Matching is textual rather than a full manifest parse, so quoted mentions in comments can count.
        """

        return any(
            PYTHON_PLAYWRIGHT_REQUIREMENT.search(
                self._file_access.read_file_from_repo(repo, path)
            )
            is not None
            for path in find_unignored_files(
                self._file_access, repo, PYTHON_MANIFEST_PATTERN
            )
        )


# MARK: find_unignored_files
def find_unignored_files(
    file_access: RepoFileAccess, repo: RepoRef, pattern: str
) -> list[str]:
    """Returns paths whose base name matches `pattern`, excluding vendored dependency directories."""

    return [
        path
        for path in file_access.find_files(repo, pattern)
        if IGNORED_DIRS.isdisjoint(path.split(PATH_SEPARATOR))
    ]


# MARK: detector_for
def detector_for(language: Language, file_access: RepoFileAccess) -> DependencyDetector:
    """Returns the dependency detector for `language`'s package manager.
    The match is exhaustive, so a type checker flags any Language member left unhandled.
    """

    match language:
        case Language.python:
            return PythonDependencyDetector(file_access)
        case Language.typescript | Language.javascript:
            return NpmDependencyDetector(file_access)
        case _:
            assert_never(language)
