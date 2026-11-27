# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.panel``.

Las funciones puras no necesitan Tk. Las de humo crean una ventana oculta y se saltan si no
hay Tk o escritorio. Nunca tocan la pantalla (la gamma): usan un controlador falso.
"""

import tkinter as tk
from types import SimpleNamespace

import pytest

from vislumbra import color, escala, panel
from vislumbra.panel import Deslizador, GraficoCurva

IDENTIDAD = color.rampa_identidad()


# --- Funciones puras ------------------------------------------------------------------------------------
def test_x_y_posicion_son_inversas_y_se_limitan():
    for p in (0.0, 0.25, 0.5, 1.0):
        assert panel.x_a_posicion(panel.posicion_a_x(p, 220, 10), 220, 10) == pytest.approx(p)
    assert panel.x_a_posicion(-50, 220, 10) == 0.0 and panel.x_a_posicion(999, 220, 10) == 1.0
    assert 0.0 <= panel.x_a_posicion(5, 1, 10) <= 1.0  # ancho diminuto: no divide por cero


def test_puntos_de_la_curva_neutra_van_por_la_diagonal():
    pts = panel.puntos_curva(IDENTIDAD, 100, 100, 0)
    assert len(pts) == 64 and pts[0] == pytest.approx((0, 99)) and pts[-1] == pytest.approx((99, 0))
    assert all(abs(x - (99 - y)) < 1.0 for x, y in pts)


def test_puntos_de_cada_canal():
    r = color.construir_rampa_segura(color.Ajuste(g=color.AjusteCanal(gamma=2.0)))
    verde = panel.puntos_curva(r, 100, 100, 1)
    rojo = panel.puntos_curva(r, 100, 100, 0)
    assert verde[32][1] < rojo[32][1]  # gamma > 1 sube los medios: «y» menor (arriba)


def test_margen_de_windows_y_canales_iguales():
    assert panel.margen_windows(IDENTIDAD) == (0.0, 50.0)
    usado, limite = panel.margen_windows(color.construir_rampa_segura(color.Ajuste.uniforme(0, 7.5, 1.7)))
    assert 10 < usado < 30 and limite == 50.0  # «19 % de 50 %» en el plan
    assert panel.canales_iguales(IDENTIDAD)
    assert not panel.canales_iguales(color.construir_rampa_segura(color.Ajuste(r=color.AjusteCanal(gamma=1.5))))


# --- Humo con Tk ------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def raiz():
    try:
        r = tk.Tk()
    except tk.TclError as e:  # sin Tk o sin escritorio
        pytest.skip(f"no hay Tk: {e}")
    r.withdraw()
    yield r
    r.destroy()


def evento(x=0, state=0, delta=0):
    return SimpleNamespace(x=x, state=state, delta=delta)


def deslizador(raiz, parametro="gamma", valor=1.7, respuesta=None):
    llamadas = []

    def al_cambiar(p, v):
        llamadas.append((p, v))
        return respuesta(v) if respuesta else None

    d = Deslizador(raiz, parametro, al_cambiar)
    d.pista.winfo_width = lambda: 220  # la ventana está oculta: se fija el ancho a mano
    d.poner_valor(valor)
    return d, llamadas


def test_el_campo_muestra_el_valor_con_coma(raiz):
    d, _ = deslizador(raiz)
    assert d.texto.get() == "1,70"
    d.poner_valor(6500.0)  # fuera de rango para gamma: se limita
    assert d.texto.get() == "4,00"
    d.destroy()


def test_rueda_y_mayus(raiz):
    d, llamadas = deslizador(raiz)
    d._al_rueda(evento(delta=120))
    d._al_rueda(evento(delta=-120))
    d._al_rueda(evento(delta=120, state=panel.SHIFT))
    assert [round(v, 2) for _, v in llamadas] == [1.75, 1.7, 1.71]
    d.destroy()


def test_flechas_y_botones(raiz):
    d, llamadas = deslizador(raiz, "temperatura", 6500.0)
    d.pista.event_generate("<Right>")
    d.pista.event_generate("<Left>")
    d._paso(1, False)
    assert [v for _, v in llamadas][-1] == 6600.0
    d.destroy()


def test_escribir_un_numero_con_coma(raiz):
    d, llamadas = deslizador(raiz)
    d.texto.set("1,9")
    d._desde_texto()
    assert llamadas == [("gamma", 1.9)] and d.texto.get() == "1,90"
    d.texto.set("abc")
    d._desde_texto()
    assert len(llamadas) == 1 and d.texto.get() == "1,90"  # no es un número: se queda como estaba
    d.texto.set("99")
    d._desde_texto()
    assert llamadas[-1] == ("gamma", 4.0)  # se limita al rango
    d.destroy()


def test_enter_con_el_mismo_valor_no_llama(raiz):
    d, llamadas = deslizador(raiz)
    d.texto.set("1,7")
    d._desde_texto()
    assert llamadas == []
    d.destroy()


def test_doble_clic_vuelve_al_neutro(raiz):
    d, llamadas = deslizador(raiz)
    d._al_doble_clic(evento())
    assert llamadas[-1] == ("gamma", 1.0) and d.valor == 1.0
    d.destroy()


def test_el_tope_coloca_el_deslizador_en_el_valor_devuelto(raiz):
    d, llamadas = deslizador(raiz, respuesta=lambda v: min(v, 2.2))
    d._pedir(3.5)
    assert llamadas == [("gamma", 3.5)] and d.valor == 2.2 and d.texto.get() == "2,20"
    d.destroy()


def test_arrastrar_y_arrastrar_con_mayus(raiz):
    d, llamadas = deslizador(raiz, valor=1.0)
    d._al_pulsar(evento(x=110))  # centro de la pista: neutro
    assert d.valor == pytest.approx(1.0, abs=0.01)
    d._al_arrastrar(evento(x=210))
    assert d.valor == 4.0
    d._al_soltar(evento())
    d.poner_valor(1.0)
    d._al_pulsar(evento(x=110))
    d._al_arrastrar(evento(x=160, state=panel.SHIFT))  # fija la referencia: sin cambio
    d._al_arrastrar(evento(x=210, state=panel.SHIFT))  # 0,25 de recorrido -> 0,025 de posición
    assert d.valor == pytest.approx(escala.posicion_a_valor("gamma", 0.525), abs=0.01)
    d._al_soltar(evento())
    d.destroy()


def test_modo_preciso_usa_pasos_finos_y_recentra(raiz):
    d, llamadas = deslizador(raiz)
    d.poner_preciso(True)
    d._al_rueda(evento(delta=120))
    assert llamadas[-1] == ("gamma", 1.71)  # paso fino aunque no se pulse Mayús
    # La pista cubre ±0,25 alrededor del valor: el centro del recorrido es el valor actual.
    assert d._posicion() == pytest.approx(0.5)
    d._al_pulsar(evento(x=210))
    d._al_soltar(evento())
    assert d.valor == pytest.approx(1.96, abs=0.01) and d._posicion() == pytest.approx(0.5)  # recentrado
    d.poner_preciso(False)
    assert d._posicion() == pytest.approx(escala.valor_a_posicion("gamma", d.valor))
    d.destroy()


def test_dibujar_no_falla_con_ningun_valor(raiz):
    for nombre, par in escala.PARAMETROS.items():
        d, _ = deslizador(raiz, nombre, par.neutro)
        for v in (par.minimo, par.maximo, par.neutro):
            d.poner_valor(v)
        d.poner_preciso(True)
        d.poner_valor(par.minimo)
        d.destroy()


def test_grafico_dibuja_una_curva_o_tres(raiz):
    g = GraficoCurva(raiz)
    base = len(g.find_all())
    g.dibujar(IDENTIDAD)
    assert len(g.find_all()) == base + 1  # una sola línea: los canales son iguales
    desigual = color.construir_rampa_segura(color.Ajuste(r=color.AjusteCanal(gamma=1.5)))
    g.dibujar(desigual)
    assert len(g.find_all()) == base + 3
    g.dibujar(None)
    assert len(g.find_all()) == base
    g.destroy()
