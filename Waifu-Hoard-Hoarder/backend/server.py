"""Waifu-Hoard-Hoarder FastAPI server: nhentai browser, downloader, library."""
import mimetypes
import os
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import downloader
import library
import nhentai
import series

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "frontend" / "static"

app = FastAPI(title="Waifu-Hoard-Hoarder")

mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/avif", ".avif")

IMG_CACHE_HEADERS = {"Cache-Control": "public, max-age=604800"}


def _cf_error(e: Exception) -> JSONResponse:
    return JSONResponse(status_code=502, content={"error": "cloudflare", "detail": str(e)})


# ---------- browse / search ----------

@app.get("/api/search")
def api_search(query: str = "", page: int = 1, sort: str = ""):
    try:
        data = nhentai.search(query, page, sort)
    except nhentai.CloudflareBlocked as e:
        return _cf_error(e)
    except nhentai.NotFound:
        return {"result": [], "num_pages": 0, "page": page}
    downloaded = library.downloaded_ids()
    result = nhentai.shape_results(data.get("result", []))
    for slim in result:
        slim["downloaded"] = slim["id"] in downloaded
    return {"result": result, "num_pages": data.get("num_pages", 1),
            "total": data.get("total"), "page": page}


@app.get("/api/gallery/{gallery_id}")
def api_gallery(gallery_id: int):
    try:
        g = nhentai.get_gallery(gallery_id)
    except nhentai.CloudflareBlocked as e:
        return _cf_error(e)
    except nhentai.NotFound:
        raise HTTPException(404, "gallery not found")
    slim = nhentai.slim_full(g)
    slim["downloaded"] = gallery_id in library.downloaded_ids()
    return slim


@app.get("/api/related/{gallery_id}")
def api_related(gallery_id: int):
    try:
        data = nhentai.get_related(gallery_id)
    except nhentai.CloudflareBlocked as e:
        return _cf_error(e)
    except nhentai.NotFound:
        return {"result": []}
    downloaded = library.downloaded_ids()
    result = nhentai.shape_results(data.get("result", []))
    for slim in result:
        slim["downloaded"] = slim["id"] in downloaded
    return {"result": result}


@app.get("/api/status")
def api_status():
    try:
        nhentai.browse_all(1)
        return {"api_ok": True}
    except nhentai.CloudflareBlocked:
        return {"api_ok": False, "reason": "cloudflare"}
    except Exception as e:
        return {"api_ok": False, "reason": str(e)}


# ---------- image proxy ----------

def _proxy_image(path: str, hosts: list[str]) -> Response:
    try:
        data, ctype = nhentai.fetch_image(path, hosts)
    except Exception as e:
        raise HTTPException(502, f"image fetch failed: {e}")
    return Response(content=data, media_type=ctype, headers=IMG_CACHE_HEADERS)


# thumb/cover hosts (t*) and full-image hosts (i*); `path` is the real CDN path,
# e.g. "galleries/3981968/cover.jpg.webp"
@app.get("/img/t/{path:path}")
def img_thumb(path: str):
    return _proxy_image(path, nhentai.THUMB_HOSTS)


@app.get("/img/i/{path:path}")
def img_full(path: str):
    return _proxy_image(path, nhentai.IMAGE_HOSTS)


# ---------- downloads ----------

@app.post("/api/download/{gallery_id}")
def api_download(gallery_id: int, title: str = ""):
    if gallery_id in library.downloaded_ids():
        return {"status": "already_downloaded"}
    job = downloader.enqueue(gallery_id, title)
    return job.to_dict()


@app.post("/api/download/{gallery_id}/cancel")
def api_download_cancel(gallery_id: int):
    return {"cancelled": downloader.cancel(gallery_id)}


@app.get("/api/downloads")
def api_downloads():
    return {"jobs": downloader.list_jobs()}


@app.post("/api/downloads/clear-finished")
def api_downloads_clear():
    downloader.clear_finished()
    return {"ok": True}


# ---------- library ----------

@app.get("/api/library")
def api_library(query: str = "", sort: str = "added", tag: str = ""):
    return {"result": library.list_library(query, sort, tag)}


