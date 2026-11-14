from dataclasses import dataclass


# MARK: Property
@dataclass(frozen=True)
class Property:
    """A high-level, reusable PBT property identified across tests (e.g. round-trip immutability)."""

    name: str
    description: str
