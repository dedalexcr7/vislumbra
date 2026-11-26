# SPDX-License-Identifier: GPL-3.0-or-later
"""Entrada y salida con Windows: monitores y rampa de gamma (GDI, vía ``ctypes``).

Solo usa ``gdi32`` y ``user32``. No toca el registro de Windows ni los drivers.
"""

from __future__ import annotations

import atexit
import ctypes
import signal
import sys
import threading
from ctypes import wintypes
from dataclasses import dataclass

from . import color
from .color import Rampa

# Banderas de ``DISPLAY_DEVICE.StateFlags``
_ATTACHED_TO_DESKTOP = 0x1
_PRIMARY_DEVICE = 0x4
_MIRRORING_DRIVER = 0x8

# Diferencia máxima (en la escala de 16 bits) entre lo aplicado y lo leído para
# considerar que coinciden. Provisional: se mide en la sesión de test.
TOLERANCIA_LECTURA = 512


class ErrorPantalla(Exception):
    """Error al hablar con Windows o con un monitor; el mensaje va en español."""


class MonitorNoEncontrado(ErrorPantalla):
    pass


class RampaRechazada(ErrorPantalla):
    pass


class _DisplayDevice(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

# Se declaran argtypes y restype para que los HDC de 64 bits no se trunquen.
_user32.EnumDisplayDevicesW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(_DisplayDevice), wintypes.DWORD,
]
_user32.EnumDisplayDevicesW.restype = wintypes.BOOL
_gdi32.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
_gdi32.CreateDCW.restype = ctypes.c_void_p
_gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
_gdi32.DeleteDC.restype = wintypes.BOOL
_gdi32.GetDeviceGammaRamp.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_gdi32.GetDeviceGammaRamp.restype = wintypes.BOOL
_gdi32.SetDeviceGammaRamp.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_gdi32.SetDeviceGammaRamp.restype = wintypes.BOOL


@dataclass(frozen=True)
class Monitor:
    numero: int  # 1, 2, 3… solo activos, como los muestra --list
    dispositivo: str  # p. ej. r"\\.\DISPLAY1"
    adaptador: str
    nombre: str | None  # segundo nivel de EnumDisplayDevices; puede faltar
    principal: bool


def _enumerar(dispositivo: str | None, indice: int) -> _DisplayDevice | None:
    d = _DisplayDevice()
    d.cb = ctypes.sizeof(_DisplayDevice)
    if not _user32.EnumDisplayDevicesW(dispositivo, indice, ctypes.byref(d), 0):
        return None
    return d


def listar_monitores() -> list[Monitor]:
    """Monitores activos en el escritorio, sin los adaptadores virtuales ni espejos."""
    monitores: list[Monitor] = []
    i = 0
    while (d := _enumerar(None, i)) is not None:
        i += 1
        activo = d.StateFlags & _ATTACHED_TO_DESKTOP and not d.StateFlags & _MIRRORING_DRIVER
        if not activo:
            continue
        hijo = _enumerar(d.DeviceName, 0)
        monitores.append(
            Monitor(
                numero=len(monitores) + 1,
                dispositivo=d.DeviceName,
                adaptador=d.DeviceString,
                nombre=hijo.DeviceString if hijo is not None and hijo.DeviceString else None,
                principal=bool(d.StateFlags & _PRIMARY_DEVICE),
            )
        )
    return monitores


def elegir_monitores(seleccion: str, monitores: list[Monitor]) -> list[Monitor]:
    """``seleccion``: ``principal``, ``todos`` o el número de un monitor."""
    if not monitores:
        raise MonitorNoEncontrado("no se ha encontrado ningún monitor activo.")
    s = seleccion.strip().lower()
    if s == "todos":
        return list(monitores)
    if s == "principal":
        return [next((m for m in monitores if m.principal), monitores[0])]
    try:
        numero = int(s)
    except ValueError:
        raise MonitorNoEncontrado(
            f"«{seleccion}» no es un monitor válido (usa principal, todos o un número)."
        ) from None
    for m in monitores:
        if m.numero == numero:
            return [m]
    raise MonitorNoEncontrado(
        f"el monitor {numero} no existe. Usa --list para ver los disponibles."
    )


