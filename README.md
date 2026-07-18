# Keivotos

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Keivotos is a local-first library for exploring, organizing, and rediscovering the files you already own. Instead of opening unrelated folders and applications to find your images, manga, videos, music, documents, social-media archives, and other saved content, Keivotos aims to bring them together in one searchable interface. Your original files remain in their existing folders. Keivotos indexes them in place and presents useful information such as titles, tags, creators, dates, relationships, collections, and available metadata or you can add your own.

## Supported platforms

| Platform | Status |
|---|---|
| Windows | ✅ |
| Linux / macOS | untested, source may run |

## Getting started

### Portable build (Windows)

1. Extract the whole release folder. Don't run the exe from inside the ZIP.
2. Start `Keivotos.exe`.
3. Your browser opens at <http://localhost:52325/>.

Keep the console window open — closing it stops the app. If you downloaded a release with a `.sha256` file next to it, you can use it to verify the ZIP.

### From source

Install [uv](https://docs.astral.sh/uv/) and a current Node.js LTS, then:

```powershell
.\run.bat
```

The launcher sets up Python 3.11 from `uv.lock`, builds the frontend if needed, and starts the server. Manual commands and dev mode are in [docs/build/source.md](docs/build/source.md).

### First steps in the app

1. Open Settings → Library and register a folder that contains your booru images.
2. Let the import finish. Files are indexed where they are, nothing is copied.

## Features

- [x] Booru
- [ ] Add 3D model viewer
- [ ] Add Images, pdf other filetypes related formats
- [ ] Add android photos
- [ ] Add Iphone photos
- [ ] Add Midis player
- [ ] Add manga reading
- [ ] Add anime/video playback
- [ ] Add EPUB novel reader
- [ ] Add PDF reader
- [ ] Add Web archive
- [ ] Add Youtube Videos
- [ ] Add Pixiv
- [ ] Add Reddit
- [ ] Add Twitter
- [ ] Add OST, music player


## Where your data lives

The application folder is disposable; your data is not. Everything Keivotos writes goes to `%LOCALAPPDATA%\Keivotos`:

Upgrading means replacing the application folder — your library state stays put. Registered media folders are indexed in place and can live anywhere; if you move one, Settings → Library → Relocate reconnects it. Details in [docs/user/data-layout.md](docs/user/data-layout.md).

## Troubleshooting

See [docs/user/troubleshooting.md](docs/user/troubleshooting.md) and [docs/user/installation.md](docs/user/installation.md). Logs are in `%LOCALAPPDATA%\Keivotos\logs`.

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

Apache-2.0 — see [LICENSE](LICENSE). Portable builds bundle gallery-dl and FFmpeg as separate GPL-licensed executables; their license texts ship in the `licenses/` folder of each release, with details in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
