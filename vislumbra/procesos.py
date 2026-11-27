# SPDX-License-Identifier: GPL-3.0-or-later
"""Lista de procesos en ejecución (solo los nombres de sus ejecutables), con ``ctypes``.

Es lo mismo que hace el Administrador de tareas: no abre los procesos ni toca su memoria, así
que sirve también para programas ejecutados como administrador. Ni inyecta nada ni modifica nada.
"""

from __future__ import annotations

import ctypes
from collections.abc import Collection
from ctypes import wintypes

_TH32CS_SNAPPROCESS = 0x00000002
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _ProcessEntry32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
_k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessEntry32)]
_k32.Process32FirstW.restype = wintypes.BOOL
_k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ProcessEntry32)]
_k32.Process32NextW.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [ctypes.c_void_p]
_k32.CloseHandle.restype = wintypes.BOOL


class ErrorProcesos(OSError):
    pass


def _procesos() -> list[tuple[int, str]]:
    """(PID, nombre en minúsculas) de todos los procesos."""
    instantanea = _k32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if instantanea is None or instantanea == _INVALID_HANDLE_VALUE:
        raise ErrorProcesos(f"no se pudo leer la lista de procesos (código {ctypes.get_last_error()}).")
    try:
        entrada = _ProcessEntry32()
        entrada.dwSize = ctypes.sizeof(_ProcessEntry32)
        lista: list[tuple[int, str]] = []
        ok = _k32.Process32FirstW(instantanea, ctypes.byref(entrada))
        while ok:
            lista.append((int(entrada.th32ProcessID), entrada.szExeFile.lower()))
            ok = _k32.Process32NextW(instantanea, ctypes.byref(entrada))
        return lista
    finally:
        _k32.CloseHandle(instantanea)


def nombres_en_ejecucion() -> frozenset[str]:
    """Nombres (en minúsculas) de los ejecutables de todos los procesos en ejecución."""
    return frozenset(nombre for _, nombre in _procesos())


# --- Monitor donde está la ventana de cada programa ---------------------------------------------------------
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_dwm = ctypes.WinDLL("dwmapi")
_ENUMERAR = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class _InfoMonitor(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32),
    ]


_user32.EnumWindows.argtypes = [_ENUMERAR, wintypes.LPARAM]
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsIconic.argtypes = [wintypes.HWND]
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.MonitorFromWindow.restype = ctypes.c_void_p
_user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_InfoMonitor)]
_user32.GetMonitorInfoW.restype = wintypes.BOOL
_GWL_EXSTYLE, _WS_EX_TOOLWINDOW, _DWMWA_CLOAKED = -20, 0x80, 14
_MONITOR_DEFAULTTONEAREST = 2
AREA_MINIMA = 200 * 150  # las ventanas más pequeñas (ayudas, avisos) no cuentan


def monitores_de_ventanas(programas: Collection[str]) -> dict[str, str]:
    """Para cada programa de ``programas`` con una ventana visible: el dispositivo del monitor donde está
    (``\\.\DISPLAY1``). Cuenta la ventana visible más grande; se ignoran las minimizadas, las de herramienta, las
    ocultas y las diminutas. Los programas sin ventana visible no aparecen. Solo lee: no toca ninguna ventana.
    """
    if not programas:
        return {}
    por_pid = {pid: nombre for pid, nombre in _procesos() if nombre in programas}
    if not por_pid:
        return {}
    mejor: dict[str, tuple[int, str]] = {}

    def revisar(hwnd, _lparam) -> bool:
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        nombre = por_pid.get(int(pid.value))
        if nombre is None or not _user32.IsWindowVisible(hwnd) or _user32.IsIconic(hwnd):
            return True
        if _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE) & _WS_EX_TOOLWINDOW:
            return True
        oculta = wintypes.DWORD(0)
        _dwm.DwmGetWindowAttribute(hwnd, _DWMWA_CLOAKED, ctypes.byref(oculta), 4)
        if oculta.value:
            return True
        r = wintypes.RECT()
        if not _user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return True
        area = max(0, r.right - r.left) * max(0, r.bottom - r.top)
        if area < AREA_MINIMA:
            return True
        info = _InfoMonitor()
        info.cbSize = ctypes.sizeof(_InfoMonitor)
        if not _user32.GetMonitorInfoW(_user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST), ctypes.byref(info)):
            return True
        if nombre not in mejor or area > mejor[nombre][0]:
            mejor[nombre] = (area, info.szDevice)
        return True

    _user32.EnumWindows(_ENUMERAR(revisar), 0)
    return {nombre: dispositivo for nombre, (_, dispositivo) in mejor.items()}


def nombres_ordenados() -> list[str]:
    """Para elegir un programa en la lista: sin repetidos, solo ``.exe`` y sin los del sistema más comunes."""
    return sorted(n for n in nombres_en_ejecucion() if n.endswith(".exe") and n not in _DEL_SISTEMA)


_DEL_SISTEMA = frozenset({
    "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "svchost.exe",
    "winlogon.exe", "fontdrvhost.exe", "dwm.exe", "conhost.exe", "dllhost.exe", "runtimebroker.exe", "sihost.exe",
    "taskhostw.exe", "ctfmon.exe", "searchindexer.exe", "spoolsv.exe", "wudfhost.exe", "audiodg.exe", "memcompression",
})
