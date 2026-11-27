# SPDX-License-Identifier: GPL-3.0-or-later
"""Abre el panel con perfiles de ejemplo y guarda un PNG de la ventana (para compararlo con la maqueta).

No toca la gamma: el controlador es falso y no hay aplicador ni bandeja. La ventana aparece
unos segundos en la pantalla; no hay que tocarla ni taparla.

Uso: python herramientas/captura_panel.py [salida.png] [--monitores N] [--normal]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk  # noqa: E402

from PIL import ImageGrab  # noqa: E402

from vislumbra import color, sistema  # noqa: E402
from vislumbra.estado import Estado  # noqa: E402
from vislumbra.panel import Panel  # noqa: E402
from vislumbra.perfiles import Configuracion, Perfil  # noqa: E402


@dataclass(frozen=True)
class Mon:
    numero: int
    clave: str
    principal: bool = False


class ControladorFalso:
    def rampas_cambiaron(self) -> None: ...
    def persistir(self) -> None: ...
    def ocultar_panel(self) -> None: ...
    def salir(self) -> None: ...


def montar(raiz: tk.Tk, monitores: int = 3, normal: bool = False) -> Panel:
    """Panel con los perfiles de ejemplo de la maqueta (Oscuro activo, el monitor 3 fijo en Código)."""
    conf = Configuracion()
    conf.guardar(Perfil("Oscuro", color.Ajuste.uniforme(0.0, 7.5, 1.7)))
    conf.guardar(Perfil("Muy oscuro", color.Ajuste.uniforme(0.0, 7.5, 2.5)))
    conf.guardar(Perfil("Código", color.Ajuste.uniforme(-20.0, 5.0, 1.0, 6000.0)))
    mons = [Mon(1, "m-1"), Mon(2, "m-2", True), Mon(3, "m-3")][:monitores]
    estado = Estado(conf, mons)
    if not normal:
        estado.cambiar_activo("Oscuro")
        if monitores >= 3:
            estado.fijar_monitor(3, "Código")
    estado.mirar(1)
    panel = Panel(raiz, estado, ControladorFalso())
    panel.refrescar()
    return panel


def capturar(raiz: tk.Tk, salida: Path) -> tuple[int, int]:
    raiz.geometry("+80+60")
    raiz.deiconify()
    raiz.attributes("-topmost", True)
    for _ in range(6):  # deja que Tk dibuje todo
        raiz.update_idletasks()
        raiz.update()
        raiz.after(60)
    x, y, w, h = raiz.winfo_rootx(), raiz.winfo_rooty(), raiz.winfo_width(), raiz.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(salida)
    return w, h


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("salida", nargs="?", default="captura-panel.png", type=Path)
    ap.add_argument("--monitores", type=int, default=3, choices=(1, 2, 3))
    ap.add_argument("--normal", action="store_true", help="con «Normal» activo (nada fijo)")
    a = ap.parse_args()
    sistema.activar_dpi()
    raiz = tk.Tk()
    panel = montar(raiz, a.monitores, a.normal)
    panel.mostrar()
    w, h = capturar(raiz, a.salida)
    print(f"Captura de {w} × {h} px en {a.salida} (escala de Tk: {raiz.winfo_fpixels('1i') / 96:.2f})")
    raiz.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
