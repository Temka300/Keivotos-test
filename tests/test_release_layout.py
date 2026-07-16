from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def isolated_home():
    path = ROOT / "tests" / f".tmp-release-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class ReleaseLayoutTests(unittest.TestCase):
    def test_checked_in_defaults_are_external_to_the_repository(self) -> None:
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["data_root"], "library")
        self.assertEqual(config["metadata_dir"], ".")
        self.assertEqual(config["gallery_dl_dir"], "gallery-dl")
        self.assertEqual(config["backup_destination"], "backups/waifu-hoard")

    def test_release_outputs_are_ignored_at_the_repository_root(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/Keivotos-V*-windows-x64/", ignore)
        self.assertIn("/Keivotos-V*-windows-x64.zip", ignore)
        self.assertIn("/Keivotos-V*-windows-x64.zip.sha256", ignore)
        self.assertIn("/download.png", ignore)

    def test_default_scan_configuration_contains_no_personal_folder_names(self) -> None:
        config_source = (ROOT / "backend" / "config.py").read_text(encoding="utf-8")
        pipeline_source = (ROOT / "scripts" / "danbooru_gallery_dl.py").read_text(encoding="utf-8")
        for personal_name in ("Danbooru_kivotos", "Danbooru_zANKI"):
            self.assertNotIn(personal_name, config_source)
            self.assertNotIn(personal_name, pipeline_source)

    def test_windows_documents_known_folder_is_the_default_source(self) -> None:
        source = (ROOT / "backend" / "config.py").read_text(encoding="utf-8")
        self.assertIn("SHGetKnownFolderPath", source)
        self.assertIn("FOLDERID_DOCUMENTS", source)
        self.assertIn('documents_directory() / "Keivotos"', source)

    def test_legacy_metadata_wrapper_is_flattened_without_overwrite(self) -> None:
        with isolated_home() as temporary:
            legacy = temporary / "modules" / "waifu-hoard" / "metadata"
            (legacy / "sidecars" / "roots").mkdir(parents=True)
            (legacy / "sidecars" / "roots" / "sample.json").write_text("sidecar", encoding="utf-8")
            (legacy / "danbooru.sqlite").write_bytes(b"library-db")
            (legacy / "user.sqlite").write_bytes(b"user-db")
            environment = {**os.environ, "KEIVOTOS_HOME": str(temporary)}
            code = (
                "import json, sys; "
                f"sys.path.insert(0, {str(ROOT / 'backend')!r}); "
                "import config; "
                "print(json.dumps(config.migrate_legacy_default_metadata()))"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            migration = json.loads(result.stdout)
            module_home = temporary / "modules" / "waifu-hoard"
            self.assertTrue(migration["migrated"])
            self.assertFalse(legacy.exists())
            self.assertEqual((module_home / "danbooru.sqlite").read_bytes(), b"library-db")
            self.assertEqual((module_home / "user.sqlite").read_bytes(), b"user-db")
            self.assertEqual((module_home / "sidecars" / "roots" / "sample.json").read_text(encoding="utf-8"), "sidecar")

    def test_legacy_metadata_conflict_is_preserved(self) -> None:
        with isolated_home() as temporary:
            module_home = temporary / "modules" / "waifu-hoard"
            legacy = module_home / "metadata"
            legacy.mkdir(parents=True)
            (module_home / "user.sqlite").write_bytes(b"new-location")
            (legacy / "user.sqlite").write_bytes(b"legacy-location")
            environment = {**os.environ, "KEIVOTOS_HOME": str(temporary)}
            code = (
                "import sys; "
                f"sys.path.insert(0, {str(ROOT / 'backend')!r}); "
                "import config; "
                "config.migrate_legacy_default_metadata()"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("conflicting destination", result.stderr)
            self.assertEqual((module_home / "user.sqlite").read_bytes(), b"new-location")
            self.assertEqual((legacy / "user.sqlite").read_bytes(), b"legacy-location")

    def test_generated_folder_guard_allows_library_beside_metadata(self) -> None:
        with isolated_home() as temporary:
            environment = {**os.environ, "KEIVOTOS_HOME": str(temporary)}
            code = (
                "import json, sys; "
                f"sys.path.insert(0, {str(ROOT / 'backend')!r}); "
                "import config; from routers.folders import _is_generated_folder; "
                "p=config.MODULE_HOME; "
                "print(json.dumps({"
                "'root': _is_generated_folder(p), "
                "'library': _is_generated_folder(p/'library'/'images'), "
                "'sidecars': _is_generated_folder(p/'sidecars'/'roots'), "
                "'gallery': _is_generated_folder(p/'gallery-dl'/'work')"
                "}))"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            guard = json.loads(result.stdout)
            self.assertTrue(guard["root"])
            self.assertFalse(guard["library"])
            self.assertTrue(guard["sidecars"])
            self.assertTrue(guard["gallery"])

    def test_runtime_config_is_written_under_isolated_keivotos_home(self) -> None:
        with isolated_home() as temporary:
            environment = {**os.environ, "KEIVOTOS_HOME": str(temporary)}
            code = (
                "import sys; "
                f"sys.path.insert(0, {str(ROOT / 'backend')!r}); "
                "import config; "
                "config.save_config({'thumbnail_cache_limit_gb': 5}); "
                "print(config.get_config_path())"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            runtime_config = Path(result.stdout.strip())
            self.assertEqual(runtime_config, temporary / "config.json")
            self.assertEqual(json.loads(runtime_config.read_text(encoding="utf-8"))["thumbnail_cache_limit_gb"], 5)

    def test_product_identity_and_portable_check(self) -> None:
        with isolated_home() as temporary:
            environment = {**os.environ, "KEIVOTOS_HOME": str(temporary)}
            version = subprocess.run(
                [sys.executable, "app.py", "--version"],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(version.stdout.strip(), "Keivotos - Waifu-Hoard 1.0.0")
            portable = subprocess.run(
                [sys.executable, "app.py", "--portable-check"],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn(f"Writable home: {temporary}", portable.stdout)
            self.assertIn("Frontend: ok", portable.stdout)
            self.assertIn("Backend: ok", portable.stdout)
            self.assertIn("Folder picker: ok", portable.stdout)

    def test_windows_spec_collects_the_backend_composition_root(self) -> None:
        spec = (ROOT / "packaging" / "windows" / "Keivotos.spec").read_text(encoding="utf-8")
        self.assertIn('hiddenimports=["server"]', spec)

    def test_web_document_uses_suite_identity(self) -> None:
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Keivotos — Waifu-Hoard</title>", index)
        self.assertIn('href="/favicon.png"', index)
        self.assertTrue((ROOT / "frontend" / "public" / "keivotos-logo.png").is_file())
        self.assertTrue((ROOT / "packaging" / "windows" / "assets" / "keivotos.ico").is_file())

    def test_launcher_and_brand_assets_use_the_keivotos_defaults(self) -> None:
        sys.path.insert(0, str(ROOT / "backend"))
        try:
            from product import DEFAULT_HOST, DEFAULT_ORIGIN, DEFAULT_PORT
        finally:
            sys.path.pop(0)
        self.assertEqual((DEFAULT_HOST, DEFAULT_PORT), ("localhost", 52325))
        self.assertEqual(DEFAULT_ORIGIN, "http://localhost:52325")

        canonical = (
            ROOT / "assets" / "branding" / "keivotos" / "source" / "keivotos-angular-logo.svg"
        ).read_text(encoding="utf-8")
        module_mark = (
            ROOT / "assets" / "branding" / "waifu-hoard" / "icon.svg"
        ).read_text(encoding="utf-8")
        module_profile_mark = (
            ROOT / "assets" / "branding" / "waifu-hoard" / "profile-avatar.svg"
        ).read_text(encoding="utf-8")
        self.assertIn("Keivotos angular avatar logo", canonical)
        self.assertIn('aria-label="Waifu Hoard"', module_mark)
        self.assertEqual((ROOT / "frontend" / "public" / "logo.svg").read_text(encoding="utf-8"), module_mark)
        self.assertEqual((ROOT / "frontend" / "public" / "favicon.svg").read_text(encoding="utf-8"), canonical)
        self.assertEqual(
            (ROOT / "frontend" / "public" / "profile-avatar.svg").read_text(encoding="utf-8"),
            module_profile_mark,
        )
        user_menu = (ROOT / "frontend" / "src" / "components" / "UserMenu.svelte").read_text(encoding="utf-8")
        profile_view = (ROOT / "frontend" / "src" / "components" / "ProfileView.svelte").read_text(encoding="utf-8")
        app_drawer = (ROOT / "frontend" / "src" / "components" / "AppDrawer.svelte").read_text(encoding="utf-8")
        self.assertIn('src="/profile-avatar.svg"', user_menu)
        self.assertNotIn('src="/keivotos-logo.png"', user_menu)
        self.assertIn(": '/profile-avatar.svg';", profile_view)
        self.assertIn('<img src="/profile-avatar.svg" alt="" class="h-9 w-9', app_drawer)


if __name__ == "__main__":
    unittest.main()
