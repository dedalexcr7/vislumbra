# SPDX-License-Identifier: GPL-3.0-or-later
"""Panel de Vislumbra con Tkinter: deslizador fino, gráfico de la curva y la ventana.

Solo el hilo principal toca Tk. La lógica está en ``estado.py``; aquí solo se dibuja y se
traducen los gestos (arrastrar, rueda, flechas, doble clic, escribir un número) en llamadas
al estado.
"""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import messagebox, simpledialog, ttk
from typing import Protocol

from . import color, escala, sistema
from .estado import Estado
from .perfiles import ErrorPerfil

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

IDENTIDAD = color.rampa_identidad()
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


# --- Ventana ----------------------------------------------------------------------------------------------------------
class Controlador(Protocol):
    """Lo que el panel necesita de la app (la app lo implementa; las pruebas usan uno falso)."""

    def rampas_cambiaron(self) -> None: ...  # empuja ``estado.rampas()`` al aplicador

    def persistir(self) -> None: ...  # escribe la configuración (perfiles, activo y monitores)

    def ocultar_panel(self) -> None: ...

    def salir(self) -> None: ...


def _estilo_ttk(raiz) -> None:
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")
    estilo.configure(
        "TCombobox", fieldbackground=SUPERFICIE, background=SUPERFICIE, foreground=TEXTO, arrowcolor=TEXTO,
        bordercolor=BORDE, lightcolor=SUPERFICIE, darkcolor=SUPERFICIE, selectbackground=SUPERFICIE, selectforeground=TEXTO,
    )
    estilo.map("TCombobox", fieldbackground=[("readonly", SUPERFICIE)], foreground=[("readonly", TEXTO)])
    raiz.option_add("*TCombobox*Listbox.background", SUPERFICIE)
    raiz.option_add("*TCombobox*Listbox.foreground", TEXTO)
    raiz.option_add("*TCombobox*Listbox.selectBackground", BORDE)


