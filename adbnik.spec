# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — run from the project root:
#   pip install -e ".[build]"
#   pyinstaller adbnik.spec
#
# Output: dist/Adbnik/Adbnik.exe (folder bundle — reliable for PyQt5).
# PyQt5 is picked up via PyInstaller hooks (avoid collect_all — it pulls all of Qt/QML).

import os

_spec_dir = os.path.dirname(os.path.abspath(SPEC))
_main = os.path.join(_spec_dir, "main.py")
_icon = os.path.join(_spec_dir, "assets", "adbnik.ico")

a = Analysis(
    [_main],
    pathex=[_spec_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        # serial.tools.miniterm is loaded by subprocess path for serial terminal tabs
        "serial.tools.miniterm",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

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
    icon=_icon if os.path.isfile(_icon) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Adbnik",
)
