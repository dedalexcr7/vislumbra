# SPDX-License-Identifier: GPL-3.0-or-later
"""Atajos de teclado globales con ``RegisterHotKey`` (sin ganchos de teclado).

Windows avisa solo de las combinaciones registradas: la app **no ve el resto de teclas** (a diferencia de un gancho global
``WH_KEYBOARD_LL``, que ve todas, contraseñas incluidas). No pide permisos de administrador.

``RegisterHotKey`` solo funciona desde el hilo que recibe los mensajes: por eso hay un hilo propio (``vislumbra-atajos``)
y las peticiones (registrar, pausar, probar, parar) viajan por una cola y se despiertan con ``PostThreadMessageW``. El hilo
**solo avisa** con ``al_atajo(clave)``; no toca Tk ni el estado.
"""

from __future__ import annotations

import ctypes
import queue
import threading
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass

from .atajos import Combinacion

WM_HOTKEY = 0x0312
WM_APP = 0x8000
MOD_NOREPEAT = 0x4000  # mantener pulsada la combinación no repite la acción
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
_ID_PRUEBA = 0xBFFF  # el último identificador válido: para «probar» una combinación sin dejarla registrada
_VK_MODIFICADORES = {"Ctrl": 0x11, "Alt": 0x12, "Shift": 0x10}
_VK_WIN = (0x5B, 0x5C)

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class _Msg(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND), ("message", wintypes.UINT), ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD), ("pt", wintypes.POINT),
    ]


