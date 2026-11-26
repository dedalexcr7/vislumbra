# SPDX-License-Identifier: GPL-3.0-or-later
"""Escala de los deslizadores: funciones puras, sin Tk ni pantalla.

Cada parámetro tiene una posición del deslizador ``p`` en [0, 1] y un valor de usuario.
El neutro queda en el centro (``p = 0,5``) y la respuesta no es lineal para dar más
resolución cerca del neutro. Los valores son provisionales y se calibran con A/B.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import color

NEUTRO_P = 0.5
FACTOR_SHIFT = 10.0  # con Shift el arrastre es 10 veces más lento


@dataclass(frozen=True)
class Parametro:
    nombre: str
    etiqueta: str
    minimo: float
    maximo: float
    neutro: float
    decimales: int
    paso: float  # rueda del ratón y flechas
    paso_fino: float  # con Shift
    ventana_precisa: float  # semiancho de la ventana del modo preciso
    unidad: str = ""


PARAMETROS: dict[str, Parametro] = {
    "brillo": Parametro("brillo", "Brillo", color.BRILLO_MIN, color.BRILLO_MAX, 0.0, 1, 1.0, 0.1, 10.0),
    "contraste": Parametro(
        "contraste", "Contraste", color.CONTRASTE_MIN, color.CONTRASTE_MAX, 0.0, 1, 0.5, 0.1, 4.0
    ),
    "gamma": Parametro("gamma", "Gamma", color.GAMMA_MIN, color.GAMMA_MAX, 1.0, 2, 0.05, 0.01, 0.25),
    "temperatura": Parametro(
        "temperatura", "Temperatura", color.TEMPERATURA_MIN, color.TEMPERATURA_MAX,
        color.TEMPERATURA_NEUTRA, 0, 100.0, 10.0, 500.0, " K",
    ),
}


def parametro(nombre: str) -> Parametro:
    return PARAMETROS[nombre]


def limitar(nombre: str, valor: float) -> float:
    p = PARAMETROS[nombre]
    return min(p.maximo, max(p.minimo, valor))


def redondear(nombre: str, valor: float) -> float:
    """Redondea a los decimales del parámetro (evita 0,30000000000000004)."""
    r = round(valor, PARAMETROS[nombre].decimales)
    return 0.0 if r == 0 else r  # sin «-0,0»


# --- Posición del deslizador <-> valor ----------------------------------------------
def _simetrica_a_valor(t: float, maximo: float) -> float:
    """Cuadrática con signo: ``t`` en [-1, 1] -> valor en [-máx, máx]."""
    return math.copysign(t * t, t) * maximo


def _simetrica_a_t(valor: float, maximo: float) -> float:
    return math.copysign(math.sqrt(abs(valor) / maximo), valor)


def _mired(kelvin: float) -> float:
    return 1e6 / kelvin


def posicion_a_valor(nombre: str, p: float) -> float:
    """Valor para la posición ``p`` (se limita a [0, 1])."""
    p = min(1.0, max(0.0, p))
    par = PARAMETROS[nombre]
    if nombre in ("brillo", "contraste"):
        return _simetrica_a_valor(2.0 * p - 1.0, par.maximo)
    if nombre == "gamma":
        if p <= NEUTRO_P:
            return par.minimo * (par.neutro / par.minimo) ** (p / NEUTRO_P)
        return par.neutro * (par.maximo / par.neutro) ** ((p - NEUTRO_P) / (1.0 - NEUTRO_P))
    if nombre == "temperatura":
        # Lineal en mired a tramos: lo que el ojo percibe es más uniforme en mired que en kelvin.
        # p = 0 es el extremo cálido (3300 K), p = 0,5 el neutro y p = 1 el frío (10 000 K).
        m_calido, m_n, m_frio = _mired(par.minimo), _mired(par.neutro), _mired(par.maximo)
        if p <= NEUTRO_P:
            return _mired(m_calido + (m_n - m_calido) * (p / NEUTRO_P))
        return _mired(m_n + (m_frio - m_n) * ((p - NEUTRO_P) / (1.0 - NEUTRO_P)))
    raise KeyError(nombre)


def valor_a_posicion(nombre: str, valor: float) -> float:
    """Posición de ``valor`` (se limita al rango del parámetro)."""
    par = PARAMETROS[nombre]
    v = limitar(nombre, valor)
    if nombre in ("brillo", "contraste"):
        return (_simetrica_a_t(v, par.maximo) + 1.0) / 2.0
    if nombre == "gamma":
        if v <= par.neutro:
            return NEUTRO_P * math.log(v / par.minimo) / math.log(par.neutro / par.minimo)
        return NEUTRO_P + (1.0 - NEUTRO_P) * math.log(v / par.neutro) / math.log(par.maximo / par.neutro)
    if nombre == "temperatura":
        m_calido, m_n, m_frio = _mired(par.minimo), _mired(par.neutro), _mired(par.maximo)
        m = _mired(v)
        if m >= m_n:
            return NEUTRO_P * (m_calido - m) / (m_calido - m_n)
        return NEUTRO_P + (1.0 - NEUTRO_P) * (m_n - m) / (m_n - m_frio)
    raise KeyError(nombre)


def arrastre_fino(p_inicio: float, p_actual: float, factor: float = FACTOR_SHIFT) -> float:
    """Posición con el ratón a ``factor`` veces menos velocidad desde ``p_inicio``."""
    return min(1.0, max(0.0, p_inicio + (p_actual - p_inicio) / factor))


# --- Pasos (rueda, flechas, botones − y +) --------------------------------------------
def paso_rueda(nombre: str, valor: float, direccion: int, fino: bool = False) -> float:
    """Valor tras un paso arriba (+1) o abajo (−1); redondeado y dentro del rango."""
    par = PARAMETROS[nombre]
    paso = par.paso_fino if fino else par.paso
    nuevo = valor + math.copysign(paso, direccion)
    # Alinea a múltiplos del paso para que 7,5 + 0,5 no acumule error ni salga 7,9999.
    nuevo = round(nuevo / paso) * paso
    return redondear(nombre, limitar(nombre, nuevo))


# --- Modo preciso: ventana lineal alrededor del valor ----------------------------------------
def ventana_precisa(nombre: str, centro: float) -> tuple[float, float]:
    par = PARAMETROS[nombre]
    c = limitar(nombre, centro)
    return max(par.minimo, c - par.ventana_precisa), min(par.maximo, c + par.ventana_precisa)


def posicion_precisa_a_valor(nombre: str, p: float, centro: float) -> float:
    bajo, alto = ventana_precisa(nombre, centro)
    return redondear(nombre, bajo + min(1.0, max(0.0, p)) * (alto - bajo))


def valor_a_posicion_precisa(nombre: str, valor: float, centro: float) -> float:
    bajo, alto = ventana_precisa(nombre, centro)
    return min(1.0, max(0.0, (valor - bajo) / (alto - bajo)))


# --- Texto <-> número --------------------------------------------------------------------------
def formatear(nombre: str, valor: float, con_unidad: bool = False) -> str:
    """Número con coma decimal y los decimales del parámetro (``0,0``, ``1,70``, ``6500``)."""
    par = PARAMETROS[nombre]
    texto = f"{redondear(nombre, valor):.{par.decimales}f}".replace(".", ",")
    return texto + (par.unidad if con_unidad else "")


def leer_numero(texto: str) -> float | None:
    """Número escrito con coma o con punto (y con el signo menos tipográfico); ``None`` si no vale."""
    t = texto.strip().replace("−", "-").replace(",", ".")
    for sufijo in ("k", "K"):
        t = t.removesuffix(sufijo).strip()
    try:
        valor = float(t)
    except ValueError:
        return None
    return valor if math.isfinite(valor) else None
