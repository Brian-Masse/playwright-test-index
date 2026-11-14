import os
import subprocess
from pathlib import Path, PurePosixPath
from typing import Protocol

from models.repo_ref import COMMIT_SHA_PATTERN, FULL_NAME_PATTERN, RepoRef

GITHUB_CLONE_URL: str = "https://github.com/{full_name}.git"
REMOTE_NAME: str = "origin"
CLONE_TIMEOUT_SECONDS: int = 300
PARENT_DIR: str = ".."


SAFE_GIT_CONFIG: tuple[str, ...] = (
    "core.symlinks=false",
    "core.hooksPath=/dev/null",
    "protocol.allow=never",
    "protocol.https.allow=always",
    "submodule.recurse=false",
    "fetch.recurseSubmodules=false",
)

# Ignore the user's git config (credential helpers, URL rewrites), never prompt for
# credentials, and skip Git LFS downloads.
SAFE_GIT_ENVIRONMENT: dict[str, str] = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_LFS_SKIP_SMUDGE": "1",
}


# MARK: CloneError
class CloneError(Exception):
    """Raised when a repository cannot be cloned."""


# MARK: RepoIOManager
class RepoIOManager(Protocol):
    """Provides and removes the per-repo storage locations that checkouts are written into."""

    def get_dir(self, repo: RepoRef) -> Path:
        """Returns the location for the repo's commit, whether or not it exists."""

        ...

    def create_dir(self, repo: RepoRef, override: bool = True) -> None:
        """Creates an empty location for the repo's commit."""

        ...

    def prune_dir(self, repo: RepoRef) -> None:
        """Removes the repo's location if it exists."""

        ...


# MARK: RepoStore
class RepoStore(Protocol):
    """Writes repository checkouts to storage and removes them."""

    def write(self, repo: RepoRef, include_dirs: list[str] | None = None) -> None:
        """Writes a checkout of `repo` at its commit_SHA to storage."""

        ...

    def delete(self, repo: RepoRef) -> None:
        """Removes the checkout of `repo` from storage."""

        ...

    def get_location(self, repo: RepoRef) -> Path:
        """Returns where the checkout of `repo` lives in storage."""

        ...


# MARK: RepoWriter
class RepoWriter:
    """Writes shallow, sandboxed checkouts of repository commits into storage provided by a RepoIOManager."""

    def __init__(
        self, io_manager: RepoIOManager, timeout_seconds: int = CLONE_TIMEOUT_SECONDS
    ) -> None:
        self._io_manager: RepoIOManager = io_manager
        self._timeout_seconds: int = timeout_seconds

    # MARK: write
    def write(self, repo: RepoRef, include_dirs: list[str] | None = None) -> None:
        """Clones `repo` at its commit_SHA into a fresh location, replacing any previous checkout.
        Only the single commit is fetched; file contents download only for `include_dirs` (plus root files) when given.
        """

        self._validate(repo, include_dirs)

        # NOTE: A possible seperation of responsibilities issue here
        # the ioManager should probably be responsible for creating the directory, not the writer.
        self._io_manager.create_dir(repo)
        destination: Path = self._io_manager.get_dir(repo)

        try:
            self._clone(repo, destination, include_dirs)
        except CloneError:
            self._io_manager.prune_dir(repo)
            raise

    # MARK: delete
    def delete(self, repo: RepoRef) -> None:
        """Removes the checkout of `repo`. Does nothing if it was never written."""

        self._io_manager.prune_dir(repo)

    # MARK: get_location
    def get_location(self, repo: RepoRef) -> Path:
        """Returns where the checkout of `repo` lives, whether or not it has been written."""

        return self._io_manager.get_dir(repo)

    def _clone(
        self, repo: RepoRef, destination: Path, include_dirs: list[str] | None
    ) -> None:
        self._run_git(["init", "--quiet", str(destination)])
        self._run_git_in(
            destination,
            [
                "remote",
                "add",
                REMOTE_NAME,
                GITHUB_CLONE_URL.format(full_name=repo.full_name),
            ],
        )

        if include_dirs:
            self._run_git_in(
                destination, ["sparse-checkout", "set", "--", *include_dirs]
            )

        self._run_git_in(
            destination,
            [
                "fetch",
                "--quiet",
                "--depth=1",
                "--filter=blob:none",
                "--no-tags",
                REMOTE_NAME,
                str(repo.commit_SHA),
            ],
        )
        self._run_git_in(destination, ["checkout", "--quiet", "FETCH_HEAD"])

    @staticmethod
    def _validate(repo: RepoRef, include_dirs: list[str] | None) -> None:
        if not FULL_NAME_PATTERN.fullmatch(repo.full_name):
            raise ValueError(f"Invalid repository name: {repo.full_name!r}.")

        if repo.commit_SHA is None:
            raise ValueError(
                f"{repo.full_name} has no commit_SHA; resolve it before cloning."
            )

        if not COMMIT_SHA_PATTERN.fullmatch(repo.commit_SHA):
            raise ValueError(f"Invalid commit SHA: {repo.commit_SHA!r}.")

        for include_dir in include_dirs or []:
            include_path: PurePosixPath = PurePosixPath(include_dir)
            if include_path.is_absolute() or PARENT_DIR in include_path.parts:
                raise ValueError(
                    f"include_dirs must be relative paths inside the repo: {include_dir!r}."
                )

    def _run_git_in(self, repo_dir: Path, arguments: list[str]) -> None:
        self._run_git(["-C", str(repo_dir), *arguments])

    def _run_git(self, arguments: list[str]) -> None:
        config_flags: list[str] = [
            flag for setting in SAFE_GIT_CONFIG for flag in ("-c", setting)
        ]
        command: list[str] = ["git", *config_flags, *arguments]

        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=self._timeout_seconds,
                env={**os.environ, **SAFE_GIT_ENVIRONMENT},
            )
        except subprocess.TimeoutExpired as error:
            raise CloneError(
                f"git {arguments[0]} timed out after {self._timeout_seconds}s."
            ) from error

        if result.returncode != 0:
            raise CloneError(
                f"git {' '.join(arguments)} failed: {result.stderr.strip()}"
            )
