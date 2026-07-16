"""Local collection: scan downloaded CBZ files + info sidecars, serve pages."""
import json
import random
import re
import shutil
import threading
import zipfile
from pathlib import Path

import config

_cache_lock = threading.Lock()
_meta_cache: dict[int, dict] = {}
_meta_mtimes: dict[int, float] = {}


def manga_dir() -> Path | None:
    return config.effective_dirs()[0]


def info_dir() -> Path | None:
    return config.effective_dirs()[1]


def downloaded_ids() -> set[int]:
    d = manga_dir()
    if not d or not d.exists():
        return set()
    return {int(p.stem) for p in d.glob("*.cbz") if p.stem.isdigit()}


def _load_meta(json_path: Path) -> dict | None:
    gid = int(json_path.stem)
    mtime = json_path.stat().st_mtime
    with _cache_lock:
        if _meta_mtimes.get(gid) == mtime:
            return _meta_cache.get(gid)
    try:
        meta = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    with _cache_lock:
        _meta_cache[gid] = meta
        _meta_mtimes[gid] = mtime
    return meta


SORTS = ("added", "title", "pages", "date", "artist", "favorites", "random", "series")


def pinned_ids() -> set[int]:
    return {int(i) for i in config.load().get("pinned", [])}


def set_pinned(gallery_id: int, on: bool) -> bool:
    cfg = config.load()
    pins = {int(i) for i in cfg.get("pinned", [])}
    if on:
        pins.add(gallery_id)
    else:
        pins.discard(gallery_id)
    cfg["pinned"] = sorted(pins)
    config.save(cfg)
    return gallery_id in pins


def list_items(query: str = "") -> list[dict]:
    """All downloaded galleries with metadata (unsorted)."""
    ids = downloaded_ids()
    md, inf, _ = config.effective_dirs()
    if not md or not inf:
        return []
    pins = pinned_ids()
    items = []
    for gid in ids:
        json_path = inf / f"{gid}.json"
        meta = _load_meta(json_path) if json_path.exists() else None
        cbz = md / f"{gid}.cbz"
        m = meta or {}
        languages = m.get("languages") or ([m["language"].lower()] if m.get("language") else [])
        items.append({
            "id": gid,
            "title": m.get("title", f"#{gid}"),
            "media_id": m.get("media_id"),
            "num_pages": m.get("count", 0),
            "language": m.get("language", ""),
            "languages": languages,
            "artist": m.get("artist", []),
            "group": m.get("group", []),
            "parody": m.get("parody", []),
            "characters": m.get("characters", []),
            "tags": [{"name": t, "type": "tag"} for t in m.get("tags", [])],
            "favorites": m.get("favorites", 0),
            "date": m.get("date", ""),
            "mtime": cbz.stat().st_mtime,
            "pinned": gid in pins,
        })
    return items


# tag types aggregated for the local tag section, in display order
TAG_FIELDS = (
    ("tag", "tags"), ("artist", "artist"), ("group", "group"),
    ("parody", "parody"), ("character", "characters"), ("language", "languages"),
)


def _item_tag_names(it: dict, field: str) -> list[str]:
    vals = it.get(field, [])
    return [t["name"] if isinstance(t, dict) else t for t in vals]


def list_tags() -> list[dict]:
    """Aggregate every tag across the library with a count of galleries."""
    counts: dict[tuple, int] = {}
    for it in list_items():
        for tag_type, field in TAG_FIELDS:
            for name in _item_tag_names(it, field):
                if name:
                    counts[(tag_type, name.lower())] = counts.get((tag_type, name.lower()), 0) + 1
    out = [{"type": t, "name": n, "count": c} for (t, n), c in counts.items()]
    out.sort(key=lambda x: (-x["count"], x["name"]))
    return out


def _has_tag(it: dict, tag_name: str) -> bool:
    target = tag_name.lower()
    for _type, field in TAG_FIELDS:
        if any(n.lower() == target for n in _item_tag_names(it, field)):
            return True
    return False


# search field -> item key (supports nhentai-style artist:/tag:/parody:/etc.)
_QUERY_FIELDS = {
    "artist": "artist", "artists": "artist",
    "group": "group", "groups": "group", "circle": "group",
    "parody": "parody", "parodies": "parody", "series": "parody",
    "character": "characters", "characters": "characters", "char": "characters",
    "tag": "tags", "tags": "tags",
    "language": "languages", "lang": "languages",
}
# quote-aware token splitter: keeps `tag:"big breasts"` as one token
_QUERY_SPLIT = re.compile(r'\S*"[^"]*"\S*|\S+')


def _split_commas(q: str) -> list[str]:
    """Split on commas outside quotes."""
    parts = []
    buf = []
    quoted = False
    for ch in q:
        if ch == '"':
            quoted = not quoted
            buf.append(ch)
        elif ch == "," and not quoted:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
    part = "".join(buf).strip()
    if part:
        parts.append(part)
    return parts


def _parse_term(raw: str):
    raw = raw.strip()
    if not raw:
        return None
    neg = len(raw) > 1 and raw[0] == "-" and not raw.endswith("-")
    t = raw[1:].strip() if neg else raw
    field = None
    fm = re.match(r"(\w+):(.*)$", t)
    if fm:
        field = fm.group(1).lower()
        t = fm.group(2)
    val = t.replace('"', "").strip().lower()
    if not val:
        return None
    return neg, field, val


