# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


ROOT = Path(SPECPATH).parents[1]

analysis = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT), str(ROOT / "backend")],
    binaries=[],
    datas=[
        (str(ROOT / "frontend" / "dist"), "frontend/dist"),
        (str(ROOT / "scripts" / "danbooru_gallery_dl.py"), "scripts"),
        (str(ROOT / "scripts" / "windows_folder_picker.py"), "scripts"),
        (str(ROOT / "config.json"), "."),
    ],
    hiddenimports=["server"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["gallery_dl", "imageio_ffmpeg"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Keivotos",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=str(ROOT / "packaging" / "windows" / "assets" / "keivotos.ico"),
    version=str(ROOT / "packaging" / "windows" / "version_info.txt"),
)
collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Keivotos",
)
