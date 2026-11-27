# SPDX-License-Identifier: GPL-3.0-or-later
"""Salida de texto cuando no hay consola (el ``.exe`` sin ventana de terminal).

Sin consola, Windows no da ``stdout`` ni ``stderr``: valen ``None``. Los ``print`` normales no
fallan, pero ``argparse`` (``--help``, ``--version`` y los errores de uso) escribe sin comprobarlo y
lanza ``AttributeError``. ``asegurar_salida`` sustituye **solo** los flujos que valen ``None`` por un
registro en ``%APPDATA%\\Vislumbra\\vislumbra.log``.

- El archivo se crea **al escribir por primera vez**: un arranque sin mensajes no deja nada.
- Tiene un tope de tamaño; al abrirlo, si lo supera, se conserva solo lo más reciente.
- Puede contener rutas del equipo (por ejemplo en un traceback). Vive fuera del repositorio y no se envía a ningún sitio.
- Con una consola de verdad (``python -m vislumbra``, ``vislumbra-cli.exe``) no hace nada.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from . import perfiles

NOMBRE_REGISTRO = "vislumbra.log"
TOPE_BYTES = 256 * 1024  # al abrir, si el archivo lo supera se recorta a la mitad (lo más reciente)


def ruta_registro(carpeta: Path | None = None) -> Path:
    return (Path(carpeta) if carpeta is not None else perfiles.carpeta_config()) / NOMBRE_REGISTRO


def _recortar(ruta: Path, tope: int) -> None:
    """Si ``ruta`` pesa más que ``tope``, deja solo la mitad final, empezando en una línea entera."""
    try:
        if ruta.stat().st_size <= tope:
            return
        datos = ruta.read_bytes()[-(tope // 2):]
        salto = datos.find(b"\n")
        ruta.write_bytes(datos[salto + 1:] if salto >= 0 else datos)
    except OSError:
        pass  # no poder recortar no debe impedir escribir


class SalidaARegistro:
    """Objeto con ``write`` y ``flush`` que sustituye a un flujo ausente y escribe en el registro."""

    encoding = "utf-8"
    errors = "replace"

    def __init__(self, ruta: Path, version: str = "", tope: int = TOPE_BYTES):
        self._ruta, self._version, self._tope = ruta, version, tope
        self._archivo = None  # None: sin abrir todavía; False: no se pudo abrir (se descarta lo escrito)
        self._cerrojo = threading.Lock()

    def _abrir(self):
        if self._archivo is None:
            try:
                self._ruta.parent.mkdir(parents=True, exist_ok=True)
                _recortar(self._ruta, self._tope)
                self._archivo = open(self._ruta, "a", encoding="utf-8", errors="replace")
                marca = time.strftime("%Y-%m-%d %H:%M:%S")
                self._archivo.write(f"--- Vislumbra {self._version} · {marca} ---\n")
            except OSError:
                self._archivo = False
        return self._archivo or None

    def write(self, texto: str) -> int:
        if not texto:
            return 0
        with self._cerrojo:
            archivo = self._abrir()
            if archivo is not None:
                try:
                    archivo.write(texto)
                    archivo.flush()
                except (OSError, ValueError):
                    pass
        return len(texto)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


def asegurar_salida(version: str = "", carpeta: Path | None = None) -> Path | None:
    """Pone un registro en ``sys.stdout`` y ``sys.stderr`` si valen ``None``. Devuelve su ruta, o ``None`` si no hizo falta."""
    if sys.stdout is not None and sys.stderr is not None:
        return None
    ruta = ruta_registro(carpeta)
    salida = SalidaARegistro(ruta, version)
    if sys.stdout is None:
        sys.stdout = salida
    if sys.stderr is None:
        sys.stderr = salida
    return ruta
