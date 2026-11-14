from typing import Any

from models.language import Language
from models.playwright_test import TestRecord
from models.property import Property, PropertyRating, PropertyTag
from models.repo_analysis import RepoAnalysis
from models.repo_ref import RepoRecord, RepoRef

type JsonDict = dict[str, Any]


# MARK: AnnotationError
class AnnotationError(ValueError):
    """Raised when an annotations document is missing fields or holds invalid values."""


# MARK: AnnotationParser
class AnnotationParser:
    """Converts an analyst's annotations JSON document into a RepoAnalysis.

    Expected shape:
    {
      "repo": {"full_name", "commit_SHA", "repo_size", "stars", "language", "url"},
      "repo_description": str,
      "properties": [{"name", "description", "rating", "tag"}],   # optional
      "tests": [{"name", "description", "language", "test_path",
                 "start_line", "end_line", "property_names"}]
    }
    """

    # MARK: parse
    def parse(self, document: JsonDict) -> RepoAnalysis:
        """Returns the analysis described by `document`, raising AnnotationError on malformed input."""

        try:
            repo: RepoRef = self._parse_repo(document["repo"])
            commit_SHA: str = self._require_commit_SHA(repo)

            return RepoAnalysis(
                repo=RepoRecord(repo=repo, description=document["repo_description"]),
                properties=tuple(
                    self._parse_property(entry)
                    for entry in document.get("properties", [])
                ),
                tests=tuple(
                    self._parse_test(entry, repo.full_name, commit_SHA)
                    for entry in document["tests"]
                ),
            )
        except KeyError as error:
            raise AnnotationError(f"Annotations are missing field {error}.") from error
        except (TypeError, ValueError) as error:
            raise AnnotationError(f"Invalid annotations: {error}") from error

    @staticmethod
    def _parse_repo(data: JsonDict) -> RepoRef:
        return RepoRef(
            full_name=data["full_name"],
            commit_SHA=data["commit_SHA"],
            repo_size=data["repo_size"],
            stars=data["stars"],
            language=data["language"],
            url=data["url"],
        )

    @staticmethod
    def _require_commit_SHA(repo: RepoRef) -> str:
        if repo.commit_SHA is None:
            raise ValueError(f"{repo.full_name} has no commit_SHA.")

        return repo.commit_SHA

    @staticmethod
    def _parse_property(data: JsonDict) -> Property:
        return Property(
            name=data["name"],
            description=data["description"],
            rating=PropertyRating(data["rating"]),
            tag=PropertyTag.from_label(data.get("tag")),
        )

    @staticmethod
    def _parse_test(data: JsonDict, repo_full_name: str, commit_SHA: str) -> TestRecord:
        return TestRecord(
            repo_full_name=repo_full_name,
            repo_commit_SHA=commit_SHA,
            name=data["name"],
            description=data["description"],
            language=Language(data["language"]),
            test_path=data["test_path"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            property_names=tuple(data["property_names"]),
        )
