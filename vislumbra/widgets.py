# SPDX-License-Identifier: GPL-3.0-or-later
"""Tema y widgets dibujados en ``Canvas`` para el panel (Tk no hace esquinas redondeadas ni degradados).

Los colores y las medidas salen del CSS de la maqueta aprobada (``docs/diseno-panel-maqueta.md``).
Las medidas se dan en píxeles de la maqueta (100 % de escala) y se pasan por ``px()``, que las
ajusta al DPI de la ventana. Aquí no hay lógica de la app: solo dibujo y gestos.
"""

from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import font as tkfont

# --- Tema (CSS de la maqueta) ----------------------------------------------------------------------
FONDO_VENTANA = "#1d1d1a"
CABECERA = "#191916"
BORDE_VENTANA = "#34332d"
LINEA = "#2c2b26"
BOTON = "#2a2925"
BOTON_HOVER = "#34332d"
BORDE_BOTON = "#45443c"
CAMPO = "#141412"
PESTANA = "#23221f"
PESTANA_ACTIVA = "#2f2d26"
TEXTO = "#ece8dc"
TEXTO_SUAVE = "#a7a392"
TEXTO_OSCURO = "#1d1d1a"
ACENTO = "#c9b98f"
ACENTO_HOVER = "#d6c8a2"
OLIVA = "#8c8a5e"
PISTA = "#3a3933"
MARCA_NEUTRO = "#6d6b5c"
VERDE = "#9cc47a"
AVISO = "#e8b062"
AVISO_MARGEN = "#e0a050"
PELIGRO = "#e06a5a"
CANAL = {"r": "#e0705a", "g": "#7fbf6a", "b": "#6a9be0"}
DEGRADADO_TEMPERATURA = ("#d98a45", "#d8d4c8", "#6f9be0")
FUERTE_FONDO = "#3a2c17"
FUERTE_BORDE = "#8a6328"
CASILLA_VACIA = "#f0ede4"
CASILLA_BORDE = "#8c8a7c"

_ESCALA = 1.0


def fijar_escala(raiz: tk.Misc) -> float:
    """Toma la escala de pantalla (DPI / 96) de Tk; ``px()`` la aplica a todas las medidas."""
    global _ESCALA
    try:
        _ESCALA = max(1.0, raiz.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        _ESCALA = 1.0
    return _ESCALA


def px(n: float) -> int:
    return int(round(n * _ESCALA))


def fuente(tam: float, negrita: bool = False) -> tuple:
    """Fuente de ``tam`` píxeles de la maqueta (tamaño negativo en Tk = píxeles)."""
    base = ("Segoe UI", -px(tam))
    return base + ("bold",) if negrita else base


# --- Utilidades puras --------------------------------------------------------------------------------
def _rgb(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def mezclar(a: str, b: str, t: float) -> str:
    """Color entre ``a`` (t = 0) y ``b`` (t = 1)."""
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ra, rb))


def degradado(colores: Sequence[str], t: float) -> str:
    """Color del degradado de varias paradas igualmente espaciadas en ``t`` (0..1)."""
    t = min(1.0, max(0.0, t))
    if len(colores) == 1:
        return colores[0]
    tramo = t * (len(colores) - 1)
    i = min(int(tramo), len(colores) - 2)
    return mezclar(colores[i], colores[i + 1], tramo - i)


def nueva_posicion(origen_ventana: tuple[int, int], origen_raton: tuple[int, int], raton: tuple[int, int]) -> tuple[int, int]:
    """Esquina de la ventana al arrastrar la cabecera: se mueve lo mismo que el ratón."""
    return origen_ventana[0] + raton[0] - origen_raton[0], origen_ventana[1] + raton[1] - origen_raton[1]


def _puntos_redondeados(x0: float, y0: float, x1: float, y1: float, r: float, n: int = 8) -> list[float]:
    pts: list[float] = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