@app.get("/api/library/grouped")
def api_library_grouped(query: str = "", group: bool = True,
                        sort: str = "added", tag: str = ""):
    items = library.list_library(query, sort, tag)
    return {"entries": series.build_entries(items, group)}


@app.get("/api/library/tags")
def api_library_tags():
    return {"result": library.list_tags()}


TAG_TYPES = {"tag", "artist", "group", "parody", "character", "language", "category"}


@app.get("/api/tags/{tag_type}")
def api_tags(tag_type: str, page: int = 1):
    if tag_type not in TAG_TYPES:
        raise HTTPException(404, "unknown tag type")
    try:
        data = nhentai.get_tags(tag_type, page)
    except nhentai.CloudflareBlocked as e:
        return _cf_error(e)
    result = [{"name": t["name"], "count": t.get("count", 0), "type": t.get("type", tag_type)}
              for t in data.get("result", [])]
    return {"result": result, "num_pages": data.get("num_pages", 1), "page": page}


@app.get("/api/library/{gallery_id}/pages")
def api_library_pages(gallery_id: int):
    pages = library.list_pages(gallery_id)
    if not pages:
        raise HTTPException(404, "not downloaded")
    return {"pages": pages, "meta": library.get_meta(gallery_id)}


@app.get("/api/library/{gallery_id}/cover")
def api_library_cover(gallery_id: int):
    pages = library.list_pages(gallery_id)
    if not pages:
        raise HTTPException(404, "not downloaded")
    data = library.read_page(gallery_id, pages[0])
    ctype = mimetypes.guess_type(pages[0])[0] or "application/octet-stream"
    return Response(content=data, media_type=ctype, headers=IMG_CACHE_HEADERS)


@app.get("/api/library/{gallery_id}/page/{name}")
def api_library_page(gallery_id: int, name: str):
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "bad page name")
    data = library.read_page(gallery_id, name)
    if data is None:
        raise HTTPException(404, "page not found")
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return Response(content=data, media_type=ctype, headers=IMG_CACHE_HEADERS)


class Pin(BaseModel):
    on: bool


@app.post("/api/library/{gallery_id}/pin")
def api_pin(gallery_id: int, p: Pin):
    return {"pinned": library.set_pinned(gallery_id, p.on)}


@app.post("/api/library/{gallery_id}/open-folder")
def api_open_folder(gallery_id: int):
    cbz = library.manga_dir() / f"{gallery_id}.cbz"
    if not cbz.exists():
        raise HTTPException(404, "not downloaded")
    subprocess.Popen(["explorer", "/select,", str(cbz)])
    return {"ok": True}


# ---------- settings ----------

class Settings(BaseModel):
    user_agent: str | None = None
    cf_clearance: str | None = None
    csrftoken: str | None = None
    blur_covers: bool | None = None
    blacklist_tags: list[str] | None = None
    private_search: bool | None = None
    hide_downloaded: bool | None = None


@app.get("/api/settings")
def api_settings_get():
    cfg = config.load()
    md, inf, root = config.effective_dirs(cfg)
    return {
        "user_agent": cfg.get("user_agent", ""),
        "cf_clearance": cfg.get("cf_clearance", ""),
        "csrftoken": cfg.get("csrftoken", ""),
        "blur_covers": cfg.get("blur_covers", True),
        "blacklist_tags": cfg.get("blacklist_tags", []),
        "private_search": cfg.get("private_search", False),
        "hide_downloaded": cfg.get("hide_downloaded", False),
        "download_root": root,
        "manga_dir": str(md) if md else "",
        "info_dir": str(inf) if inf else "",
        "location_set": bool(md),
    }


@app.post("/api/settings")
def api_settings_set(s: Settings):
    cfg = config.load()
    for field in ("user_agent", "cf_clearance", "csrftoken", "blur_covers", "blacklist_tags",
                  "private_search", "hide_downloaded"):
        value = getattr(s, field)
        if value is not None:
            cfg[field] = value
    config.save(cfg)
    return api_settings_get()


class Location(BaseModel):
    download_root: str
    migrate: bool = False


@app.post("/api/settings/location")
def api_settings_location(loc: Location):
    try:
        result = library.set_location(loc.download_root, loc.migrate)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"could not set location: {e}")
    return result


# ---------- frontend ----------

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
