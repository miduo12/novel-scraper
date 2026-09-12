# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path.cwd().resolve()
icon_path = root / "src" / "novel_scraper" / "resources" / "app.ico"
resources_path = root / "src" / "novel_scraper" / "resources"

EXCLUDED_BINARY_DLLS = {"icuuc.dll", "icudt78.dll"}

a = Analysis(
    [str(root / "packaging" / "launcher.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(resources_path), "novel_scraper/resources")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtQml",
        "PySide6.QtQuick",
    ],
    noarchive=False,
)
a.binaries = [item for item in a.binaries if Path(item[0]).name.lower() not in EXCLUDED_BINARY_DLLS]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="NovelScraper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)
