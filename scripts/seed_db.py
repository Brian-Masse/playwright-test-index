import argparse
import json
import sys
from pathlib import Path

from dataset.annotation_parser import AnnotationParser
from dataset.dataset_seeder import DatasetSeeder
from dataset.sqlite_dataset_store import SqliteDatasetStore

DATA_DIR: Path = Path(__file__).resolve().parents[1] / "data"
DEFAULT_DB_PATH: Path = DATA_DIR / "dataset.db"
DEFAULT_TEMPLATE_PATH: Path = DATA_DIR / "seed_template.json"
FILE_ENCODING: str = "utf-8"


# MARK: seed
def seed(template_path: Path, db_path: Path) -> None:
    """Builds a new database at `db_path` from the seed template, refusing to touch an existing one."""

    if db_path.exists():
        sys.exit(f"{db_path} already exists; delete it or pass --db to seed a new file.")

    template: dict = json.loads(template_path.read_text(encoding=FILE_ENCODING))
    seeder: DatasetSeeder = DatasetSeeder(AnnotationParser(), SqliteDatasetStore(db_path))

    try:
        seeder.seed(template)
    except Exception:
        db_path.unlink(missing_ok=True)
        raise

    print(f"Seeded {db_path} from {template_path}.")


# MARK: main
def main() -> None:
    """Creates the local SQLite dataset from the committed seed template."""

    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE_PATH, help="Seed template JSON")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite database to create")

    arguments: argparse.Namespace = parser.parse_args()
    seed(arguments.template, arguments.db)


if __name__ == "__main__":
    main()
