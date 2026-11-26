# SPDX-License-Identifier: GPL-3.0-or-later
"""Entrada y salida con Windows: monitores y rampa de gamma (GDI, vía ``ctypes``).

Solo usa ``gdi32`` y ``user32``. No toca el registro de Windows ni los drivers.
"""

from __future__ import annotations

import atexit
import ctypes
import signal
import sys
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