class _ContextoDispositivo:
    """``CreateDCW`` con ``DeleteDC`` garantizado."""

    def __init__(self, m: Monitor):
        self._m = m
        self.hdc = None

    def __enter__(self) -> int:
        self.hdc = _gdi32.CreateDCW("DISPLAY", self._m.dispositivo, None, None)
        if not self.hdc:
            raise ErrorPantalla(
                f"no se pudo acceder al monitor {self._m.numero} "
                f"(código de Windows {ctypes.get_last_error()})."
            )
        return self.hdc

    def __exit__(self, *_):
        if self.hdc:
            _gdi32.DeleteDC(self.hdc)
            self.hdc = None


def leer_rampa(m: Monitor) -> Rampa:
    """Rampa actual del monitor: 768 enteros (R, G y B seguidos)."""
    buffer = (ctypes.c_ushort * color.LONGITUD_RAMPA)()
    with _ContextoDispositivo(m) as hdc:
        if not _gdi32.GetDeviceGammaRamp(hdc, buffer):
            raise ErrorPantalla(
                f"Windows no permite leer la rampa del monitor {m.numero} "
                f"(código {ctypes.get_last_error()})."
            )
    return list(buffer)


def _escribir(m: Monitor, r: Rampa) -> None:
    buffer = (ctypes.c_ushort * color.LONGITUD_RAMPA)(*r)
    with _ContextoDispositivo(m) as hdc:
        if not _gdi32.SetDeviceGammaRamp(hdc, buffer):
            codigo = ctypes.get_last_error()
            detalle = f" (código de Windows {codigo})" if codigo else ""
            raise RampaRechazada(
                f"Windows ha rechazado la rampa en el monitor {m.numero}{detalle}. "
                "Prueba con valores más suaves."
            )


def rampas_coinciden(a: Rampa, b: Rampa, tolerancia: int = TOLERANCIA_LECTURA) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= tolerancia for x, y in zip(a, b))


def aplicar_rampa(m: Monitor, r: Rampa, *, validar: bool = True) -> bool:
    """Aplica la rampa al monitor. Devuelve ``True`` si la lectura posterior coincide.

    Antes de tocar la pantalla llama a ``color.validar_rampa`` (``RampaIlegible``).
    Si Windows la rechaza lanza ``RampaRechazada``. Un ``False`` significa que
    Windows la aceptó pero el controlador parece limitarla (aviso, no error).
    """
    if validar:
        color.validar_rampa(r)
    _escribir(m, r)
    return rampas_coinciden(leer_rampa(m), r)


def restaurar_identidad(monitores: list[Monitor]) -> None:
    """Aplica la rampa neutra a todos los monitores indicados, aunque alguno falle.

    No pasa por el validador: restaurar nunca debe bloquearse. Si alguno falla,
    lanza ``ErrorPantalla`` al final, tras intentarlo con todos.
    """
    identidad = color.rampa_identidad()
    fallos = []
    for m in monitores:
        try:
            _escribir(m, identidad)
        except ErrorPantalla as e:
            fallos.append(f"monitor {m.numero}: {e}")
    if fallos:
        raise ErrorPantalla("no se pudo restaurar: " + "; ".join(fallos))


# --- Sesión con restauración al salir -----------------------------------------
_CTRL_CLOSE_EVENT = 2
_CTRL_LOGOFF_EVENT = 5
_CTRL_SHUTDOWN_EVENT = 6
_ManejadorConsola = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.SetConsoleCtrlHandler.argtypes = [_ManejadorConsola, wintypes.BOOL]
_kernel32.SetConsoleCtrlHandler.restype = wintypes.BOOL