def rect_redondeado(c: tk.Canvas, x0: float, y0: float, x1: float, y1: float, r: float, outline: str | None = None, **kw) -> int:
    """Rectángulo con esquinas redondeadas en un lienzo. Con ``outline`` el borde (de 1 px) es otro polígono debajo:
    el contorno de Tk sale discontinuo en las curvas. Devuelve el polígono exterior."""
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    relleno = kw.pop("fill", "")
    if outline and outline != relleno:
        ext = c.create_polygon(_puntos_redondeados(x0, y0, x1, y1, r), fill=outline, outline="", **kw)
        c.create_polygon(_puntos_redondeados(x0 + 1, y0 + 1, x1 - 1, y1 - 1, max(0.0, r - 1)), fill=relleno, outline="", **kw)
        return ext
    return c.create_polygon(_puntos_redondeados(x0, y0, x1, y1, r), fill=relleno, outline="", **kw)


def _lienzo(master, **kw) -> dict:
    return dict(bg=master.cget("bg"), highlightthickness=0, bd=0, **kw)


# --- Botón --------------------------------------------------------------------------------------------
class Boton(tk.Canvas):
    """Botón de esquinas redondeadas. ``configure(text=, state=, estilo=, punto=)`` y ``cget`` como un ``tk.Button``."""

    ESTILOS = {
        "normal": (BOTON, BORDE_BOTON, TEXTO, BOTON_HOVER),
        "activo": (ACENTO, ACENTO, TEXTO_OSCURO, ACENTO_HOVER),
        "limpio": (None, None, TEXTO, BOTON_HOVER),
        "chip": (PESTANA, BORDE_BOTON, TEXTO, BOTON_HOVER),
    }

    def __init__(
        self, master, texto: str = "", comando: Callable[[], None] | None = None, estilo: str = "normal", alto: int = 32,
        radio: int = 7, tam: int = 13, ancho: int | None = None, minimo: int = 0, relleno: int = 12, punto: str | None = None,
        negrita: bool = False,
    ):
        super().__init__(master, cursor="hand2", takefocus=False, **_lienzo(master))
        self._texto, self._estado, self._estilo, self._punto = texto, "normal", estilo, punto
        self._comando, self._alto, self._radio = comando, alto, radio
        self._ancho, self._minimo, self._relleno = ancho, minimo, relleno
        self._fuente = tkfont.Font(root=master, font=fuente(tam, negrita))
        self._encima = self._pulsado = False
        self._ancho_px = 0
        self._medir()
        self.bind("<Configure>", lambda e: self._dibujar())
        self.bind("<Enter>", lambda e: self._poner(encima=True))
        self.bind("<Leave>", lambda e: self._poner(encima=False, pulsado=False))
        self.bind("<ButtonPress-1>", lambda e: self._poner(pulsado=True))
        self.bind("<ButtonRelease-1>", self._soltar)

    # -- API como tk.Button --------------------------------------------------------------------------------
    def configure(self, cnf=None, **kw):
        if cnf:
            kw = {**cnf, **kw}
        propios = {k: kw.pop(k) for k in ("text", "state", "estilo", "punto", "command") if k in kw}
        if "text" in propios:
            self._texto = propios["text"]
        if "state" in propios:
            self._estado = str(propios["state"])
        if "estilo" in propios:
            self._estilo = propios["estilo"]
        if "punto" in propios:
            self._punto = propios["punto"]
        if "command" in propios:
            self._comando = propios["command"]
        if kw:
            super().configure(**kw)
        if propios:
            self._medir()
            self._dibujar()

    config = configure

    def cget(self, clave):
        if clave == "text":
            return self._texto
        if clave == "state":
            return self._estado
        return super().cget(clave)

    # -- gestos ---------------------------------------------------------------------------------------------
    def _poner(self, encima: bool | None = None, pulsado: bool | None = None) -> None:
        if encima is not None:
            self._encima = encima
        if pulsado is not None:
            self._pulsado = pulsado
        self._dibujar()

    def _soltar(self, e) -> None:
        era = self._pulsado
        self._pulsado = False
        self._dibujar()
        dentro = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        if era and dentro and self._estado != "disabled" and self._comando is not None:
            self._comando()

    def invocar(self) -> None:
        if self._estado != "disabled" and self._comando is not None:
            self._comando()

    # -- dibujo ---------------------------------------------------------------------------------------------
    def _medir(self) -> None:
        w = self._fuente.measure(self._texto) + 2 * px(self._relleno) + (px(18) if self._punto else 0)
        w = px(self._ancho) if self._ancho else max(w, px(self._minimo))
        self._ancho_px = w
        super().configure(width=w, height=px(self._alto))

    def _dibujar(self) -> None:
        self.delete("all")
        w = self.winfo_width() if self.winfo_width() > 1 else self._ancho_px
        h = px(self._alto)
        fondo, borde, texto, hover = self.ESTILOS[self._estilo]
        base = self.cget("bg")
        relleno = fondo or base
        if self._estado == "disabled":
            texto, borde = mezclar(base, texto, 0.45), (mezclar(base, borde, 0.45) if borde else None)
            relleno = mezclar(base, relleno, 0.45) if fondo else base
        elif self._encima:
            relleno = hover
        rect_redondeado(self, 0.5, 0.5, w - 0.5, h - 0.5, px(self._radio), fill=relleno, outline=borde or relleno)
        x = w / 2
        ancla = "center"
        if self._punto:
            self.create_oval(px(12), h / 2 - px(5), px(22), h / 2 + px(5), fill=self._punto, outline="")
            x, ancla = px(30), "w"
        self.create_text(x, h / 2, text=self._texto, fill=texto, font=self._fuente, anchor=ancla)


