# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path



a_cli = Analysis(
    ['src/cli.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz_cli = PYZ(a_cli.pure)

exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name='pygurashify',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

a_gui = Analysis(
    ['src/gui.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['src/rthook_pyside6.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz_gui = PYZ(a_gui.pure)

exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    [],
    exclude_binaries=True,
    name='pygurashify-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

a_gui.binaries = [b for b in a_gui.binaries if not Path(b[0]).name.lower().startswith("icu")]
a_cli.binaries = [b for b in a_cli.binaries if not Path(b[0]).name.lower().startswith("icu")]

coll = COLLECT(
    exe_cli,
    a_cli.binaries,
    a_cli.datas,
    exe_gui,
    a_gui.binaries,
    a_gui.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pygurashify',
)


