import shutil
from pathlib import Path

from models.repo_ref import RepoRef
from repo.repo_writer import COMMIT_SHA_PATTERN

DEFAULT_REPO_PATH: Path = Path(
    "/Users/brianmasse/Developer/school/salad-lab/playright-test-index/tmp/data"
)


# MARK: WorkspaceError
class WorkspaceError(Exception):
    """Raised when the workspace is missing or holds contents the manager did not create."""


# MARK: OnDiskRepoManager
class OnDiskRepoManager:
    """Owns a workspace directory holding one checkout directory per commit SHA."""

    def __init__(self, repo_path: Path = DEFAULT_REPO_PATH) -> None:
        self._workspace_path: Path = repo_path

    # MARK: initialize_workspace
    def initialize_workspace(self) -> None:
        """Create the workspace directory at path, reusing it if it already exists."""

        self._workspace_path.mkdir(parents=True, exist_ok=True)

    # MARK: deinitialize_workspace
    def deinitialize_workspace(self) -> None:
        """Delete the workspace created by the manager."""

        self._require_workspace()

        unexpected_entries: list[str] = [
            entry.name
            for entry in self._workspace_path.iterdir()
            if not self._is_commit_dir(entry)
        ]
        if unexpected_entries:
            raise WorkspaceError(
                f"Refusing to delete {self._workspace_path}: unexpected entries {sorted(unexpected_entries)}."
            )

        shutil.rmtree(self._workspace_path)

    def _get_dir(self, repo: RepoRef) -> Path:
        """Returns the checkout directory path for the repo's commit, whether or not it exists."""

        if repo.commit_SHA is None:
            raise ValueError(f"{repo.full_name} has no commit_SHA; resolve it first.")
        if not COMMIT_SHA_PATTERN.fullmatch(repo.commit_SHA):
            raise ValueError(f"Invalid commit SHA: {repo.commit_SHA!r}.")

        return self._workspace_path / repo.commit_SHA

    # MARK: request_new_dir
    def request_new_dir(self, repo: RepoRef, override: bool = True) -> Path:
        """Create an empty directory keyed by the repo's SHA and return its path. Only override pre-existing dirs if override = True, otherwise raise error"""

        self._require_workspace()
        commit_dir: Path = self._get_dir(repo)

        if commit_dir.exists():
            if not override:
                raise FileExistsError(
                    f"Directory already exists for {repo.full_name}: {commit_dir}."
                )
            self._remove_commit_dir(commit_dir)

        commit_dir.mkdir()

        return commit_dir

    # MARK: prune_dir
    def prune_dir(self, repo: RepoRef) -> None:
        """Delete the directory associated with the repo. Does nothing if it does not exist."""

        commit_dir: Path = self._get_dir(repo)

        if commit_dir.exists():
            self._remove_commit_dir(commit_dir)

    def _require_workspace(self) -> None:
        if self._workspace_path.is_symlink() or not self._workspace_path.is_dir():
            raise WorkspaceError(
                f"Workspace is not initialized: {self._workspace_path}."
            )

    def _remove_commit_dir(self, commit_dir: Path) -> None:
        if not self._is_commit_dir(commit_dir):
            raise WorkspaceError(f"Refusing to delete non-commit entry: {commit_dir}.")

        shutil.rmtree(commit_dir)

    @staticmethod
    def _is_commit_dir(entry: Path) -> bool:
        # Symlinks are rejected so a deletion can never follow a link out of the workspace.
        return (
            not entry.is_symlink()
            and entry.is_dir()
            and COMMIT_SHA_PATTERN.fullmatch(entry.name) is not None
        )