class SesionGamma:
    """Guarda la rampa original de cada monitor y la restaura al salir.

    Uso: ``with SesionGamma(monitores) as sesion: sesion.aplicar(rampa)``.
    ``restaurar()`` es idempotente y se llama también desde ``atexit``, las
    señales ``SIGINT``/``SIGTERM``/``SIGBREAK`` y los eventos de cierre de la
    consola (cerrar la ventana, cerrar sesión o apagar).
    """

    def __init__(self, monitores: list[Monitor]):
        self.monitores = list(monitores)
        self._originales: dict[int, Rampa] = {}
        self._tocados: set[int] = set()
        self._bloqueo = threading.RLock()
        self._senales_previas: dict[int, object] = {}
        self._manejador_consola = None  # se conserva para que no lo recoja el recolector
        self._instalada = False

    # -- ciclo de vida
    def __enter__(self) -> "SesionGamma":
        self.iniciar()
        return self

    def __exit__(self, *_) -> None:
        self.cerrar()

    def iniciar(self) -> None:
        for m in self.monitores:
            self._originales[m.numero] = leer_rampa(m)
        atexit.register(self._restaurar_sin_excepcion)
        self._instalar_manejadores()
        self._instalada = True

    def cerrar(self) -> None:
        """Restaura y desinstala los manejadores. Lanza ``ErrorPantalla`` si no pudo restaurar."""
        try:
            self.restaurar()
        finally:
            if self._instalada:
                atexit.unregister(self._restaurar_sin_excepcion)
                self._desinstalar_manejadores()
                self._instalada = False

    # -- información
    def originales_modificados(self) -> list[Monitor]:
        """Monitores cuya rampa original no era la identidad (otra herramienta la tocó)."""
        neutra = color.rampa_identidad()
        return [m for m in self.monitores if self._originales.get(m.numero) != neutra]

    # -- acciones
    def aplicar(self, r: Rampa) -> list[Monitor]:
        """Aplica ``r`` a todos los monitores de la sesión.

        Valida antes de tocar nada. Si falla uno, deshace los ya aplicados en esta
        llamada y vuelve a lanzar el error. Devuelve los monitores que aceptaron la
        rampa pero cuya lectura posterior no coincide (aviso, no error).
        """
        color.validar_rampa(r)
        intentados: list[Monitor] = []
        sin_coincidir: list[Monitor] = []
        with self._bloqueo:
            try:
                for m in self.monitores:
                    # Se marca antes de escribir: si falla la lectura posterior o llega un
                    # Ctrl+C, el monitor ya cuenta como tocado y se restaura (hacerlo con uno
                    # que no llegó a cambiar es inocuo).
                    intentados.append(m)
                    self._tocados.add(m.numero)
                    coincide = aplicar_rampa(m, r, validar=False)
                    if not coincide:
                        sin_coincidir.append(m)
            except BaseException:
                self._restaurar_monitores(intentados, silencioso=True)
                raise
        return sin_coincidir

    def restaurar(self) -> None:
        """Devuelve cada monitor tocado a su rampa original. Idempotente."""
        with self._bloqueo:
            pendientes = [m for m in self.monitores if m.numero in self._tocados]
            self._restaurar_monitores(pendientes, silencioso=False)

    def conservar(self) -> None:
        """Olvida lo aplicado: al salir no se restaurará (para ``--persist``)."""
        with self._bloqueo:
            self._tocados.clear()

    def _restaurar_monitores(self, monitores: list[Monitor], silencioso: bool) -> None:
        fallos = []
        for m in monitores:
            try:
                _escribir(m, self._originales[m.numero])
                self._tocados.discard(m.numero)
            except ErrorPantalla as e:
                fallos.append(f"monitor {m.numero}: {e}")
        if fallos and not silencioso:
            raise ErrorPantalla("no se pudo restaurar: " + "; ".join(fallos))

    def _restaurar_sin_excepcion(self) -> None:
        try:
            self.restaurar()
        except ErrorPantalla as e:
            print(f"Aviso: {e}", file=sys.stderr)

    # -- señales y cierre de consola
    def _al_recibir_senal(self, numero, _marco) -> None:
        self._restaurar_sin_excepcion()
        raise KeyboardInterrupt if numero == signal.SIGINT else SystemExit(1)

    def _al_evento_consola(self, evento: int) -> bool:
        if evento in (_CTRL_CLOSE_EVENT, _CTRL_LOGOFF_EVENT, _CTRL_SHUTDOWN_EVENT):
            self._restaurar_sin_excepcion()
        return False  # Ctrl+C y Ctrl+Pausa los gestionan las señales; el resto sigue su curso

    def _instalar_manejadores(self) -> None:
        if threading.current_thread() is threading.main_thread():
            for nombre in ("SIGINT", "SIGTERM", "SIGBREAK"):
                numero = getattr(signal, nombre, None)
                if numero is not None:
                    self._senales_previas[numero] = signal.signal(numero, self._al_recibir_senal)
        self._manejador_consola = _ManejadorConsola(self._al_evento_consola)
        _kernel32.SetConsoleCtrlHandler(self._manejador_consola, True)

    def _desinstalar_manejadores(self) -> None:
        if self._manejador_consola is not None:
            _kernel32.SetConsoleCtrlHandler(self._manejador_consola, False)
            self._manejador_consola = None
        for numero, previo in self._senales_previas.items():
            signal.signal(numero, previo)
        self._senales_previas.clear()
