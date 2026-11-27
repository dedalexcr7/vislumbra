# SPDX-License-Identifier: GPL-3.0-or-later
"""Panel de Vislumbra con Tkinter: deslizador fino, gráfico de la curva y la ventana.

Solo el hilo principal toca Tk. La lógica está en ``estado.py``; aquí solo se dibuja y se
traducen los gestos (arrastrar, rueda, flechas, doble clic, escribir un número) en llamadas
al estado. El aspecto sigue la maqueta aprobada (``docs/diseno-panel-maqueta.md``); los
elementos que Tk no dibuja (esquinas redondeadas, degradados) están en ``widgets.py``.
"""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable, Sequence
from typing import Protocol

from . import color, dialogos, escala, procesos, sistema
from .estado import Estado
from .perfiles import ErrorPerfil
from .widgets import (  # noqa: F401  (AVISO, PELIGRO y TEXTO_SUAVE los importa app.py)
    ACENTO, AVISO, AVISO_MARGEN, BORDE_BOTON, BORDE_VENTANA, BOTON, CABECERA, CAMPO, CANAL, DEGRADADO_TEMPERATURA,
    FONDO_VENTANA, FUERTE_BORDE, FUERTE_FONDO, LINEA, MARCA_NEUTRO, OLIVA, PELIGRO, PESTANA, PESTANA_ACTIVA, PISTA, TEXTO,
    TEXTO_SUAVE, VERDE, Boton, Casilla, Tarjeta, TextoMixto, degradado, dibujar_logo, fijar_escala, fuente,
    nueva_posicion, px, rect_redondeado,
)

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


def color_margen(fraccion: float) -> str:
    """Color de la barra de margen (de la maqueta: aviso desde el 40 % de desviación, peligro desde el 47 %)."""
    return PELIGRO if fraccion > 0.94 else (AVISO_MARGEN if fraccion > 0.8 else ACENTO)


