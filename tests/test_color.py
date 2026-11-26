# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de las funciones puras de ``vislumbra.color`` (no tocan la pantalla)."""

import itertools
import math

import pytest

from vislumbra import color
from vislumbra.color import Ajuste, AjusteCanal, ValorFueraDeRango


# --- Validación de ajustes ----------------------------------------------------
def test_ajuste_neutro_es_valido():
    color.validar_ajuste(Ajuste())
    assert Ajuste() == Ajuste.uniforme()


@pytest.mark.parametrize("extremo", [
    dict(brillo=100), dict(brillo=-100), dict(contraste=40), dict(contraste=-40),
    dict(gamma=0.5), dict(gamma=4.0), dict(temperatura=3300), dict(temperatura=10000),
])
def test_los_extremos_de_cada_rango_son_validos(extremo):
    color.validar_ajuste(Ajuste.uniforme(**extremo))


@pytest.mark.parametrize("malo", [
    dict(gamma=7), dict(gamma=0), dict(gamma=-1), dict(gamma=0.49),
    dict(brillo=101), dict(brillo=-100.5), dict(contraste=41), dict(contraste=-90),
    dict(temperatura=2000), dict(temperatura=3299), dict(temperatura=12000),
])
def test_valores_fuera_de_rango_se_rechazan(malo):
    with pytest.raises(ValorFueraDeRango):
        color.validar_ajuste(Ajuste.uniforme(**malo))


@pytest.mark.parametrize("campo", ["brillo", "contraste", "gamma", "temperatura"])
@pytest.mark.parametrize("valor", [math.nan, math.inf, -math.inf])
def test_nan_e_infinito_se_rechazan_en_español(campo, valor):
    with pytest.raises(ValorFueraDeRango, match="número finito"):
        color.validar_ajuste(Ajuste.uniforme(**{campo: valor}))


def test_mensaje_de_rango_en_español_con_coma_decimal():
    with pytest.raises(ValorFueraDeRango) as e:
        color.validar_ajuste(Ajuste.uniforme(gamma=7))
    assert str(e.value) == "gamma 7,0 está fuera del rango permitido (0,5 a 4,0)."


def test_el_mensaje_indica_el_canal_si_los_canales_difieren():
    a = Ajuste(g=AjusteCanal(gamma=9.0))
    with pytest.raises(ValorFueraDeRango, match="gamma del canal G"):
        color.validar_ajuste(a)


# --- Curva y rampa ------------------------------------------------------------
IDENTIDAD = [i * 257 for i in range(256)]


def test_identidad_exacta():
    assert color.curva_canal(AjusteCanal()) == IDENTIDAD
    assert color.rampa_identidad() == IDENTIDAD * 3
    assert color.construir_rampa(Ajuste()) == IDENTIDAD * 3


def test_construir_rampa_tiene_768_enteros_en_rango():
    r = color.construir_rampa(Ajuste.uniforme(brillo=10, contraste=5, gamma=1.7))
    assert len(r) == color.LONGITUD_RAMPA == 768
    assert all(isinstance(x, int) and 0 <= x <= 65535 for x in r)


def test_gamma_mayor_que_uno_sube_los_medios_y_menor_los_baja():
    claro = color.curva_canal(AjusteCanal(gamma=2.0))
    oscuro = color.curva_canal(AjusteCanal(gamma=0.7))
    assert claro[128] > IDENTIDAD[128] > oscuro[128]
    for curva in (claro, oscuro):
        assert curva[0] == 0 and curva[255] == 65535


def test_brillo_sube_y_baja_con_recorte():
    sube = color.curva_canal(AjusteCanal(brillo=50))
    baja = color.curva_canal(AjusteCanal(brillo=-50))
    assert sube[128] > IDENTIDAD[128] > baja[128]
    assert sube[255] == 65535 and baja[0] == 0  # recorte


def test_contraste_aleja_o_acerca_de_los_medios_con_recorte():
    alto = color.curva_canal(AjusteCanal(contraste=40))
    bajo = color.curva_canal(AjusteCanal(contraste=-40))
    assert alto[64] < IDENTIDAD[64] and alto[192] > IDENTIDAD[192]
    assert bajo[64] > IDENTIDAD[64] and bajo[192] < IDENTIDAD[192]
    assert alto[0] == 0 and alto[255] == 65535  # recorte
    assert bajo[255] - bajo[0] < 65535  # contraste bajo reduce el rango


