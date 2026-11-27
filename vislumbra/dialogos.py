# SPDX-License-Identifier: GPL-3.0-or-later
"""Diálogos con el tema oscuro de la maqueta (sustituyen a los de Tk, que salen claros).

Ventana sin barra, con cabecera propia como el panel. ``Dialogo`` no bloquea: ``ejecutar`` lo
muestra y espera el resultado; las pruebas usan ``Dialogo`` directamente.
"""

from __future__ import annotations

import tkinter as tk

from . import sistema
from .widgets import (
    ACENTO, BORDE_BOTON, BORDE_VENTANA, CABECERA, CAMPO, FONDO_VENTANA, LINEA, TEXTO, Boton, fuente, nueva_posicion, px,
    rect_redondeado,
)

ACEPTAR = "__aceptar__"  # valor de un botón que devuelve el texto escrito


class Dialogo(tk.Toplevel):
    """Mensaje con botones y, si ``campo`` no es ``None``, una línea de texto con ese valor inicial.

    ``botones``: lista de ``(texto, valor, estilo)``. ``resultado`` es el valor del botón pulsado
    (``ACEPTAR`` devuelve el texto escrito) o ``cancelar`` si se cierra con la ✕ o con Escape.
    """

    ANCHO_TEXTO = 340

    def __init__(self, raiz: tk.Misc, titulo: str, mensaje: str, botones: list[tuple[str, object, str]], campo: str | None = None, cancelar: object = None):
        super().__init__(raiz)
        self.withdraw()
        self.resultado = cancelar
        self._cancelar = cancelar
        self._entrada: tk.Entry | None = None
        self._arrastre: tuple[int, int, int, int] | None = None
        self.overrideredirect(True)
        self.configure(bg=BORDE_VENTANA)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        marco = tk.Frame(self, bg=FONDO_VENTANA)
        marco.pack(fill="both", expand=True, padx=1, pady=1)
        cab = tk.Frame(marco, bg=CABECERA, height=px(36))
        cab.pack(fill="x")
        cab.pack_propagate(False)
        lbl = tk.Label(cab, text=titulo, bg=CABECERA, fg=TEXTO, font=fuente(13, True))
        lbl.pack(side="left", padx=(px(14), 0))
        Boton(cab, "✕", lambda: self._cerrar(self._cancelar), estilo="limpio", alto=28, ancho=28, relleno=0, tam=15).pack(side="right", padx=(0, px(4)))
        for w in (cab, lbl):
            w.bind("<ButtonPress-1>", self._arrastre_inicio)
            w.bind("<B1-Motion>", self._arrastre_mover)
        tk.Frame(marco, bg=LINEA, height=1).pack(fill="x")
        cuerpo = tk.Frame(marco, bg=FONDO_VENTANA, padx=px(16), pady=px(16))
        cuerpo.pack(fill="both", expand=True)
        tk.Label(
            cuerpo, text=mensaje, bg=FONDO_VENTANA, fg=TEXTO, font=fuente(13), anchor="w", justify="left", wraplength=px(self.ANCHO_TEXTO),
        ).pack(fill="x")
        if campo is not None:
            self._crear_campo(cuerpo, campo)
        fila = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        fila.pack(fill="x", pady=(px(16), 0))
        self.botones: list[Boton] = []
        for texto, valor, estilo in reversed(botones):
            b = Boton(fila, texto, lambda v=valor: self._cerrar(v), estilo=estilo, minimo=76)
            b.pack(side="right", padx=(px(8), 0))
            self.botones.insert(0, b)
        self._por_defecto = next((v for _, v, e in botones if e == "activo"), None)
        self.bind("<Escape>", lambda e: self._cerrar(self._cancelar))
        self.bind("<Return>", lambda e: self._cerrar(self._por_defecto) if self._por_defecto is not None else None)

    def _crear_campo(self, padre: tk.Misc, inicial: str) -> None:
        ancho, alto = px(self.ANCHO_TEXTO), px(32)
        c = tk.Canvas(padre, width=ancho, height=alto, bg=FONDO_VENTANA, highlightthickness=0)
        c.pack(pady=(px(12), 0))
        rect_redondeado(c, 0.5, 0.5, ancho - 0.5, alto - 0.5, px(7), fill=CAMPO, outline=BORDE_BOTON, tags="borde")
        self._var = tk.StringVar(master=self, value=inicial)
        self._entrada = tk.Entry(c, textvariable=self._var, bg=CAMPO, fg=TEXTO, insertbackground=TEXTO, relief="flat", bd=0, highlightthickness=0, font=fuente(13))
        c.create_window(px(8), alto / 2, window=self._entrada, anchor="w", width=ancho - px(16), height=px(20))
        self._entrada.bind("<FocusIn>", lambda e: self._borde(c, True))
        self._entrada.bind("<FocusOut>", lambda e: self._borde(c, False))
        self._entrada.bind("<Button-1>", lambda e: self._entrada.focus_force(), add="+")

    @staticmethod
    def _borde(c: tk.Canvas, enfocado: bool) -> None:
        c.delete("borde")
        ancho, alto = int(c.cget("width")), int(c.cget("height"))
        rect_redondeado(c, 0.5, 0.5, ancho - 0.5, alto - 0.5, px(7), fill=CAMPO, outline=ACENTO if enfocado else BORDE_BOTON, tags="borde")
        c.tag_lower("borde")

    # -- resultado ------------------------------------------------------------------------------------------
    def _cerrar(self, valor: object) -> None:
        if valor == ACEPTAR and self._entrada is not None:
            valor = self._var.get()
        self.resultado = valor
        self.grab_release()
        self.destroy()

    # -- arrastrar ------------------------------------------------------------------------------------------
    def _arrastre_inicio(self, e) -> None:
        self._arrastre = (e.x_root, e.y_root, self.winfo_x(), self.winfo_y())

    def _arrastre_mover(self, e) -> None:
        if self._arrastre is None:
            return
        rx, ry, vx, vy = self._arrastre
        x, y = nueva_posicion((vx, vy), (rx, ry), (e.x_root, e.y_root))
        self.geometry(f"+{x}+{y}")

    # -- mostrar --------------------------------------------------------------------------------------------
    def mostrar(self, sobre: tk.Misc) -> None:
        """Lo centra sobre ``sobre`` (sin salirse de la pantalla), lo muestra y le da el foco."""
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = sobre.winfo_rootx() + (sobre.winfo_width() - w) // 2
        y = sobre.winfo_rooty() + (sobre.winfo_height() - h) // 3
        x, y = sistema.limitar_al_area(x, y, w, h, sistema.area_de_trabajo())
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        sistema.redondear_ventana(self, BORDE_VENTANA)
        self.lift()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()
        if self._entrada is not None:
            self._entrada.focus_force()
            self._entrada.select_range(0, "end")


