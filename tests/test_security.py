from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from security import validate_local_browser_request  # noqa: E402


class LocalApiSecurityTests(unittest.TestCase):
    def test_same_origin_loopback_browser_request_is_allowed(self) -> None:
        self.assertIsNone(validate_local_browser_request(
            host_header="localhost:52325",
            scheme="http",
            origin_header="http://localhost:52325",
        ))

    def test_loopback_navigation_without_origin_is_allowed(self) -> None:
        self.assertIsNone(validate_local_browser_request(
            host_header="localhost:52325",
            scheme="http",
            origin_header=None,
        ))

    def test_cross_origin_browser_request_is_rejected(self) -> None:
        rejection = validate_local_browser_request(
            host_header="localhost:52325",
            scheme="http",
            origin_header="https://example.com",
        )
        self.assertEqual(rejection[0] if rejection else None, 403)

    def test_non_loopback_host_is_rejected(self) -> None:
        rejection = validate_local_browser_request(
            host_header="attacker.example:52325",
            scheme="http",
            origin_header=None,
        )
        self.assertEqual(rejection[0] if rejection else None, 400)

    def test_cross_site_subresource_without_origin_is_rejected(self) -> None:
        rejection = validate_local_browser_request(
            host_header="localhost:52325",
            scheme="http",
            origin_header=None,
            fetch_site_header="cross-site",
        )
        self.assertEqual(rejection[0] if rejection else None, 403)


if __name__ == "__main__":
    unittest.main()