# --- Deslizador fino ---------------------------------------------------------------------------------
class Deslizador(tk.Frame):
    """Etiqueta, pista con mínimo y máximo, botones − y +, y campo numérico editable.

    Gestos: arrastrar (con Mayús, 10 veces más lento), doble clic (vuelve al neutro), rueda y
    flechas (paso fijo; Mayús = paso fino), escribir un número (coma o punto) y los botones.
    En modo preciso la pista cubre una ventana lineal alrededor del valor, que se recentra al soltar.

    ``al_cambiar(parametro, valor)`` puede devolver el valor realmente aplicado (si hubo tope);
    el deslizador se coloca en él.
    """

    MARGEN = 10
    ALTO = 46  # 32 de pista + 14 para el mínimo y el máximo

    def __init__(self, master, parametro: str, al_cambiar: Callable[[str, float], float | None]):
        super().__init__(master, bg=master.cget("bg"))
        bg = self.cget("bg")
        self.parametro = parametro
        self.par = escala.PARAMETROS[parametro]
        self.al_cambiar = al_cambiar
        self.valor = self.par.neutro
        self.preciso = False
        self._centro = self.par.neutro
        self._ref: tuple[float, float] | None = None  # (posición del ratón, posición del valor) con Mayús
        self._arrastrando = False
        self.columnconfigure(0, minsize=px(84))
        self.columnconfigure(1, weight=1)

        tk.Label(self, text=self.par.etiqueta, anchor="w", bg=bg, fg=TEXTO, font=fuente(13)).grid(row=0, column=0, sticky="nw", pady=(px(6), 0))
        self.pista = tk.Canvas(self, width=px(100), height=px(self.ALTO), bg=bg, highlightthickness=0, takefocus=True, cursor="hand2")
        self.pista.grid(row=0, column=1, sticky="ew", padx=px(8))
        self._boton("−", -1).grid(row=0, column=2, sticky="n")
        self.texto = tk.StringVar()
        self._marco_campo = tk.Canvas(self, width=px(72), height=px(32), bg=bg, highlightthickness=0)
        self._marco_campo.grid(row=0, column=3, sticky="n", padx=px(8))
        self.campo = tk.Entry(
            self._marco_campo, textvariable=self.texto, justify="right", bg=CAMPO, fg=TEXTO, insertbackground=TEXTO,
            relief="flat", bd=0, highlightthickness=0, font=fuente(13),
        )
        self._marco_campo.create_window(px(64), px(16), window=self.campo, anchor="e", width=px(56), height=px(20))
        self._borde_campo(False)
        self._boton("+", +1).grid(row=0, column=4, sticky="n")

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
        self.campo.bind("<FocusIn>", lambda e: self._borde_campo(True), add="+")
        self.campo.bind("<FocusOut>", lambda e: self._borde_campo(False), add="+")
        self.campo.bind("<Button-1>", lambda e: self.campo.focus_force(), add="+")  # ventana sin borde: pide el foco
        self.campo.bind("<Escape>", lambda e: self._actualizar_texto())
        self.poner_valor(self.par.neutro)

    def _boton(self, simbolo: str, d: int) -> Boton:
        return Boton(self, simbolo, lambda: self._paso(d, False), alto=32, ancho=32, tam=16, relleno=0)

    def _borde_campo(self, enfocado: bool) -> None:
        c = self._marco_campo
        c.delete("borde")
        rect_redondeado(c, 0.5, 0.5, px(72) - 0.5, px(32) - 0.5, px(7), fill=CAMPO, outline=ACENTO if enfocado else BORDE_BOTON, tags="borde")
        c.tag_lower("borde")

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
        self.texto.set(escala.formatear(self.parametro, self.valor, con_unidad=True))

    def _pedir(self, valor: float) -> None:
        valor = escala.limitar(self.parametro, valor)
        aplicado = self.al_cambiar(self.parametro, valor)
        self.poner_valor(valor if aplicado is None else aplicado)

    # -- gestos ------------------------------------------------------------------------------------------------
    def _p_raton(self, x: float) -> float:
        return x_a_posicion(x, self.pista.winfo_width(), px(self.MARGEN))

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
    def _dibujar_pista(self, c: tk.Canvas, x0: float, x1: float, y: float) -> None:
        grosor = px(6)
        if self.parametro != "temperatura":
            c.create_line(x0, y, x1, y, fill=PISTA, width=grosor, capstyle="round")
            return
        pasos = max(8, int((x1 - x0) / 4))
        for k in range(pasos):  # degradado naranja → gris → azul
            a, b = x0 + (x1 - x0) * k / pasos, x0 + (x1 - x0) * (k + 1) / pasos
            c.create_line(a, y, b + 1, y, fill=degradado(DEGRADADO_TEMPERATURA, (k + 0.5) / pasos), width=grosor)
        r = grosor / 2
        for x, col in ((x0, DEGRADADO_TEMPERATURA[0]), (x1, DEGRADADO_TEMPERATURA[-1])):
            c.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="")

    def _dibujar(self) -> None:
        c = self.pista
        c.delete("all")
        ancho = c.winfo_width()
        if ancho < 2:
            ancho = int(c.cget("width") or 200)
        y = px(16)
        marg = px(self.MARGEN)
        x0, x1 = posicion_a_x(0, ancho, marg), posicion_a_x(1, ancho, marg)
        pos = self._posicion()
        if self.preciso:
            neutro = escala.valor_a_posicion_precisa(self.parametro, self.par.neutro, self._centro)
            neutro = neutro if 0.0 < neutro < 1.0 else None
        else:
            neutro = escala.valor_a_posicion(self.parametro, self.par.neutro)
        if neutro is not None:  # marca vertical del neutro (la pista la tapa en el centro)
            xn = posicion_a_x(neutro, ancho, marg)
            c.create_line(xn, y - px(10), xn, y + px(10), fill=MARCA_NEUTRO, width=px(2))
        self._dibujar_pista(c, x0, x1, y)
        xp = posicion_a_x(pos, ancho, marg)
        resaltado = self.preciso or self._arrastrando
        for radio, col in ((9, OLIVA), (8, FONDO_VENTANA), (6, ACENTO if resaltado else TEXTO)):
            r = px(radio)
            c.create_oval(xp - r, y - r, xp + r, y + r, fill=col, outline="")
        if self.preciso:
            bajo, alto_v = escala.ventana_precisa(self.parametro, self._centro)
        else:
            bajo, alto_v = self.par.minimo, self.par.maximo
        yt = px(32) + px(7)
        c.create_text(0, yt, text=escala.formatear(self.parametro, bajo, con_unidad=True), fill=TEXTO_SUAVE, font=fuente(11), anchor="w")
        c.create_text(ancho, yt, text=escala.formatear(self.parametro, alto_v, con_unidad=True), fill=TEXTO_SUAVE, font=fuente(11), anchor="e")


