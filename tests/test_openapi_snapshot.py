from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from server import app  # noqa: E402


class OpenApiSnapshotTests(unittest.TestCase):
    def test_openapi_schema_matches_snapshot(self) -> None:
        expected = json.loads((ROOT / "tests" / "snapshots" / "openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(app.openapi(), expected)
