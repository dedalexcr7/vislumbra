# SPDX-License-Identifier: GPL-3.0-or-later
"""Iniciar con Windows: un acceso directo en la carpeta Inicio del usuario.

No toca el registro de Windows ni ningún ajuste del sistema: solo crea o borra
``Vislumbra.lnk`` en ``%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup``. Se puede ver y
borrar a mano. El acceso directo contiene rutas del equipo y vive fuera del repositorio.

Todas las funciones aceptan la carpeta como parámetro: las pruebas usan una temporal y nunca la real.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

NOMBRE_ACCESO = "Vislumbra.lnk"
ARGUMENTOS_ARRANQUE = "--oculto"  # al iniciar sesión, solo el icono en la bandeja (sin abrir el panel)
_SIN_CONSOLA = 0x08000000  # CREATE_NO_WINDOW

# Los valores van por variables de entorno, no dentro del texto del script: evita problemas de comillas.
_CREAR = (
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:VIS_LNK); "
    "$s.TargetPath = $env:VIS_EXE; $s.Arguments = $env:VIS_ARGS; $s.WorkingDirectory = $env:VIS_DIR; "
    "$s.Description = 'Vislumbra'; $s.Save()"
)
_LEER = (
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:VIS_LNK); "
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
    "$s.TargetPath; $s.Arguments; $s.WorkingDirectory"
)


class ErrorArranque(OSError):
    """No se pudo crear, leer o borrar el acceso directo; el mensaje va en español."""


def carpeta_inicio() -> Path:
    base = os.environ.get("APPDATA")
    raiz = Path(base) if base else Path.home() / "AppData" / "Roaming"
    return raiz / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def ruta_acceso(carpeta: Path | None = None) -> Path:
    return (Path(carpeta) if carpeta is not None else carpeta_inicio()) / NOMBRE_ACCESO


def esta_activado(carpeta: Path | None = None) -> bool:
    return ruta_acceso(carpeta).is_file()


def destino_por_defecto() -> tuple[str, str, str]:
    """(programa, argumentos, carpeta de trabajo) con los que se lanza esta misma instalación.

    Empaquetada como ``.exe``: el propio ejecutable. Desde Python: ``pythonw.exe`` del mismo entorno
    (sin ventana de consola) con ``-m vislumbra``, desde la carpeta del proyecto.
    """
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return str(exe), ARGUMENTOS_ARRANQUE, str(exe.parent)
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    programa = pythonw if pythonw.exists() else Path(sys.executable)
    proyecto = Path(__file__).resolve().parents[1]
    return str(programa), f"-m vislumbra {ARGUMENTOS_ARRANQUE}", str(proyecto)


def _powershell(script: str, **entorno: str) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, **entorno}, capture_output=True, text=True, encoding="utf-8",
            timeout=30, creationflags=_SIN_CONSOLA,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ErrorArranque(f"no se pudo ejecutar PowerShell para el acceso directo: {e}") from e
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()[:1]
        raise ErrorArranque("Windows no permitió crear el acceso directo" + (f": {detalle[0]}" if detalle else "."))
    return r.stdout


def activar(carpeta: Path | None = None, destino: tuple[str, str, str] | None = None) -> Path:
    """Crea el acceso directo (la carpeta se crea si no existe) y devuelve su ruta."""
    acceso = ruta_acceso(carpeta)
    programa, argumentos, trabajo = destino or destino_por_defecto()
    try:
        acceso.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ErrorArranque(f"no se pudo crear la carpeta de inicio: {e}") from e
    _powershell(_CREAR, VIS_LNK=str(acceso), VIS_EXE=programa, VIS_ARGS=argumentos, VIS_DIR=trabajo)
    if not acceso.is_file():
        raise ErrorArranque("el acceso directo no se creó.")
    return acceso


def desactivar(carpeta: Path | None = None) -> None:
    """Borra el acceso directo. Si no existe, no hace nada."""
    try:
        ruta_acceso(carpeta).unlink(missing_ok=True)
    except OSError as e:
        raise ErrorArranque(f"no se pudo borrar el acceso directo: {e}") from e


def leer_destino(carpeta: Path | None = None) -> tuple[str, str, str] | None:
    """(programa, argumentos, carpeta de trabajo) del acceso directo, o ``None`` si no existe."""
    acceso = ruta_acceso(carpeta)
    if not acceso.is_file():
        return None
    lineas = _powershell(_LEER, VIS_LNK=str(acceso)).splitlines()
    lineas += [""] * (3 - len(lineas))
    return lineas[0].strip(), lineas[1].strip(), lineas[2].strip()


def apunta_a_algo_que_existe(carpeta: Path | None = None) -> bool:
    """¿El programa del acceso directo sigue existiendo? (por si se movió la carpeta del proyecto)"""
    try:
        destino = leer_destino(carpeta)
    except ErrorArranque:
        return False
    return destino is not None and Path(destino[0]).exists()