# --- Casilla --------------------------------------------------------------------------------------------
class Casilla(tk.Canvas):
    """Casilla con texto, ligada a una ``BooleanVar``. Al pulsar cambia la variable y llama al comando (como ``tk.Checkbutton``)."""

    def __init__(self, master, texto: str, variable: tk.BooleanVar, comando: Callable[[], None] | None = None, tam: int = 13):
        super().__init__(master, cursor="hand2", takefocus=False, **_lienzo(master))
        self._texto, self._var, self._comando, self._estado = texto, variable, comando, "normal"
        self._fuente = tkfont.Font(root=master, font=fuente(tam))
        super().configure(width=px(24) + self._fuente.measure(texto) + px(2), height=px(24))
        variable.trace_add("write", lambda *a: self._dibujar())
        self.bind("<ButtonRelease-1>", self._pulsar)
        self.bind("<Configure>", lambda e: self._dibujar())
        self._dibujar()

    def configure(self, cnf=None, **kw):
        if cnf:
            kw = {**cnf, **kw}
        if "state" in kw:
            self._estado = str(kw.pop("state"))
        if "text" in kw:
            self._texto = kw.pop("text")
        if kw:
            super().configure(**kw)
        self._dibujar()

    config = configure

    def cget(self, clave):
        if clave == "state":
            return self._estado
        if clave == "text":
            return self._texto
        return super().cget(clave)

    def _pulsar(self, _e) -> None:
        if self._estado == "disabled":
            return
        self._var.set(not self._var.get())
        if self._comando is not None:
            self._comando()

    def _dibujar(self) -> None:
        self.delete("all")
        h = px(24)
        base = self.cget("bg")
        apagada = self._estado == "disabled"
        marcada = bool(self._var.get())
        y0 = (h - px(16)) / 2
        relleno = ACENTO if marcada else CASILLA_VACIA
        borde = relleno if marcada else CASILLA_BORDE
        if apagada:
            relleno, borde = mezclar(base, relleno, 0.45), mezclar(base, borde, 0.45)
        rect_redondeado(self, 0.5, y0 + 0.5, px(16) - 0.5, y0 + px(16) - 0.5, px(3), fill=relleno, outline=borde)
        if marcada:
            self.create_line(
                px(3.5), y0 + px(8.5), px(6.5), y0 + px(11.5), px(12.5), y0 + px(4.5),
                fill=TEXTO_OSCURO, width=max(2, px(2)), capstyle="round", joinstyle="round",
            )
        self.create_text(px(24), h / 2, text=self._texto, fill=mezclar(base, TEXTO, 0.45) if apagada else TEXTO, font=self._fuente, anchor="w")


