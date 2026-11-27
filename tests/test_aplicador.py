# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.aplicador`` con una sesión doble y un reloj falso: no tocan la pantalla."""

import time
from dataclasses import dataclass

import pytest

from vislumbra import color, display
from vislumbra.aplicador import MAX_REAPLICACIONES, VENTANA_CONFLICTO, Aplicador, Aviso

IDENTIDAD = color.rampa_identidad()
R1 = color.construir_rampa_segura(color.Ajuste.uniforme(0.0, 0.0, 1.5))
R2 = color.construir_rampa_segura(color.Ajuste.uniforme(0.0, 0.0, 2.0))
R3 = color.construir_rampa_segura(color.Ajuste.uniforme(0.0, 0.0, 1.2))


@dataclass(frozen=True)
class Mon:
    numero: int
    clave: str


MONS = [Mon(1, "a"), Mon(2, "b"), Mon(3, "c")]


class SesionDoble:
    def __init__(self, monitores=MONS):
        self.monitores = list(monitores)
        self.pantalla = {m.numero: list(IDENTIDAD) for m in monitores}
        self.llamadas: list[dict] = []
        self.fallos: list[Exception] = []  # se lanza el primero en la siguiente llamada
        self.sin_coincidir: list[Mon] = []

    def aplicar_por_monitor(self, rampas):
        self.llamadas.append(dict(rampas))
        if self.fallos:
            raise self.fallos.pop(0)
        for n, r in rampas.items():
            self.pantalla[n] = list(IDENTIDAD if r is None else r)
        return list(self.sin_coincidir)

    def leer(self, m):
        return list(self.pantalla[m.numero])


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def montaje():
    sesion, avisos, reloj = SesionDoble(), [], Reloj()
    ap = Aplicador(
        sesion, avisos.append, leer=sesion.leer, listar=lambda: list(sesion.monitores),
        reloj=reloj, intervalo_vigilancia=0.05, intervalo_minimo=0.0,
    )
    return ap, sesion, avisos, reloj


def tipos(avisos):
    return [a.tipo for a in avisos]


# --- Aplicar --------------------------------------------------------------------------------------
def test_el_ultimo_gana(montaje):
    ap, sesion, avisos, _ = montaje
    ap.pedir({1: R1, 2: R1, 3: R1})
    ap.pedir({1: R2, 2: R2, 3: R2})
    ap.procesar_cambio()
    assert len(sesion.llamadas) == 1 and sesion.pantalla[1] == R2
    assert tipos(avisos) == ["aplicado"] and avisos[0].monitores == (1, 2, 3)


def test_una_rampa_distinta_por_monitor(montaje):
    ap, sesion, _, _ = montaje
    ap.pedir({1: R1, 2: R2, 3: None})
    ap.procesar_cambio()
    assert sesion.pantalla[1] == R1 and sesion.pantalla[2] == R2 and sesion.pantalla[3] == IDENTIDAD
    assert 3 not in sesion.llamadas[0]  # un monitor sin tocar no recibe nada
    assert set(ap.aplicado) == {1, 2}


def test_no_se_vuelve_a_escribir_lo_que_ya_esta_aplicado(montaje):
    ap, sesion, _, _ = montaje
    ap.pedir({1: R1, 2: R1})
    ap.procesar_cambio()
    ap.pedir({1: R1, 2: R2})
    ap.procesar_cambio()
    assert sesion.llamadas[1] == {2: R2}
    ap.pedir({1: R1, 2: R2})
    ap.procesar_cambio()
    assert len(sesion.llamadas) == 2  # nada que hacer


def test_none_restaura_solo_lo_que_se_toco(montaje):
    ap, sesion, _, _ = montaje
    ap.pedir({1: None, 2: R1})
    ap.procesar_cambio()
    assert sesion.llamadas == [{2: R1}]
    ap.pedir({1: None, 2: None})
    ap.procesar_cambio()
    assert sesion.llamadas[1] == {2: None} and ap.aplicado == {}


