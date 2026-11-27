# SPDX-License-Identifier: GPL-3.0-or-later
# -*- mode: python ; coding: utf-8 -*-
"""Receta de PyInstaller: ``dist\\Vislumbra\\`` con dos ejecutables que comparten ``_internal\\``.

- ``Vislumbra.exe``: sin consola (doble clic, «Iniciar con Windows»).
- ``vislumbra-cli.exe``: con consola (``--list``, ``--reset``, ``--perfil``, ``--help``).

No se lanza a mano: ``python herramientas/compilar.py``. Las rutas salen de ``SPECPATH``, así que
no hay rutas del equipo en el archivo.
"""

import sys
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

RAIZ = Path(SPECPATH).resolve().parent  # noqa: F821 - SPECPATH lo define PyInstaller
sys.path.insert(0, str(RAIZ))
from vislumbra import __version__  # noqa: E402

ICONO = RAIZ / "assets" / "vislumbra.ico"
DATOS = [(str(RAIZ / "assets" / "iconos"), "assets/iconos")]  # único recurso que lee el programa (iconos de la bandeja)
# Nada de pruebas ni de la librería «keyboard» (la fase 3 la quitó): no deben entrar en el ejecutable.
EXCLUIR = ["pytest", "keyboard", "_pytest"]


def _version_info() -> VSVersionInfo:
    """Propiedades del archivo en el Explorador. Sin copyright hasta que el autor decida el nombre (plan, D6)."""
    numeros = tuple((int(n) for n in __version__.split(".")[:3])) + (0,) * (4 - len(__version__.split(".")[:3]))
    cadenas = [
        ("FileDescription", "Vislumbra: brillo, contraste, gamma y color de la pantalla"),
        ("FileVersion", __version__),
        ("InternalName", "Vislumbra"),
        ("ProductName", "Vislumbra"),
        ("ProductVersion", __version__),
    ]
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numeros, prodvers=numeros),
        kids=[
            StringFileInfo([StringTable("0c0a04b0", [StringStruct(k, v) for k, v in cadenas])]),  # español (c0a), Unicode (04b0)
            VarFileInfo([VarStruct("Translation", [0x0C0A, 1200])]),
        ],
    )


def _analisis():
    return Analysis(  # noqa: F821
        [str(RAIZ / "herramientas" / "lanzador.py")],
        pathex=[str(RAIZ)], datas=DATOS, excludes=EXCLUIR, noarchive=False,
    )


def _exe(analisis, nombre: str, consola: bool):
    return EXE(  # noqa: F821
        PYZ(analisis.pure), analisis.scripts, [], exclude_binaries=True, name=nombre,  # noqa: F821
        console=consola, icon=str(ICONO), version=_version_info(),
    )


a_app, a_cli = _analisis(), _analisis()
MERGE((a_app, "Vislumbra", "Vislumbra"), (a_cli, "vislumbra-cli", "vislumbra-cli"))  # noqa: F821
exe_app, exe_cli = _exe(a_app, "Vislumbra", False), _exe(a_cli, "vislumbra-cli", True)
COLLECT(  # noqa: F821
    exe_app, a_app.binaries, a_app.datas, exe_cli, a_cli.binaries, a_cli.datas, name="Vislumbra",
)
