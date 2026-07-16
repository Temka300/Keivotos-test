# Building the Windows portable distribution

Keivotos uses a PyInstaller one-folder build. One-folder is intentional: the web
assets and separately licensed command-line tools remain visible, replaceable,
and easier to inspect than they would be in a single self-extracting binary.

## Build

Install uv and Node.js, then run from the repository root:

```powershell
.\scripts\release\build_windows.ps1 -Version "1.0.0"
```

The script:

1. synchronizes the locked Python environment;
2. installs, checks, and builds the locked frontend;
3. regenerates committed Keivotos brand derivatives;
4. builds `Keivotos.exe` and a separate `gallery-dl.exe`;
5. places a separate `ffmpeg.exe` beside the application;
6. collects project and dependency notices;
7. runs version/resource checks for every executable; and
8. writes a ZIP plus SHA-256 checksum under `artifacts/`.

Build and work directories are cleaned only after the script verifies they are
inside this repository. User data under `Documents\Keivotos` is never packaged.

## GitHub workflow

The manual **Package Windows** workflow runs the same script on a clean Windows
runner and uploads the ZIP/checksum as a workflow artifact. It does not create a
GitHub Release, change tags, or deploy an update feed.

## Redistribution

Keep the complete output folder together, including `LICENSE`, `NOTICE`,
`THIRD_PARTY_NOTICES.md`, `licenses/`, `gallery-dl.exe`, `ffmpeg.exe`, and the
FFmpeg source-availability notice. Review the exact bundled dependency licenses
before publishing; this documentation is engineering guidance, not legal advice.
