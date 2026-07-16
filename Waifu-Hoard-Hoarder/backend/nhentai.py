"""nhentai.net official v2 API client (curl_cffi TLS impersonation).

The legacy /api/gallery endpoints are deprecated and sit behind a Cloudflare JS
challenge (403). The official v2 REST API (nhentai.net/api/v2/...) is public and
works without any cookie -- it only wants a descriptive User-Agent. Image CDN
hosts (i*/t*.nhentai.net) are likewise open.

v2 gallery objects differ from v1:
  cover/pages carry a full `path` like "galleries/<media_id>/1.webp".
  search/related results are slim and carry `tag_ids` instead of full tags,
  so we batch-resolve ids to tag objects (cached) for language + blacklist.
"""
import datetime
import threading
import time
from curl_cffi import requests

import config

API_BASE = "https://nhentai.net/api/v2"
IMPERSONATE = "chrome136"
DEFAULT_UA = "Waifu-Hoard-Hoarder/1.0 (personal local archive tool)"

# CDN fallback hosts (also fetched live from /api/v2/cdn and cached)
IMAGE_HOSTS = ["i1", "i2", "i3", "i4", "i5", "i7"]
THUMB_HOSTS = ["t1", "t2", "t3", "t4", "t5", "t7"]

LANG_CODE = {"english": "en", "japanese": "ja", "chinese": "zh"}
# language/category pseudo-tags that aren't real "languages"
_NON_LANG = {"translated", "rewrite", "speechless", "text cleaned"}

_tag_cache: dict[int, dict] = {}
_tag_lock = threading.Lock()

# per-thread keep-alive session (curl_cffi sessions are not thread-safe to share)
_local = threading.local()

# short-lived response cache so back/forward navigation is instant
_resp_cache: dict[tuple, tuple[float, dict]] = {}
_resp_lock = threading.Lock()


def _session():
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session(impersonate=IMPERSONATE)
        _local.session = s
    return s


class CloudflareBlocked(Exception):
    pass


class NotFound(Exception):
    pass


def _headers():
    cfg = config.load()
    ua = cfg.get("user_agent") or DEFAULT_UA
    return {"User-Agent": ua, "Accept": "application/json"}


def _cookies():
    cfg = config.load()
    ck = {}
    if cfg.get("cf_clearance"):
        ck["cf_clearance"] = cfg["cf_clearance"]
    if cfg.get("csrftoken"):
        ck["csrftoken"] = cfg["csrftoken"]
    return ck


def _get(path: str, params: dict | None = None) -> dict:
    r = _session().get(
        f"{API_BASE}{path}",
        params=params,
        headers=_headers(),
        cookies=_cookies(),
        timeout=20,
    )
    if r.status_code == 403:
        raise CloudflareBlocked(
            "nhentai API returned 403 (Cloudflare). The v2 API is normally open; "
            "your IP may be rate-limited or challenged. Try again shortly."
        )
    if r.status_code == 404:
        raise NotFound(path)
    r.raise_for_status()
    return r.json()


def _cached_get(path: str, params: dict | None = None, ttl: float = 120.0) -> dict:
    key = (path, tuple(sorted((params or {}).items())))
    now = time.time()
    with _resp_lock:
        hit = _resp_cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    data = _get(path, params)
    with _resp_lock:
        _resp_cache[key] = (now + ttl, data)
        if len(_resp_cache) > 400:  # keep the cache from growing unbounded
            for k in [k for k, v in _resp_cache.items() if v[0] <= now]:
                _resp_cache.pop(k, None)
    return data


# ---------- tag id resolution ----------

def resolve_tags(ids: list[int]) -> dict[int, dict]:
    ids = [int(i) for i in ids]
    with _tag_lock:
        missing = [i for i in ids if i not in _tag_cache]
    if missing:
        # batch in chunks to keep URLs sane
        for start in range(0, len(missing), 100):
            chunk = missing[start:start + 100]
            try:
                data = _get("/tags/ids", {"ids": ",".join(map(str, chunk))})
            except Exception:
                continue
            with _tag_lock:
                for t in data:
                    _tag_cache[int(t["id"])] = t
    with _tag_lock:
        return {i: _tag_cache[i] for i in ids if i in _tag_cache}


# ---------- API calls ----------

def get_gallery(gallery_id: int) -> dict:
    return _cached_get(f"/galleries/{gallery_id}", ttl=600)


def get_related(gallery_id: int) -> dict:
    return _cached_get(f"/galleries/{gallery_id}/related", ttl=600)


def search(query: str, page: int = 1, sort: str = "") -> dict:
    query = (query or "").strip()
    if not query:
        # /galleries ignores sort, so popular feeds must go through /search with a
        # catch-all query. "Recent" (empty/date sort) uses the real new-uploads feed.
        if sort and sort != "date":
            return _cached_get("/search", {"query": "pages:>0", "sort": sort, "page": page}, ttl=120)
        return browse_all(page)
    params = {"query": query, "page": page}
    if sort:
        params["sort"] = sort
    return _cached_get("/search", params, ttl=120)


def browse_all(page: int = 1) -> dict:
    return _cached_get("/galleries", {"page": page, "per_page": 25}, ttl=120)


def get_tags(tag_type: str, page: int = 1) -> dict:
    # default order is by gallery count (most popular first)
    return _cached_get(f"/tags/{tag_type}", {"page": page}, ttl=3600)


# ---------- images ----------