class Panel:
    """Ventana pequeña, de herramienta y siempre encima. La ✕ la oculta en la bandeja."""

    ANCHO = 560

    def __init__(self, raiz: tk.Tk, estado: Estado, controlador: Controlador, reloj: Callable[[], float] = time.monotonic):
        self.raiz, self.estado, self.ctl, self.reloj = raiz, estado, controlador, reloj
        # Diálogos sustituibles (las pruebas no deben abrir ventanas de verdad).
        self.preguntar_texto: Callable[[str, str, str], str | None] = self._preguntar_texto
        self.confirmar: Callable[[str, str], bool] = lambda t, m: messagebox.askyesno(t, m, parent=self.raiz)
        self.preguntar_guardar: Callable[[], bool | None] = self._preguntar_guardar
        self._mensaje: tuple[str, str, float] | None = None  # (texto, color, hasta)
        self._colocada = False
        self._construir()
        self.refrescar()
        self.raiz.after(250, self._tick)

    # -- construcción -------------------------------------------------------------------------------------------------
    def _construir(self) -> None:
        r = self.raiz
        r.title("Vislumbra")
        r.configure(bg=BG)
        r.resizable(False, False)
        for opcion, valor in (("-topmost", True), ("-toolwindow", True)):
            try:
                r.attributes(opcion, valor)
            except tk.TclError:
                pass
        r.protocol("WM_DELETE_WINDOW", self.ctl.ocultar_panel)
        r.bind("<space>", self._tecla_espacio)
        _estilo_ttk(r)
        self.marco = tk.Frame(r, bg=BG, padx=12, pady=10, width=self.ANCHO)
        self.marco.pack(fill="both", expand=True)
        m = self.marco

        # Perfil activo
        cab = tk.Frame(m, bg=BG)
        cab.pack(fill="x")
        tk.Label(cab, text="Perfil activo", bg=BG, fg=TEXTO_SUAVE, font=FUENTE).pack(side="left")
        self._btn(cab, "‹", lambda: self._cambiar_activo(-1), 2).pack(side="left", padx=(8, 2))
        self.var_activo = tk.StringVar()
        self.combo_activo = ttk.Combobox(cab, textvariable=self.var_activo, state="readonly", width=18, font=FUENTE)
        self.combo_activo.pack(side="left")
        self.combo_activo.bind("<<ComboboxSelected>>", lambda e: self._elegir_activo(self.var_activo.get()))
        self._btn(cab, "›", lambda: self._cambiar_activo(+1), 2).pack(side="left", padx=(2, 0))
        self.var_on = tk.BooleanVar(value=True)
        tk.Checkbutton(
            cab, text="● Activo", variable=self.var_on, command=self._alternar_activo, indicatoron=False, bg=SUPERFICIE,
            fg=TEXTO, selectcolor=OLIVA, activebackground=BORDE, activeforeground=TEXTO, relief="flat", bd=0, padx=10, pady=3, font=FUENTE_NEGRITA,
        ).pack(side="right")

        # Pestañas de monitor
        self.marco_pestanas = tk.Frame(m, bg=BG)
        self.marco_pestanas.pack(fill="x", pady=(8, 0))
        self.fila_monitor = tk.Frame(m, bg=BG)
        self.fila_monitor.pack(fill="x", pady=(4, 0))
        self.lbl_monitor = tk.Label(self.fila_monitor, bg=BG, fg=TEXTO, font=FUENTE_NEGRITA)
        self.lbl_monitor.pack(side="left")
        self.var_asignacion = tk.StringVar(value="activo")
        for texto, valor in (("Sigue al perfil activo", "activo"), ("Perfil fijo", "fijo")):
            tk.Radiobutton(
                self.fila_monitor, text=texto, value=valor, variable=self.var_asignacion, command=self._asignacion_cambiada,
                bg=BG, fg=TEXTO, selectcolor=SUPERFICIE, activebackground=BG, activeforeground=TEXTO, font=FUENTE,
            ).pack(side="left", padx=(10, 0))
        self.var_fijo = tk.StringVar()
        self.combo_fijo = ttk.Combobox(self.fila_monitor, textvariable=self.var_fijo, state="readonly", width=14, font=FUENTE)
        self.combo_fijo.pack(side="left", padx=(6, 0))
        self.combo_fijo.bind("<<ComboboxSelected>>", lambda e: self._asignacion_cambiada())

        # Editor
        ed = tk.Frame(m, bg=SUPERFICIE, padx=10, pady=8, highlightthickness=1, highlightbackground=BORDE)
        ed.pack(fill="x", pady=(8, 0))
        tit = tk.Frame(ed, bg=SUPERFICIE)
        tit.pack(fill="x")
        self.lbl_editando = tk.Label(tit, bg=SUPERFICIE, fg=TEXTO, font=FUENTE_NEGRITA)
        self.lbl_editando.pack(side="left")
        self.lbl_sin_guardar = tk.Label(tit, text="● sin guardar", bg=SUPERFICIE, fg=AVISO, font=FUENTE)
        self.lbl_sin_guardar.pack(side="left", padx=8)
        botones = tk.Frame(ed, bg=SUPERFICIE)
        botones.pack(fill="x", pady=(6, 4))
        self.btns = {
            "guardar": self._btn(botones, "Guardar", self._guardar),
            "como": self._btn(botones, "Guardar como…", self._guardar_como),
            "renombrar": self._btn(botones, "Renombrar", self._renombrar),
            "borrar": self._btn(botones, "Borrar", self._borrar),
            "descartar": self._btn(botones, "Descartar", self._descartar),
        }
        for b in self.btns.values():
            b.pack(side="left", padx=(0, 4))
        canales = tk.Frame(ed, bg=SUPERFICIE)
        canales.pack(fill="x")
        self.var_vinculado = tk.BooleanVar(value=True)
        self.chk_vincular = tk.Checkbutton(
            canales, text="Vincular canales", variable=self.var_vinculado, command=self._vincular_cambiado, bg=SUPERFICIE, fg=TEXTO,
            selectcolor=BG, activebackground=SUPERFICIE, activeforeground=TEXTO, font=FUENTE,
        )
        self.chk_vincular.pack(side="left")
        self.lbl_canales = tk.Label(canales, text="R, G y B a la vez", bg=SUPERFICIE, fg=TEXTO_SUAVE, font=FUENTE)
        self.lbl_canales.pack(side="left", padx=8)
        self.btn_canal = {}
        for letra in "rgb":
            b = tk.Button(
                canales, text=letra.upper(), width=3, bg=BG, fg=CANAL[letra], relief="flat", bd=0, font=FUENTE_NEGRITA,
                command=lambda l=letra: self._elegir_canal(l),
            )
            self.btn_canal[letra] = b
        self.deslizadores = {}
        for nombre in escala.PARAMETROS:
            d = Deslizador(ed, nombre, self._mover)
            d.pack(fill="x", pady=1)
            self.deslizadores[nombre] = d

        # Pie: curva, A/B, restablecer, modo preciso y margen
        pie = tk.Frame(m, bg=BG)
        pie.pack(fill="x", pady=(8, 0))
        self.grafico = GraficoCurva(pie)
        self.grafico.pack(side="left")
        der = tk.Frame(pie, bg=BG)
        der.pack(side="left", fill="x", expand=True, padx=(12, 0))
        fila = tk.Frame(der, bg=BG)
        fila.pack(fill="x")
        self.var_ab = tk.BooleanVar(value=False)
        tk.Checkbutton(
            fila, text="A/B", variable=self.var_ab, command=self._alternar_ab, indicatoron=False, bg=SUPERFICIE, fg=TEXTO,
            selectcolor=OLIVA, activebackground=BORDE, activeforeground=TEXTO, relief="flat", bd=0, padx=12, pady=3, font=FUENTE_NEGRITA,
        ).pack(side="left")
        self._btn(fila, "Restablecer", self._restablecer).pack(side="left", padx=4)
        self.btn_deshacer = self._btn(fila, "Deshacer", self._deshacer)
        self.var_preciso = tk.BooleanVar(value=False)
        tk.Checkbutton(
            fila, text="Modo preciso", variable=self.var_preciso, command=self._preciso_cambiado, bg=BG, fg=TEXTO, selectcolor=SUPERFICIE,
            activebackground=BG, activeforeground=TEXTO, font=FUENTE,
        ).pack(side="right")
        self.lbl_margen = tk.Label(der, bg=BG, fg=TEXTO_SUAVE, font=FUENTE, anchor="w")
        self.lbl_margen.pack(fill="x", pady=(8, 2))
        self.barra = tk.Canvas(der, height=10, bg=SUPERFICIE, highlightthickness=0)
        self.barra.pack(fill="x")

        # Ajuste fuerte y línea de estado
        self.marco_fuerte = tk.Frame(m, bg=BG)
        self.lbl_fuerte = tk.Label(self.marco_fuerte, bg=BG, fg=AVISO, font=FUENTE_NEGRITA)
        self.lbl_fuerte.pack(side="left")
        self._btn(self.marco_fuerte, "Mantener", self._mantener).pack(side="left", padx=8)
        self.lbl_resumen = tk.Label(m, bg=BG, fg=TEXTO_SUAVE, font=FUENTE, anchor="w", justify="left", wraplength=self.ANCHO - 24)
        self.lbl_resumen.pack(fill="x", pady=(8, 0))
        self.lbl_aviso = tk.Label(m, bg=BG, fg=AVISO, font=FUENTE, anchor="w", justify="left", wraplength=self.ANCHO - 24)
        self.lbl_aviso.pack(fill="x")

    def _btn(self, padre, texto: str, comando, ancho: int | None = None) -> tk.Button:
        return tk.Button(
            padre, text=texto, command=comando, width=ancho or 0, bg=SUPERFICIE if padre.cget("bg") == BG else BG, fg=TEXTO,
            activebackground=BORDE, activeforeground=TEXTO, disabledforeground=BORDE, relief="flat", bd=0, padx=8, pady=3, font=FUENTE,
        )

    # -- diálogos --------------------------------------------------------------------------------------------------------------
    def _preguntar_texto(self, titulo: str, mensaje: str, inicial: str) -> str | None:
        return simpledialog.askstring(titulo, mensaje, initialvalue=inicial, parent=self.raiz)

    def _preguntar_guardar(self) -> bool | None:
        return messagebox.askyesnocancel(
            "Cambios sin guardar", "Hay perfiles con cambios sin guardar.\n\nSí: guardar · No: descartar · Cancelar: volver.", parent=self.raiz,
        )

    # -- mensajes -----------------------------------------------------------------------------------------------------------------
    def mensaje(self, texto: str, color_: str = AVISO, segundos: float = 6.0) -> None:
        self._mensaje = (texto, color_, self.reloj() + segundos)
        self.lbl_aviso.configure(text=texto, fg=color_)

    def _error(self, e: Exception) -> None:
        self.mensaje(str(e)[:1].upper() + str(e)[1:], PELIGRO)

    # -- sincronizar con el modelo ----------------------------------------------------------------------------------------
    def refrescar(self) -> None:
        """Vuelve a leer todo del estado (tras cambiar de perfil, de monitor, guardar, etc.)."""
        e = self.estado
        nombres = e.nombres()
        self.combo_activo.configure(values=nombres)
        self.var_activo.set(e.activo)
        self.var_on.set(e.activo_on)
        self.var_ab.set(e.ab)
        self._reconstruir_pestanas()
        clave = next((m.clave for m in e.monitores if m.numero == e.mirado), "")
        fijo = e.asignacion(clave) if clave else None
        self.lbl_monitor.configure(text=f"Monitor {e.mirado}")
        self.var_asignacion.set("fijo" if fijo is not None else "activo")
        self.combo_fijo.configure(values=nombres, state="readonly" if fijo is not None else "disabled")
        self.var_fijo.set(fijo or e.activo)
        p = e.perfil_editado()
        for nombre, d in self.deslizadores.items():
            d.poner_valor(e.valor(nombre))
            d.poner_preciso(e.preciso)
        self.var_vinculado.set(p.vinculado)
        self.chk_vincular.configure(state="disabled" if p.es_normal else "normal")
        self._mostrar_canales(p.vinculado)
        self._refrescar_ligero()

    def _mostrar_canales(self, vinculado: bool) -> None:
        for b in self.btn_canal.values():
            b.pack_forget()
        if vinculado:
            self.lbl_canales.configure(text="R, G y B a la vez")
            return
        self.lbl_canales.configure(text="Canal:")
        for letra, b in self.btn_canal.items():
            b.pack(side="left", padx=1)
            b.configure(relief="sunken" if letra == self.estado.canal else "flat", bg=BORDE if letra == self.estado.canal else BG)

    def _refrescar_ligero(self) -> None:
        """Lo que cambia con cada movimiento de un deslizador (rápido)."""
        e = self.estado
        p = e.perfil_editado()
        self.lbl_editando.configure(text=f"Editando «{p.nombre}»")
        sin = e.sin_guardar(p.nombre)
        if sin:
            self.lbl_sin_guardar.pack(side="left", padx=8)
        else:
            self.lbl_sin_guardar.pack_forget()
        for clave, b in self.btns.items():
            if p.es_normal:
                activado = False
            elif clave in ("guardar", "descartar"):
                activado = sin
            else:
                activado = True
            b.configure(state="normal" if activado else "disabled")
        try:
            rampa = color.construir_rampa_segura(p.ajuste)
        except color.ErrorColor:
            rampa = None
        self.grafico.dibujar(rampa if rampa is not None else IDENTIDAD)
        usado, limite = margen_windows(rampa if rampa is not None else IDENTIDAD)
        self.lbl_margen.configure(text=f"Margen de Windows: {usado:.0f} % de {limite:.0f} %")
        self._dibujar_barra(usado / limite)
        self.lbl_resumen.configure(text=e.resumen())
        self._refrescar_confirmaciones()

    def _dibujar_barra(self, fraccion: float) -> None:
        b = self.barra
        b.delete("all")
        ancho = b.winfo_width() if b.winfo_width() > 1 else self.ANCHO // 2
        b.create_rectangle(0, 0, ancho * min(1.0, fraccion), 10, fill=PELIGRO if fraccion > 0.8 else (AVISO if fraccion > 0.6 else OLIVA), width=0)

    def _refrescar_confirmaciones(self) -> None:
        ahora = self.reloj()
        s = self.estado.segundos_restantes(ahora)
        if s is None:
            self.marco_fuerte.pack_forget()
        else:
            self.lbl_fuerte.configure(text=f"Ajuste fuerte · se deshará en {s:.0f} s")
            self.marco_fuerte.pack(fill="x", pady=(6, 0), before=self.lbl_resumen)
        if self.estado.puede_deshacer(ahora):
            self.btn_deshacer.pack(side="left")
        else:
            self.btn_deshacer.pack_forget()

    def _reconstruir_pestanas(self) -> None:
        for w in self.marco_pestanas.winfo_children():
            w.destroy()
        e = self.estado
        if len(e.monitores) <= 1:
            self.marco_pestanas.pack_forget()
            return
        self.marco_pestanas.pack(fill="x", pady=(8, 0), before=self.fila_monitor)
        for p in e.pestanas():
            marco = tk.Frame(self.marco_pestanas, bg=BORDE if p.numero == e.mirado else SUPERFICIE, padx=8, pady=4, cursor="hand2")
            marco.pack(side="left", padx=(0, 4))
            titulo = f"Monitor {p.numero}" + (" · principal" if p.principal else "")
            sub = f"{p.perfil} ({'fijo' if p.fijo else 'activo'})"
            for texto, col, fuente in ((titulo, TEXTO, FUENTE_NEGRITA), (sub, ACENTO if p.fijo else TEXTO_SUAVE, FUENTE)):
                lbl = tk.Label(marco, text=texto, bg=marco.cget("bg"), fg=col, font=fuente, anchor="w")
                lbl.pack(fill="x")
                lbl.bind("<Button-1>", lambda ev, n=p.numero: self._mirar(n))
            marco.bind("<Button-1>", lambda ev, n=p.numero: self._mirar(n))

    # -- acciones ---------------------------------------------------------------------------------------------------------------
    def _aplicar(self, persistir: bool = False) -> None:
        if persistir:
            self.ctl.persistir()
        self.ctl.rampas_cambiaron()

    def _mover(self, parametro: str, valor: float) -> float:
        res = self.estado.mover(parametro, valor, self.reloj())
        if res.tope:
            self.mensaje(f"Tope: {res.tope}")
        if res.perfil_creado:
            self.refrescar()
            self.mensaje(f"Se creó «{res.perfil_creado}» (sin guardar): «Normal» no se edita.", TEXTO_SUAVE)
        else:
            self._refrescar_ligero()
        self._aplicar()
        return res.valor

    def _mirar(self, numero: int) -> None:
        self.estado.mirar(numero)
        self.refrescar()

    def _elegir_activo(self, nombre: str) -> None:
        try:
            self.estado.cambiar_activo(nombre)
        except ErrorPerfil as e:
            self._error(e)
        self.refrescar()
        self._aplicar(persistir=True)

    def _cambiar_activo(self, delta: int) -> None:
        self.estado.mover_activo(delta)
        self.refrescar()
        self._aplicar(persistir=True)

    def _alternar_activo(self) -> None:
        self.estado.poner_activo(self.var_on.get())
        self.refrescar()
        self._aplicar()
        self.mensaje("Vislumbra está activo." if self.estado.activo_on else "Vislumbra está desactivado: pantalla original.", TEXTO_SUAVE)

    def _alternar_ab(self) -> None:
        if not self.estado.activo_on:
            self.var_ab.set(False)
            return
        self.estado.alternar_ab()
        self.var_ab.set(self.estado.ab)
        self._aplicar()

    def _tecla_espacio(self, ev) -> None:
        if isinstance(ev.widget, (tk.Entry, ttk.Combobox)):
            return
        self._alternar_ab()

    def _asignacion_cambiada(self) -> None:
        e = self.estado
        try:
            e.fijar_monitor(e.mirado, self.var_fijo.get() if self.var_asignacion.get() == "fijo" else None)
        except ErrorPerfil as err:
            self._error(err)
        self.refrescar()
        self._aplicar(persistir=True)

    def _guardar(self) -> None:
        try:
            nombre = self.estado.guardar()
        except (ErrorPerfil, color.ErrorColor) as e:
            return self._error(e)
        self.refrescar()
        self._aplicar(persistir=True)
        self.mensaje(f"Guardado «{nombre}».", TEXTO_SUAVE)

    def _guardar_como(self) -> None:
        nombre = self.preguntar_texto("Guardar como", "Nombre del perfil nuevo:", self.estado.perfil_editado().nombre + " 2")
        if nombre is None:
            return
        try:
            guardado = self.estado.guardar_como(nombre)
        except (ErrorPerfil, color.ErrorColor) as e:
            return self._error(e)
        self.refrescar()
        self._aplicar(persistir=True)
        self.mensaje(f"Guardado como «{guardado}».", TEXTO_SUAVE)

    def _renombrar(self) -> None:
        nombre = self.preguntar_texto("Renombrar", "Nuevo nombre del perfil:", self.estado.perfil_editado().nombre)
        if nombre is None:
            return
        try:
            self.estado.renombrar(nombre)
        except ErrorPerfil as e:
            return self._error(e)
        self.refrescar()
        self._aplicar(persistir=True)

    def _borrar(self) -> None:
        p = self.estado.perfil_editado()
        if not self.confirmar("Borrar perfil", f"¿Borrar el perfil «{p.nombre}»?\nLos monitores que lo tenían fijo pasarán a seguir al perfil activo."):
            return
        try:
            self.estado.borrar()
        except ErrorPerfil as e:
            return self._error(e)
        self.refrescar()
        self._aplicar(persistir=True)

    def _descartar(self) -> None:
        self.estado.descartar()
        self.refrescar()
        self._aplicar(persistir=True)

    def _vincular_cambiado(self) -> None:
        e = self.estado
        quiere = self.var_vinculado.get()
        if quiere and e.canales_distintos() and not self.confirmar(
            "Vincular canales", f"Los canales tienen valores distintos. Al vincular se usarán los del canal {e.canal.upper()}. ¿Continuar?",
        ):
            self.var_vinculado.set(False)
            return
        e.vincular(quiere)
        self.refrescar()
        self._aplicar()

    def _elegir_canal(self, letra: str) -> None:
        self.estado.poner_canal(letra)
        self.refrescar()

    def _restablecer(self) -> None:
        if self.estado.restablecer(self.reloj()):
            self.refrescar()
            self._aplicar()
            self.mensaje("Perfil en neutro (sin guardar). Puedes deshacerlo durante 10 s.", TEXTO_SUAVE)

    def _deshacer(self) -> None:
        if self.estado.deshacer(self.reloj()):
            self.refrescar()
            self._aplicar()

    def _mantener(self) -> None:
        self.estado.mantener()
        self._refrescar_confirmaciones()

    def _preciso_cambiado(self) -> None:
        self.estado.preciso = self.var_preciso.get()
        for d in self.deslizadores.values():
            d.poner_preciso(self.estado.preciso)

    # -- reloj ---------------------------------------------------------------------------------------------------------------------------
    def _tick(self) -> None:
        try:
            if self.estado.vencer(self.reloj()):
                if self.estado.aviso:
                    self.mensaje(self.estado.aviso)
                self.refrescar()
                self._aplicar()
            else:
                self._refrescar_confirmaciones()
            if self._mensaje and self.reloj() >= self._mensaje[2]:
                self._mensaje = None
                self.lbl_aviso.configure(text="")
        finally:
            self.raiz.after(250, self._tick)

    # -- ventana ------------------------------------------------------------------------------------------------------------------------
    def mostrar(self) -> None:
        r = self.raiz
        r.deiconify()
        r.update_idletasks()
        if not self._colocada:
            x, y = sistema.colocar_abajo_derecha(sistema.area_de_trabajo(), r.winfo_reqwidth(), r.winfo_reqheight())
            r.geometry(f"+{x}+{y}")
            self._colocada = True
        r.lift()
        r.focus_force()

    def ocultar(self) -> None:
        self.raiz.withdraw()

    @property
    def visible(self) -> bool:
        return self.raiz.state() != "withdrawn"

    def confirmar_salida(self) -> bool:
        """Si hay cambios sin guardar pregunta (Guardar, Descartar o Cancelar). ``False`` si se cancela."""
        if not self.estado.sin_guardar():
            return True
        respuesta = self.preguntar_guardar()
        if respuesta is None:
            return False
        if respuesta:
            try:
                self.estado.guardar_todos()
            except (ErrorPerfil, color.ErrorColor) as e:
                self._error(e)
                return False
            self.ctl.persistir()
        else:
            self.estado.descartar_todo()
        return True
