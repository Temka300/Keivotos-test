# Waifu-Hoard-Hoarder

Local web app for browsing nhentai.net and hoarding galleries as `.cbz` + metadata `.json`,
matching the existing `E:\Archive\Manga_N` layout. Sibling project of Waifu-Hoard.

## Run

```
pip install -r requirements.txt
python app.py            # http://127.0.0.1:8113
python app.py --dev      # auto-reload
```

Port defaults to **8113** (set in `config.json`).

## No setup needed

This app uses nhentai's **official public v2 API** (`nhentai.net/api/v2/...`), which works with
no login and no Cloudflare cookie — just a descriptive User-Agent the app sends automatically.
Browsing, search, and downloads work out of the box.

(The legacy `/api/gallery` endpoint is deprecated and Cloudflare-blocked; this app does not use it.)

**Fallback:** if nhentai ever rate-limits or challenges your IP, **Settings** has optional
`cf_clearance` cookie + User-Agent override fields. Grab the cookie via DevTools (F12) →
Application → Cookies → `nhentai.net` → `cf_clearance`, and set the matching User-Agent.

## Features

- **Browse / search** with full nhentai query syntax (`tag:"fox girl" artist:x -yaoi pages:>20`),
  sort by newest / popular (today / week / all-time), pagination.
- **Gallery page**: full metadata, clickable tag chips (search by tag/artist/parody/character/
  group/language/category), page thumbnails, related items via API.
- **Download**: one click queues the gallery; a background worker fetches pages (4 in parallel,
  mirror-host fallback) and writes:
  - `manga_dir\<id>.cbz` — pages stored as `001.webp`, `002.webp`, …
  - `info_dir\<id>.json` — metadata sidecar in the same format gallery-dl produces.
  Already-downloaded galleries show a ✓ badge everywhere.
- **Queue tab**: live progress bars, cancel queued jobs, clear finished.
- **Library tab**: everything already downloaded (scanned from disk), filter box,
  open-in-Explorer button.
- **Reader**: built-in viewer for both local CBZs and online galleries
  (← → / Space / Esc, click left/right edges).
- **Cover blur**: covers blurred by default; eye button in the header toggles for the session,
  Settings → "Blur covers by default" controls the startup state.
- **Tag blacklist**: listed tags hide matching cards behind a click-to-reveal overlay.

## Config (`config.json`)

| key | meaning |
|-----|---------|
| `port` | server port (default 8113) |
| `manga_dir` | where `.cbz` files go (`E:\Archive\Manga_N\manga\nhentai`) |
| `info_dir` | where `.json` sidecars go (`E:\Archive\Manga_N\info\nhentai`) |
| `user_agent`, `cf_clearance`, `csrftoken` | Cloudflare bypass (set via Settings UI) |
| `blur_covers` | blur covers on startup |
| `blacklist_tags` | tags to hide behind overlay |

## Layout

- `app.py` — launcher
- `backend/server.py` — FastAPI routes (API proxy, image proxy, downloads, library, settings)
- `backend/nhentai.py` — nhentai API client (curl_cffi TLS impersonation)
- `backend/downloader.py` — download queue worker, CBZ/JSON writer
- `backend/library.py` — local collection scan + CBZ page serving
- `frontend/static/` — vanilla JS single-page UI
