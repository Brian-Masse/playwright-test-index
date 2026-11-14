from dataclasses import dataclass

from models.language import Language
from models.repo_ref import RepoRef


# MARK: PlaywrightTest
@dataclass(frozen=True)
class PlaywrightTest:
    """An individual playwright test associated with a target repo"""

    repo: RepoRef
    test_path: str
    source: PlaywrightTestSource


# MARK: PlaywrightTestSource
@dataclass(frozen=True)
class PlaywrightTestSource:
    """The source properties of a playright test.
    These values are independent of where the test lives"""

    title: str
    start_line: int
    end_line: int
    language: Language
    source: str


# MARK: TestRecord
@dataclass(frozen=True)
class TestRecord:
    """A single analyzed Playwright test: its summary and the high-level properties it exercises."""

    repo_full_name: str
    repo_commit_SHA: str
    name: str
    description: str
    language: Language
    test_path: str
    start_line: int
    end_line: int
    property_names: tuple[str, ...]
