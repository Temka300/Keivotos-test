"""Central configuration and the external Keivotos writable-data layout."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
import uuid
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any


def _resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled).resolve() if bundled else Path(__file__).resolve().parent.parent


CODE_ROOT = _resource_root()
SOURCE_CONFIG_FILE = CODE_ROOT / "config.json"


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, value: str) -> "_Guid":
        return cls.from_buffer_copy(uuid.UUID(value).bytes_le)


FOLDERID_DOCUMENTS = _Guid.parse("FDD39AD0-238F-46AF-ADB4-6C85480369C7")


def windows_documents_directory() -> Path | None:
    """Return the Windows Documents known folder, including redirected paths."""
    if os.name != "nt":
        return None
    try:
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        ole32 = ctypes.OleDLL("ole32")
    except (AttributeError, OSError):
        return None
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(_Guid),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None
    raw_path = ctypes.c_void_p()
    result = shell32.SHGetKnownFolderPath(
        ctypes.byref(FOLDERID_DOCUMENTS),
        0,
        None,
        ctypes.byref(raw_path),
    )
    if result != 0 or not raw_path.value:
        return None
    try:
        return Path(ctypes.wstring_at(raw_path.value))
    finally:
        ole32.CoTaskMemFree(raw_path)


def documents_directory() -> Path:
    return windows_documents_directory() or (Path.home() / "Documents")


_suite_home_override = os.environ.get("KEIVOTOS_HOME", "").strip()
SUITE_HOME = (
    Path(_suite_home_override).expanduser()
    if _suite_home_override
    else documents_directory() / "Keivotos"
)
MODULE_HOME = SUITE_HOME / "modules" / "waifu-hoard"
DEFAULT_LIBRARY_DIR = MODULE_HOME / "library"
DEFAULT_METADATA_DIR = MODULE_HOME
LEGACY_DEFAULT_METADATA_DIR = MODULE_HOME / "metadata"
DEFAULT_GALLERY_DL_DIR = MODULE_HOME / "gallery-dl"
DEFAULT_BACKUP_DIR = SUITE_HOME / "backups" / "waifu-hoard"
LOG_DIR = SUITE_HOME / "logs"
LOG_FILE_LIMIT_MB = 5
LOG_ROLLOVER_FILES = 5
LOG_RETENTION_FILES = 30
LOG_SESSION_ID = f"{datetime.now().astimezone():%Y-%m-%d_%H-%M-%S}-p{os.getpid()}"
RUNTIME_LOG_FILE = LOG_DIR / f"waifu-hoard-runtime-{LOG_SESSION_ID}.log"
ACCESS_LOG_FILE = LOG_DIR / f"waifu-hoard-access-{LOG_SESSION_ID}.log"
RUNTIME_CONFIG_FILE = SUITE_HOME / "config.json"

# Compatibility name used by existing APIs; it means the module's writable
# root inside the Keivotos Documents layout.
DOCUMENTS_ROOT = DEFAULT_METADATA_DIR

_defaults: dict[str, Any] = {
    "data_root": str(DEFAULT_LIBRARY_DIR),
    "metadata_dir": str(DEFAULT_METADATA_DIR),
    "gallery_dl_dir": str(DEFAULT_GALLERY_DL_DIR),
    "automation_enabled": False,
    "automation_enabled_at": None,
    "automation_interval_minutes": 15,
    "backup_destination": str(DEFAULT_BACKUP_DIR),
    "backup_components": {
        "user_database": True,
        "library_database": True,
        "sidecars": True,
        "sidecar_history": False,
        "artist_profile_archive": False,
    },
    "thumbnail_cache_limit_gb": 10,
}
_external_path_defaults = {
    key: _defaults[key]
    for key in ("data_root", "metadata_dir", "gallery_dl_dir", "backup_destination")
}


class ConfigurationError(RuntimeError):
    """A user-editable configuration file could not be loaded safely."""


def _record_configuration_error(message: str) -> None:
    """Persist import-time failures before normal logging is available."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        with RUNTIME_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"{timestamp} ERROR config: Configuration error: {message}\n")
    except OSError:
        pass


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        message = f"Could not read configuration file {path}: {exc}"
        _record_configuration_error(message)
        raise ConfigurationError(message) from exc
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        message = (
            f"Invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}. "
            "Fix or rename this file, then start Keivotos again."
        )
        _record_configuration_error(message)
        raise ConfigurationError(message) from exc
    if not isinstance(value, dict):
        message = f"Configuration must contain a JSON object: {path}"
        _record_configuration_error(message)
        raise ConfigurationError(message)
    return value


def _load() -> dict[str, Any]:
    config = {**_defaults, **_read_json(SOURCE_CONFIG_FILE)}
    # Tests and portable verification can redirect every writable default with
    # one environment variable, regardless of the checked-in template paths.
    if "KEIVOTOS_HOME" in os.environ:
        config.update(_external_path_defaults)
    config.update(_read_json(RUNTIME_CONFIG_FILE))
    return config


_cfg = _load()


def _resolve_path(value: str, base: Path = MODULE_HOME) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


DATA_ROOT = _resolve_path(str(_cfg["data_root"]))
METADATA_DIR = _resolve_path(str(_cfg["metadata_dir"]))
if METADATA_DIR.resolve(strict=False) == LEGACY_DEFAULT_METADATA_DIR.resolve(strict=False):
    METADATA_DIR = DEFAULT_METADATA_DIR
    _cfg["metadata_dir"] = str(DEFAULT_METADATA_DIR)
