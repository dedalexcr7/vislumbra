# SPDX-License-Identifier: GPL-3.0-or-later
"""Diálogos con el tema oscuro de la maqueta (sustituyen a los de Tk, que salen claros).

Ventana sin barra, con cabecera propia como el panel. ``Dialogo`` no bloquea: ``ejecutar`` lo
muestra y espera el resultado; las pruebas usan ``Dialogo`` directamente.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from . import sistema
from .estado import Estado
from .perfiles import ErrorPerfil
from .programas import ALCANCE_ACTIVO, ALCANCE_VENTANA, alcance_de_monitor, clave_de_alcance
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
        self._cuerpo = cuerpo
        tk.Label(
            cuerpo, text=mensaje, bg=FONDO_VENTANA, fg=TEXTO, font=fuente(13), anchor="w", justify="left", wraplength=px(self.ANCHO_TEXTO),
        ).pack(fill="x")
        if campo is not None:
            self._crear_campo(cuerpo, campo)
        fila = tk.Frame(cuerpo, bg=FONDO_VENTANA)
        fila.pack(fill="x", pady=(px(16), 0))
        self._fila = fila
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


# --- Programas asociados a perfiles ----------------------------------------------------------------------------
ETIQUETA_VENTANA = "El monitor donde esté el programa"
ETIQUETA_MONITOR = "Un monitor concreto"
ETIQUETA_ACTIVO = "El perfil activo (todos los monitores que lo siguen)"
ETIQUETAS_ALCANCE = (ETIQUETA_VENTANA, ETIQUETA_MONITOR, ETIQUETA_ACTIVO)


class DialogoProgramas(Dialogo):
    """Programas (.exe) y el perfil que se activa solo cuando están abiertos, y en qué monitores.

    Al elegir una fila de la lista, sus datos pasan al formulario y se pueden cambiar con «Guardar cambios»
    (perfil, alcance e incluso el nombre del programa) sin borrar y volver a crear.
    """

    _COLOR_ERROR = "#e06a5a"

    def __init__(self, raiz: tk.Misc, estado: Estado, procesos_abiertos: Callable[[], list[str]], al_cambiar: Callable[[], None]):
        super().__init__(
            raiz, "Programas y perfiles",
            "Cuando uno de estos programas esté abierto se activa su perfil; al cerrarlo vuelve el de antes.",
            [("Cerrar", None, "activo")],
        )
        self.estado, self._procesos, self._al_cambiar = estado, procesos_abiertos, al_cambiar
        self._monitores = {self._etiqueta_monitor(m): m.clave for m in estado.monitores}
        marco = tk.Frame(self._cuerpo, bg=FONDO_VENTANA)
        marco.pack(before=self._fila, fill="x", pady=(px(12), 0))
        self.lista = tk.Listbox(
            marco, height=6, width=52, bg=CAMPO, fg=TEXTO, selectbackground=BORDE_BOTON, selectforeground=TEXTO, relief="flat",
            highlightthickness=1, highlightbackground=BORDE_BOTON, activestyle="none", exportselection=False, font=fuente(12),
        )
        self.lista.pack(fill="x")
        self.lista.bind("<<ListboxSelect>>", lambda e: self._cargar_seleccion())
        Boton(marco, "Quitar el seleccionado", self._quitar, minimo=76).pack(anchor="e", pady=(px(6), 0))
        self.lbl_forma = tk.Label(marco, text="Añadir un programa", bg=FONDO_VENTANA, fg=TEXTO, font=fuente(12, True), anchor="w")
        self.lbl_forma.pack(fill="x", pady=(px(10), 0))
        self.var_exe = tk.StringVar(master=self)
        self.entrada = tk.Entry(
            marco, textvariable=self.var_exe, bg=CAMPO, fg=TEXTO, insertbackground=TEXTO, relief="flat", highlightthickness=1,
            highlightbackground=BORDE_BOTON, highlightcolor=ACENTO, font=fuente(12),
        )
        self.entrada.pack(fill="x", pady=(px(4), 0), ipady=px(3))
        self.entrada.bind("<Button-1>", lambda e: self.entrada.focus_force(), add="+")
        tk.Label(marco, text="Escribe su nombre (juego.exe) o elígelo entre los abiertos:", bg=FONDO_VENTANA, fg=TEXTO, font=fuente(11), anchor="w").pack(fill="x", pady=(px(4), 0))
        self.var_abiertos = tk.StringVar(master=self)
        self.combo_abiertos = ttk.Combobox(marco, textvariable=self.var_abiertos, state="readonly", values=self._abiertos(), font=fuente(12))
        self.combo_abiertos.pack(fill="x", pady=(px(2), 0))
        self.combo_abiertos.bind("<<ComboboxSelected>>", lambda e: self.var_exe.set(self.var_abiertos.get()))
        fila = tk.Frame(marco, bg=FONDO_VENTANA)
        fila.pack(fill="x", pady=(px(8), 0))
        tk.Label(fila, text="Perfil", bg=FONDO_VENTANA, fg=TEXTO, font=fuente(12), width=8, anchor="w").pack(side="left")
        self.var_perfil = tk.StringVar(master=self, value=estado.activo)
        self.combo_perfil = ttk.Combobox(fila, textvariable=self.var_perfil, state="readonly", values=estado.nombres(), width=24, font=fuente(12))
        self.combo_perfil.pack(side="left")
        fila2 = tk.Frame(marco, bg=FONDO_VENTANA)
        fila2.pack(fill="x", pady=(px(6), 0))
        tk.Label(fila2, text="Aplicar a", bg=FONDO_VENTANA, fg=TEXTO, font=fuente(12), width=8, anchor="w").pack(side="left")
        self.var_alcance = tk.StringVar(master=self, value=ETIQUETA_VENTANA)
        self.combo_alcance = ttk.Combobox(fila2, textvariable=self.var_alcance, state="readonly", values=list(ETIQUETAS_ALCANCE), width=24, font=fuente(12))
        self.combo_alcance.pack(side="left")
        self.combo_alcance.bind("<<ComboboxSelected>>", lambda e: self._alcance_cambiado())
        self.var_monitor = tk.StringVar(master=self, value=next(iter(self._monitores), ""))
        self.combo_monitor = ttk.Combobox(marco, textvariable=self.var_monitor, state="disabled", values=list(self._monitores), font=fuente(12))
        self.combo_monitor.pack(fill="x", pady=(px(4), 0))
        botones = tk.Frame(marco, bg=FONDO_VENTANA)
        botones.pack(fill="x", pady=(px(10), 0))
        self.btn_guardar = Boton(botones, "Guardar cambios", self._guardar_cambios, minimo=76)
        self.btn_guardar.pack(side="right", padx=(px(8), 0))
        Boton(botones, "Añadir", self._anadir, estilo="activo", minimo=76).pack(side="right")
        self.lbl_error = tk.Label(marco, text="", bg=FONDO_VENTANA, fg=self._COLOR_ERROR, font=fuente(11), anchor="w", justify="left", wraplength=px(self.ANCHO_TEXTO))
        self.lbl_error.pack(fill="x", pady=(px(6), 0))
        self._editando: str | None = None  # el programa de la fila elegida
        self._refrescar_lista()

    # -- datos ---------------------------------------------------------------------------------------------
    @staticmethod
    def _etiqueta_monitor(m) -> str:
        return f"Monitor {m.numero}" + (" · principal" if m.principal else "")

    def _abiertos(self) -> list[str]:
        try:
            return list(self._procesos())
        except OSError:
            return []

    def _texto_alcance(self, alcance: str) -> str:
        if alcance == ALCANCE_VENTANA:
            return "monitor donde esté"
        clave = clave_de_alcance(alcance)
        if clave is not None:
            return next((et for et, c in self._monitores.items() if c == clave), "monitor no conectado")
        return "perfil activo"

    def filas(self) -> list[str]:
        return [f"{a.exe}  →  {a.perfil}  ·  {self._texto_alcance(a.alcance)}" for a in self.estado.programas]

    def alcance_elegido(self) -> str:
        """El alcance que dice el formulario («activo», «ventana» o «monitor:<clave>»)."""
        et = self.var_alcance.get()
        if et == ETIQUETA_ACTIVO:
            return ALCANCE_ACTIVO
        if et == ETIQUETA_MONITOR:
            clave = self._monitores.get(self.var_monitor.get())
            if clave is None:
                raise ErrorPerfil("elige el monitor.")
            return alcance_de_monitor(clave)
        return ALCANCE_VENTANA

    def _alcance_cambiado(self) -> None:
        self.combo_monitor.configure(state="readonly" if self.var_alcance.get() == ETIQUETA_MONITOR else "disabled")

    def _refrescar_lista(self) -> None:
        self.lista.delete(0, "end")
        for texto in self.filas():
            self.lista.insert("end", texto)
        self.btn_guardar.configure(state="normal" if self._editando else "disabled")

    # -- acciones ------------------------------------------------------------------------------------------
    def _cargar_seleccion(self) -> None:
        """Pasa la fila elegida al formulario, para cambiarla sin borrarla."""
        seleccion = self.lista.curselection()
        if not seleccion or seleccion[0] >= len(self.estado.programas):
            return
        a = self.estado.programas[seleccion[0]]
        self._editando = a.exe
        self.var_exe.set(a.exe)
        self.var_perfil.set(a.perfil)
        clave = clave_de_alcance(a.alcance)
        if clave is not None:
            self.var_alcance.set(ETIQUETA_MONITOR)
            etiqueta = next((et for et, c in self._monitores.items() if c == clave), None)
            if etiqueta:
                self.var_monitor.set(etiqueta)
        else:
            self.var_alcance.set(ETIQUETA_VENTANA if a.alcance == ALCANCE_VENTANA else ETIQUETA_ACTIVO)
        self._alcance_cambiado()
        self.lbl_forma.configure(text=f"Cambiar «{a.exe}»")
        self.lbl_error.configure(text="")

    def _terminar(self) -> None:
        self.lbl_error.configure(text="")
        self._editando = None
        self.lbl_forma.configure(text="Añadir un programa")
        self.var_exe.set("")
        self.lista.selection_clear(0, "end")
        self._refrescar_lista()
        self._al_cambiar()

    def _error(self, e: Exception) -> None:
        self.lbl_error.configure(text=str(e)[:1].upper() + str(e)[1:])

    def _anadir(self) -> None:
        try:
            self.estado.asociar_programa(self.var_exe.get(), self.var_perfil.get(), self.alcance_elegido())
        except ErrorPerfil as e:
            return self._error(e)
        self._terminar()

    def _guardar_cambios(self) -> None:
        if self._editando is None:
            return self._error(ErrorPerfil("elige primero un programa de la lista."))
        try:
            self.estado.modificar_programa(self._editando, self.var_exe.get(), self.var_perfil.get(), self.alcance_elegido())
        except ErrorPerfil as e:
            return self._error(e)
        self._terminar()

    def _quitar(self) -> None:
        seleccion = self.lista.curselection()
        if not seleccion:
            return self._error(ErrorPerfil("elige primero un programa de la lista."))
        self.estado.quitar_programa(self.estado.programas[seleccion[0]].exe)
        self._terminar()


def programas(raiz: tk.Misc, estado: Estado, procesos_abiertos: Callable[[], list[str]], al_cambiar: Callable[[], None]) -> None:
    ejecutar(raiz, DialogoProgramas(raiz, estado, procesos_abiertos, al_cambiar))
