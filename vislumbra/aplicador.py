# SPDX-License-Identifier: GPL-3.0-or-later
"""Hilo que aplica la rampa de cada monitor y la vigila. La interfaz nunca espera a Windows.

El panel deja el estado deseado (``{monitor: rampa | None}``) en una ranura; el hilo aplica
siempre **el último** (con un intervalo mínimo entre escrituras). ``None`` significa «devolver
la rampa original». Cada pocos segundos vigila:

- si algo cambió una rampa (un juego, otro programa), la vuelve a aplicar;
- si tiene que hacerlo más de 5 veces en 60 s, deja de hacerlo para ese monitor y avisa
  de un conflicto (para no pelearse con otra herramienta);
- si cambió la lista de monitores, avisa y se detiene: la app recrea la sesión (en el hilo
  principal, por las señales) y un aplicador nuevo.

La sesión y las funciones de lectura se inyectan, y los métodos ``procesar_cambio`` y
``vigilar`` se pueden llamar sin hilo y con un reloj falso, para probar sin pantalla.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from . import color, display
from .color import Rampa

INTERVALO_VIGILANCIA = 2.0
INTERVALO_MINIMO = 0.015
VENTANA_CONFLICTO = 60.0
MAX_REAPLICACIONES = 5


@dataclass(frozen=True)
class Aviso:
    """Resultado de una acción del hilo. ``tipo``: aplicado, lectura, rechazo, error, conflicto, monitores."""

    tipo: str
    mensaje: str = ""
    monitores: tuple[int, ...] = ()


class Aplicador:
    def __init__(
        self,
        sesion,
        al_avisar: Callable[[Aviso], None],
        *,
        leer=display.leer_rampa,
        listar=display.listar_monitores,
        coinciden=display.rampas_coinciden,
        reloj: Callable[[], float] = time.monotonic,
        intervalo_vigilancia: float = INTERVALO_VIGILANCIA,
        intervalo_minimo: float = INTERVALO_MINIMO,
    ):
        self._sesion = sesion
        self._avisar = al_avisar
        self._leer, self._listar, self._coinciden = leer, listar, coinciden
        self._reloj = reloj
        self._intervalo_vigilancia = intervalo_vigilancia
        self._intervalo_minimo = intervalo_minimo
        self._bloqueo = threading.Lock()
        self._deseado: dict[int, Rampa | None] | None = None
        self._cambio = threading.Event()
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None
        self._aceptado: dict[int, Rampa | None] = {}  # lo que está aplicado en cada monitor
        self._reaplicaciones: dict[int, deque[float]] = {}
        self._conflicto: set[int] = set()
        self._firma_monitores = self._firma(sesion.monitores)
        self.monitores_cambiaron = False
        self.ultima_duracion = 0.0  # lo que tardó la última aplicación (s); se mide en la sesión de test
        self.max_duracion = 0.0

    @staticmethod
    def _firma(monitores) -> tuple:
        return tuple((m.numero, m.clave) for m in monitores)

    # -- hilo ---------------------------------------------------------------------------------
    def iniciar(self) -> None:
        if self._hilo is None:
            self._hilo = threading.Thread(target=self._bucle, name="vislumbra-aplicador", daemon=True)
            self._hilo.start()

    def parar(self, esperar: float = 5.0) -> None:
        """Para el hilo y espera a que termine (no deja una escritura a medias)."""
        self._parar.set()
        self._cambio.set()
        if self._hilo is not None and self._hilo is not threading.current_thread():
            self._hilo.join(esperar)

    @property
    def vivo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def _bucle(self) -> None:
        while not self._parar.is_set():
            hubo_cambio = self._cambio.wait(self._intervalo_vigilancia)
            if self._parar.is_set():
                break
            try:
                if hubo_cambio:
                    inicio = self._reloj()
                    self.procesar_cambio()
                    resto = self._intervalo_minimo - (self._reloj() - inicio)
                    if resto > 0:
                        self._parar.wait(resto)
                else:
                    self.vigilar(self._reloj())
            except Exception as e:  # el hilo no debe morir: se avisa y se sigue
                self._avisar(Aviso("error", f"error inesperado al aplicar: {e}"))

    # -- petición -------------------------------------------------------------------------------
    def pedir(self, rampas: dict[int, Rampa | None]) -> None:
        """Deja el estado deseado; si ya había uno sin aplicar, se sustituye (el último gana)."""
        with self._bloqueo:
            self._deseado = dict(rampas)
        self._cambio.set()

    # -- aplicar --------------------------------------------------------------------------------------
    def procesar_cambio(self) -> None:
        """Aplica el último estado deseado (solo lo que difiere de lo ya aplicado)."""
        with self._bloqueo:
            deseado, self._deseado = self._deseado, None
            self._cambio.clear()
        if deseado is None:
            return
        cambios = {
            n: r for n, r in deseado.items()
            if r != self._aceptado.get(n) and not (r is None and n not in self._aceptado)
        }
        for n in deseado:  # el usuario volvió a pedir algo: se reintenta aunque hubiera conflicto
            self._conflicto.discard(n)
            self._reaplicaciones.pop(n, None)
        if not cambios:
            return
        inicio = self._reloj()
        try:
            sin_coincidir = self._sesion.aplicar_por_monitor(cambios)
        except (display.ErrorPantalla, color.ErrorColor) as e:
            self._recuperar(cambios, e)
            return
        self.ultima_duracion = self._reloj() - inicio
        self.max_duracion = max(self.max_duracion, self.ultima_duracion)
        for n, r in cambios.items():
            if r is None:
                self._aceptado.pop(n, None)
            else:
                self._aceptado[n] = r
        self._avisar(Aviso("aplicado", monitores=tuple(sorted(cambios))))
        if sin_coincidir:
            nums = tuple(m.numero for m in sin_coincidir)
            self._avisar(Aviso(
                "lectura",
                "Windows aceptó la rampa pero la lectura posterior no coincide; el controlador puede estar limitándola.",
                nums,
            ))

    def _recuperar(self, cambios: dict[int, Rampa | None], error: Exception) -> None:
        """Windows o el validador rechazaron: se vuelve a la última rampa aceptada de esos monitores."""
        previo = {n: self._aceptado.get(n) for n in cambios}
        try:
            self._sesion.aplicar_por_monitor(previo)
        except Exception as e2:  # no se pudo ni volver: se dice, y la sesión restaurará al salir
            self._avisar(Aviso("error", f"{error} Además no se pudo volver a la rampa anterior: {e2}", tuple(sorted(cambios))))
            return
        self._avisar(Aviso("rechazo", str(error), tuple(sorted(cambios))))

    # -- vigilancia --------------------------------------------------------------------------------------
    def vigilar(self, ahora: float) -> None:
        """Comprueba la lista de monitores y que las rampas aplicadas sigan puestas."""
        if self.monitores_cambiaron:
            return
        try:
            actuales = self._firma(self._listar())
        except display.ErrorPantalla:
            actuales = None
        if actuales is not None and actuales != self._firma_monitores:
            self.monitores_cambiaron = True
            self._avisar(Aviso("monitores", "Cambió la lista de monitores."))
            return
        por_numero = {m.numero: m for m in self._sesion.monitores}
        for n, esperada in list(self._aceptado.items()):
            if esperada is None or n in self._conflicto or n not in por_numero:
                continue
            try:
                if self._coinciden(self._leer(por_numero[n]), esperada):
                    continue
            except display.ErrorPantalla:
                continue  # no se pudo leer ahora: se reintenta en la próxima vigilancia
            historial = self._reaplicaciones.setdefault(n, deque())
            while historial and ahora - historial[0] > VENTANA_CONFLICTO:
                historial.popleft()
            if len(historial) >= MAX_REAPLICACIONES:
                self._conflicto.add(n)
                self._avisar(Aviso(
                    "conflicto",
                    f"Algo cambia la rampa del monitor {n} sin parar; Vislumbra deja de reaplicarla. "
                    "Cierra el otro programa o mueve un deslizador para volver a intentarlo.",
                    (n,),
                ))
                continue
            historial.append(ahora)
            try:
                self._sesion.aplicar_por_monitor({n: esperada})
            except (display.ErrorPantalla, color.ErrorColor) as e:
                self._avisar(Aviso("error", f"No se pudo volver a aplicar la rampa del monitor {n}: {e}", (n,)))

    @property
    def en_conflicto(self) -> set[int]:
        return set(self._conflicto)

    @property
    def aplicado(self) -> dict[int, Rampa | None]:
        return dict(self._aceptado)
