# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# Collect all PySide6 data (QtWebEngine resources, locales, translations).
pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all("PySide6")

# Resolve paths relative to this spec file so the build works anywhere.
# SPECPATH is the absolute path of the spec file itself.
PROJECT = Path(SPECPATH).resolve().parent
if not (PROJECT / "run.py").exists():
    PROJECT = Path(os.getcwd()).resolve()

ASSETS = PROJECT / "assets"
LISTS = PROJECT / "pri" / "privacy" / "lists"
JS = PROJECT / "pri" / "js"

a = Analysis(
    [str(PROJECT / "run.py")],
    pathex=[str(PROJECT)],
    datas=[
        (str(ASSETS), "assets"),
        (str(LISTS), "pri/privacy/lists"),
        (str(JS), "pri/js"),
    ] + pyside6_datas,
    binaries=pyside6_binaries,
    hiddenimports=[
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebChannel",
        "PySide6.QtPdf",
        "pri",
        "pri.app",
        "pri.browser",
        "pri.page",
        "pri.config",
        "pri.paths",
        "pri.privacy",
        "pri.privacy.interceptor",
        "pri.privacy.rules",
        "pri.privacy.urlclean",
        "pri.privacy.report",
        "pri.ui",
        "pri.ui.theme",
    ] + pyside6_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy"],
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
    name="Pri-Yandex",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS / "logo.ico") if (ASSETS / "logo.ico").exists() else None,
)
