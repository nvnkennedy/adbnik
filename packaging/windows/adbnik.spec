# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir bundle for Windows (used by packaging/windows/build.ps1 and CI)."""

import os

block_cipher = None

SPEC_DIR = os.path.abspath(os.path.dirname(SPEC))
PROJECT_ROOT = os.path.abspath(os.path.join(SPEC_DIR, "..", ".."))
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, "main.py")

from PyInstaller.utils.hooks import collect_all

# Pull Paramiko + crypto binaries; avoid collect_all(PyQt5) (pulls entire Qt tree).
datas = []
binaries = []
hiddenimports = []

for pkg in ("paramiko", "cryptography"):
    try:
        pkg_d, pkg_bin, pkg_hi = collect_all(pkg)
        datas += pkg_d
        binaries += pkg_bin
        hiddenimports += pkg_hi
    except Exception:
        pass

hiddenimports += [
    "PyQt5.sip",
    "serial",
]

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Adbnik",
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
    icon=os.path.join(PROJECT_ROOT, "branding", "favicon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Adbnik",
)