def test_conversiones_de_escala():
    assert color.brillo_a_desplazamiento(0) == 0
    assert color.brillo_a_desplazamiento(100) == pytest.approx(100 / 375)
    assert color.contraste_a_factor(75) == pytest.approx(2.0)
    assert color.contraste_a_factor(0) == 1
    assert 0 < color.contraste_a_factor(-40) < 1 < color.contraste_a_factor(40)


GRILLA = [
    Ajuste.uniforme(brillo=b, contraste=c, gamma=g, temperatura=t)
    for b, c, g, t in itertools.product(
        (-100, -60, 0, 60, 100), (-40, -20, 0, 5, 20, 40),
        (0.5, 1.0, 1.7, 2.5, 4.0), (3300, 6500, 10000),
    )
]


@pytest.mark.parametrize("a", GRILLA[::7])
def test_curvas_monotonas_y_en_rango_en_una_rejilla(a):
    r = color.construir_rampa(a)
    for canal in (r[:256], r[256:512], r[512:]):
        assert all(x <= y for x, y in zip(canal, canal[1:]))
        assert all(0 <= x <= 65535 for x in canal)


# --- Temperatura de color -----------------------------------------------------
def test_6500_kelvin_es_neutro_exacto():
    assert color.kelvin_a_rgb(6500) == (1.0, 1.0, 1.0)


@pytest.mark.parametrize("k", range(2500, 10001, 250))
def test_canales_de_temperatura_en_cero_uno(k):
    assert all(0 < c <= 1 for c in color.kelvin_a_rgb(k))


def test_tendencias_de_temperatura():
    r, g, b = color.kelvin_a_rgb(3000)
    assert b < r
    r, g, b = color.kelvin_a_rgb(10000)
    assert r < b


def test_valores_de_ejemplo_del_plan():
    esperado = {2500: (1.0, 0.626, 0.28), 4000: (1.0, 0.81, 0.664), 10000: (0.776, 0.841, 1.0)}
    for k, e in esperado.items():
        assert color.kelvin_a_rgb(k) == pytest.approx(e, abs=0.01)


@pytest.mark.parametrize("k", [math.nan, math.inf, 0, -5])
def test_kelvin_invalido_se_rechaza(k):
    with pytest.raises(ValorFueraDeRango):
        color.kelvin_a_rgb(k)


def test_la_temperatura_se_aplica_a_la_rampa():
    r = color.construir_rampa(Ajuste.uniforme(temperatura=3500))
    rojo, verde, azul = r[255], r[256 + 255], r[512 + 255]
    assert rojo == 65535 and azul < verde < rojo


# --- Validación de rampas -----------------------------------------------------
from vislumbra.color import RampaIlegible  # noqa: E402


def _rampa_con(canal0):
    return list(canal0) + IDENTIDAD + IDENTIDAD


def test_validar_rampa_acepta_la_identidad():
    color.validar_rampa(color.rampa_identidad())


def test_validar_rampa_rechaza_rampas_planas_e_invertidas():
    with pytest.raises(RampaIlegible, match="rango de salida"):
        color.validar_legibilidad(_rampa_con([30000] * 256))
    with pytest.raises(RampaIlegible, match="no monótono"):
        color.validar_rampa(_rampa_con(IDENTIDAD[::-1]))


def test_validar_rampa_rechaza_no_monotona():
    mala = list(IDENTIDAD)
    mala[100], mala[101] = mala[101], mala[100]
    with pytest.raises(RampaIlegible, match="no monótono"):
        color.validar_rampa(_rampa_con(mala))


def test_validar_rampa_rechaza_demasiado_oscura_o_clara():
    oscura = [round(i / 255 * 0.2 * 65535) for i in range(256)]
    with pytest.raises(RampaIlegible, match="rango de salida"):
        color.validar_legibilidad(_rampa_con(oscura))
    # Rango completo, pero casi todo blanco: el valor central queda fuera de margen.
    clara = [0] + [64000] * 255
    with pytest.raises(RampaIlegible, match="valor central"):
        color.validar_legibilidad(_rampa_con(clara))


