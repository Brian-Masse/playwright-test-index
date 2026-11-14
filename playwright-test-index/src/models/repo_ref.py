import re
from dataclasses import dataclass

FULL_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
COMMIT_SHA_PATTERN: re.Pattern[str] = re.compile(r"^[0-9a-f]{40}$")


# MARK: RepoRef
@dataclass(frozen=True)
class RepoRef:
    """Identifies a GitHub repository independently of PyGithub."""

    full_name: str
    commit_SHA: str | None
    repo_size: int

    stars: int
    language: str | None
    url: str


# MARK: RepoRecord
@dataclass(frozen=True)
class RepoRecord:
    """A repository paired with the analyst's high-level description of the project."""

    repo: RepoRef
    description: str
