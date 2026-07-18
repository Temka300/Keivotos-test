# Keivotos

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

A local gallery for your own image and video collection. Keivotos ships with
**Waifu-Hoard**, a Danbooru-style browser for files that already live on your
disk. No account, no cloud, no upload — point it at your folders and browse.

## Why Keivotos?

Booru sites are great for finding art but terrible for keeping it. Once you
save files locally you lose the tags, the search, and the related-post links.
Waifu-Hoard puts that back: it indexes your folders in place, matches files
against Danbooru by MD5 to recover their tags and metadata, and gives you the
familiar tag search, ratings, and parent/child navigation over your own copy.
Your originals are never moved or modified.

## Supported platforms

| Platform | Status |
|---|---|
| Windows 10 / 11 (portable build) | ✅ |
| Windows (from source) | ✅ |
| Linux / macOS | untested, source may run |

## Getting started

### Portable build (Windows)

1. Extract the whole release folder. Don't run the exe from inside the ZIP.
2. Start `Keivotos.exe`.
3. Your browser opens at <http://localhost:52325/>.

Keep the console window open — closing it stops the app. If you downloaded a
release with a `.sha256` file next to it, you can use it to verify the ZIP.

### From source

Install [uv](https://docs.astral.sh/uv/) and a current Node.js LTS, then:

```powershell
.\run.bat
```

The launcher sets up Python 3.11 from `uv.lock`, builds the frontend if
needed, and starts the server. Manual commands and dev mode are in
[docs/build/source.md](docs/build/source.md).

### First steps in the app

1. Open Settings → Library and register a folder that contains your images.
2. Let the import finish. Files are indexed where they are, nothing is copied.
3. Optional: add your Danbooru username and API key in Settings to raise the
   metadata-matching rate limits. The key is stored encrypted with Windows
   DPAPI, outside the app folder.

## Features

- [x] Tag search with Danbooru syntax: categories, ratings, `-exclusions`,
      resolution and date filters, filename search
- [x] Favorites, pinned items, collections, and your own custom tags
- [x] Metadata backfill by MD5 lookup, stored as sidecar files that survive
      database rebuilds
- [x] Parent / child / sibling post navigation, tag wikis, artist pages
- [x] Duplicate finder, popularity views, timelapse, daily challenges
- [x] Downloads through [gallery-dl](https://github.com/mikf/gallery-dl)
      (user-triggered, with your own credentials)
- [x] Verified backups (`.keivotosbk`) and automatic local recovery
      checkpoints for the data you can't regenerate
- [ ] More modules (manga, music, video archives) — see
      [docs/project-direction.md](docs/project-direction.md)

## Where your data lives

The application folder is disposable; your data is not. Everything Keivotos
writes goes to `%LOCALAPPDATA%\Keivotos`:

```text
%LOCALAPPDATA%/Keivotos/
├── config.json                # your settings
├── logs/
├── modules/waifu-hoard/
│   ├── library/               # default download folder
│   ├── danbooru.sqlite        # search index (rebuildable)
│   ├── user.sqlite            # favorites, collections, tags (back this up!)
│   ├── sidecars/              # per-file metadata
│   ├── thumbnails/            # cache
│   ├── local_recovery/        # automatic checkpoints
│   └── gallery-dl/            # download work files
└── backups/waifu-hoard/       # manual .keivotosbk bundles
```

Upgrading means replacing the application folder — your library state stays
put. Registered media folders are indexed in place and can live anywhere; if
you move one, Settings → Library → Relocate reconnects it. Details in
[docs/user/data-layout.md](docs/user/data-layout.md).

## Troubleshooting

See [docs/user/troubleshooting.md](docs/user/troubleshooting.md) and
[docs/user/installation.md](docs/user/installation.md). Logs are in
`%LOCALAPPDATA%\Keivotos\logs`.

## Building and testing

```powershell
uv sync --locked --python 3.11
uv run python -m unittest discover -s tests -v

cd frontend
npm.cmd ci
npm.cmd run check
npm.cmd run build
```

Windows packaging is documented in [docs/build/windows.md](docs/build/windows.md).

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md). Security reports:
[SECURITY.md](.github/SECURITY.md). Questions and support:
[SUPPORT.md](.github/SUPPORT.md).

## License

Apache-2.0 — see [LICENSE](LICENSE). Portable builds bundle gallery-dl and
FFmpeg as separate GPL-licensed executables; their license texts ship in the
`licenses/` folder of each release, with details in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
