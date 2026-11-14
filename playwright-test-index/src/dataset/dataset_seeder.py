from typing import Any

from models.repo_analysis import RepoAnalysis

from dataset.annotation_parser import AnnotationError, AnnotationParser
from dataset.sqlite_dataset_store import DatasetStore

type JsonDict = dict[str, Any]

ANALYSES_KEY: str = "analyses"


# MARK: DatasetSeeder
class DatasetSeeder:
    """Loads a seed template, a list of per-repo annotation documents, into a dataset store.

    Template shape: {"analyses": [<annotations document>, ...]}, where each document is the
    format AnnotationParser accepts.
    """

    def __init__(self, parser: AnnotationParser, store: DatasetStore) -> None:
        self._parser: AnnotationParser = parser
        self._store: DatasetStore = store

    # MARK: seed
    def seed(self, template: JsonDict) -> None:
        """Parses every analysis in `template` and stores them in order.
        All analyses are parsed before anything is written, so a malformed template writes nothing.
        """

        if ANALYSES_KEY not in template:
            raise AnnotationError(f"Seed template is missing field '{ANALYSES_KEY}'.")

        analyses: list[RepoAnalysis] = [
            self._parser.parse(document) for document in template[ANALYSES_KEY]
        ]

        for analysis in analyses:
            self._store.add_analysis(analysis)