# --- Gráfico de la curva --------------------------------------------------------------------------------------------
class GraficoCurva(tk.Canvas):
    """Curva de entrada → salida del perfil editado (azul si los tres canales son iguales; R, G y B si no)."""

    LADO = 130

    def __init__(self, master):
        n = px(self.LADO)
        super().__init__(master, width=n, height=n, bg=master.cget("bg"), highlightthickness=0, bd=0)
        self._rampa: Sequence[int] | None = None
        self.dibujar(None)

    def dibujar(self, rampa: Sequence[int] | None) -> None:
        self._rampa = rampa
        self.delete("all")
        n, pad = px(self.LADO), px(4)
        rect_redondeado(self, 0.5, 0.5, n - 0.5, n - 0.5, px(8), fill=CAMPO, outline=BORDE_VENTANA)
        lado = n - 2 * pad
        self.create_line(pad, n - pad, n - pad, pad, fill="#4a4940", width=px(2), dash=(px(6), px(5)))  # la diagonal neutra
        if rampa is None:
            return

        def trazo(canal: int, col: str) -> None:
            pts = [v for x, y in puntos_curva(rampa, lado, lado, canal) for v in (x + pad, y + pad)]
            self.create_line(*pts, fill=col, width=px(2), joinstyle="round", smooth=True)

        if canales_iguales(rampa):
            trazo(0, CANAL["b"])
        else:
            for i, letra in enumerate("rgb"):
                trazo(i, CANAL[letra])


# --- Etiqueta del perfil activo --------------------------------------------------------------------------------------
class EtiquetaPerfil(tk.Label):
    """Nombre del perfil activo (sin caja). Guarda la lista de perfiles en ``values`` y abre un menú al pulsarla."""

    def __init__(self, master, **kw):
        self._valores: list[str] = []
        super().__init__(master, **kw)

    def configure(self, cnf=None, **kw):
        if "values" in kw:
            self._valores = list(kw.pop("values"))
        return super().configure(cnf, **kw) if (cnf or kw) else None

    config = configure

    def cget(self, clave):
        return self._valores if clave == "values" else super().cget(clave)


# --- Ventana ----------------------------------------------------------------------------------------------------------
class Controlador(Protocol):
    """Lo que el panel necesita de la app (la app lo implementa; las pruebas usan uno falso)."""

    def rampas_cambiaron(self) -> None: ...  # empuja ``estado.rampas()`` al aplicador

    def persistir(self) -> None: ...  # escribe la configuración (perfiles, activo y monitores)

    def ocultar_panel(self) -> None: ...

    def salir(self) -> None: ...