def ejecutar(raiz: tk.Misc, dialogo: Dialogo) -> object:
    dialogo.mostrar(raiz)
    dialogo.wait_window()
    return dialogo.resultado


# --- Los tres diálogos que usa el panel -------------------------------------------------------------------------
def preguntar_texto(raiz: tk.Misc, titulo: str, mensaje: str, inicial: str) -> str | None:
    d = Dialogo(raiz, titulo, mensaje, [("Aceptar", ACEPTAR, "activo"), ("Cancelar", None, "normal")], campo=inicial)
    return ejecutar(raiz, d)  # type: ignore[return-value]


def confirmar(raiz: tk.Misc, titulo: str, mensaje: str) -> bool:
    d = Dialogo(raiz, titulo, mensaje, [("Sí", True, "activo"), ("No", False, "normal")], cancelar=False)
    return bool(ejecutar(raiz, d))


def preguntar_guardar(raiz: tk.Misc) -> bool | None:
    """``True`` guardar, ``False`` descartar, ``None`` volver."""
    d = Dialogo(
        raiz, "Cambios sin guardar", "Hay perfiles con cambios sin guardar.",
        [("Guardar", True, "activo"), ("Descartar", False, "normal"), ("Cancelar", None, "normal")], cancelar=None,
    )
    return ejecutar(raiz, d)  # type: ignore[return-value]
