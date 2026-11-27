# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.widgets``: funciones puras y widgets en una ventana oculta (nunca tocan la gamma)."""

import tkinter as tk
from types import SimpleNamespace

import pytest

from vislumbra import widgets
from vislumbra.widgets import Boton, Casilla, Tarjeta, TextoMixto


# --- Funciones puras ------------------------------------------------------------------------------------
def test_mezclar_y_degradado():
    assert widgets.mezclar("#000000", "#ffffff", 0.0) == "#000000"
    assert widgets.mezclar("#000000", "#ffffff", 1.0) == "#ffffff"
    assert widgets.mezclar("#000000", "#ffffff", 0.5) == "#808080"
    paradas = widgets.DEGRADADO_TEMPERATURA
    assert widgets.degradado(paradas, 0.0) == paradas[0] and widgets.degradado(paradas, 0.5) == paradas[1]
    assert widgets.degradado(paradas, 1.0) == paradas[2] and widgets.degradado(paradas, 7) == paradas[2]


def test_nueva_posicion_mueve_la_ventana_lo_mismo_que_el_raton():
    assert widgets.nueva_posicion((100, 50), (400, 300), (430, 290)) == (130, 40)
    assert widgets.nueva_posicion((100, 50), (400, 300), (400, 300)) == (100, 50)


def test_los_puntos_redondeados_quedan_dentro_del_rectangulo():
    pts = widgets._puntos_redondeados(0, 0, 100, 40, 8)
    xs, ys = pts[0::2], pts[1::2]
    assert min(xs) >= 0 and max(xs) <= 100 and min(ys) >= 0 and max(ys) <= 40
    assert len(pts) == 2 * 4 * 9
    assert widgets._puntos_redondeados(0, 0, 10, 10, 99) and True  # el radio se limita en rect_redondeado


@pytest.fixture
def ventana(ventana):
    """Ventana con fondo en hexadecimal (los widgets mezclan colores con el del padre)."""
    ventana.configure(bg=widgets.FONDO_VENTANA)
    return ventana


# --- Widgets ----------------------------------------------------------------------------------------------
def test_boton_se_comporta_como_un_button(ventana):
    llamadas = []
    b = Boton(ventana, "Guardar", lambda: llamadas.append(1))
    assert b.cget("text") == "Guardar" and b.cget("state") == "normal"
    b.invocar()
    b.configure(state="disabled", text="Otro")
    b.invocar()
    assert llamadas == [1] and b.cget("state") == "disabled" and b.cget("text") == "Otro"
    b.configure(estilo="activo", punto="#9cc47a")  # no deben fallar
    b.configure(state="normal")
    b._soltar(SimpleNamespace(x=-5, y=-5))  # suelta fuera: no cuenta como clic
    assert llamadas == [1]
    b.destroy()


def test_el_ancho_del_boton_sigue_al_texto_y_se_puede_fijar(ventana):
    corto, largo = Boton(ventana, "A"), Boton(ventana, "Un texto bastante largo")
    assert largo.winfo_reqwidth() > corto.winfo_reqwidth()
    assert Boton(ventana, "x", ancho=32).winfo_reqwidth() == widgets.px(32)


def test_casilla_cambia_la_variable_y_llama_al_comando(ventana):
    var, llamadas = tk.BooleanVar(master=ventana, value=False), []
    c = Casilla(ventana, "Vincular", var, lambda: llamadas.append(var.get()))
    c._pulsar(None)
    c._pulsar(None)
    assert llamadas == [True, False]
    c.configure(state="disabled")
    c._pulsar(None)
    assert llamadas == [True, False] and c.cget("state") == "disabled"
    c.destroy()


def test_tarjeta_compensa_el_borde_interno_del_marco(ventana):
    t = Tarjeta(ventana, "#191916", "#34332d", padx=12, pady=10)
    tk.Label(t, text="hola").pack()
    t.pack()
    ventana.update_idletasks()
    assert t.lienzo.winfo_width() == t.winfo_width() and t.lienzo.winfo_height() == t.winfo_height()
    t.destroy()


def test_texto_mixto_parte_el_texto_y_devuelve_el_completo(ventana):
    t = TextoMixto(ventana, " ", 13, "#aaaaaa", 14, "#ffffff", negrita2=True)
    t.configure(text="Editando «Oscuro»")
    assert t.cget("text") == "Editando «Oscuro»" and t._partes() == ("Editando", "«Oscuro»")
    assert len(t.find_all()) == 2
    lados = TextoMixto(ventana, ": ", 12, "#aaaaaa", 12, "#ffffff", lados=True)
    lados.configure(text="Margen de Windows: 19 % de 50 %")
    assert lados._partes() == ("Margen de Windows", "19 % de 50 %")
    lados.configure(text="sin separador")
    assert lados._partes() == ("sin separador", "") and len(lados.find_all()) == 1


def test_dibujar_logo_pone_tres_formas(ventana):
    c = tk.Canvas(ventana)
    widgets.dibujar_logo(c)
    assert len(c.find_all()) == 3
    c.destroy()


def test_selector_se_comporta_como_un_combobox_de_solo_lectura(ventana):
    var, llamadas = tk.StringVar(master=ventana, value="a"), []
    s = widgets.Selector(ventana, var, ["a", "b"], comando=lambda: llamadas.append(var.get()))
    assert list(s.cget("values")) == ["a", "b"] and s.cget("state") == "readonly"
    s.elegir("b")
    assert var.get() == "b" and llamadas == ["b"]
    s.configure(values=["x"], state="disabled")
    assert s.cget("values") == ["x"] and s.cget("state") == "disabled"
    s._abrir(None)  # desactivado: no abre nada
    s.destroy()


def test_campo_redondo_comparte_la_variable_con_su_entry(ventana):
    var = tk.StringVar(master=ventana, value="juego.exe")
    c = widgets.CampoRedondo(ventana, var)
    assert c.entrada.get() == "juego.exe"
    var.set("otro.exe")
    assert c.entrada.get() == "otro.exe"
    c.destroy()
