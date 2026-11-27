# SPDX-License-Identifier: GPL-3.0-or-later
"""Pequeñas llamadas a Windows con ``ctypes``: instancia única, eventos con nombre, DPI y
área de trabajo. Ninguna toca la pantalla ni el registro; solo objetos del sistema que
desaparecen al cerrar el proceso (mutex y eventos con nombre).
"""

from __future__ import annotations

import ctypes
from collections.abc import Sequence
from ctypes import wintypes

PREFIJO = r"Local\Vislumbra"  # «Local\» es por sesión de usuario
ERROR_ALREADY_EXISTS = 183
WAIT_TIMEOUT = 0x102
WAIT_FAILED = 0xFFFFFFFF
INFINITO = 0xFFFFFFFF
_EVENT_MODIFY_STATE = 0x0002
_SYNCHRONIZE = 0x00100000
_SPI_GETWORKAREA = 0x0030

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)

_k32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_k32.CreateMutexW.restype = wintypes.HANDLE
_k32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_k32.CreateEventW.restype = wintypes.HANDLE
_k32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_k32.OpenEventW.restype = wintypes.HANDLE
_k32.SetEvent.argtypes = [wintypes.HANDLE]
_k32.SetEvent.restype = wintypes.BOOL
_k32.ResetEvent.argtypes = [wintypes.HANDLE]
_k32.ResetEvent.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL
_k32.WaitForMultipleObjects.argtypes = [
    wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL, wintypes.DWORD,
]
_k32.WaitForMultipleObjects.restype = wintypes.DWORD
_user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
_user32.SystemParametersInfoW.restype = wintypes.BOOL


def nombres(prefijo: str = PREFIJO) -> dict[str, str]:
    """Nombres de los objetos del sistema. Las pruebas pasan un prefijo aleatorio."""
    return {
        "mutex": f"{prefijo}.UnaInstancia",
        "mostrar": f"{prefijo}.Mostrar",
        "desactivar": f"{prefijo}.Desactivar",
        "peticion": f"{prefijo}.Peticion",
    }


class ErrorSistema(OSError):
    pass


class Mutex:
    """Instancia única: la primera que lo crea es la dueña; las demás ven ``ya_existia``."""

    def __init__(self, nombre: str):
        self._h = _k32.CreateMutexW(None, False, nombre)
        if not self._h:
            raise ErrorSistema(f"no se pudo crear el mutex (código {ctypes.get_last_error()}).")
        self.ya_existia = ctypes.get_last_error() == ERROR_ALREADY_EXISTS

    def cerrar(self) -> None:
        if self._h:
            _k32.CloseHandle(self._h)
            self._h = None


class Evento:
    """Evento de reinicio automático, con nombre (compartido entre procesos) o sin él."""

    def __init__(self, nombre: str | None = None, _handle=None):
        self._h = _handle or _k32.CreateEventW(None, False, False, nombre)
        if not self._h:
            raise ErrorSistema(f"no se pudo crear el evento (código {ctypes.get_last_error()}).")

    @classmethod
    def abrir(cls, nombre: str) -> "Evento | None":
        """Abre un evento que ya existe (de otra instancia) o devuelve ``None`` si no hay ninguno."""
        h = _k32.OpenEventW(_EVENT_MODIFY_STATE | _SYNCHRONIZE, False, nombre)
        return cls(_handle=h) if h else None

    @property
    def handle(self):
        return self._h

    def activar(self) -> None:
        if self._h:
            _k32.SetEvent(self._h)

    def limpiar(self) -> None:
        if self._h:
            _k32.ResetEvent(self._h)

    def cerrar(self) -> None:
        if self._h:
            _k32.CloseHandle(self._h)
            self._h = None


