import argparse
import os
from pathlib import Path

from ghapi.github_gateway import GitHubGateway
from ghapi.on_disk_repo_manager import OnDiskRepoManager
from ghapi.repo_writer import RepoWriter
from models.repo_ref import RepoRef
from pipelines.clone_repo import CloneRepoPipeline

TOKEN_ENV_VAR: str = "GITHUB_TOKEN"
WORKSPACE_PATH: Path = Path(__file__).resolve().parents[1] / "tmp" / "data"


# MARK: clone
def clone(url: str) -> None:
    """Clones the repo at `url` at its latest commit into the local workspace and prints where it landed."""

    writer: RepoWriter = RepoWriter(OnDiskRepoManager(WORKSPACE_PATH))

    with GitHubGateway.from_token(os.environ[TOKEN_ENV_VAR]) as gateway:
        pipeline: CloneRepoPipeline = CloneRepoPipeline(lookup=gateway, store=writer)
        repo: RepoRef = pipeline.resolve(url)

    pipeline.clone(repo)

    print(f"{repo!r}")
    print(f"# Cloned to {pipeline.get_clone_dir(repo)}")


# MARK: main
def main() -> None:
    """Clones a GitHub repo into the local tmp workspace for manual analysis."""

    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("url", help="GitHub repo URL, e.g. https://github.com/owner/name")

    clone(parser.parse_args().url)


if __name__ == "__main__":
    main()
