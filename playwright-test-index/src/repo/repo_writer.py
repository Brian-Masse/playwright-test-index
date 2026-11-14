import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Protocol

from models.repo_ref import RepoRef

GITHUB_CLONE_URL: str = "https://github.com/{full_name}.git"
REMOTE_NAME: str = "origin"
CLONE_TIMEOUT_SECONDS: int = 300
FULL_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
COMMIT_SHA_PATTERN: re.Pattern[str] = re.compile(r"^[0-9a-f]{40}$")
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


# MARK: RepoCloner
class RepoCloner(Protocol):
    """Clones a repository at a specific commit into a directory."""

    # MARK: clone
    def clone(
        self, repo: RepoRef, destination: Path, include_dirs: list[str] | None = None
    ) -> None:
        """Clones `repo` at its commit_SHA into the empty `destination` directory."""

        ...


# MARK: RepoWriter
class RepoWriter:
    """Writes a pruned, sandboxed checkout of a repository commit to disk using the git CLI."""

    def __init__(self, timeout_seconds: int = CLONE_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds: int = timeout_seconds

    # MARK: clone
    def clone(
        self, repo: RepoRef, destination: Path, include_dirs: list[str] | None = None
    ) -> None:
        """Clones `repo` at its commit_SHA into the empty `destination` directory.
        Only the single commit is fetched, file contents download only for `include_dirs` (plus root files) when given.
        """

        self._validate(repo, destination, include_dirs)

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
                repo.commit_SHA,
            ],
        )
        self._run_git_in(destination, ["checkout", "--quiet", "FETCH_HEAD"])

    @staticmethod
    def _validate(
        repo: RepoRef, destination: Path, include_dirs: list[str] | None
    ) -> None:

        if not FULL_NAME_PATTERN.fullmatch(repo.full_name):
            raise ValueError(f"Invalid repository name: {repo.full_name!r}.")

        if repo.commit_SHA is None:
            raise ValueError(f"{repo.full_name} has no commit_SHA; resolve it before cloning.")

        if not COMMIT_SHA_PATTERN.fullmatch(repo.commit_SHA):
            raise ValueError(f"Invalid commit SHA: {repo.commit_SHA!r}.")

        if not destination.is_dir() or any(destination.iterdir()):
            raise ValueError(
                f"Destination must be an existing, empty directory: {destination}."
            )

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
