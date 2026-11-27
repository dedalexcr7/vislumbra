# SPDX-License-Identifier: GPL-3.0-or-later
"""Panel de Vislumbra con Tkinter: deslizador fino, gráfico de la curva y la ventana.

Solo el hilo principal toca Tk. La lógica está en ``estado.py``; aquí solo se dibuja y se
traducen los gestos (arrastrar, rueda, flechas, doble clic, escribir un número) en llamadas
al estado.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence

from . import color, escala

# --- Tema oscuro (de la paleta del logo) --------------------------------------------------------
BG = "#1d1f1b"
SUPERFICIE = "#272a24"
BORDE = "#3a3e35"
TEXTO = "#e6e3d4"
TEXTO_SUAVE = "#9a9c8d"
ACENTO = "#c9b98a"
OLIVA = "#8b8b68"
AVISO = "#e0a15f"
PELIGRO = "#d9694f"
CANAL = {"r": "#e06c5f", "g": "#7fc27a", "b": "#6fa0e0"}
FUENTE = ("Segoe UI", 9)
FUENTE_NEGRITA = ("Segoe UI", 9, "bold")

LIMITE_WINDOWS = 50.0  # % de desviación de la identidad que Windows tolera (deducido en el test de la fase 1)
SHIFT = 0x0001


# --- Funciones puras (se prueban sin Tk) -------------------------------------------------------
def x_a_posicion(x: float, ancho: float, margen: float) -> float:
    """Posición 0..1 del deslizador para una coordenada ``x`` del lienzo."""
    util = max(1.0, ancho - 2 * margen)
    return min(1.0, max(0.0, (x - margen) / util))


def posicion_a_x(p: float, ancho: float, margen: float) -> float:
    return margen + min(1.0, max(0.0, p)) * max(1.0, ancho - 2 * margen)


def puntos_curva(rampa: Sequence[int], ancho: int, alto: int, canal: int, puntos: int = 64) -> list[tuple[float, float]]:
    """Polilínea de un canal (0 = R, 1 = G, 2 = B) en un lienzo de ``ancho`` × ``alto`` (y hacia abajo)."""
    base = canal * color.PUNTOS
    res = []
    for k in range(puntos):
        i = round(k * (color.PUNTOS - 1) / (puntos - 1))
        res.append((k * (ancho - 1) / (puntos - 1), (alto - 1) * (1 - rampa[base + i] / color.MAXIMO)))
    return res


def margen_windows(rampa: Sequence[int]) -> tuple[float, float]:
    """(% usado, % límite) de la desviación de la identidad: «19 % de 50 %»."""
    return 100.0 * color.desviacion(rampa) / color.MAXIMO, LIMITE_WINDOWS


def canales_iguales(rampa: Sequence[int]) -> bool:
    n = color.PUNTOS
    return list(rampa[:n]) == list(rampa[n:2 * n]) == list(rampa[2 * n:])


# --- Deslizador fino ---------------------------------------------------------------------------------
class Deslizador(tk.Frame):
    """Etiqueta, pista, botones − y +, y campo numérico editable.

    Gestos: arrastrar (con Mayús, 10 veces más lento), doble clic (vuelve al neutro), rueda y
    flechas (paso fijo; Mayús = paso fino), escribir un número (coma o punto) y los botones.
    En modo preciso la pista cubre una ventana lineal alrededor del valor, que se recentra al soltar.

    ``al_cambiar(parametro, valor)`` puede devolver el valor realmente aplicado (si hubo tope);
    el deslizador se coloca en él.
    """

    MARGEN = 10
    ALTO = 28

    def __init__(self, master, parametro: str, al_cambiar: Callable[[str, float], float | None]):
        super().__init__(master, bg=BG)
        self.parametro = parametro
        self.par = escala.PARAMETROS[parametro]
        self.al_cambiar = al_cambiar
        self.valor = self.par.neutro
        self.preciso = False
        self._centro = self.par.neutro
        self._ref: tuple[float, float] | None = None  # (posición del ratón, posición del valor) con Mayús
        self._arrastrando = False
        self.columnconfigure(1, weight=1)

        tk.Label(self, text=self.par.etiqueta, width=11, anchor="w", bg=BG, fg=TEXTO, font=FUENTE).grid(row=0, column=0)
        self.pista = tk.Canvas(self, height=self.ALTO, bg=BG, highlightthickness=0, takefocus=True, cursor="hand2")
        self.pista.grid(row=0, column=1, sticky="ew", padx=4)
        self._boton("−", -1).grid(row=0, column=2)
        self.texto = tk.StringVar()
        self.campo = tk.Entry(
            self, textvariable=self.texto, width=7, justify="right", bg=SUPERFICIE, fg=TEXTO,
            insertbackground=TEXTO, relief="flat", highlightthickness=1, highlightbackground=BORDE,
            highlightcolor=ACENTO, font=FUENTE,
        )
        self.campo.grid(row=0, column=3, padx=2)
        self._boton("+", +1).grid(row=0, column=4)
        tk.Label(self, text=self.par.unidad.strip(), width=2, anchor="w", bg=BG, fg=TEXTO_SUAVE, font=FUENTE).grid(row=0, column=5)

        p = self.pista
        p.bind("<Configure>", lambda e: self._dibujar())
        p.bind("<ButtonPress-1>", self._al_pulsar)
        p.bind("<B1-Motion>", self._al_arrastrar)
        p.bind("<ButtonRelease-1>", self._al_soltar)
        p.bind("<Double-Button-1>", self._al_doble_clic)
        for destino in (p, self.campo):
            destino.bind("<MouseWheel>", self._al_rueda)
        for tecla, d in (("<Right>", 1), ("<Up>", 1), ("<Left>", -1), ("<Down>", -1)):
            p.bind(tecla, lambda e, d=d: self._paso(d, bool(e.state & SHIFT)))
        self.campo.bind("<Return>", self._desde_texto)
        self.campo.bind("<FocusOut>", self._desde_texto)
        self.campo.bind("<Escape>", lambda e: self._actualizar_texto())
        self.poner_valor(self.par.neutro)

    def _boton(self, simbolo: str, d: int) -> tk.Button:
        b = tk.Button(
            self, text=simbolo, width=2, bg=SUPERFICIE, fg=TEXTO, activebackground=BORDE, activeforeground=TEXTO,
            relief="flat", bd=0, font=FUENTE, takefocus=False, command=lambda: self._paso(d, False),
        )
        return b

    # -- valor y posición ----------------------------------------------------------------------------------
    def poner_valor(self, valor: float) -> None:
        """Sincroniza con el modelo, sin llamar a ``al_cambiar``."""
        self.valor = escala.redondear(self.parametro, escala.limitar(self.parametro, valor))
        if not self._arrastrando:
            self._centro = self.valor  # solo importa en modo preciso
        self._actualizar_texto()
        self._dibujar()

    def poner_preciso(self, activo: bool) -> None:
        self.preciso = activo
        self._centro = self.valor
        self._dibujar()

    def _posicion(self) -> float:
        if self.preciso:
            return escala.valor_a_posicion_precisa(self.parametro, self.valor, self._centro)
        return escala.valor_a_posicion(self.parametro, self.valor)

    def _valor_en(self, p: float) -> float:
        if self.preciso:
            return escala.posicion_precisa_a_valor(self.parametro, p, self._centro)
        return escala.redondear(self.parametro, escala.posicion_a_valor(self.parametro, p))

    def _actualizar_texto(self) -> None:
        self.texto.set(escala.formatear(self.parametro, self.valor))

    def _pedir(self, valor: float) -> None:
        valor = escala.limitar(self.parametro, valor)
        aplicado = self.al_cambiar(self.parametro, valor)
        self.poner_valor(valor if aplicado is None else aplicado)

    # -- gestos ------------------------------------------------------------------------------------------------
    def _p_raton(self, x: float) -> float:
        return x_a_posicion(x, self.pista.winfo_width(), self.MARGEN)

    def _al_pulsar(self, e) -> None:
        self.pista.focus_set()
        self._arrastrando = True
        self._ref = None
        self._arrastre(e)

    def _arrastre(self, e) -> None:
        pm = self._p_raton(e.x)
        if e.state & SHIFT:
            if self._ref is None:  # al activar Mayús se fija la referencia: desde aquí, 10 veces más lento
                self._ref = (pm, self._posicion())
            p = escala.arrastre_fino(self._ref[1], self._ref[1] + (pm - self._ref[0]))
        else:
            self._ref = None
            p = pm
        self._pedir(self._valor_en(p))

    def _al_arrastrar(self, e) -> None:
        if self._arrastrando:
            self._arrastre(e)

    def _al_soltar(self, _e) -> None:
        self._arrastrando = False
        self._ref = None
        if self.preciso:
            self._centro = self.valor  # recentra la ventana en el valor
        self._dibujar()

    def _al_doble_clic(self, _e=None) -> None:
        self._pedir(self.par.neutro)

    def _al_rueda(self, e) -> str:
        self._paso(1 if e.delta > 0 else -1, bool(e.state & SHIFT))
        return "break"

    def _paso(self, direccion: int, fino: bool) -> None:
        nuevo = escala.paso_rueda(self.parametro, self.valor, direccion, fino=fino or self.preciso)
        self._pedir(nuevo)
        if self.preciso:
            self._centro = self.valor
            self._dibujar()

    def _desde_texto(self, _e=None) -> None:
        n = escala.leer_numero(self.texto.get())
        if n is None:  # no es un número: se vuelve a mostrar el valor actual
            self._actualizar_texto()
            return
        if escala.redondear(self.parametro, escala.limitar(self.parametro, n)) != self.valor:
            self._pedir(n)
        else:
            self._actualizar_texto()
        if self.preciso:
            self._centro = self.valor
            self._dibujar()

    # -- dibujo ----------------------------------------------------------------------------------------------------
    def _dibujar(self) -> None:
        c = self.pista
        c.delete("all")
        ancho, alto = c.winfo_width(), c.winfo_height()
        if ancho < 2:
            ancho, alto = int(c.cget("width") or 200), self.ALTO
        y = alto / 2
        x0, x1 = posicion_a_x(0, ancho, self.MARGEN), posicion_a_x(1, ancho, self.MARGEN)
        c.create_line(x0, y, x1, y, fill=BORDE, width=4, capstyle="round")
        pos = self._posicion()
        if self.preciso:
            neutro = escala.valor_a_posicion_precisa(self.parametro, self.par.neutro, self._centro)
            neutro = neutro if 0.0 < neutro < 1.0 else None
        else:
            neutro = escala.valor_a_posicion(self.parametro, self.par.neutro)
        if neutro is not None:
            xn = posicion_a_x(neutro, ancho, self.MARGEN)
            c.create_line(xn, y - 7, xn, y + 7, fill=TEXTO_SUAVE, width=1)
            c.create_line(xn, y, posicion_a_x(pos, ancho, self.MARGEN), y, fill=OLIVA, width=4, capstyle="round")
        xp = posicion_a_x(pos, ancho, self.MARGEN)
        c.create_oval(xp - 7, y - 7, xp + 7, y + 7, fill=ACENTO if self.preciso or self._arrastrando else TEXTO, outline=BG, width=2)
        if self.preciso:
            bajo, alto_v = escala.ventana_precisa(self.parametro, self._centro)
            c.create_text(x0, y + 11, text=escala.formatear(self.parametro, bajo), fill=TEXTO_SUAVE, font=("Segoe UI", 7), anchor="w")
            c.create_text(x1, y + 11, text=escala.formatear(self.parametro, alto_v), fill=TEXTO_SUAVE, font=("Segoe UI", 7), anchor="e")


# --- Gráfico de la curva --------------------------------------------------------------------------------------------
class GraficoCurva(tk.Canvas):
    """Curva de entrada → salida del perfil editado (los tres canales, o uno si son iguales)."""

    LADO = 96

    def __init__(self, master):
        super().__init__(master, width=self.LADO, height=self.LADO, bg=SUPERFICIE, highlightthickness=1, highlightbackground=BORDE)
        self._rampa: Sequence[int] | None = None
        self.dibujar(None)

    def dibujar(self, rampa: Sequence[int] | None) -> None:
        self._rampa = rampa
        self.delete("all")
        n = self.LADO
        for k in (0.25, 0.5, 0.75):
            self.create_line(k * n, 0, k * n, n, fill=BORDE)
            self.create_line(0, k * n, n, k * n, fill=BORDE)
        self.create_line(0, n - 1, n - 1, 0, fill=TEXTO_SUAVE, dash=(2, 3))  # la diagonal neutra
        if rampa is None:
            return
        if canales_iguales(rampa):
            self.create_line(*[v for p in puntos_curva(rampa, n, n, 0) for v in p], fill=ACENTO, width=2)
        else:
            for i, letra in enumerate("rgb"):
                self.create_line(*[v for p in puntos_curva(rampa, n, n, i) for v in p], fill=CANAL[letra], width=1)