def test_procesar_sin_nada_pedido_no_hace_nada(montaje):
    ap, sesion, avisos, _ = montaje
    ap.procesar_cambio()
    assert sesion.llamadas == [] and avisos == []


def test_ab_quita_y_devuelve_el_ajuste(montaje):
    ap, sesion, _, _ = montaje
    ap.pedir({1: R1, 2: R1, 3: R1})
    ap.procesar_cambio()
    ap.pedir({1: None, 2: None, 3: None})  # A/B: ver la pantalla normal
    ap.procesar_cambio()
    assert all(sesion.pantalla[n] == IDENTIDAD for n in (1, 2, 3)) and ap.aplicado == {}
    ap.pedir({1: R1, 2: R1, 3: R1})
    ap.procesar_cambio()
    assert all(sesion.pantalla[n] == R1 for n in (1, 2, 3))


def test_desactivar_restaura_y_para_la_vigilancia(montaje):
    ap, sesion, avisos, reloj = montaje
    ap.pedir({1: R1})
    ap.procesar_cambio()
    ap.pedir({1: None})
    ap.procesar_cambio()
    sesion.pantalla[1] = list(R2)  # otro programa toca la rampa
    llamadas = len(sesion.llamadas)
    ap.vigilar(reloj())
    assert len(sesion.llamadas) == llamadas and sesion.pantalla[1] == R2  # ya no se vigila


def test_aviso_si_la_lectura_posterior_no_coincide(montaje):
    ap, sesion, avisos, _ = montaje
    sesion.sin_coincidir = [MONS[1]]
    ap.pedir({2: R1})
    ap.procesar_cambio()
    lectura = [a for a in avisos if a.tipo == "lectura"]
    assert len(lectura) == 1 and lectura[0].monitores == (2,)


def test_se_mide_lo_que_tarda_en_aplicar(montaje):
    ap, sesion, _, reloj = montaje
    original = sesion.aplicar_por_monitor

    def lenta(r):
        reloj.t += 0.02
        return original(r)

    sesion.aplicar_por_monitor = lenta
    ap.pedir({1: R1})
    ap.procesar_cambio()
    assert ap.ultima_duracion == pytest.approx(0.02) and ap.max_duracion == pytest.approx(0.02)


# --- Rechazos ----------------------------------------------------------------------------------------
def test_si_windows_rechaza_se_vuelve_a_la_ultima_rampa_aceptada(montaje):
    ap, sesion, avisos, _ = montaje
    ap.pedir({1: R1})
    ap.procesar_cambio()
    sesion.fallos = [display.RampaRechazada("Windows ha rechazado la rampa en el monitor 1.")]
    ap.pedir({1: R2})
    ap.procesar_cambio()
    assert sesion.pantalla[1] == R1 and ap.aplicado == {1: R1}
    assert sesion.llamadas[-1] == {1: R1}  # volvió a la anterior
    rechazo = [a for a in avisos if a.tipo == "rechazo"]
    assert len(rechazo) == 1 and "rechazado" in rechazo[0].mensaje and rechazo[0].monitores == (1,)


def test_rechazo_sin_rampa_anterior_vuelve_a_la_original(montaje):
    ap, sesion, avisos, _ = montaje
    sesion.fallos = [display.RampaRechazada("no")]
    ap.pedir({2: R1})
    ap.procesar_cambio()
    assert sesion.llamadas[-1] == {2: None} and ap.aplicado == {} and "rechazo" in tipos(avisos)


def test_si_ni_siquiera_se_puede_volver_se_avisa_del_error(montaje):
    ap, sesion, avisos, _ = montaje
    sesion.fallos = [display.RampaRechazada("primero"), display.ErrorPantalla("segundo")]
    ap.pedir({1: R1})
    ap.procesar_cambio()
    assert tipos(avisos) == ["error"] and "primero" in avisos[0].mensaje and "segundo" in avisos[0].mensaje


def test_una_rampa_ilegible_tambien_se_recupera(montaje):
    ap, sesion, avisos, _ = montaje
    sesion.fallos = [color.RampaIlegible("este ajuste dejaría la pantalla casi ilegible")]
    ap.pedir({1: R1})
    ap.procesar_cambio()
    assert "rechazo" in tipos(avisos) and ap.aplicado == {}


