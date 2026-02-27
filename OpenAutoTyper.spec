# OpenAutoTyper.spec
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

pyside_bins = collect_dynamic_libs("PySide6")
pyside_data = collect_data_files("PySide6")

a = Analysis(
    ["OpenAutoTyper.py"],
    pathex=[".", "appdata"],
    binaries=pyside_bins,
    datas=[("appdata/resources/images/icon.ico", "appdata/resources/images")] + pyside_data,
    hiddenimports=[],
    hookspath=["appdata/hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="OpenAutoTyper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="appdata/resources/images/icon.ico",
)
