from dataclasses import dataclass


# MARK: RepoTree
@dataclass(frozen=True)
class RepoTree:
    """Snapshot of every file and directory path in a repository."""

    file_paths: frozenset[str]
    dir_paths: frozenset[str]
