# SPDX-License-Identifier: GPL-3.0-or-later
"""Lista de procesos en ejecución (solo los nombres de sus ejecutables), con ``ctypes``.

Es lo mismo que hace el Administrador de tareas: no abre los procesos ni toca su memoria, así
que sirve también para programas ejecutados como administrador. Ni inyecta nada ni modifica nada.
"""

from __future__ import annotations

import ctypes
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


def nombres_en_ejecucion() -> frozenset[str]:
    """Nombres (en minúsculas) de los ejecutables de todos los procesos en ejecución."""
    instantanea = _k32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if instantanea is None or instantanea == _INVALID_HANDLE_VALUE:
        raise ErrorProcesos(f"no se pudo leer la lista de procesos (código {ctypes.get_last_error()}).")
    try:
        entrada = _ProcessEntry32()
        entrada.dwSize = ctypes.sizeof(_ProcessEntry32)
        nombres: set[str] = set()
        ok = _k32.Process32FirstW(instantanea, ctypes.byref(entrada))
        while ok:
            nombres.add(entrada.szExeFile.lower())
            ok = _k32.Process32NextW(instantanea, ctypes.byref(entrada))
        return frozenset(nombres)
    finally:
        _k32.CloseHandle(instantanea)


def nombres_ordenados() -> list[str]:
    """Para elegir un programa en la lista: sin repetidos, solo ``.exe`` y sin los del sistema más comunes."""
    return sorted(n for n in nombres_en_ejecucion() if n.endswith(".exe") and n not in _DEL_SISTEMA)


_DEL_SISTEMA = frozenset({
    "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "svchost.exe",
    "winlogon.exe", "fontdrvhost.exe", "dwm.exe", "conhost.exe", "dllhost.exe", "runtimebroker.exe", "sihost.exe",
    "taskhostw.exe", "ctfmon.exe", "searchindexer.exe", "spoolsv.exe", "wudfhost.exe", "audiodg.exe", "memcompression",
})