# --- Vigilancia ------------------------------------------------------------------------------------------
def test_la_vigilancia_vuelve_a_aplicar_lo_que_cambio_otro_programa(montaje):
    ap, sesion, _, reloj = montaje
    ap.pedir({1: R1, 2: R2})
    ap.procesar_cambio()
    sesion.pantalla[1] = list(IDENTIDAD)  # un juego reinicia la rampa del monitor 1
    ap.vigilar(10.0)
    assert sesion.pantalla[1] == R1 and sesion.llamadas[-1] == {1: R1}
    llamadas = len(sesion.llamadas)
    ap.vigilar(12.0)
    assert len(sesion.llamadas) == llamadas  # todo en orden: no se escribe nada


def test_la_vigilancia_tolera_una_lectura_fallida(montaje):
    ap, sesion, avisos, _ = montaje
    ap.pedir({1: R1})
    ap.procesar_cambio()
    ap._leer = lambda m: (_ for _ in ()).throw(display.ErrorPantalla("sin lectura"))
    ap.vigilar(5.0)
    assert [a for a in avisos if a.tipo != "aplicado"] == []


def test_conflicto_tras_mas_de_10_reaplicaciones_en_10_s(montaje):
    ap, sesion, avisos, _ = montaje
    ap.pedir({1: R1})
    ap.procesar_cambio()
    for i in range(MAX_REAPLICACIONES):
        sesion.pantalla[1] = list(IDENTIDAD)
        ap.vigilar(0.5 * i)
        assert sesion.pantalla[1] == R1  # las 10 primeras veces se reaplica
    sesion.pantalla[1] = list(IDENTIDAD)
    ap.vigilar(5.5)  # la undécima: conflicto
    assert sesion.pantalla[1] == IDENTIDAD and ap.en_conflicto == {1}
    conflicto = [a for a in avisos if a.tipo == "conflicto"]
    assert len(conflicto) == 1 and conflicto[0].monitores == (1,)
    llamadas = len(sesion.llamadas)
    ap.vigilar(6.0)
    assert len(sesion.llamadas) == llamadas and len([a for a in avisos if a.tipo == "conflicto"]) == 1


def test_las_reaplicaciones_antiguas_no_cuentan(montaje):
    ap, sesion, avisos, _ = montaje
    ap.pedir({1: R1})
    ap.procesar_cambio()
    for i in range(MAX_REAPLICACIONES):
        sesion.pantalla[1] = list(IDENTIDAD)
        ap.vigilar(0.5 * i)
    sesion.pantalla[1] = list(IDENTIDAD)
    ap.vigilar(VENTANA_CONFLICTO + 10.0)  # ya pasó la ventana de 10 s
    assert sesion.pantalla[1] == R1 and ap.en_conflicto == set()


def test_un_cambio_del_usuario_sale_del_conflicto(montaje):
    ap, sesion, avisos, _ = montaje
    ap.pedir({1: R1})
    ap.procesar_cambio()
    for i in range(MAX_REAPLICACIONES + 1):
        sesion.pantalla[1] = list(IDENTIDAD)
        ap.vigilar(0.5 * i)
    assert ap.en_conflicto == {1}
    ap.pedir({1: R2})
    ap.procesar_cambio()
    assert ap.en_conflicto == set() and sesion.pantalla[1] == R2


def test_un_monitor_en_conflicto_no_afecta_a_los_demas(montaje):
    ap, sesion, _, _ = montaje
    ap.pedir({1: R1, 2: R2})
    ap.procesar_cambio()
    for i in range(MAX_REAPLICACIONES + 1):
        sesion.pantalla[1] = list(IDENTIDAD)
        ap.vigilar(0.5 * i)
    sesion.pantalla[2] = list(IDENTIDAD)
    ap.vigilar(6.0)
    assert sesion.pantalla[2] == R2 and ap.en_conflicto == {1}


