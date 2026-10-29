from dataclasses import dataclass


# MARK: RepoRef
@dataclass(frozen=True)
class RepoRef:
    """Identifies a GitHub repository independently of PyGithub."""

    full_name: str
    stars: int
    language: str | None
    default_branch: str
    url: str
