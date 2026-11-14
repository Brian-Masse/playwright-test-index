from dataclasses import dataclass

from models.language import Language


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
