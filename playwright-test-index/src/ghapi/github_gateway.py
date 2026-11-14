import re
import warnings
from collections.abc import Iterator
from dataclasses import replace
from itertools import islice
from types import TracebackType
from typing import Protocol, Self

from github import Auth, BadCredentialsException, Github, UnknownObjectException
from github.Commit import Commit
from github.GitTree import GitTree
from github.Repository import Repository
from models.language import Language
from models.repo_ref import RepoRef
from models.repo_tree import RepoTree

MAX_SEARCH_RESULTS: int = 1000
BLOB_TYPE: str = "blob"
TREE_TYPE: str = "tree"
LATEST_COMMIT_REF: str = "HEAD"


# what are the properties?
# What is the prooperty language?
# Possible to use git blame


# MARK: GitHubAuthenticationError
class GitHubAuthenticationError(Exception):
    """Raised when GitHub rejects the provided credentials."""


# MARK: RepoFileAccess
class RepoFileAccess(Protocol):
    """Read-only access to the files of a repository."""

    def read_file_from_repo(self, repo: RepoRef, path: str) -> str:
        """Returns the decoded text content of a file."""

        ...

    def check_file_exists_in_repo(self, repo: RepoRef, path: str) -> bool:
        """Checks whether a file exists in a repo without reading it."""

        ...

    def check_dir_exists_in_repo(self, repo: RepoRef, path: str) -> bool:
        """Checks whether a directory exists in a repo without reading its contents."""

        ...

    def find_files(self, repo: RepoRef, name: str) -> list[str]:
        """Returns paths of files whose name matches the regex `name`."""

        ...