GALLERY_DL_DIR = _resolve_path(str(_cfg.get("gallery_dl_dir", DEFAULT_GALLERY_DL_DIR)))

DATA_DB_PATH = METADATA_DIR / "danbooru.sqlite"
USER_DB_PATH = METADATA_DIR / "user.sqlite"
THUMB_DIR = METADATA_DIR / "thumbnails"
SIDECAR_DIR = METADATA_DIR / "sidecars"
ARTIST_PROFILE_ARCHIVE_DIR = METADATA_DIR / "artist_profile_archive"
CREDENTIALS_PATH = METADATA_DIR / "danbooru_credentials.json"


def _files_match(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False

    def digest(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    return digest(left) == digest(right)


def _merge_legacy_entry(source: Path, destination: Path) -> tuple[int, int]:
    """Move one legacy entry without overwriting a different destination."""
    if source.is_symlink():
        raise RuntimeError(f"Refused to migrate symbolic link: {source}")
    if not destination.exists():
        source.replace(destination)
        return (1, 0)
    if source.is_dir() and destination.is_dir():
        moved = deduplicated = 0
        for child in sorted(source.iterdir(), key=lambda item: item.name.casefold()):
            child_moved, child_deduplicated = _merge_legacy_entry(child, destination / child.name)
            moved += child_moved
            deduplicated += child_deduplicated
        source.rmdir()
        return moved, deduplicated
    if source.is_file() and destination.is_file() and _files_match(source, destination):
        source.unlink()
        return (0, 1)
    raise RuntimeError(
        "Legacy metadata migration found a conflicting destination. "
        f"Preserved both paths for manual review: {source} and {destination}"
    )


def migrate_legacy_default_metadata() -> dict[str, Any]:
    """Flatten the former module/metadata wrapper at startup, once and safely."""
    target = DEFAULT_METADATA_DIR.resolve(strict=False)
    legacy = LEGACY_DEFAULT_METADATA_DIR
    if METADATA_DIR.resolve(strict=False) != target or not legacy.exists():
        return {"migrated": False, "moved": 0, "deduplicated": 0}
    if legacy.is_symlink() or legacy.parent.resolve(strict=False) != target:
        raise RuntimeError(f"Refused unsafe legacy metadata migration: {legacy}")

    moved = deduplicated = 0
    for child in sorted(legacy.iterdir(), key=lambda item: item.name.casefold()):
        child_moved, child_deduplicated = _merge_legacy_entry(child, DEFAULT_METADATA_DIR / child.name)
        moved += child_moved
        deduplicated += child_deduplicated
    legacy.rmdir()
    return {"migrated": True, "moved": moved, "deduplicated": deduplicated}

def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


SCAN_FOLDERS: list[str] = _string_list(_cfg.get("scan_folders"))


def save_config(overrides: dict[str, Any]) -> None:
    """Persist user overrides outside the source tree and packaged app."""
    current = _read_json(RUNTIME_CONFIG_FILE)
    current.update(overrides)
    RUNTIME_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = RUNTIME_CONFIG_FILE.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(current, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(RUNTIME_CONFIG_FILE)
    _cfg.update(overrides)


def runtime_config_snapshot() -> dict[str, Any]:
    """Return the effective, non-secret settings suitable for a backup bundle."""
    private_paths = {"data_root", "metadata_dir", "gallery_dl_dir", "backup_destination"}
    return {
        key: value
        for key, value in _cfg.items()
        if key not in private_paths
    }


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def get_automation_config() -> dict[str, Any]:
    return {
        "enabled": bool(_cfg.get("automation_enabled", False)),
        "enabled_at": _cfg.get("automation_enabled_at"),
        "interval_minutes": _bounded_int(_cfg.get("automation_interval_minutes"), 15, 5, 1440),
    }


def get_backup_config() -> dict[str, Any]:
    defaults = dict(_defaults["backup_components"])
    components = _cfg.get("backup_components")
    if isinstance(components, dict):
        defaults.update({key: bool(value) for key, value in components.items() if key in defaults})
    destination = _resolve_path(str(_cfg.get("backup_destination", DEFAULT_BACKUP_DIR)), SUITE_HOME)
    return {"destination": str(destination), "components": defaults}


def get_thumbnail_cache_limit_bytes() -> int:
    value = _bounded_int(_cfg.get("thumbnail_cache_limit_gb"), 10, 1, 100)
    return value * 1024 * 1024 * 1024


def public_storage_config() -> dict[str, Any]:
    resolved = METADATA_DIR.resolve(strict=False)
    expected = DEFAULT_METADATA_DIR.resolve(strict=False)
    return {
        "metadata_dir": str(METADATA_DIR),
        "documents_default": str(DEFAULT_METADATA_DIR),
        "suite_home": str(SUITE_HOME),
        "module_home": str(MODULE_HOME),
        "library_dir": str(DATA_ROOT),
        "config_file": str(RUNTIME_CONFIG_FILE),
        "gallery_dl_dir": str(GALLERY_DL_DIR),
        "log_dir": str(LOG_DIR),
        "runtime_log_file": str(RUNTIME_LOG_FILE),
        "access_log_file": str(ACCESS_LOG_FILE),
        "log_retention_files": LOG_RETENTION_FILES,
        "mode": "keivotos" if resolved == expected else "custom",
    }


def get_config_path() -> Path:
    return RUNTIME_CONFIG_FILE
