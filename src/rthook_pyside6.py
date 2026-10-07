import os
import sys
from pathlib import Path

if sys.platform == "win32":
    _dll_handles = []

    base_dirs = []
    if hasattr(sys, "_MEIPASS"):
        base_dirs.append(Path(sys._MEIPASS))
    exe_dir = Path(sys.executable).resolve().parent
    base_dirs.extend([exe_dir, exe_dir / "_internal"])

    for base in base_dirs:
        for sub in ["", "PySide6", "shiboken6", "PySide6/plugins", "plugins"]:
            target = (base / sub).resolve()
            if target.is_dir():
                if hasattr(os, "add_dll_directory"):
                    try:
                        _dll_handles.append(os.add_dll_directory(str(target)))
                    except Exception:
                        pass
                os.environ["PATH"] = str(target) + os.pathsep + os.environ.get("PATH", "")

        for plugin_candidate in [base / "PySide6" / "plugins", base / "plugins"]:
            if (plugin_candidate / "platforms").is_dir():
                os.environ["QT_PLUGIN_PATH"] = str(plugin_candidate)
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugin_candidate / "platforms")
                break