def esperar_alguno(eventos: Sequence[Evento], milisegundos: int | None = None) -> int | None:
    """Espera a que se active alguno. Devuelve su posición, o ``None`` si venció el tiempo."""
    manejadores = (wintypes.HANDLE * len(eventos))(*[e.handle for e in eventos])
    r = _k32.WaitForMultipleObjects(
        len(eventos), manejadores, False, INFINITO if milisegundos is None else int(milisegundos)
    )
    if r == WAIT_TIMEOUT:
        return None
    if r == WAIT_FAILED or r >= len(eventos):
        raise ErrorSistema(f"fallo al esperar los eventos (código {ctypes.get_last_error()}).")
    return int(r)


def activar_dpi() -> bool:
    """Hace el proceso consciente del DPI del sistema (modo 1). Debe llamarse antes de crear ventanas."""
    try:
        return ctypes.WinDLL("shcore").SetProcessDpiAwareness(1) == 0
    except (OSError, AttributeError):
        return False


def area_de_trabajo() -> tuple[int, int, int, int]:
    """(izquierda, arriba, derecha, abajo) del escritorio sin la barra de tareas."""
    r = wintypes.RECT()
    if not _user32.SystemParametersInfoW(_SPI_GETWORKAREA, 0, ctypes.byref(r), 0):
        return (0, 0, 1280, 720)
    return (r.left, r.top, r.right, r.bottom)


def colocar_abajo_derecha(area: tuple[int, int, int, int], ancho: int, alto: int, margen: int = 12) -> tuple[int, int]:
    """Esquina de la ventana para que quede abajo a la derecha del área de trabajo (junto a la bandeja)."""
    izq, arriba, der, abajo = area
    x = max(izq, der - ancho - margen)
    y = max(arriba, abajo - alto - margen)
    return x, y


def limitar_al_area(x: int, y: int, ancho: int, alto: int, area: tuple[int, int, int, int]) -> tuple[int, int]:
    """Esquina de la ventana movida lo justo para que quepa en el área de trabajo (si no cabe, manda la esquina superior izquierda)."""
    izq, arriba, der, abajo = area
    return max(izq, min(x, der - ancho)), max(arriba, min(y, abajo - alto))


def redondear_ventana(ventana, borde: str | None = None) -> bool:
    """Pide a Windows 11 esquinas redondeadas (y el color del borde ``#rrggbb``) para una ventana de Tk sin barra.

    Es solo cosmético (``DwmSetWindowAttribute``): no toca el registro ni los controladores. Devuelve
    ``False`` si el sistema no lo admite (Windows 10) o algo falla; entonces la ventana queda cuadrada.
    """
    try:
        hwnd = int(ventana.wm_frame(), 16)
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        dwm.DwmSetWindowAttribute.restype = ctypes.c_long
        redondeo = ctypes.c_int(2)  # DWMWCP_ROUND
        ok = dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(redondeo), ctypes.sizeof(redondeo)) == 0  # DWMWA_WINDOW_CORNER_PREFERENCE
        if borde and ok:
            r, g, b = (int(borde[i:i + 2], 16) for i in (1, 3, 5))
            colorref = ctypes.c_uint(r | (g << 8) | (b << 16))
            dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(colorref), ctypes.sizeof(colorref))  # DWMWA_BORDER_COLOR
        return ok
    except Exception:  # cosmético: nunca debe impedir mostrar el panel
        return False


def menus_oscuros() -> bool:
    """Pide a Windows que los menús nativos de este proceso (el de la bandeja) salgan con el tema oscuro.

    Usa dos funciones de ``uxtheme.dll`` que Microsoft no documenta (por número: 135 ``SetPreferredAppMode``
    y 136 ``FlushMenuThemes``). Solo afectan a los menús de este proceso, no tocan el registro ni los
    controladores y no cambian nada del sistema. Si Windows no las tiene, el menú queda claro y devuelve ``False``.
    """
    try:
        ux = ctypes.WinDLL("uxtheme")
        establecer, refrescar = ux[135], ux[136]
        establecer.argtypes, establecer.restype = [ctypes.c_int], ctypes.c_int
        refrescar.argtypes, refrescar.restype = [], None
        establecer(2)  # ForceDark: siempre oscuro, como el resto de la app
        refrescar()
        return True
    except Exception:  # cosmético: nunca debe impedir arrancar la bandeja
        return False
