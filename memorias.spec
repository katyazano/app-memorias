# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller para Memorias de Gastos.
Modo onedir: genera MemoriasGastos.exe (sin consola) y MemoriasGastos-Debug.exe (con consola).
"""
import sys
from pathlib import Path

block_cipher = None

added_files = [
    ('frontend/dist', 'frontend/dist'),
    ('migrations', 'migrations'),
    ('alembic.ini', '.'),
]

hidden_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespans',
    'uvicorn.lifespans.on',
    'uvicorn.lifespans.off',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.sqlite.pysqlite',
    'alembic',
    'alembic.runtime.migration',
    'alembic.script',
    'alembic.operations',
    'pydantic',
    'openpyxl',
    'pypdf',
    'dotenv',
    'multipart',
    'jinja2',
]

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pandas', 'scipy', 'playwright'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

version_file = 'version_info.txt' if Path('version_info.txt').exists() else None

# 1. Versión de producción (sin ventana de consola)
exe_prod = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MemoriasGastos',
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
    version=version_file,
)

# 2. Versión de depuración (con ventana de consola)
exe_debug = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MemoriasGastos-Debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_file,
)

coll = COLLECT(
    exe_prod,
    exe_debug,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MemoriasGastos',
)
