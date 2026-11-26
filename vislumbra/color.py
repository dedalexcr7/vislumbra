# SPDX-License-Identifier: GPL-3.0-or-later
"""Cálculo de la rampa de gamma: funciones puras, sin pantalla ni ``ctypes``.

Valores de usuario (los que escribe quien usa la app):
    brillo, contraste: 0 = neutro; gamma: 1,0 = neutro; temperatura: 6500 K = neutro.

Las constantes de escala son **provisionales**: se calibran probando en pantalla.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

# --- Rangos de usuario y escala (provisionales) -----------------------------
BRILLO_MIN, BRILLO_MAX = -125.0, 125.0
CONTRASTE_MIN, CONTRASTE_MAX = -82.0, 82.0
GAMMA_MIN, GAMMA_MAX = 0.5, 4.0
TEMPERATURA_MIN, TEMPERATURA_MAX = 2500.0, 10000.0
TEMPERATURA_NEUTRA = 6500.0

BRILLO_POR_UNIDAD = 1.0 / 250.0  # brillo ±125 -> desplazamiento ±0,5
CONTRASTE_ESCALA = 50.0  # factor de contraste = 2 ** (contraste / 50)

# --- Tamaños de la rampa de Windows ------------------------------------------
PUNTOS = 256
MAXIMO = 65535
LONGITUD_RAMPA = 3 * PUNTOS

Rampa = list[int]  # 768 enteros 0..65535: 256 de R, 256 de G y 256 de B


class ErrorColor(ValueError):
    """Error de valores de color; el mensaje va en español."""


class ValorFueraDeRango(ErrorColor):
    """Un parámetro no es un número finito o está fuera de su rango permitido."""


class RampaIlegible(ErrorColor):
    """La rampa dejaría la pantalla casi ilegible y no debe aplicarse."""


@dataclass(frozen=True)
class AjusteCanal:
    brillo: float = 0.0
    contraste: float = 0.0
    gamma: float = 1.0


@dataclass(frozen=True)
class Ajuste:
    r: AjusteCanal = AjusteCanal()
    g: AjusteCanal = AjusteCanal()
    b: AjusteCanal = AjusteCanal()
    temperatura: float = TEMPERATURA_NEUTRA

    @classmethod
    def uniforme(
        cls,
        brillo: float = 0.0,
        contraste: float = 0.0,
        gamma: float = 1.0,
        temperatura: float = TEMPERATURA_NEUTRA,
    ) -> "Ajuste":
        canal = AjusteCanal(brillo, contraste, gamma)
        return cls(canal, canal, canal, temperatura)


def _num(x: float, decimales: int) -> str:
    return f"{x:.{decimales}f}".replace(".", ",")


def _comprobar(nombre: str, valor: float, minimo: float, maximo: float, decimales: int) -> None:
    if not math.isfinite(valor):
        raise ValorFueraDeRango(f"{nombre} debe ser un número finito.")
    if not minimo <= valor <= maximo:
        raise ValorFueraDeRango(
            f"{nombre} {_num(valor, decimales)} está fuera del rango permitido "
            f"({_num(minimo, decimales)} a {_num(maximo, decimales)})."
        )


def validar_ajuste(a: Ajuste) -> None:
    """Lanza ``ValorFueraDeRango`` si algún valor no es finito o se sale de su rango."""
    canales = (("R", a.r), ("G", a.g), ("B", a.b))
    uniforme = a.r == a.g == a.b
    for letra, c in canales:
        sufijo = "" if uniforme else f" del canal {letra}"
        _comprobar(f"brillo{sufijo}", c.brillo, BRILLO_MIN, BRILLO_MAX, 0)
        _comprobar(f"contraste{sufijo}", c.contraste, CONTRASTE_MIN, CONTRASTE_MAX, 0)
        _comprobar(f"gamma{sufijo}", c.gamma, GAMMA_MIN, GAMMA_MAX, 1)
        if uniforme:
            break
    _comprobar("temperatura", a.temperatura, TEMPERATURA_MIN, TEMPERATURA_MAX, 0)


# --- Conversión de escala y curva por canal ----------------------------------
def brillo_a_desplazamiento(brillo: float) -> float:
    return brillo * BRILLO_POR_UNIDAD


def contraste_a_factor(contraste: float) -> float:
    """Factor exponencial: siempre positivo, así la curva nunca se invierte."""
    return 2.0 ** (contraste / CONTRASTE_ESCALA)


def curva_canal(a: AjusteCanal, factor_temp: float = 1.0) -> list[int]:
    """256 valores de 16 bits para un canal: gamma, contraste, brillo y temperatura."""
    exponente = 1.0 / a.gamma
    c = contraste_a_factor(a.contraste)
    b = brillo_a_desplazamiento(a.brillo)
    salida = []
    for i in range(PUNTOS):
        v = (i / (PUNTOS - 1)) ** exponente
        v = (v - 0.5) * c + 0.5
        v = (v + b) * factor_temp
        salida.append(round(min(1.0, max(0.0, v)) * MAXIMO))
    return salida


def rampa_identidad() -> Rampa:
    return curva_canal(AjusteCanal()) * 3


def construir_rampa(a: Ajuste) -> Rampa:
    """Valida el ajuste y devuelve la rampa de 768 valores (R, G y B seguidos)."""
    validar_ajuste(a)
    fr, fg, fb = kelvin_a_rgb(a.temperatura)
    return curva_canal(a.r, fr) + curva_canal(a.g, fg) + curva_canal(a.b, fb)


# --- Temperatura de color -----------------------------------------------------
def _recortar255(x: float) -> float:
    return min(255.0, max(0.0, x))


def _rgb_helland(kelvin: float) -> tuple[float, float, float]:
    """Color aproximado de un cuerpo negro, canales de 0 a 1.

    Aproximación pública de Tanner Helland («How to Convert Temperature (K) to
    RGB: Algorithm and Sample Code», 2012), escrita aquí de nuevo a partir de
    sus fórmulas; no se copia código de otros proyectos.
    """
    t = kelvin / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
    else:
        r = 329.698727446 * (t - 60.0) ** -0.1332047592
        g = 288.1221695283 * (t - 60.0) ** -0.0755148492
    if t >= 66:
        b = 255.0
    elif t <= 19:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(t - 10.0) - 305.0447927307
    return _recortar255(r) / 255.0, _recortar255(g) / 255.0, _recortar255(b) / 255.0


def kelvin_a_rgb(kelvin: float) -> tuple[float, float, float]:
    """Factor RGB para multiplicar la rampa: 6500 K da (1, 1, 1) y ningún canal supera 1."""
    if not math.isfinite(kelvin) or kelvin <= 0:
        raise ValorFueraDeRango("temperatura debe ser un número finito y positivo.")
    base = _rgb_helland(TEMPERATURA_NEUTRA)
    relativo = [c / n for c, n in zip(_rgb_helland(kelvin), base)]
    maximo = max(relativo)
    return tuple(c / maximo for c in relativo)  # type: ignore[return-value]
