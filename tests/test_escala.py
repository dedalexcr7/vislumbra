# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.escala`` (funciones puras)."""

import math

import pytest

from vislumbra import color, escala
from vislumbra.escala import PARAMETROS

NOMBRES = list(PARAMETROS)
POSICIONES = [i / 200 for i in range(201)]


@pytest.mark.parametrize("nombre", NOMBRES)
def test_el_neutro_esta_en_el_centro(nombre):
    par = PARAMETROS[nombre]
    assert escala.posicion_a_valor(nombre, 0.5) == pytest.approx(par.neutro, abs=1e-9)
    assert escala.valor_a_posicion(nombre, par.neutro) == pytest.approx(0.5, abs=1e-9)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_los_extremos_son_exactos(nombre):
    par = PARAMETROS[nombre]
    assert escala.posicion_a_valor(nombre, 0.0) == pytest.approx(par.minimo, abs=1e-9)
    assert escala.posicion_a_valor(nombre, 1.0) == pytest.approx(par.maximo, abs=1e-9)
    assert escala.valor_a_posicion(nombre, par.minimo) == pytest.approx(0.0, abs=1e-9)
    assert escala.valor_a_posicion(nombre, par.maximo) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_ida_y_vuelta_posicion_valor(nombre):
    for p in POSICIONES:
        v = escala.posicion_a_valor(nombre, p)
        assert escala.valor_a_posicion(nombre, v) == pytest.approx(p, abs=1e-9)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_la_escala_es_estrictamente_creciente(nombre):
    valores = [escala.posicion_a_valor(nombre, p) for p in POSICIONES]
    assert all(a < b for a, b in zip(valores, valores[1:]))
    assert all(PARAMETROS[nombre].minimo <= v <= PARAMETROS[nombre].maximo for v in valores)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_fuera_de_rango_se_limita(nombre):
    par = PARAMETROS[nombre]
    assert escala.posicion_a_valor(nombre, -3) == pytest.approx(par.minimo)
    assert escala.posicion_a_valor(nombre, 7) == pytest.approx(par.maximo)
    assert escala.valor_a_posicion(nombre, par.minimo - 1e6) == pytest.approx(0.0)
    assert escala.valor_a_posicion(nombre, par.maximo + 1e6) == pytest.approx(1.0)


def test_brillo_y_contraste_son_cuadraticos():
    assert escala.posicion_a_valor("brillo", 0.75) == pytest.approx(25.0)
    assert escala.posicion_a_valor("brillo", 0.25) == pytest.approx(-25.0)
    assert escala.posicion_a_valor("contraste", 0.75) == pytest.approx(10.0)
    assert escala.posicion_a_valor("contraste", 0.25) == pytest.approx(-10.0)


def test_gamma_es_logaritmica_por_tramos():
    assert escala.posicion_a_valor("gamma", 0.25) == pytest.approx(0.5 * 2 ** 0.5)
    assert escala.posicion_a_valor("gamma", 0.75) == pytest.approx(2.0)


def test_temperatura_es_lineal_en_mired_por_tramos():
    p25 = escala.posicion_a_valor("temperatura", 0.25)
    assert 1e6 / p25 == pytest.approx((1e6 / 3300 + 1e6 / 6500) / 2)
    p75 = escala.posicion_a_valor("temperatura", 0.75)
    assert 1e6 / p75 == pytest.approx((1e6 / 6500 + 1e6 / 10000) / 2)
    assert 3300 < p25 < 6500 < p75 < 10000


def test_los_rangos_coinciden_con_color():
    assert PARAMETROS["brillo"].maximo == color.BRILLO_MAX
    assert PARAMETROS["gamma"].minimo == color.GAMMA_MIN
    assert PARAMETROS["temperatura"].minimo == color.TEMPERATURA_MIN


