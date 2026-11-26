# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de las funciones puras de ``vislumbra.color`` (no tocan la pantalla)."""

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
