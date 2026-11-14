from pathlib import Path

from ghapi.github_gateway import RepoLookup
from ghapi.repo_writer import RepoStore
from models.repo_ref import RepoRef


# MARK: CloneRepoPipeline
class CloneRepoPipeline:
    """Pins a GitHub repo URL to its latest commit and writes that checkout to local storage."""

    def __init__(self, lookup: RepoLookup, store: RepoStore) -> None:
        self._lookup: RepoLookup = lookup
        self._store: RepoStore = store

    # MARK: resolve
    def resolve(self, url: str) -> RepoRef:
        """Returns the repo at `url` pinned to the latest commit on its default branch."""

        return self._lookup.resolve_commit(self._lookup.get_repo_from_url(url))

    # MARK: clone
    def clone(self, repo: RepoRef) -> None:
        """Writes a full checkout of the pinned `repo` to storage, replacing any previous one."""

        self._store.write(repo)

    # MARK: get_clone_dir
    def get_clone_dir(self, repo: RepoRef) -> Path:
        """Returns the directory holding the checkout of `repo`."""

        return self._store.get_location(repo)
