from dataclasses import dataclass, field

from models.language import Language

DEFAULT_SEARCH_LIMIT: int = 100


# MARK: RepoSearchQuery
@dataclass(frozen=True)
class RepoSearchQuery:
    """Criteria for a GitHub repository search, ranked by stars descending."""

    keywords: tuple[str, ...] = field(default_factory=tuple)
    language: Language | None = None
    min_stars: int | None = None
    limit: int = DEFAULT_SEARCH_LIMIT
