import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol

from models.playwright_test import TestRecord
from models.property import Property
from models.repo_analysis import RepoAnalysis
from models.repo_ref import RepoRecord

SCHEMA_SQL: str = """
CREATE TABLE IF NOT EXISTS repos (
  full_name   TEXT NOT NULL,
  commit_sha  TEXT NOT NULL,
  repo_size   INTEGER,
  stars       INTEGER,
  language    TEXT,
  url         TEXT,
  description TEXT,
  PRIMARY KEY (full_name, commit_sha)
);
CREATE TABLE IF NOT EXISTS properties (
  name        TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  rating      INTEGER,
  tag         TEXT
);
CREATE TABLE IF NOT EXISTS tests (
  id              INTEGER PRIMARY KEY,
  repo_full_name  TEXT NOT NULL,
  repo_commit_sha TEXT NOT NULL,
  name            TEXT NOT NULL,
  description     TEXT NOT NULL,
  language        TEXT NOT NULL,
  test_path       TEXT NOT NULL,
  start_line      INTEGER NOT NULL,
  end_line        INTEGER NOT NULL,
  UNIQUE (repo_full_name, repo_commit_sha, test_path, start_line),
  FOREIGN KEY (repo_full_name, repo_commit_sha)
    REFERENCES repos (full_name, commit_sha)
);
CREATE TABLE IF NOT EXISTS test_properties (
  test_id       INTEGER NOT NULL REFERENCES tests (id) ON DELETE CASCADE,
  property_name TEXT    NOT NULL REFERENCES properties (name),
  PRIMARY KEY (test_id, property_name)
);
"""

UPSERT_REPO_SQL: str = """
INSERT INTO repos (full_name, commit_sha, repo_size, stars, language, url, description)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (full_name, commit_sha) DO UPDATE SET
  repo_size = excluded.repo_size, stars = excluded.stars, language = excluded.language,
  url = excluded.url, description = excluded.description;
"""

UPSERT_PROPERTY_SQL: str = """
INSERT INTO properties (name, description, rating, tag) VALUES (?, ?, ?, ?)
ON CONFLICT (name) DO UPDATE SET
  description = excluded.description, rating = excluded.rating, tag = excluded.tag;
"""

UPSERT_TEST_SQL: str = """
INSERT INTO tests (repo_full_name, repo_commit_sha, name, description, language,
                   test_path, start_line, end_line)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (repo_full_name, repo_commit_sha, test_path, start_line) DO UPDATE SET
  name = excluded.name, description = excluded.description,
  language = excluded.language, end_line = excluded.end_line
RETURNING id;
"""

DELETE_TEST_PROPERTIES_SQL: str = "DELETE FROM test_properties WHERE test_id = ?;"
INSERT_TEST_PROPERTY_SQL: str = (
    "INSERT INTO test_properties (test_id, property_name) VALUES (?, ?);"
)
SELECT_PROPERTY_NAMES_SQL: str = "SELECT name FROM properties;"
ENABLE_FOREIGN_KEYS_SQL: str = "PRAGMA foreign_keys = ON;"


# MARK: UnknownPropertyError
class UnknownPropertyError(ValueError):
    """Raised when a test references a property that is neither stored nor defined in the analysis."""


# MARK: DatasetStore
class DatasetStore(Protocol):
    """Persists analyzed repositories, their properties, and their tests."""

    def add_analysis(self, analysis: RepoAnalysis) -> None:
        """Stores the analysis, overwriting entries that share a key."""

        ...


# MARK: SqliteDatasetStore
class SqliteDatasetStore:
    """Stores analyses in a SQLite database, creating the schema on first use."""

    def __init__(self, db_path: Path) -> None:
        self._db_path: Path = db_path

    # MARK: add_analysis
    def add_analysis(self, analysis: RepoAnalysis) -> None:
        """Upserts the repo, properties, and tests in one transaction, replacing each stored test's property links.
        Raises UnknownPropertyError, writing nothing, if a test references an undefined property.
        """

        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        with closing(sqlite3.connect(self._db_path)) as connection:
            connection.execute(ENABLE_FOREIGN_KEYS_SQL)
            connection.executescript(SCHEMA_SQL)

            with connection:
                self._require_known_properties(connection, analysis)

                self._upsert_repo(connection, analysis.repo)
                self._upsert_properties(connection, analysis.properties)
                self._upsert_tests(connection, analysis.tests)

    def _require_known_properties(
        self, connection: sqlite3.Connection, analysis: RepoAnalysis
    ) -> None:
        stored_names: set[str] = {
            row[0] for row in connection.execute(SELECT_PROPERTY_NAMES_SQL)
        }
        defined_names: set[str] = stored_names | {
            property.name for property in analysis.properties
        }

        referenced_names: set[str] = {
            name for test in analysis.tests for name in test.property_names
        }
        unknown_names: set[str] = referenced_names - defined_names

        if unknown_names:
            raise UnknownPropertyError(
                f"Tests reference undefined properties: {sorted(unknown_names)}."
            )

    @staticmethod
    def _upsert_repo(connection: sqlite3.Connection, record: RepoRecord) -> None:
        connection.execute(
            UPSERT_REPO_SQL,
            (
                record.repo.full_name,
                record.repo.commit_SHA,
                record.repo.repo_size,
                record.repo.stars,
                record.repo.language,
                record.repo.url,
                record.description,
            ),
        )

    @staticmethod
    def _upsert_properties(
        connection: sqlite3.Connection, properties: tuple[Property, ...]
    ) -> None:
        connection.executemany(
            UPSERT_PROPERTY_SQL,
            [
                (
                    property.name,
                    property.description,
                    property.rating.value,
                    property.tag.value if property.tag else None,
                )
                for property in properties
            ],
        )

    @staticmethod
    def _upsert_tests(
        connection: sqlite3.Connection, tests: tuple[TestRecord, ...]
    ) -> None:
        for test in tests:
            test_id: int = connection.execute(
                UPSERT_TEST_SQL,
                (
                    test.repo_full_name,
                    test.repo_commit_SHA,
                    test.name,
                    test.description,
                    test.language.value,
                    test.test_path,
                    test.start_line,
                    test.end_line,
                ),
            ).fetchone()[0]

            connection.execute(DELETE_TEST_PROPERTIES_SQL, (test_id,))
            connection.executemany(
                INSERT_TEST_PROPERTY_SQL,
                [(test_id, name) for name in test.property_names],
            )
