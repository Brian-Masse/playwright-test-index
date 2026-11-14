from dataclasses import dataclass
from enum import Enum
from typing import Self

MIN_RATING: int = 1
MAX_RATING: int = 5


# MARK: PropertyTag
class PropertyTag(Enum):
    """The broad area of behavior a property describes."""

    functional = "functional"
    ui = "UI"
    api = "API"
    input = "input"

    # MARK: from_label
    @classmethod
    def from_label(cls, label: str | None) -> Self | None:
        """Parses a tag case-insensitively, returning None for a missing or blank label.
        Raises ValueError for an unrecognized label.
        """

        if label is None or not label.strip():
            return None

        normalized_label: str = label.strip().lower()
        for tag in cls:
            if tag.value.lower() == normalized_label:
                return tag

        raise ValueError(
            f"Unknown property tag {label!r}; expected one of {[tag.value for tag in cls]}."
        )


# MARK: PropertyRating
@dataclass(frozen=True)
class PropertyRating:
    """How strongly a property qualifies as a reusable PBT property, from 1 (weak) to 5 (strong)."""

    value: int

    def __post_init__(self) -> None:
        if not MIN_RATING <= self.value <= MAX_RATING:
            raise ValueError(
                f"Rating must be between {MIN_RATING} and {MAX_RATING}, got {self.value}."
            )


# MARK: Property
@dataclass(frozen=True)
class Property:
    """A high-level, reusable PBT property identified across tests (e.g. round-trip immutability)."""

    name: str
    description: str
    rating: PropertyRating
    tag: PropertyTag | None
