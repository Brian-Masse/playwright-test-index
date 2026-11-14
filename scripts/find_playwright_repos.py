import argparse
import os

from ghapi.github_gateway import GitHubGateway
from ghapi.repo_reader import RepoReader
from models.language import Language
from models.repo_ref import RepoRef
from models.repo_search_query import RepoSearchQuery
from pipelines.find_playwright_repos import FindPlaywrightReposPipeline

TOKEN_ENV_VAR: str = "GITHUB_TOKEN"
DEFAULT_KEYWORDS: list[str] = ["playwright"]
DEFAULT_LIMIT: int = 50


# MARK: find
def find(query: RepoSearchQuery) -> None:
    """Prints the most-starred repos matching `query` that contain a Playwright config, ranked."""

    with GitHubGateway.from_token(os.environ[TOKEN_ENV_VAR]) as gateway:
        reader: RepoReader = RepoReader(gateway)
        pipeline: FindPlaywrightReposPipeline = FindPlaywrightReposPipeline(
            search=gateway, checks=[reader.has_playwright_config]
        )
        repos: list[RepoRef] = pipeline.find(query)

    for rank, repo in enumerate(repos, start=1):
        print(f"{rank:>3}. {repo.stars:>7} stars  {repo.url}")

    print(f"{len(repos)} of {query.limit} searched repositories use Playwright.")


# MARK: main
def main() -> None:
    """Searches GitHub for repositories that use Playwright."""

    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("keywords", nargs="*", default=DEFAULT_KEYWORDS, help="Search keywords")
    parser.add_argument("--language", choices=[language.value for language in Language], help="Primary repo language")
    parser.add_argument("--min-stars", type=int, help="Minimum star count")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="How many search results to check")

    arguments: argparse.Namespace = parser.parse_args()
    find(
        RepoSearchQuery(
            keywords=tuple(arguments.keywords),
            language=Language(arguments.language) if arguments.language else None,
            min_stars=arguments.min_stars,
            limit=arguments.limit,
        )
    )


if __name__ == "__main__":
    main()
