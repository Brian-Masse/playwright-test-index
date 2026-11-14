from dataclasses import dataclass


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
