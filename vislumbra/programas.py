# SPDX-License-Identifier: GPL-3.0-or-later
"""Perfil automático por programa: lógica pura (sin Windows ni Tk).

Un programa se identifica por el **nombre de su ejecutable** (``juego.exe``), nunca por la ruta:
así no se guardan rutas del equipo y la asociación sirve aunque el juego esté en otra carpeta.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

NOMBRE_MAX = 64
_PROHIBIDOS = re.compile(r'[<>:"|?*\x00-\x1f]')


class ErrorPrograma(ValueError):
    """Nombre de programa no válido; el mensaje va en español."""


@dataclass(frozen=True)
class Asociacion:
    exe: str  # en minúsculas y sin ruta: «juego.exe»
    perfil: str


def normalizar_exe(texto: str) -> str:
    """Deja solo el nombre del ejecutable, en minúsculas. Si se pega una ruta, se descarta la carpeta.

    ``C:\\Juegos\\Juego.EXE`` -> ``juego.exe``; ``juego`` -> ``juego.exe``.
    """
    t = texto.strip().strip('"').strip()
    t = re.split(r"[\\/]", t)[-1].strip()
    if not t:
        raise ErrorPrograma("escribe el nombre del programa, por ejemplo «juego.exe».")
    if _PROHIBIDOS.search(t):
        raise ErrorPrograma("el nombre del programa tiene caracteres no válidos.")
    t = t.lower()
    if "." not in t:
        t += ".exe"
    if not t.endswith(".exe") or t == ".exe":
        raise ErrorPrograma("solo se admiten programas «.exe».")
    if len(t) > NOMBRE_MAX:
        raise ErrorPrograma(f"el nombre del programa no puede pasar de {NOMBRE_MAX} caracteres.")
    return t


def buscar(asociaciones: Iterable[Asociacion], exe: str) -> Asociacion | None:
    return next((a for a in asociaciones if a.exe == exe), None)


class SeguimientoProgramas:
    """Qué programa asociado manda ahora: el **último que se abrió** de los que siguen abiertos.

    Si hay varios abiertos y se cierra el último, pasa a mandar el anterior; sin ninguno, ``None``.
    """

    def __init__(self) -> None:
        self._orden: list[str] = []

    @property
    def orden(self) -> list[str]:
        return list(self._orden)

    def actualizar(self, abiertos: Iterable[str]) -> str | None:
        abiertos = set(abiertos)
        self._orden = [e for e in self._orden if e in abiertos]
        for nuevo in sorted(abiertos - set(self._orden)):  # varios a la vez: orden alfabético (estable)
            self._orden.append(nuevo)
        return self._orden[-1] if self._orden else None