_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = wintypes.BOOL
_user32.GetMessageW.argtypes = [ctypes.POINTER(_Msg), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.GetMessageW.restype = ctypes.c_int
_user32.PeekMessageW.argtypes = [ctypes.POINTER(_Msg), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
_user32.PeekMessageW.restype = wintypes.BOOL
_user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.PostThreadMessageW.restype = wintypes.BOOL
_user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_user32.GetAsyncKeyState.restype = ctypes.c_short
_user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
_user32.GetKeyboardLayout.restype = ctypes.c_void_p
_user32.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
_user32.MapVirtualKeyExW.restype = wintypes.UINT
_user32.ToUnicodeEx.argtypes = [
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte), wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, ctypes.c_void_p,
]
_user32.ToUnicodeEx.restype = ctypes.c_int
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class ErrorTeclado(OSError):
    """El hilo de atajos no responde o no pudo arrancar; el mensaje va en español."""


@dataclass(frozen=True)
class Resultado:
    ok: bool
    codigo: int = 0  # el de GetLastError si falló

    @property
    def en_uso(self) -> bool:
        """Otra aplicación (o Windows) ya tiene esa combinación."""
        return not self.ok and self.codigo == ERROR_HOTKEY_ALREADY_REGISTERED


Clave = tuple[str, str]


class GestorAtajos:
    """Registra combinaciones y avisa con ``al_atajo(clave)`` (desde el hilo de atajos) cuando se pulsan."""

    def __init__(self, al_atajo: Callable[[Clave], None]):
        self._al_atajo = al_atajo
        self._ordenes: queue.Queue = queue.Queue()
        self._hilo: threading.Thread | None = None
        self._listo = threading.Event()
        self._tid = 0
        # Solo los toca el hilo de atajos:
        self._mapa: dict[Clave, Combinacion] = {}
        self._por_id: dict[int, Clave] = {}
        self._ids: dict[Clave, int] = {}
        self._pausado = False
        self._siguiente_id = 1

    # -- ciclo de vida -------------------------------------------------------------------------------------------
    def iniciar(self) -> None:
        if self._hilo is not None:
            return
        self._hilo = threading.Thread(target=self._bucle, name="vislumbra-atajos", daemon=True)
        self._hilo.start()
        if not self._listo.wait(5.0):
            raise ErrorTeclado("el hilo de atajos no arrancó.")

    @property
    def thread_id(self) -> int:
        return self._tid

    @property
    def vivo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def id_de(self, clave: Clave) -> int | None:
        """Identificador con el que está registrado ahora (para las pruebas, que simulan ``WM_HOTKEY``)."""
        return self._ids.get(clave)

    def parar(self, espera: float = 2.0) -> None:
        """Desregistra todo y para el hilo. Se puede llamar varias veces."""
        if not self.vivo:
            return
        try:
            self._enviar("parar", espera=espera)
        except ErrorTeclado:
            pass
        if self._hilo is not None:
            self._hilo.join(espera)

    # -- peticiones (desde cualquier hilo) --------------------------------------------------------------------------
    def aplicar(self, mapa: dict[Clave, Combinacion], espera: float = 2.0) -> dict[Clave, Resultado]:
        """Sustituye lo registrado por ``mapa``. Devuelve el resultado de cada atajo (por ejemplo, «en uso»)."""
        return self._enviar("aplicar", dict(mapa), espera=espera)

    def pausar(self, espera: float = 2.0) -> None:
        """Desregistra todo sin olvidarlo (mientras se graba una combinación: si no, saltaría la acción)."""
        self._enviar("pausar", espera=espera)

    def reanudar(self, espera: float = 2.0) -> dict[Clave, Resultado]:
        return self._enviar("reanudar", espera=espera)

    def probar(self, comb: Combinacion, espera: float = 2.0) -> Resultado:
        """Intenta registrar la combinación un instante y la libera: dice si está libre sin dejar nada registrado."""
        return self._enviar("probar", comb, espera=espera)

    def _enviar(self, orden: str, *args, espera: float):
        if not self.vivo:
            raise ErrorTeclado("el hilo de atajos no está en marcha.")
        hecho, respuesta = threading.Event(), []
        self._ordenes.put((orden, args, hecho, respuesta))
        _user32.PostThreadMessageW(self._tid, WM_APP, 0, 0)
        if not hecho.wait(espera):
            raise ErrorTeclado("el hilo de atajos no respondió a tiempo.")
        if respuesta and isinstance(respuesta[0], BaseException):
            raise respuesta[0]
        return respuesta[0] if respuesta else None

    # -- hilo de atajos ---------------------------------------------------------------------------------------------
    def _bucle(self) -> None:
        self._tid = int(_kernel32.GetCurrentThreadId())
        msg = _Msg()
        _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # crea la cola de mensajes del hilo
        self._listo.set()
        try:
            while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    clave = self._por_id.get(int(msg.wParam))
                    if clave is not None and not self._pausado:
                        try:
                            self._al_atajo(clave)
                        except Exception:  # el hilo no debe morir por un fallo del que escucha
                            pass
                elif msg.message == WM_APP and self._procesar_ordenes():
                    break
        finally:
            self._liberar()
            self._vaciar_ordenes()

    def _procesar_ordenes(self) -> bool:
        """Atiende lo pedido. Devuelve ``True`` si hay que terminar."""
        terminar = False
        while True:
            try:
                orden, args, hecho, respuesta = self._ordenes.get_nowait()
            except queue.Empty:
                return terminar
            try:
                if orden == "aplicar":
                    self._mapa = dict(args[0])
                    respuesta.append(self._registrar_todo())
                elif orden == "pausar":
                    self._pausado = True
                    self._liberar()
                elif orden == "reanudar":
                    self._pausado = False
                    respuesta.append(self._registrar_todo())
                elif orden == "probar":
                    respuesta.append(self._probar(args[0]))
                elif orden == "parar":
                    terminar = True
            except Exception as e:  # lo que falle se devuelve a quien lo pidió
                respuesta.append(e)
            hecho.set()
            if terminar:
                return True

    def _registrar_todo(self) -> dict[Clave, Resultado]:
        self._liberar()
        resultados: dict[Clave, Resultado] = {}
        for clave, comb in self._mapa.items():
            if self._pausado:
                resultados[clave] = Resultado(True)  # se registrará al reanudar
                continue
            identificador = self._siguiente_id
            self._siguiente_id += 1
            if _user32.RegisterHotKey(None, identificador, comb.banderas | MOD_NOREPEAT, comb.vk):
                self._por_id[identificador] = clave
                self._ids[clave] = identificador
                resultados[clave] = Resultado(True)
            else:
                resultados[clave] = Resultado(False, ctypes.get_last_error())
        return resultados

    def _liberar(self) -> None:
        for identificador in list(self._por_id):
            _user32.UnregisterHotKey(None, identificador)
        self._por_id.clear()
        self._ids.clear()

    @staticmethod
    def _probar(comb: Combinacion) -> Resultado:
        if _user32.RegisterHotKey(None, _ID_PRUEBA, comb.banderas | MOD_NOREPEAT, comb.vk):
            _user32.UnregisterHotKey(None, _ID_PRUEBA)
            return Resultado(True)
        return Resultado(False, ctypes.get_last_error())

    def _vaciar_ordenes(self) -> None:
        """Si el hilo termina con peticiones sin atender, se avisa a quien espera."""
        while True:
            try:
                _, _, hecho, respuesta = self._ordenes.get_nowait()
            except queue.Empty:
                return
            respuesta.append(ErrorTeclado("el hilo de atajos terminó."))
            hecho.set()


# --- Lectura del teclado para grabar combinaciones ---------------------------------------------------------------------
def leer_modificadores() -> frozenset[str]:
    """Modificadores pulsados ahora mismo (incluye la tecla Windows, que Tk no da)."""
    mods = {nombre for nombre, vk in _VK_MODIFICADORES.items() if _user32.GetAsyncKeyState(vk) & 0x8000}
    if any(_user32.GetAsyncKeyState(vk) & 0x8000 for vk in _VK_WIN):
        mods.add("Win")
    return frozenset(mods)


def caracter_con_altgr(comb: Combinacion) -> str | None:
    """El carácter que esa combinación escribe con AltGr en la distribución de teclado actual, o ``None``.

    Windows trata AltGr como Ctrl+Alt: un atajo con Ctrl+Alt+<esa tecla> impediría escribir ese carácter.
    """
    if not {"Ctrl", "Alt"} <= comb.mods or "Win" in comb.mods:
        return None
    estado = (ctypes.c_ubyte * 256)()
    for nombre in ("Ctrl", "Alt"):
        estado[_VK_MODIFICADORES[nombre]] = 0x80
    if "Shift" in comb.mods:
        estado[_VK_MODIFICADORES["Shift"]] = 0x80
    distribucion = _user32.GetKeyboardLayout(0)
    escaneo = _user32.MapVirtualKeyExW(comb.vk, 0, distribucion)
    texto = ctypes.create_unicode_buffer(8)
    n = _user32.ToUnicodeEx(comb.vk, escaneo, estado, texto, 8, 0x4, distribucion)  # 0x4: no altera el estado del teclado
    if n >= 1 and texto[0].isprintable() and not texto[0].isspace():
        return texto[0]
    return None
