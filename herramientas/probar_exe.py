# SPDX-License-Identifier: GPL-3.0-or-later
"""Prueba de humo de los ejecutables compilados. **No aplica nada a la pantalla.**

Uso::

    python herramientas/probar_exe.py [carpeta]      # por defecto dist\\Vislumbra

Comprueba, con un ``%APPDATA%`` temporal (nunca el real):

- ``vislumbra-cli.exe``: ``--version``, ``--help``, ``--list``, ``--simulate``, un valor inválido, un
  uso incorrecto y ``--perfil siguiente --simulate``, que importa la app entera (Tk, bandeja, atajos).
- ``Vislumbra.exe`` (sin consola): lanzado **sin** salida estándar, ``--version`` y un error de uso no
  deben romperse; lo que habrían escrito queda en ``vislumbra.log``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CORTO = 60  # segundos: ninguna de estas órdenes debería tardar tanto

# (argumentos, código esperado, texto que debe salir)
CASOS_CLI = [
    (["--version"], 0, "Vislumbra "),
    (["--help"], 0, "Uso: "),
    (["--list"], 0, "DISPLAY"),
    (["--simulate", "--gamma", "1.4"], 0, "El ajuste es válido."),
    (["--gamma", "99"], 1, "fuera del rango"),
    (["--nada"], 2, "argumentos no reconocidos"),
    # Importa la app entera (Tk, bandeja, atajos): si falta un módulo en el .exe, se rompe aquí. Con otra
    # instancia abierta da 2 («con Vislumbra abierta…», sin enviarle nada); ambos resultados prueban que las
    # importaciones funcionan.
    (["--perfil", "siguiente", "--simulate"], (0, 2), ("Simulación", "con Vislumbra abierta")),
]


def _entorno(appdata: Path) -> dict[str, str]:
    return {**os.environ, "APPDATA": str(appdata)}


def _ejecutar(exe: Path, args: list[str], appdata: Path, **extra) -> subprocess.CompletedProcess:
    return subprocess.run([str(exe), *args], env=_entorno(appdata), capture_output=True, timeout=CORTO, **extra)


def _texto(r: subprocess.CompletedProcess) -> str:
    return (r.stdout + r.stderr).decode("utf-8", errors="replace")


def probar_cli(carpeta: Path, appdata: Path) -> list[str]:
    fallos = []
    exe = carpeta / "vislumbra-cli.exe"
    for args, esperado, texto in CASOS_CLI:
        r = _ejecutar(exe, args, appdata)
        salida = _texto(r)
        codigos = esperado if isinstance(esperado, tuple) else (esperado,)
        textos = (texto,) if isinstance(texto, str) else texto
        bien = r.returncode in codigos and any(t in salida for t in textos) and "Traceback" not in salida
        print(f"  {'OK ' if bien else 'MAL'} vislumbra-cli.exe {' '.join(args)}  -> código {r.returncode}")
        if not bien:
            fallos.append(f"vislumbra-cli.exe {' '.join(args)}: código {r.returncode}, salida: {salida.strip()[:300]!r}")
    return fallos


def probar_sin_consola(carpeta: Path, appdata: Path) -> list[str]:
    """``Vislumbra.exe`` sin entrada ni salida estándar (como al abrirlo con doble clic o desde Inicio)."""
    fallos = []
    exe = carpeta / "Vislumbra.exe"
    for args, esperado, texto in ((["--version"], 0, "Vislumbra "), (["--nada"], 2, "argumentos no reconocidos")):
        registro = appdata / "Vislumbra" / "vislumbra.log"
        registro.unlink(missing_ok=True)
        # Sin redirecciones y sin heredar manejadores: el proceso arranca sin stdout ni stderr.
        r = subprocess.run([str(exe), *args], env=_entorno(appdata), timeout=CORTO, close_fds=True,
                           stdin=None, stdout=None, stderr=None, creationflags=0x08000000)  # CREATE_NO_WINDOW
        contenido = registro.read_text(encoding="utf-8", errors="replace") if registro.exists() else ""
        bien = r.returncode == esperado and texto in contenido
        print(f"  {'OK ' if bien else 'MAL'} Vislumbra.exe {' '.join(args)} (sin consola)  -> código {r.returncode}, "
              f"{'queda en vislumbra.log' if texto in contenido else 'NO llegó al registro'}")
        if not bien:
            fallos.append(f"Vislumbra.exe {' '.join(args)} sin consola: código {r.returncode}, registro: {contenido.strip()[:300]!r}")
    return fallos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Prueba de humo de los ejecutables (no toca la pantalla).")
    p.add_argument("carpeta", nargs="?", type=Path, default=RAIZ / "dist" / "Vislumbra")
    carpeta = p.parse_args(argv).carpeta.resolve()
    faltan = [n for n in ("Vislumbra.exe", "vislumbra-cli.exe") if not (carpeta / n).is_file()]
    if faltan:
        print(f"Faltan en {carpeta}: {', '.join(faltan)}. ¿Compilaste con herramientas/compilar.py?", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="vislumbra-humo-") as tmp:
        appdata = Path(tmp)
        print("Con consola:")
        fallos = probar_cli(carpeta, appdata)
        print("Sin consola:")
        fallos += probar_sin_consola(carpeta, appdata)
    if fallos:
        print("\nFALLOS:\n- " + "\n- ".join(fallos), file=sys.stderr)
        return 1
    print("\nTodo bien. (No se ha tocado la pantalla ni el %APPDATA% real.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