# --- Pasos ---------------------------------------------------------------------------
@pytest.mark.parametrize("nombre, paso, fino", [
    ("brillo", 1.0, 0.1), ("contraste", 0.5, 0.1), ("gamma", 0.05, 0.01), ("temperatura", 100.0, 10.0),
])
def test_pasos_de_la_rueda(nombre, paso, fino):
    neutro = PARAMETROS[nombre].neutro
    assert escala.paso_rueda(nombre, neutro, +1) == pytest.approx(neutro + paso)
    assert escala.paso_rueda(nombre, neutro, -1) == pytest.approx(neutro - paso)
    assert escala.paso_rueda(nombre, neutro, +1, fino=True) == pytest.approx(neutro + fino)


def test_pasos_sin_deriva_decimal():
    v = 0.0
    for _ in range(10):
        v = escala.paso_rueda("contraste", v, +1, fino=True)
    assert v == 1.0
    g = 1.0
    for _ in range(7):
        g = escala.paso_rueda("gamma", g, +1)
    assert g == 1.35


def test_los_pasos_respetan_el_rango_y_no_dan_menos_cero():
    assert escala.paso_rueda("gamma", 4.0, +1) == 4.0
    assert escala.paso_rueda("brillo", -100.0, -1) == -100.0
    assert str(escala.paso_rueda("brillo", 0.5, -1, fino=True)) != "-0.0"
    assert escala.redondear("brillo", -0.0001) == 0.0 and math.copysign(1, escala.redondear("brillo", -0.0001)) == 1


def test_arrastre_fino_es_diez_veces_mas_lento():
    assert escala.arrastre_fino(0.5, 0.6) == pytest.approx(0.51)
    assert escala.arrastre_fino(0.5, 0.4) == pytest.approx(0.49)
    assert escala.arrastre_fino(0.95, 5.0) == 1.0


# --- Modo preciso ------------------------------------------------------------------------------
def test_ventana_del_modo_preciso():
    assert escala.ventana_precisa("gamma", 1.7) == (pytest.approx(1.45), pytest.approx(1.95))
    assert escala.ventana_precisa("brillo", 0.0) == (-10.0, 10.0)
    assert escala.ventana_precisa("gamma", 0.5) == (0.5, pytest.approx(0.75))  # recortada al rango


@pytest.mark.parametrize("nombre", NOMBRES)
def test_modo_preciso_ida_y_vuelta_y_extremos(nombre):
    centro = PARAMETROS[nombre].neutro
    bajo, alto = escala.ventana_precisa(nombre, centro)
    assert escala.posicion_precisa_a_valor(nombre, 0.0, centro) == pytest.approx(bajo, abs=0.01)
    assert escala.posicion_precisa_a_valor(nombre, 1.0, centro) == pytest.approx(alto, abs=0.01)
    assert escala.valor_a_posicion_precisa(nombre, centro, centro) == pytest.approx(0.5)


# --- Texto <-> número -----------------------------------------------------------------------------
@pytest.mark.parametrize("texto, esperado", [
    ("1,7", 1.7), ("1.7", 1.7), (" −3 ", -3.0), ("-3", -3.0), ("6500 K", 6500.0), ("6500k", 6500.0),
    ("0", 0.0), ("+2,5", 2.5),
])
def test_leer_numero_valido(texto, esperado):
    assert escala.leer_numero(texto) == esperado


@pytest.mark.parametrize("texto", ["abc", "", "  ", "1,2,3", "nan", "inf", "-inf", "1e999"])
def test_leer_numero_invalido(texto):
    assert escala.leer_numero(texto) is None


@pytest.mark.parametrize("nombre, valor, esperado", [
    ("brillo", 0, "0,0"), ("brillo", -3.25, "-3,2"), ("contraste", 7.5, "7,5"),
    ("gamma", 1.7, "1,70"), ("gamma", 1, "1,00"), ("temperatura", 6500, "6500"),
])
def test_formatear_con_coma_y_decimales(nombre, valor, esperado):
    assert escala.formatear(nombre, valor) == esperado


def test_formatear_con_unidad():
    assert escala.formatear("temperatura", 6500, con_unidad=True) == "6500 K"
    assert escala.formatear("gamma", 1.7, con_unidad=True) == "1,70"
