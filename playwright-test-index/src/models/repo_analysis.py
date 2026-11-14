from dataclasses import dataclass

from models.playwright_test import TestRecord
from models.property import Property
from models.repo_ref import RepoRecord


# MARK: RepoAnalysis
@dataclass(frozen=True)
class RepoAnalysis:
    """One repository's analysis: the repo, the properties it defines, and its analyzed tests."""

    repo: RepoRecord
    properties: tuple[Property, ...]
    tests: tuple[TestRecord, ...]