def fetch_image(path: str, hosts: list[str], referer: str = "https://nhentai.net/") -> tuple[bytes, str]:
    """Fetch image given a CDN path like 'galleries/<id>/1.webp'. Tries mirrors."""
    path = path.lstrip("/")
    headers = {"User-Agent": _headers()["User-Agent"], "Referer": referer}
    last_err = None
    for host in hosts:
        url = f"https://{host}.nhentai.net/{path}"
        try:
            r = _session().get(url, headers=headers, timeout=30)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                return r.content, r.headers["content-type"]
            last_err = f"HTTP {r.status_code} from {host}"
        except Exception as e:
            last_err = f"{host}: {e}"
        time.sleep(0.15)
    raise IOError(f"all image hosts failed for {path}: {last_err}")


def cover_path(media_id, ext: str) -> str:
    return f"galleries/{media_id}/cover.{ext}"


def thumb_path(media_id, page: int, ext: str) -> str:
    return f"galleries/{media_id}/{page}t.{ext}"


def page_path(media_id, page: int, ext: str) -> str:
    return f"galleries/{media_id}/{page}.{ext}"


def _ext_from_path(p: str) -> str:
    return p.rsplit(".", 1)[-1] if "." in p else "webp"


# ---------- shaping ----------

def _tag_names(gallery: dict, tag_type: str) -> list[str]:
    return [t["name"] for t in gallery.get("tags", []) if t.get("type") == tag_type]


def _language_of(tags: list[dict]) -> str:
    for t in tags:
        if t.get("type") == "language" and t.get("name") not in _NON_LANG:
            return t["name"]
    return ""


def build_metadata(gallery: dict) -> dict:
    """Sidecar metadata matching the existing gallery-dl info JSON format."""
    title = gallery.get("title", {})
    title_en = title.get("english") or title.get("pretty") or ""
    title_ja = title.get("japanese") or ""

    lang_name = _language_of(gallery.get("tags", []))
    types = _tag_names(gallery, "category")
    date = datetime.datetime.fromtimestamp(
        gallery.get("upload_date", 0), datetime.timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "title": title_en or title_ja,
        "title_en": title_en,
        "title_ja": title_ja,
        "gallery_id": int(gallery["id"]),
        "media_id": int(gallery["media_id"]),
        "date": date,
        "scanlator": gallery.get("scanlator", ""),
        "artist": _tag_names(gallery, "artist"),
        "group": _tag_names(gallery, "group"),
        "parody": _tag_names(gallery, "parody"),
        "characters": _tag_names(gallery, "character"),
        "tags": _tag_names(gallery, "tag"),
        "type": types[0] if types else "",
        "lang": LANG_CODE.get(lang_name, lang_name[:2] if lang_name else ""),
        "language": lang_name.capitalize() if lang_name else "",
        "languages": _tag_names(gallery, "language"),
        "count": gallery.get("num_pages", len(gallery.get("pages", []))),
        "favorites": gallery.get("num_favorites", 0),
        "category": "nhentai",
        "subcategory": "gallery",
    }


def _page_thumb(page: dict, media_id) -> str:
    # prefer the API-supplied thumbnail path; fall back to derived
    t = page.get("thumbnail")
    if t:
        return t
    p = page.get("path", "")
    if "/" in p and "." in p.rsplit("/", 1)[-1]:
        head, name = p.rsplit("/", 1)
        stem, ext = name.split(".", 1)
        return f"{head}/{stem}t.{ext}"
    return p


def slim_full(gallery: dict) -> dict:
    """Trim a full v2 gallery object for the detail view.

    Image fields carry the *real* CDN path strings (e.g.
    "galleries/<id>/cover.jpg.webp") rather than a reconstructed ext, because
    nhentai uses double extensions like `.jpg.webp` that can't be rebuilt.
    """
    title = gallery.get("title", {})
    tags = gallery.get("tags", [])
    cover = gallery.get("cover", {})
    pages = gallery.get("pages", [])
    media_id = gallery["media_id"]
    return {
        "id": int(gallery["id"]),
        "media_id": int(media_id),
        "title": title.get("english") or title.get("pretty") or title.get("japanese") or "",
        "title_ja": title.get("japanese") or "",
        "cover": cover.get("path", ""),
        "num_pages": gallery.get("num_pages", len(pages)),
        "language": _language_of(tags),
        "languages": [t["name"] for t in tags if t.get("type") == "language"],
        "tags": [{"name": t["name"], "type": t["type"]} for t in tags],
        "pages": [p.get("path", "") for p in pages],
        "page_thumbs": [_page_thumb(p, media_id) for p in pages],
        "upload_date": gallery.get("upload_date", 0),
        "favorites": gallery.get("num_favorites", 0),
        "scanlator": gallery.get("scanlator", ""),
    }


def slim_result(item: dict, tag_map: dict[int, dict]) -> dict:
    """Trim a slim v2 search/related item for grid cards (enriched via tag_map)."""
    tags = [tag_map[i] for i in item.get("tag_ids", []) if i in tag_map]
    return {
        "id": int(item["id"]),
        "media_id": int(item["media_id"]),
        "title": item.get("english_title") or item.get("japanese_title") or "",
        "title_ja": item.get("japanese_title") or "",
        "thumb": item.get("thumbnail", ""),  # real cover-thumbnail path
        "num_pages": item.get("num_pages", 0),
        "language": _language_of(tags),
        "languages": [t["name"] for t in tags if t.get("type") == "language"],
        "tags": [{"name": t["name"], "type": t["type"]} for t in tags],
        "upload_date": item.get("upload_date", 0),
    }


def shape_results(items: list[dict]) -> list[dict]:
    """Resolve tag ids across a page of slim items, then shape each."""
    all_ids = {i for it in items for i in it.get("tag_ids", [])}
    tag_map = resolve_tags(list(all_ids)) if all_ids else {}
    return [slim_result(it, tag_map) for it in items]
