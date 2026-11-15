import argparse
import json
from pathlib import Path

from dataset.annotation_parser import AnnotationParser
from dataset.sqlite_dataset_store import SqliteDatasetStore
from models.repo_analysis import RepoAnalysis

DEFAULT_DB_PATH: Path = Path(__file__).resolve().parents[1] / "data" / "dataset.db"
FILE_ENCODING: str = "utf-8"


# MARK: store
def store(annotations_path: Path, db_path: Path) -> None:
    """Parses an annotations file and upserts its repo, properties, and tests into the database."""

    document: dict = json.loads(annotations_path.read_text(encoding=FILE_ENCODING))
    analysis: RepoAnalysis = AnnotationParser().parse(document)

    SqliteDatasetStore(db_path).add_analysis(analysis)

    print(
        f"Stored {analysis.repo.repo.full_name}: {len(analysis.tests)} tests, "
        f"{len(analysis.properties)} properties -> {db_path}"
    )


# MARK: main
def main() -> None:
    """Stores one repo's analysis annotations in the local SQLite dataset."""

    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "annotations", type=Path, help="Path to the annotations JSON file"
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite database to write to"
    )

    arguments: argparse.Namespace = parser.parse_args()
    store(arguments.annotations, arguments.db)


if __name__ == "__main__":
    main()