def test_cambio_en_la_lista_de_monitores(montaje):
    ap, sesion, avisos, _ = montaje
    ap.pedir({1: R1})
    ap.procesar_cambio()
    sesion.monitores = sesion.monitores[:2]  # se desconectó el 3
    ap.vigilar(2.0)
    assert ap.monitores_cambiaron and [a.tipo for a in avisos].count("monitores") == 1
    sesion.pantalla[1] = list(IDENTIDAD)
    llamadas = len(sesion.llamadas)
    ap.vigilar(4.0)
    assert len(sesion.llamadas) == llamadas  # se detiene hasta que la app cree una sesión nueva
    assert [a.tipo for a in avisos].count("monitores") == 1


def test_si_no_se_puede_listar_no_se_considera_un_cambio(montaje):
    ap, _, avisos, _ = montaje
    ap._listar = lambda: (_ for _ in ()).throw(display.ErrorPantalla("sin lista"))
    ap.vigilar(1.0)
    assert not ap.monitores_cambiaron and avisos == []


# --- Hilo real -----------------------------------------------------------------------------------------------
def esperar(condicion, segundos=3.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.01)
    return False


def hilo_real():
    sesion, avisos = SesionDoble(), []
    ap = Aplicador(sesion, avisos.append, leer=sesion.leer, listar=lambda: list(sesion.monitores),
                   intervalo_vigilancia=0.05, intervalo_minimo=0.0)
    return ap, sesion, avisos


def test_el_hilo_aplica_y_se_para():
    ap, sesion, avisos = hilo_real()
    ap.iniciar()
    try:
        assert ap.vivo
        ap.pedir({1: R1})
        assert esperar(lambda: sesion.pantalla[1] == R1)
    finally:
        ap.parar()
    assert not ap.vivo


def test_el_hilo_aplica_siempre_lo_ultimo_aunque_se_pida_muy_rapido():
    ap, sesion, _ = hilo_real()
    ap.iniciar()
    try:
        for r in (R1, R2, R3, R1, R2):
            ap.pedir({1: r})
        assert esperar(lambda: sesion.pantalla[1] == R2)
        time.sleep(0.1)
        assert sesion.pantalla[1] == R2
    finally:
        ap.parar()


def test_el_hilo_vigila_solo():
    ap, sesion, _ = hilo_real()
    ap.iniciar()
    try:
        ap.pedir({1: R1})
        assert esperar(lambda: sesion.pantalla[1] == R1)
        sesion.pantalla[1] = list(IDENTIDAD)
        assert esperar(lambda: sesion.pantalla[1] == R1)
    finally:
        ap.parar()


def test_un_error_inesperado_se_avisa_y_el_hilo_sigue_vivo():
    ap, sesion, avisos = hilo_real()
    sesion.fallos = [RuntimeError("fallo raro")]
    ap.iniciar()
    try:
        ap.pedir({1: R1})
        assert esperar(lambda: any(a.tipo == "error" for a in avisos))
        assert ap.vivo
        ap.pedir({1: R2})
        assert esperar(lambda: sesion.pantalla[1] == R2)
    finally:
        ap.parar()


def test_parar_sin_haber_iniciado_no_falla_y_se_puede_repetir():
    ap, _, _ = hilo_real()
    ap.parar()
    ap.parar()
    assert not ap.vivo


def test_una_rampa_reiniciada_por_un_juego_se_recupera_en_un_ciclo_de_vigilancia(montaje):
    """Entrar y salir de un juego varias veces seguidas (alt-tab) nunca dispara el conflicto."""
    ap, sesion, _, _ = montaje
    ap.pedir({1: R1})
    ap.procesar_cambio()
    for i in range(30):  # 30 entradas o salidas en 3 minutos
        sesion.pantalla[1] = list(IDENTIDAD)
        ap.vigilar(6.0 * i)
        assert sesion.pantalla[1] == R1
    assert ap.en_conflicto == set()


def test_el_intervalo_de_vigilancia_por_defecto_es_corto():
    from vislumbra.aplicador import INTERVALO_VIGILANCIA

    assert INTERVALO_VIGILANCIA <= 0.3