# MARK: GitHubGateway
class GitHubGateway:
    def __init__(self, client: Github) -> None:
        self._client: Github = client
        self._lazy_client: Github = client.withLazy(True)
        self._trees: dict[str, RepoTree] = {}

    # MARK: from_token
    @classmethod
    def from_token(cls, personal_access_token: str) -> Self:
        """Creates a gateway authenticated with a Personal Access Token, failing fast on bad credentials."""

        client: Github = Github(auth=Auth.Token(personal_access_token))

        try:
            _ = client.get_user().login
        except BadCredentialsException as error:
            client.close()
            raise GitHubAuthenticationError(
                "GitHub rejected the personal access token."
            ) from error

        return cls(client)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # MARK: close
    def close(self) -> None:
        """Closes the underlying GitHub connections."""

        self._lazy_client.close()
        self._client.close()

    # MARK: build_query
    def _build_query(
        self, keywords: list[str], language: Language | None, min_stars: int | None
    ) -> str:
        """Builds a GitHub search query string, raising ValueError on malformed input."""

        cleaned_keywords: list[str] = [
            keyword.strip() for keyword in keywords if keyword.strip()
        ]

        if len(cleaned_keywords) != len(keywords):
            raise ValueError("Keywords must be non-empty strings.")
        if min_stars is not None and min_stars < 0:
            raise ValueError(f"min_stars must be non-negative, got {min_stars}.")
        if not cleaned_keywords and language is None and min_stars is None:
            raise ValueError(
                "Query needs at least one keyword, language, or min_stars."
            )

        terms: list[str] = [
            f'"{keyword}"' if " " in keyword else keyword
            for keyword in cleaned_keywords
        ]
        if language is not None:
            terms.append(f"language:{language.value}")
        if min_stars is not None:
            terms.append(f"stars:>={min_stars}")

        return " ".join(terms)

    # MARK: get_repos
    def get_repos(
        self,
        keywords: list[str] | None = None,
        language: Language | None = None,
        min_stars: int | None = None,
        limit: int = 100,
    ) -> list[RepoRef]:
        """Searches for repos matching the parameters, sorted by stars descending."""

        if not 0 < limit <= MAX_SEARCH_RESULTS:
            raise ValueError(
                f"limit must be between 1 and {MAX_SEARCH_RESULTS}, got {limit}."
            )

        query: str = self._build_query(keywords or [], language, min_stars)
        results: Iterator[Repository] = iter(
            self._client.search_repositories(query=query, sort="stars", order="desc")
        )

        return [self._to_repo_ref(repository) for repository in islice(results, limit)]

    # MARK: get_repo
    def get_repo(self, repo_name: str) -> RepoRef:
        """Fetches a single repo by its "owner/name", raising LookupError if it does not exist."""

        try:
            repository: Repository = self._client.get_repo(repo_name)
        except UnknownObjectException as error:
            raise LookupError(f"{repo_name} not found on GitHub.") from error

        return self._to_repo_ref(repository)

    # MARK: resolve_commit
    def resolve_commit(self, repo: RepoRef) -> RepoRef:
        """Returns a copy of `repo` pinned to the latest commit SHA on its default branch."""

        commit: Commit = self._lazy_client.get_repo(repo.full_name).get_commit(
            LATEST_COMMIT_REF
        )

        try:
            commit.update()
        except UnknownObjectException as error:
            raise LookupError(f"{repo.full_name} not found on GitHub.") from error

        return replace(repo, commit_SHA=commit.sha)

    # MARK: read_file_from_repo
    def read_file_from_repo(self, repo: RepoRef, path: str) -> str:
        """Returns the decoded text content of a file, raising FileNotFoundError if it is absent."""

        normalized_path: str = self._normalize_path(path)
        if not self.check_file_exists_in_repo(repo, normalized_path):
            raise FileNotFoundError(f"{normalized_path} not found in {repo.full_name}.")

        repository: Repository = self._lazy_client.get_repo(repo.full_name)
        content: bytes = repository.get_contents(
            normalized_path, ref=self._ref(repo)
        ).decoded_content

        return content.decode("utf-8", errors="replace")

    # MARK: check_file_exists_in_repo
    def check_file_exists_in_repo(self, repo: RepoRef, path: str) -> bool:
        """Checks whether a file exists in a repo without reading it."""

        return self._normalize_path(path) in self._get_tree(repo).file_paths

    # MARK: check_dir_exists_in_repo
    def check_dir_exists_in_repo(self, repo: RepoRef, path: str) -> bool:
        """Checks whether a directory exists in a repo without reading its contents."""

        return self._normalize_path(path) in self._get_tree(repo).dir_paths

    # MARK: find_files
    def find_files(self, repo: RepoRef, name: str) -> list[str]:
        """Returns paths of files whose base name matches the regex `name` (via re.search)."""

        pattern: re.Pattern[str] = re.compile(name)

        return sorted(
            path
            for path in self._get_tree(repo).file_paths
            if pattern.search(path.rsplit("/", 1)[-1])
        )

    def _get_tree(self, repo: RepoRef) -> RepoTree:
        if repo.full_name not in self._trees:
            self._trees[repo.full_name] = self._fetch_tree(repo)

        return self._trees[repo.full_name]

    def _fetch_tree(self, repo: RepoRef) -> RepoTree:
        repository: Repository = self._lazy_client.get_repo(repo.full_name)
        git_tree: GitTree = repository.get_git_tree(sha=self._ref(repo), recursive=True)

        if git_tree.truncated:
            warnings.warn(
                f"File tree for {repo.full_name} is truncated; some paths are missing."
            )

        return RepoTree(
            file_paths=frozenset(
                element.path for element in git_tree.tree if element.type == BLOB_TYPE
            ),
            dir_paths=frozenset(
                element.path for element in git_tree.tree if element.type == TREE_TYPE
            ),
        )

    @staticmethod
    def _ref(repo: RepoRef) -> str:
        return repo.commit_SHA or LATEST_COMMIT_REF

    @staticmethod
    def _normalize_path(path: str) -> str:
        return path.strip("/")

    @staticmethod
    def _to_repo_ref(repository: Repository) -> RepoRef:
        return RepoRef(
            full_name=repository.full_name,
            commit_SHA=None,
            repo_size=repository.size,
            stars=repository.stargazers_count,
            language=repository.language,
            url=repository.html_url,
        )