class Panel:
    """Ventana sin barra de título (cabecera propia), siempre encima y fuera de la barra de tareas. La ✕ la oculta en la bandeja."""

    ANCHO = 490

    def __init__(self, raiz: tk.Tk, estado: Estado, controlador: Controlador, reloj: Callable[[], float] = time.monotonic):
        self.raiz, self.estado, self.ctl, self.reloj = raiz, estado, controlador, reloj
        # Diálogos sustituibles (las pruebas no deben abrir ventanas de verdad).
        self.preguntar_texto: Callable[[str, str, str], str | None] = self._preguntar_texto
        self.confirmar: Callable[[str, str], bool] = lambda t, m: dialogos.confirmar(self.raiz, t, m)
        self.preguntar_guardar: Callable[[], bool | None] = self._preguntar_guardar
        self.procesos_abiertos: Callable[[], list[str]] = procesos.nombres_ordenados
        self.abrir_dialogo_programas = dialogos.programas  # las pruebas lo sustituyen
        self._mensaje: tuple[str, str, float] | None = None  # (texto, color, hasta)
        self._colocada = False
        self._arrastre_ini: tuple[int, int, int, int] | None = None
        fijar_escala(raiz)
        self._construir()
        self.refrescar()
        self.raiz.after(250, self._tick)

    # -- construcción -------------------------------------------------------------------------------------------------
    def _construir(self) -> None:
        r = self.raiz
        r.title("Vislumbra")
        r.configure(bg=BORDE_VENTANA)
        r.resizable(False, False)
        r.overrideredirect(True)  # sin barra de Windows: tampoco hay botón en la barra de tareas
        try:
            r.attributes("-topmost", True)
        except tk.TclError:
            pass
        r.protocol("WM_DELETE_WINDOW", self.ctl.ocultar_panel)
        r.bind("<space>", self._tecla_espacio)
        r.bind("<Configure>", self._al_cambiar_tamano)
        self.marco = tk.Frame(r, bg=FONDO_VENTANA)
        self.marco.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(self.marco, width=px(self.ANCHO - 2), height=1, bg=FONDO_VENTANA).pack()  # fija el ancho

        self._cabecera()
        cuerpo = tk.Frame(self.marco, bg=FONDO_VENTANA, padx=px(16), pady=px(16))
        cuerpo.pack(fill="both", expand=True)
        m = self.cuerpo = cuerpo
        sep = (0, px(14))

        # Perfil activo
        cab = tk.Frame(m, bg=FONDO_VENTANA)
        cab.pack(fill="x", pady=sep)
        tk.Label(cab, text="Perfil activo", bg=FONDO_VENTANA, fg=TEXTO_SUAVE, font=fuente(13)).pack(side="left")
        self._btn_ico(cab, "‹", lambda: self._cambiar_activo(-1)).pack(side="left", padx=(px(10), 0))
        caja = tk.Frame(cab, bg=FONDO_VENTANA)
        caja.pack(side="left", padx=(px(8), 0))
        caja.columnconfigure(0, minsize=px(110))
        self.var_activo = tk.StringVar()
        self.combo_activo = EtiquetaPerfil(caja, textvariable=self.var_activo, bg=FONDO_VENTANA, fg=TEXTO, font=fuente(14, True), cursor="hand2")
        self.combo_activo.grid(row=0, column=0, sticky="ew")
        self.combo_activo.bind("<Button-1>", self._menu_perfiles)
        self._btn_ico(cab, "›", lambda: self._cambiar_activo(+1)).pack(side="left", padx=(px(8), 0))
        self.var_on = tk.BooleanVar(value=True)
        self.btn_on = Boton(cab, "Activo", self._clic_activo, radio=16, punto=VERDE)
        self.btn_on.pack(side="right")

        # Pestañas de monitor y fila del monitor
        self.marco_pestanas = tk.Frame(m, bg=FONDO_VENTANA)
        self.marco_pestanas.pack(fill="x", pady=sep)
        self.bloque_monitor = tk.Frame(m, bg=FONDO_VENTANA)
        self.bloque_monitor.pack(fill="x", pady=sep)
        self.fila_monitor = tk.Frame(self.bloque_monitor, bg=FONDO_VENTANA)
        self.fila_monitor.pack(fill="x")
        self.fila_monitor.columnconfigure(0, minsize=px(88))
        self.lbl_monitor = tk.Label(self.fila_monitor, bg=FONDO_VENTANA, fg=TEXTO_SUAVE, font=fuente(13), anchor="w")
        self.lbl_monitor.grid(row=0, column=0, sticky="w")
        self.var_asignacion = tk.StringVar(value="activo")
        self.btn_asig = {}
        for i, (texto, valor) in enumerate((("Sigue al perfil activo", "activo"), ("Perfil fijo", "fijo"))):
            b = Boton(self.fila_monitor, texto, lambda v=valor: self._clic_asignacion(v), alto=30, minimo=38, relleno=10)
            b.grid(row=0, column=i + 1, padx=(0 if i == 0 else px(8), 0))
            self.btn_asig[valor] = b
        self.var_fijo = tk.StringVar()
        self.marco_fijos = tk.Frame(self.bloque_monitor, bg=FONDO_VENTANA)

        # Editor
        ed = Tarjeta(m, CABECERA, BORDE_VENTANA, radio=10, padx=12, pady=12)
        ed.pack(fill="x", pady=sep)
        fondo = CABECERA
        linea1 = tk.Frame(ed, bg=fondo)
        linea1.pack(fill="x")
        tit = tk.Frame(linea1, bg=fondo)
        tit.pack(side="left")
        self.lbl_editando = TextoMixto(tit, " ", 13, TEXTO_SUAVE, 14, TEXTO, negrita2=True)
        self.lbl_editando.pack(side="left")
        linea2 = tk.Frame(ed, bg=fondo)
        linea2.pack(fill="x", pady=(px(8), 0))
        # En la segunda línea: junto al título no cabe y ensancharía la ventana.
        self.lbl_sin_guardar = tk.Label(linea2, text="● sin guardar", bg=fondo, fg=AVISO, font=fuente(11))
        self.btns = {
            "guardar": Boton(linea1, "Guardar", self._guardar, relleno=10),
            "como": Boton(linea1, "Guardar como…", self._guardar_como, relleno=10),
            "renombrar": Boton(linea1, "Renombrar", self._renombrar, relleno=10),
            "borrar": Boton(linea2, "Borrar", self._borrar),
            "descartar": Boton(linea2, "Descartar", self._descartar),
        }
        for clave in ("renombrar", "como", "guardar"):
            self.btns[clave].pack(side="right", padx=(px(8), 0))
        self.btns["borrar"].pack(side="left")
        self.btns["descartar"].pack(side="left", padx=(px(8), 0))
        self.btn_programas = Boton(linea2, "Programas…", self.abrir_programas, relleno=10)
        self.btn_programas.pack(side="right")

        canales = tk.Frame(ed, bg=fondo)
        canales.pack(fill="x", pady=(px(12), 0))
        self.var_vinculado = tk.BooleanVar(value=True)
        self.chk_vincular = Casilla(canales, "Vincular canales", self.var_vinculado, self._vincular_cambiado)
        self.chk_vincular.pack(side="left")
        self.grupo_canales = tk.Frame(canales, bg=fondo)
        self.grupo_canales.pack(side="right")
        self.lbl_canales = tk.Label(self.grupo_canales, text="R, G y B a la vez", bg=fondo, fg=TEXTO_SUAVE, font=fuente(12))
        self.btn_canal = {
            letra: Boton(self.grupo_canales, letra.upper(), lambda l=letra: self._elegir_canal(l), alto=30, minimo=38, relleno=10)
            for letra in "rgb"
        }
        self.deslizadores = {}
        for nombre in escala.PARAMETROS:
            d = Deslizador(ed, nombre, self._mover)
            d.pack(fill="x", pady=(px(6), 0))
            self.deslizadores[nombre] = d

        # Pie: curva, A/B, restablecer, modo preciso y margen
        pie = tk.Frame(m, bg=FONDO_VENTANA)
        pie.pack(fill="x", pady=sep)
        fig = tk.Frame(pie, bg=FONDO_VENTANA)
        fig.pack(side="left", anchor="n")
        self.grafico = GraficoCurva(fig)
        self.grafico.pack()
        tk.Label(fig, text="Curva (discontinua = normal)", bg=FONDO_VENTANA, fg=TEXTO_SUAVE, font=fuente(11)).pack(anchor="w", pady=(px(6), 0))
        der = tk.Frame(pie, bg=FONDO_VENTANA)
        der.pack(side="left", fill="x", expand=True, padx=(px(16), 0), anchor="n")
        self.var_ab = tk.BooleanVar(value=False)
        self.btn_ab = Boton(der, "A/B: viendo el ajuste", self._alternar_ab)
        self.btn_ab.pack(fill="x")
        fila = tk.Frame(der, bg=FONDO_VENTANA)
        fila.pack(fill="x", pady=(px(10), 0))
        Boton(fila, "Restablecer", self._restablecer).pack(side="left", fill="x", expand=True)
        self.btn_deshacer = Boton(fila, "Deshacer", self._deshacer)
        self.var_preciso = tk.BooleanVar(value=False)
        Casilla(der, "Modo preciso", self.var_preciso, self._preciso_cambiado).pack(anchor="w", pady=(px(10), 0))
        self.lbl_margen = TextoMixto(der, ": ", 12, TEXTO_SUAVE, 12, TEXTO, lados=True, alto=18)
        self.lbl_margen.pack(fill="x", pady=(px(10), px(5)))
        self.barra = tk.Canvas(der, width=px(50), height=px(8), bg=FONDO_VENTANA, highlightthickness=0)
        self.barra.pack(fill="x")
        self.barra.bind("<Configure>", lambda e: self._dibujar_barra(self._fraccion_margen))
        self._fraccion_margen = 0.0

        # Ajuste fuerte (aparece solo cuando hace falta) y línea de estado
        self.marco_fuerte = Tarjeta(m, FUERTE_FONDO, FUERTE_BORDE, radio=8, padx=10, pady=8)
        self.lbl_fuerte = tk.Label(self.marco_fuerte, bg=FUERTE_FONDO, fg=TEXTO, font=fuente(13))
        self.lbl_fuerte.pack(side="left")
        Boton(self.marco_fuerte, "Mantener", self._mantener, estilo="activo").pack(side="right")
        self.marco_estado = tk.Frame(m, bg=FONDO_VENTANA)
        self.marco_estado.pack(fill="x")
        tk.Frame(self.marco_estado, bg=LINEA, height=1).pack(fill="x")
        ancho_texto = px(self.ANCHO - 2 - 32)
        self.lbl_resumen = tk.Label(self.marco_estado, bg=FONDO_VENTANA, fg=TEXTO, font=fuente(12), anchor="w", justify="left", wraplength=ancho_texto)
        self.lbl_resumen.pack(fill="x", pady=(px(10), 0))
        self.lbl_aviso = tk.Label(self.marco_estado, bg=FONDO_VENTANA, fg=AVISO, font=fuente(12), anchor="w", justify="left", wraplength=ancho_texto)
        self.lbl_aviso.pack(fill="x", pady=(px(2), 0))

    def _cabecera(self) -> None:
        cab = tk.Frame(self.marco, bg=CABECERA, height=px(40))
        cab.pack(fill="x")
        cab.pack_propagate(False)
        logo = tk.Canvas(cab, width=px(16), height=px(16), bg=CABECERA, highlightthickness=0)
        dibujar_logo(logo)
        logo.pack(side="left", padx=(px(14), px(10)))
        titulo = tk.Label(cab, text="Vislumbra", bg=CABECERA, fg=TEXTO, font=fuente(13, True))
        titulo.pack(side="left")
        Boton(cab, "✕", lambda: self.ctl.ocultar_panel(), estilo="limpio", ancho=32, relleno=0, tam=17).pack(side="right", padx=(0, px(6)))
        for w in (cab, logo, titulo):  # se arrastra la ventana desde la cabecera
            w.bind("<ButtonPress-1>", self._arrastre_inicio)
            w.bind("<B1-Motion>", self._arrastre_mover)
        tk.Frame(self.marco, bg=LINEA, height=1).pack(fill="x")

    def _btn_ico(self, padre, simbolo: str, comando) -> Boton:
        return Boton(padre, simbolo, comando, ancho=32, tam=16, relleno=0)

    # -- arrastrar la ventana -----------------------------------------------------------------------------------------------
    def _arrastre_inicio(self, e) -> None:
        self._arrastre_ini = (e.x_root, e.y_root, self.raiz.winfo_x(), self.raiz.winfo_y())

    def _arrastre_mover(self, e) -> None:
        if self._arrastre_ini is None:
            return
        rx, ry, vx, vy = self._arrastre_ini
        x, y = nueva_posicion((vx, vy), (rx, ry), (e.x_root, e.y_root))
        self.raiz.geometry(f"+{x}+{y}")

    def _al_cambiar_tamano(self, e) -> None:
        """Si la ventana crece (perfil fijo, avisos, ajuste fuerte) y se sale de la pantalla, se recoloca."""
        if e.widget is not self.raiz or not self._colocada or not self.visible:
            return
        r = self.raiz
        x, y = sistema.limitar_al_area(r.winfo_x(), r.winfo_y(), r.winfo_width(), r.winfo_height(), sistema.area_de_trabajo())
        if (x, y) != (r.winfo_x(), r.winfo_y()):
            r.geometry(f"+{x}+{y}")

    def abrir_programas(self) -> None:
        """Diálogo de programas asociados a perfiles (también desde el menú de la bandeja)."""
        self.abrir_dialogo_programas(self.raiz, self.estado, self.procesos_abiertos, self.ctl.persistir)
        self.refrescar()

    # -- diálogos --------------------------------------------------------------------------------------------------------------
    def _preguntar_texto(self, titulo: str, mensaje: str, inicial: str) -> str | None:
        return dialogos.preguntar_texto(self.raiz, titulo, mensaje, inicial)

    def _preguntar_guardar(self) -> bool | None:
        return dialogos.preguntar_guardar(self.raiz)

    def _menu_perfiles(self, e) -> None:
        """Lista de perfiles al pulsar el nombre (sustituye al desplegable)."""
        menu = tk.Menu(self.raiz, tearoff=0, bg=BOTON, fg=TEXTO, activebackground=ACENTO, activeforeground=FONDO_VENTANA, bd=0, font=fuente(13))
        for nombre in self.estado.nombres():
            menu.add_command(label=nombre, command=lambda n=nombre: self._elegir_activo(n))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

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
        self._pintar_interruptores()
        self._reconstruir_pestanas()
        clave = next((m.clave for m in e.monitores if m.numero == e.mirado), "")
        fijo = e.asignacion(clave) if clave else None
        self.lbl_monitor.configure(text=f"Monitor {e.mirado}")
        self.var_asignacion.set("fijo" if fijo is not None else "activo")
        self.var_fijo.set(fijo or e.activo)
        self._pintar_asignacion(nombres)
        p = e.perfil_editado()
        for nombre, d in self.deslizadores.items():
            d.poner_valor(e.valor(nombre))
            d.poner_preciso(e.preciso)
        self.var_vinculado.set(p.vinculado)
        self.chk_vincular.configure(state="disabled" if p.es_normal else "normal")
        self._mostrar_canales(p.vinculado)
        self._refrescar_ligero()

    def _pintar_interruptores(self) -> None:
        on = bool(self.var_on.get())
        self.btn_on.configure(text="Activo" if on else "Desactivado", punto=VERDE if on else MARCA_NEUTRO)
        ab = bool(self.var_ab.get())
        self.btn_ab.configure(text="A/B: viendo la pantalla normal" if ab else "A/B: viendo el ajuste", estilo="activo" if ab else "normal")

    def _pintar_asignacion(self, nombres: Sequence[str] | None = None) -> None:
        fijo = self.var_asignacion.get() == "fijo"
        self.btn_asig["activo"].configure(estilo="normal" if fijo else "activo")
        self.btn_asig["fijo"].configure(estilo="activo" if fijo else "normal")
        for w in self.marco_fijos.winfo_children():
            w.destroy()
        if not fijo:
            self.marco_fijos.pack_forget()
            return
        self.marco_fijos.pack(fill="x", pady=(px(8), 0))
        disponible = px(self.ANCHO - 2 - 32 - 96)
        fila, usado = None, 0
        for nombre in nombres if nombres is not None else self.estado.nombres():
            for _ in range(2):
                if fila is None:
                    fila = tk.Frame(self.marco_fijos, bg=FONDO_VENTANA)
                    fila.pack(fill="x", padx=(px(96), 0), pady=(0, px(6)))
                    usado = 0
                b = Boton(
                    fila, nombre, lambda n=nombre: self._elegir_fijo(n), estilo="activo" if nombre == self.var_fijo.get() else "chip",
                    alto=28, radio=14, tam=12, relleno=10,
                )
                if usado and usado + b._ancho_px > disponible:  # no cabe: nueva línea
                    b.destroy()
                    fila = None
                    continue
                b.pack(side="left", padx=(0, px(6)))
                usado += b._ancho_px + px(6)
                break

    def _mostrar_canales(self, vinculado: bool) -> None:
        for w in (self.lbl_canales, *self.btn_canal.values()):
            w.pack_forget()
        if vinculado:
            self.lbl_canales.pack(side="left")
            return
        for letra, b in self.btn_canal.items():
            b.pack(side="left", padx=(0, px(6)))
            b.configure(estilo="activo" if letra == self.estado.canal else "normal")

    def _refrescar_ligero(self) -> None:
        """Lo que cambia con cada movimiento de un deslizador (rápido)."""
        e = self.estado
        p = e.perfil_editado()
        self.lbl_editando.configure(text=f"Editando «{p.nombre}»")
        sin = e.sin_guardar(p.nombre)
        if sin:
            self.lbl_sin_guardar.pack(side="left", padx=px(12))
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
        self._fraccion_margen = fraccion
        b = self.barra
        b.delete("all")
        ancho = b.winfo_width() if b.winfo_width() > 1 else px(self.ANCHO // 2)
        alto = px(8)
        rect_redondeado(b, 0, 0, ancho, alto, alto / 2, fill=LINEA, outline="")
        lleno = max(alto, ancho * min(1.0, fraccion))
        if fraccion > 0:
            rect_redondeado(b, 0, 0, lleno, alto, alto / 2, fill=color_margen(fraccion), outline="")

    def _refrescar_confirmaciones(self) -> None:
        ahora = self.reloj()
        s = self.estado.segundos_restantes(ahora)
        if s is None:
            self.marco_fuerte.pack_forget()
        else:
            self.lbl_fuerte.configure(text=f"Ajuste fuerte · se deshará en {s:.0f} s")
            self.marco_fuerte.pack(fill="x", pady=(0, px(14)), before=self.marco_estado)
        if self.estado.puede_deshacer(ahora):
            self.btn_deshacer.pack(side="left", padx=(px(8), 0))
        else:
            self.btn_deshacer.pack_forget()

    def _reconstruir_pestanas(self) -> None:
        for w in self.marco_pestanas.winfo_children():
            w.destroy()
        e = self.estado
        if len(e.monitores) <= 1:
            self.marco_pestanas.pack_forget()
            return
        self.marco_pestanas.pack(fill="x", pady=(0, px(14)), before=self.bloque_monitor)
        for i, p in enumerate(e.pestanas()):
            elegida = p.numero == e.mirado
            fondo = PESTANA_ACTIVA if elegida else PESTANA
            marco = Tarjeta(
                self.marco_pestanas, fondo, ACENTO if elegida else BORDE_BOTON, radio=8, padx=8, pady=7,
                inset=ACENTO if elegida else None, cursor="hand2",
            )
            self.marco_pestanas.columnconfigure(i, weight=1, uniform="pestana")
            marco.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else px(8), 0))
            titulo = f"Monitor {p.numero}" + (" · principal" if p.principal else "")
            sub = f"{p.perfil} ({'fijo' if p.fijo else 'activo'})"
            marco.bind("<Button-1>", lambda ev, n=p.numero: self._mirar(n))
            for texto, col, fuente_ in ((titulo, TEXTO, fuente(13, True)), (sub, ACENTO if p.fijo else TEXTO_SUAVE, fuente(11))):
                lbl = tk.Label(marco, text=texto, bg=fondo, fg=col, font=fuente_, anchor="w", padx=0, pady=0)
                lbl.pack(fill="x")
                lbl.bind("<Button-1>", lambda ev, n=p.numero: self._mirar(n))

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

    def _clic_activo(self) -> None:
        self.var_on.set(not self.var_on.get())
        self._alternar_activo()

    def _alternar_activo(self) -> None:
        self.estado.poner_activo(self.var_on.get())
        self.refrescar()
        self._aplicar()
        self.mensaje("Vislumbra está activo." if self.estado.activo_on else "Vislumbra está desactivado: pantalla original.", TEXTO_SUAVE)

    def _alternar_ab(self) -> None:
        if not self.estado.activo_on:
            self.var_ab.set(False)
            self._pintar_interruptores()
            return
        self.estado.alternar_ab()
        self.var_ab.set(self.estado.ab)
        self._pintar_interruptores()
        self._aplicar()

    def _tecla_espacio(self, ev) -> None:
        if isinstance(ev.widget, tk.Entry):
            return
        self._alternar_ab()

    def _clic_asignacion(self, valor: str) -> None:
        self.var_asignacion.set(valor)
        self._asignacion_cambiada()

    def _elegir_fijo(self, nombre: str) -> None:
        self.var_fijo.set(nombre)
        self._asignacion_cambiada()

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
            sistema.redondear_ventana(r, BORDE_VENTANA)
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
