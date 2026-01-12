# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_dir = Path(__file__).parent
entrypoint = project_dir / "backend" / "desktop_app.py"
datas = []
frontend_dist = project_dir / "frontend" / "dist"
if frontend_dist.exists():
    datas.append((str(frontend_dist), "frontend/dist"))
models_dir = project_dir / "models"
if models_dir.exists():
    datas.append((str(models_dir), "models"))
icon_file = project_dir / "assets" / "app.ico"

a = Analysis(
    [str(entrypoint)],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
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
    name="OratioViva",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_file) if icon_file.exists() else None,
)
