# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PySide6.QtCore import QLibraryInfo

qt_plugins_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
extra_binaries = []
extra_datas = []

# Collect Qt plugins
for sub in [
    'platforms',
    'xcbglintegrations',
    'wayland-shell-integration',
    'wayland-decoration-client',
    'wayland-graphics-integration-client',
    'platformthemes',
    'styles',
    'imageformats',
]:
    p_path = Path(qt_plugins_dir) / sub
    if p_path.exists():
        for pattern in ('*.so*', '*.dll'):
            for f in p_path.glob(pattern):
                extra_binaries.append((str(f), f'PySide6/plugins/{sub}'))
                extra_binaries.append((str(f), f'plugins/{sub}'))

qt_conf_path = Path("build/qt.conf")
qt_conf_path.parent.mkdir(parents=True, exist_ok=True)
qt_conf_path.write_text("[Paths]\nPrefix = .\nPlugins = PySide6/plugins\n")
extra_datas.append((str(qt_conf_path), '.'))

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
    binaries=extra_binaries,
    datas=extra_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
