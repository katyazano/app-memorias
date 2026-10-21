#!/usr/bin/env python3
"""Script de estampado de versión unificada para Memorias de Gastos.
Estampa en cada compilación: <versión>+<AAAAMMDD.HHMM> desde un solo origen (archivo VERSION).
Actualiza sincronizadamente:
- app/config.py (APP_VERSION)
- frontend/src/version.ts (FRONTEND_BUILD_VERSION)
- version_info.txt (PyInstaller VSVersionInfo para propiedades de MemoriasGastos.exe)
"""
import re
import sys
from datetime import datetime
from pathlib import Path

def stamp_version(custom_timestamp: str = None) -> str:
    repo_root = Path(__file__).resolve().parent.parent
    version_file = repo_root / "VERSION"
    if not version_file.exists():
        version_file.write_text("2.0.0\n", encoding="utf-8")
    
    base_version = version_file.read_text(encoding="utf-8").strip()
    if not base_version:
        base_version = "2.0.0"

    timestamp = custom_timestamp or datetime.now().strftime("%Y%m%d.%H%M")
    full_version = f"{base_version}+{timestamp}"

    # Extraer enteros para tupla de versión binaria de Windows
    parts = re.findall(r"\d+", base_version)
    major = int(parts[0]) if len(parts) > 0 else 2
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0

    # 1. Actualizar app/config.py
    config_py = repo_root / "app" / "config.py"
    if config_py.exists():
        content = config_py.read_text(encoding="utf-8")
        updated = re.sub(
            r'APP_VERSION:\s*str\s*=\s*["\'].*?["\']',
            f'APP_VERSION: str = "{full_version}"',
            content,
            count=1,
        )
        config_py.write_text(updated, encoding="utf-8")

    # 2. Actualizar frontend/src/version.ts
    version_ts = repo_root / "frontend" / "src" / "version.ts"
    version_ts.parent.mkdir(parents=True, exist_ok=True)
    version_ts_content = f"""/**
 * Versión de compilación del frontend.
 * Generado automáticamente por scripts/stamp_version.py desde VERSION.
 */
export const FRONTEND_BUILD_VERSION = '{full_version}';
"""
    version_ts.write_text(version_ts_content, encoding="utf-8")

    # 3. Generar version_info.txt para PyInstaller
    version_info_path = repo_root / "version_info.txt"
    version_info_content = f"""# UTF-8
# VSVersionInfo generado automáticamente para PyInstaller
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Despacho de Arquitectura'),
        StringStruct('FileDescription', 'Memorias de Gastos'),
        StringStruct('FileVersion', '{full_version}'),
        StringStruct('InternalName', 'MemoriasGastos'),
        StringStruct('LegalCopyright', 'Copyright (C) 2026'),
        StringStruct('OriginalFilename', 'MemoriasGastos.exe'),
        StringStruct('ProductName', 'Memorias de Gastos'),
        StringStruct('ProductVersion', '{full_version}')])
      ]), 
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    version_info_path.write_text(version_info_content, encoding="utf-8")

    return full_version


if __name__ == "__main__":
    ts_arg = sys.argv[1] if len(sys.argv) > 1 else None
    version_stamped = stamp_version(ts_arg)
    print(version_stamped)
