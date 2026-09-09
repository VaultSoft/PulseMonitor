# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "pulsemonitor.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "_logo_b64.txt"), "."),
        (str(ROOT / "VERSION"), "."),
    ],
    hiddenimports=[
        "wmi",
        "pythoncom",
        "win32com",
        "win32com.client",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "sitecustomize",
        "pyqtgraph",
        "matplotlib",
        "multiprocessing",
        "tkinter",
        "clr",
        "pythonnet",
        "LibreHardwareMonitor",
        "GPUtil",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PulseMonitor",
    icon=str(ROOT / "icon.ico"),
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PulseMonitor",
)