# --- Tarjeta --------------------------------------------------------------------------------------------
class Tarjeta(tk.Frame):
    """Marco con borde y esquinas redondeadas. Los hijos se empaquetan dentro como en un ``Frame``.

    ``inset``: color de una raya interior abajo (la pestaña de monitor seleccionada).
    """

    def __init__(self, master, fondo: str, borde: str, radio: int = 10, padx: int = 12, pady: int = 12, inset: str | None = None, **kw):
        super().__init__(master, bg=fondo, padx=px(padx), pady=px(pady), **kw)
        self.fondo, self.borde, self.radio, self.inset = fondo, borde, radio, inset
        self._fuera = master.cget("bg")
        self.lienzo = tk.Canvas(self, bg=self._fuera, highlightthickness=0, bd=0)
        # padx/pady de un Frame son su borde interno: ``place`` mide dentro de él, así que se compensa
        self.lienzo.place(x=-px(padx), y=-px(pady), relwidth=1, relheight=1, width=2 * px(padx), height=2 * px(pady))
        tk.Misc.lower(self.lienzo)  # Canvas.lower mueve elementos: aquí hay que bajar el widget
        self.lienzo.bind("<Configure>", lambda e: self._pintar())

    def _pintar(self) -> None:
        c = self.lienzo
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        rect_redondeado(c, 0.5, 0.5, w - 0.5, h - 0.5, px(self.radio), fill=self.fondo, outline=self.borde)
        if self.inset:
            y = h - 1 - px(1.5)
            c.create_line(px(self.radio) * 0.7, y, w - px(self.radio) * 0.7, y, fill=self.inset, width=px(3))


# --- Texto con dos estilos ----------------------------------------------------------------------------
class TextoMixto(tk.Canvas):
    """Una etiqueta cuyo texto se parte en dos tramos con estilo distinto («Editando» + «Oscuro»).

    El texto se parte en la primera aparición de ``separador``. Con ``lados`` el segundo tramo va
    pegado a la derecha. ``cget("text")`` devuelve el texto completo (como un ``tk.Label``).
    """

    def __init__(self, master, separador: str, tam1: int, color1: str, tam2: int, color2: str, negrita2: bool = False, lados: bool = False, alto: int = 22):
        super().__init__(master, **_lienzo(master))
        self._sep, self._lados, self._alto = separador, lados, alto
        self._f1 = tkfont.Font(root=master, font=fuente(tam1))
        self._f2 = tkfont.Font(root=master, font=fuente(tam2, negrita2))
        self._c1, self._c2 = color1, color2
        self._texto = ""
        super().configure(height=px(alto), width=px(10))
        self.bind("<Configure>", lambda e: self._dibujar())

    def configure(self, cnf=None, **kw):
        if cnf:
            kw = {**cnf, **kw}
        if "text" in kw:
            self._texto = kw.pop("text")
        if kw:
            super().configure(**kw)
        self._dibujar()

    config = configure

    def cget(self, clave):
        return self._texto if clave == "text" else super().cget(clave)

    def _partes(self) -> tuple[str, str]:
        i = self._texto.find(self._sep)
        if i < 0:
            return self._texto, ""
        return self._texto[:i], self._texto[i + len(self._sep):]

    def _dibujar(self) -> None:
        self.delete("all")
        a, b = self._partes()
        h = px(self._alto)
        self.create_text(0, h / 2, text=a, fill=self._c1, font=self._f1, anchor="w")
        if not b:
            return
        if self._lados:
            self.create_text(max(self.winfo_width(), 1), h / 2, text=b, fill=self._c2, font=self._f2, anchor="e")
            return
        x = self._f1.measure(a + self._sep)
        self.create_text(x, h / 2, text=b, fill=self._c2, font=self._f2, anchor="w")
        if not self._lados:
            super().configure(width=x + self._f2.measure(b) + px(2))


# --- Logo ----------------------------------------------------------------------------------------------
def dibujar_logo(c: tk.Canvas, lado: int = 16) -> None:
    """Glifo del logo (los tres polígonos del SVG de la maqueta, en un lienzo de 24 × 24)."""
    k = px(lado) / 24
    formas = (
        (((3, 3), (11, 3), (11, 6), (6, 6), (6, 11), (3, 11)), "#d8c9a0"),
        (((21, 21), (13, 21), (13, 18), (18, 18), (18, 13), (21, 13)), "#d8c9a0"),
        (((15, 3), (19, 3), (9, 21), (5, 21)), OLIVA),
    )
    for puntos, col in formas:
        c.create_polygon([v * k for p in puntos for v in p], fill=col, outline="")
