# SPDX-License-Identifier: GPL-3.0-or-later
"""Icono de la bandeja del sistema con ``pystray``.

El menú y el texto emergente se calculan con funciones puras (``construir_menu`` y
``texto_emergente``) a partir de una ``InfoBandeja``; ``Bandeja`` solo los traduce a
``pystray``. Los clics llegan en el hilo de ``pystray``: ``Bandeja`` no toca Tk ni la
pantalla, solo llama a ``al_accion(accion, argumento)`` y la app lo pasa al hilo principal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pystray
from PIL import Image

from . import sistema

ICONOS = Path(__file__).resolve().parents[1] / "assets" / "iconos"
TAMANO_ICONO = 64
LIMITE_TEXTO_EMERGENTE = 120  # Windows corta el texto emergente a 127 caracteres

# Acciones que la bandeja envía a la app
MOSTRAR_OCULTAR = "mostrar_ocultar"
ALTERNAR_ACTIVO = "alternar_activo"
PERFIL = "perfil"  # con el nombre como argumento
SIGUIENTE = "siguiente"
COMPARAR = "comparar"
SALIR = "salir"


@dataclass(frozen=True)
class InfoBandeja:
    """Lo que la bandeja necesita saber para dibujar el menú y el texto emergente."""

    activo_on: bool = True
    perfil_activo: str = "Normal"
    perfiles: tuple[str, ...] = ("Normal",)
    ab: bool = False
    grupos: tuple[tuple[str, tuple[int, ...]], ...] = field(default_factory=tuple)  # (perfil, monitores)


@dataclass(frozen=True)
class ItemMenu:
    texto: str = ""
    accion: str | None = None
    argumento: str | None = None
    marcado: bool | None = None  # None: sin casilla
    predeterminado: bool = False  # clic izquierdo en el icono
    hijos: tuple["ItemMenu", ...] | None = None
    separador: bool = False
    habilitado: bool = True  # False: texto gris que hace de cabecera de sección


SEPARADOR = ItemMenu(separador=True)


def construir_menu(info: InfoBandeja) -> list[ItemMenu]:
    """Menú de la bandeja: como la maqueta, con la lista de perfiles plana bajo la cabecera «Perfil activo»."""
    return [
        ItemMenu("Mostrar panel", MOSTRAR_OCULTAR, predeterminado=True),
        ItemMenu("Activo", ALTERNAR_ACTIVO, marcado=info.activo_on),
        SEPARADOR,
        ItemMenu("Perfil activo", habilitado=False),
        *(ItemMenu(n, PERFIL, n, marcado=(n == info.perfil_activo)) for n in info.perfiles),
        ItemMenu("Siguiente perfil", SIGUIENTE),
        SEPARADOR,
        ItemMenu("Comparar (A/B)", COMPARAR, marcado=info.ab),
        ItemMenu("Salir (restaura la pantalla)", SALIR),
    ]


def texto_emergente(info: InfoBandeja) -> str:
    """«Vislumbra · activo · Oscuro (1, 2) · Código (3)»"""
    if not info.activo_on:
        return "Vislumbra · desactivado"
    partes = ["Vislumbra", "A/B: pantalla original" if info.ab else "activo"]
    partes += [f"{nombre} ({', '.join(map(str, nums))})" for nombre, nums in info.grupos]
    texto = " · ".join(partes)
    return texto if len(texto) <= LIMITE_TEXTO_EMERGENTE else texto[: LIMITE_TEXTO_EMERGENTE - 1] + "…"


def cargar_icono(activo: bool = True, tamano: int = TAMANO_ICONO) -> Image.Image:
    """Icono generado por ``herramientas/generar_iconos.py``; si falta, un cuadrado liso (no debe impedir arrancar)."""
    nombre = f"glifo-{tamano}.png" if activo else f"glifo-inactivo-{tamano}.png"
    ruta = ICONOS / nombre
    if ruta.exists():
        return Image.open(ruta).convert("RGBA")
    return Image.new("RGBA", (tamano, tamano), (201, 185, 138, 255) if activo else (120, 120, 120, 160))


class Bandeja:
    """Icono, menú y avisos. ``al_accion(accion, argumento)`` se llama en el hilo de ``pystray``."""

    def __init__(self, al_accion: Callable[[str, str | None], None], obtener_info: Callable[[], InfoBandeja]):
        sistema.menus_oscuros()  # antes de crear el icono: el menú nativo sale con el tema oscuro
        self._al_accion = al_accion
        self._obtener_info = obtener_info
        info = obtener_info()
        self._icono_activo, self._icono_inactivo = cargar_icono(True), cargar_icono(False)
        self.icono = pystray.Icon(
            "vislumbra", self._icono_activo if info.activo_on else self._icono_inactivo, texto_emergente(info),
            menu=pystray.Menu(lambda: tuple(self._convertir(i) for i in construir_menu(self._obtener_info()))),
        )

    # -- menú ---------------------------------------------------------------------------------------------------------------
    def _convertir(self, item: ItemMenu):
        if item.separador:
            return pystray.Menu.SEPARATOR
        if item.hijos is not None:
            return pystray.MenuItem(item.texto, pystray.Menu(*[self._convertir(h) for h in item.hijos]))
        return pystray.MenuItem(
            item.texto,
            self._crear_accion(item.accion, item.argumento),
            checked=None if item.marcado is None else self._crear_casilla(item.marcado),
            default=item.predeterminado,
            enabled=item.habilitado,
            radio=item.marcado is not None and item.accion == PERFIL,
        )

    # pystray cuenta los argumentos de cada función (icono, elemento): no pueden llevar valores por defecto.
    def _crear_accion(self, accion: str | None, argumento: str | None):
        def ejecutar(icono, elemento):
            self._al_accion(accion, argumento)

        return ejecutar

    @staticmethod
    def _crear_casilla(marcado: bool):
        def casilla(elemento):
            return marcado

        return casilla

    # -- ciclo de vida -------------------------------------------------------------------------------------------------------------
    def iniciar(self) -> None:
        """Arranca el bucle de mensajes de la bandeja en su propio hilo."""
        self.icono.run_detached()

    def actualizar(self) -> None:
        """Vuelve a calcular el menú, el texto emergente y el icono (activo o inactivo)."""
        info = self._obtener_info()
        self.icono.icon = self._icono_activo if info.activo_on else self._icono_inactivo
        self.icono.title = texto_emergente(info)
        self.icono.update_menu()

    def avisar(self, titulo: str, mensaje: str) -> None:
        """Notificación de Windows; si no se puede, se ignora (no es esencial)."""
        try:
            self.icono.notify(mensaje, titulo)
        except Exception:
            pass

    def detener(self) -> None:
        try:
            self.icono.stop()
        except Exception:
            pass
