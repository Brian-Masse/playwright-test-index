import argparse
import json
import os
from pathlib import Path

from dataset.fetch_service import RepoTestFetcher
from dataset.serialization import repo_ref_to_dict
from ghapi.github_gateway import GitHubGateway
from models.repo_ref import RepoRef
from repo.on_disk_repo_manager import OnDiskRepoManager
from repo.repo_writer import RepoWriter

GITHUB_URL_PREFIX: str = "https://github.com/"
GIT_URL_SUFFIX: str = ".git"
TOKEN_ENV_VAR: str = "GITHUB_TOKEN"
JSON_INDENT: int = 2


# MARK: to_full_name
def to_full_name(url: str) -> str:
    """Reduces a GitHub repo URL to its "owner/name" form."""

    return url.removeprefix(GITHUB_URL_PREFIX).rstrip("/").removesuffix(GIT_URL_SUFFIX)


# MARK: fetch
def fetch(url: str) -> None:
    """Clones the repo at `url` to disk and prints its RepoRef and clone directory as JSON."""

    with GitHubGateway.from_token(os.environ[TOKEN_ENV_VAR]) as gateway:
        fetcher: RepoTestFetcher = RepoTestFetcher(
            gateway=gateway,
            disk_manager=OnDiskRepoManager(),
            cloner=RepoWriter(),
        )
        repo: RepoRef
        repo_dir: Path
        repo, repo_dir = fetcher.fetch(to_full_name(url))

    print(
        json.dumps(
            {"repo": repo_ref_to_dict(repo), "clone_dir": str(repo_dir)},
            indent=JSON_INDENT,
        )
    )


# MARK: main
def main() -> None:
    """Clones the GitHub repo URL given on the command line for manual analysis."""

    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "url", help="GitHub repo URL, e.g. https://github.com/owner/name"
    )

    fetch(parser.parse_args().url)


if __name__ == "__main__":
    main()