def _parse_query(q: str):
    """Parse nhentai-style query into (negated, field, value) terms.

    Commas are phrase-safe AND separators: `females only, yuri` searches for
    the phrase "females only" plus "yuri". Without commas, the older
    whitespace token behavior is preserved for title searches like
    `Greatest Father 4`.

    A leading '-' means negation ONLY when the token doesn't also end with '-',
    so hyphenated names like "Tou -Ni- Kengen" aren't mistaken for exclusions.
    """
    q = (q or "").strip()
    comma_parts = _split_commas(q)
    if len(comma_parts) > 1:
        return [term for part in comma_parts if (term := _parse_term(part))]

    terms = []
    for raw in _QUERY_SPLIT.findall(q):
        term = _parse_term(raw.rstrip(","))
        if term:
            terms.append(term)
    return terms


def _hay(it) -> str:
    return " ".join([
        it["title"], it.get("language", ""),
        " ".join(it.get("artist", [])), " ".join(it.get("group", [])),
        " ".join(it.get("parody", [])), " ".join(it.get("characters", [])),
        " ".join(it.get("languages", [])),
        " ".join(t["name"] for t in it.get("tags", [])),
    ]).lower()


def _term_match(it, field, val) -> bool:
    numeric = val.lstrip("#")
    if numeric.isdigit() and len(numeric) >= 5:
        if field in (None, "id", "gid", "gallery", "gallery_id"):
            return int(numeric) == int(it.get("id", -1))
        if field == "media_id":
            media_id = it.get("media_id")
            return media_id is not None and int(numeric) == int(media_id)
    if field and field in _QUERY_FIELDS:
        names = _item_tag_names(it, _QUERY_FIELDS[field])
        return any(val in n.lower() for n in names)
    return val in _hay(it)  # unknown field or bareword -> match anywhere


def _matches(it, q) -> bool:
    for neg, field, val in _parse_query(q):
        hit = _term_match(it, field, val)
        if neg and hit:
            return False
        if not neg and not hit:
            return False
    return True


def _sort_items(items: list[dict], sort: str) -> list[dict]:
    if sort == "title":
        items.sort(key=lambda it: it["title"].casefold())
    elif sort == "pages":
        items.sort(key=lambda it: it["num_pages"], reverse=True)
    elif sort == "date":
        items.sort(key=lambda it: it.get("date", ""), reverse=True)
    elif sort == "artist":
        items.sort(key=lambda it: ((it["artist"] or it.get("group") or [""])[0].casefold(),
                                   it["title"].casefold()))
    elif sort == "favorites":
        items.sort(key=lambda it: it.get("favorites", 0), reverse=True)
    elif sort == "random":
        random.shuffle(items)
    else:  # "added"
        items.sort(key=lambda it: it["mtime"], reverse=True)
    return items


def list_library(query: str = "", sort: str = "added", tag: str = "") -> list[dict]:
    """Downloaded galleries, filtered and sorted."""
    items = list_items()
    tag = (tag or "").strip()
    if tag:
        items = [it for it in items if _has_tag(it, tag)]
    q = query.strip().lower()
    if q:
        items = [it for it in items if _matches(it, q)]
    items = _sort_items(items, sort)
    items.sort(key=lambda it: not it.get("pinned"))  # stable: pinned to the front
    return items


def get_meta(gallery_id: int) -> dict | None:
    inf = info_dir()
    if not inf:
        return None
    json_path = inf / f"{gallery_id}.json"
    if not json_path.exists():
        return None
    return _load_meta(json_path)


def _cbz_path(gallery_id: int) -> Path | None:
    md = manga_dir()
    return (md / f"{gallery_id}.cbz") if md else None


def list_pages(gallery_id: int) -> list[str]:
    path = _cbz_path(gallery_id)
    if not path or not path.exists():
        return []
    with zipfile.ZipFile(path) as zf:
        return sorted(n for n in zf.namelist() if not n.endswith("/"))


def read_page(gallery_id: int, name: str) -> bytes | None:
    path = _cbz_path(gallery_id)
    if not path or not path.exists():
        return None
    with zipfile.ZipFile(path) as zf:
        if name not in zf.namelist():
            return None
        return zf.read(name)


# ---------- relocate / migrate download folder ----------

def set_location(new_root: str, migrate: bool) -> dict:
    """Point the download location at <new_root>. If migrate, move existing
    CBZ + JSON files from the old location into the new one."""
    new_root = (new_root or "").strip()
    if not new_root:
        raise ValueError("download location cannot be empty")

    old_md, old_inf, _ = config.effective_dirs()
    base = Path(new_root)
    new_md = base / "manga" / "nhentai"
    new_inf = base / "info" / "nhentai"
    new_md.mkdir(parents=True, exist_ok=True)
    new_inf.mkdir(parents=True, exist_ok=True)

    moved = 0
    if migrate and old_md and old_inf and old_md.exists():
        old_md = old_md.resolve()
        old_inf = old_inf.resolve()
        if old_md != new_md.resolve():
            for src_dir, dst_dir, pat in ((old_md, new_md, "*.cbz"),
                                          (old_inf, new_inf, "*.json")):
                if not src_dir.exists():
                    continue
                for f in src_dir.glob(pat):
                    dst = dst_dir / f.name
                    if dst.exists():
                        continue  # never clobber
                    shutil.move(str(f), str(dst))
                    moved += 1

    cfg = config.load()
    cfg["download_root"] = str(base)
    # clear legacy explicit paths so download_root is authoritative
    cfg["manga_dir"] = ""
    cfg["info_dir"] = ""
    config.save(cfg)

    with _cache_lock:
        _meta_cache.clear()
        _meta_mtimes.clear()

    return {"root": str(base), "manga_dir": str(new_md), "info_dir": str(new_inf),
            "moved": moved, "migrated": migrate}