def test_validar_rampa_rechaza_longitud_y_valores_invalidos():
    with pytest.raises(RampaIlegible):
        color.validar_rampa(IDENTIDAD)
    with pytest.raises(RampaIlegible, match="no válidos"):
        color.validar_rampa(_rampa_con([0] * 255 + [70000]))


def test_las_esquinas_de_brillo_y_contraste_con_gamma_neutro_son_legibles():
    for b in (100, -100):
        for c in (40, -40):
            color.construir_rampa_segura(Ajuste.uniforme(brillo=b, contraste=c))


def test_brillo_muy_bajo_con_gamma_bajo_se_rechaza():
    # El centro de la rampa queda por debajo del 10 %: la pantalla sería casi ilegible.
    with pytest.raises(RampaIlegible):
        color.construir_rampa_segura(Ajuste.uniforme(brillo=-100, gamma=0.5))


def test_invariante_de_seguridad_en_la_rejilla():
    """Toda combinación o valida o lanza RampaIlegible; lo que pasa es monótono y de rango amplio."""
    validas = 0
    for a in GRILLA:
        try:
            r = color.construir_rampa_segura(a)
        except RampaIlegible:
            continue
        validas += 1
        for canal in (r[:256], r[256:512], r[512:]):
            assert all(x <= y for x, y in zip(canal, canal[1:]))
            assert canal[-1] - canal[0] >= color.RANGO_SALIDA_MIN * 65535 - 1
    assert validas > 0


@pytest.mark.parametrize("ajuste", [
    Ajuste(),
    Ajuste.uniforme(contraste=5, gamma=1.7),
    Ajuste.uniforme(contraste=5, gamma=2.5),
])
def test_neutro_y_valores_de_referencia_validan(ajuste):
    color.construir_rampa_segura(ajuste)


# --- Límite de desviación de Windows (I-12) ---------------------------------------
def test_desviacion_de_la_identidad_es_cero():
    assert color.desviacion(color.rampa_identidad()) == 0


def test_desviacion_mide_la_mayor_distancia():
    r = color.rampa_identidad()
    r[300] += 1234
    assert color.desviacion(r) == 1234


@pytest.mark.parametrize("ajuste", [
    Ajuste.uniforme(temperatura=3300, contraste=-20),  # 52,7 % según el plan
    Ajuste.uniforme(temperatura=3300, brillo=-45),  # 54,5 %
])
def test_i12_se_rechaza_lo_que_windows_rechazaria(ajuste):
    with pytest.raises(RampaIlegible, match="supera lo que Windows permite"):
        color.construir_rampa_segura(ajuste)


@pytest.mark.parametrize("ajuste", [
    Ajuste.uniforme(temperatura=3300),  # 31 652
    Ajuste.uniforme(gamma=4.0),
    Ajuste.uniforme(contraste=7.5, gamma=1.7),
    Ajuste.uniforme(contraste=7.5, gamma=2.5),
])
def test_i12_siguen_siendo_validos(ajuste):
    r = color.construir_rampa(ajuste)
    assert color.desviacion(r) <= color.DESVIACION_MAX
    color.validar_rampa(r)


# --- Legibilidad sin el tinte (I-4) ---------------------------------------------------
def test_validar_legibilidad_acepta_la_identidad():
    color.validar_legibilidad(color.rampa_identidad())


def test_i4_la_legibilidad_se_juzga_sin_el_tinte():
    """3300 K baja el azul al 40 %: sin tinte se ve bien, y el tinte solo cuenta para Windows."""
    a = Ajuste.uniforme(temperatura=3300)
    color.validar_legibilidad(color.construir_rampa(Ajuste.uniforme()))
    color.construir_rampa_segura(a)  # no lanza


def test_i4_el_rechazo_dice_la_causa_real():
    """Con 3300 K y brillo −45 la causa es el límite de Windows, no la legibilidad."""
    with pytest.raises(RampaIlegible, match="supera lo que Windows permite"):
        color.construir_rampa_segura(Ajuste.uniforme(temperatura=3300, brillo=-45))
    with pytest.raises(RampaIlegible, match="casi ilegible"):
        color.construir_rampa_segura(Ajuste.uniforme(brillo=-100, gamma=0.5))
