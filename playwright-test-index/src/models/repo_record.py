from dataclasses import dataclass

from models.repo_ref import RepoRef


# MARK: RepoRecord
@dataclass(frozen=True)
class RepoRecord:
    """A repository paired with the analyst's high-level description of the project."""

    repo: RepoRef
    description: str
