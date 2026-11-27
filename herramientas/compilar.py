# SPDX-License-Identifier: GPL-3.0-or-later
"""Compila Vislumbra a ``dist\\Vislumbra\\`` (``Vislumbra.exe`` y ``vislumbra-cli.exe``) con PyInstaller.

Uso (con el entorno virtual del proyecto y ``pip install -r requirements-build.txt``)::

    python herramientas/compilar.py            # compila
    python herramientas/compilar.py --limpiar  # borra build\\ y dist\\ antes

No toca la pantalla, el registro de Windows ni nada fuera de la carpeta del proyecto. ``dist\\`` y
``build\\`` están en ``.gitignore``: lo compilado nunca se versiona.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESPECIFICACION = RAIZ / "herramientas" / "vislumbra.spec"
DIST = RAIZ / "dist"
BUILD = RAIZ / "build"
SALIDA = DIST / "Vislumbra"
ESPERADOS = ("Vislumbra.exe", "vislumbra-cli.exe", "_internal/assets/iconos/glifo-64.png")


def _mb(ruta: Path) -> float:
    return sum(f.stat().st_size for f in ruta.rglob("*") if f.is_file()) / 1_000_000


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compila Vislumbra con PyInstaller.")
    p.add_argument("--limpiar", action="store_true", help="borra build\\ y dist\\ antes de compilar")
    a = p.parse_args(argv)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Falta PyInstaller: pip install -r requirements-build.txt", file=sys.stderr)
        return 2
    if a.limpiar:
        for carpeta in (BUILD, DIST):
            shutil.rmtree(carpeta, ignore_errors=True)
    orden = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(DIST),
             "--workpath", str(BUILD), str(ESPECIFICACION)]
    if subprocess.run(orden, cwd=RAIZ).returncode != 0:
        print("La compilación falló.", file=sys.stderr)
        return 1
    faltan = [e for e in ESPERADOS if not (SALIDA / e).exists()]
    if faltan:
        print("Falta en la salida: " + ", ".join(faltan), file=sys.stderr)
        return 1
    print(f"\nListo: {SALIDA} ({_mb(SALIDA):.1f} MB). Siguiente: python herramientas/probar_exe.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
