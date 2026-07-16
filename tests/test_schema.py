from __future__ import annotations

import shutil
import sqlite3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from schema import ensure_data_schema  # noqa: E402


class SharedSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = ROOT / "tests" / ".tmp-schema"
        shutil.rmtree(self.temp, ignore_errors=True)
        self.temp.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_additive_migration_supports_backend_dictionary_rows(self) -> None:
        connection = sqlite3.connect(self.temp / "data.sqlite")
        connection.execute(
            """CREATE TABLE files (
                   id INTEGER PRIMARY KEY, path TEXT UNIQUE, folder TEXT, name TEXT,
                   ext TEXT, size INTEGER, local_md5 TEXT, downloaded_at TEXT,
                   matched_md5 TEXT, matched_by TEXT
               )"""
        )
        connection.row_factory = lambda cursor, row: {
            description[0]: value for description, value in zip(cursor.description, row)
        }
        ensure_data_schema(connection)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(files)")}
        indexes = {row["name"] for row in connection.execute("PRAGMA index_list(files)")}
        connection.close()
        self.assertIn("root_id", columns)
        self.assertIn("relative_path", columns)
        self.assertIn("idx_files_root_relative", indexes)


if __name__ == "__main__":
    unittest.main()
