from collections.abc import Callable

from ghapi.github_gateway import RepoSearch
from models.repo_ref import RepoRef
from models.repo_search_query import RepoSearchQuery

type RepoCheck = Callable[[RepoRef], bool]


# MARK: FindPlaywrightReposPipeline
class FindPlaywrightReposPipeline:
    """Searches GitHub and keeps only the repos that pass every injected Playwright check."""

    def __init__(self, search: RepoSearch, checks: list[RepoCheck]) -> None:
        self._search: RepoSearch = search
        self._checks: list[RepoCheck] = checks

    # MARK: find
    def find(self, query: RepoSearchQuery) -> list[RepoRef]:
        """Returns the repos matching `query` that pass all checks, in search order."""

        candidates: list[RepoRef] = self._search.search_repos(query)

        return [
            repo for repo in candidates if all(check(repo) for check in self._checks)
        ]
