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
    dict(brillo=125), dict(brillo=-125), dict(contraste=82), dict(contraste=-82),
    dict(gamma=0.5), dict(gamma=4.0), dict(temperatura=2500), dict(temperatura=10000),
])
def test_los_extremos_de_cada_rango_son_validos(extremo):
    color.validar_ajuste(Ajuste.uniforme(**extremo))


@pytest.mark.parametrize("malo", [
    dict(gamma=7), dict(gamma=0), dict(gamma=-1), dict(gamma=0.49),
    dict(brillo=126), dict(brillo=-125.5), dict(contraste=83), dict(contraste=-90),
    dict(temperatura=2000), dict(temperatura=12000),
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
    assert color.brillo_a_desplazamiento(125) == pytest.approx(0.5)
    assert color.contraste_a_factor(0) == 1
    assert 0 < color.contraste_a_factor(-82) < 1 < color.contraste_a_factor(82)


GRILLA = [
    Ajuste.uniforme(brillo=b, contraste=c, gamma=g, temperatura=t)
    for b, c, g, t in itertools.product(
        (-125, -60, 0, 60, 125), (-82, -30, 0, 5, 30, 82),
        (0.5, 1.0, 1.7, 2.5, 4.0), (2500, 6500, 10000),
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
    r = color.construir_rampa(Ajuste.uniforme(temperatura=3000))
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
        color.validar_rampa(_rampa_con([30000] * 256))
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
        color.validar_rampa(_rampa_con(oscura))
    # Rango completo, pero casi todo blanco: el valor central queda fuera de margen.
    clara = [0] + [64000] * 255
    with pytest.raises(RampaIlegible, match="valor central"):
        color.validar_rampa(_rampa_con(clara))


def test_validar_rampa_rechaza_longitud_y_valores_invalidos():
    with pytest.raises(RampaIlegible):
        color.validar_rampa(IDENTIDAD)
    with pytest.raises(RampaIlegible, match="no válidos"):
        color.validar_rampa(_rampa_con([0] * 255 + [70000]))


def test_las_esquinas_del_plan_se_rechazan():
    for b in (125, -125):
        r = color.construir_rampa(Ajuste.uniforme(brillo=b, contraste=-82))
        with pytest.raises(RampaIlegible):
            color.validar_rampa(r)
    with pytest.raises(RampaIlegible):
        color.validar_rampa(color.construir_rampa(Ajuste.uniforme(brillo=125)))


def test_invariante_de_seguridad_en_la_rejilla():
    """Toda combinación o valida o lanza RampaIlegible; lo que pasa es monótono y de rango amplio."""
    validas = 0
    for a in GRILLA:
        r = color.construir_rampa(a)
        try:
            color.validar_rampa(r)
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
    color.validar_rampa(color.construir_rampa(ajuste))
