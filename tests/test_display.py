# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``display``.

Tres grupos:
- lectura segura de los monitores reales (solo leen; se saltan si no hay monitores);
- sesión de gamma con dobles en memoria (nunca tocan la pantalla);
- escritura real, marcada ``pantalla`` (solo con ``--con-pantalla``).

Regla de seguridad de los dobles: ``SesionGamma`` real registra ``atexit``, señales y
``SetConsoleCtrlHandler``. El fixture ``pantalla_falsa`` neutraliza todo eso y usa
dispositivos inexistentes (``\\\\.\\PRUEBAn``), de modo que, si una prueba falla a medias,
ningún ``atexit`` puede escribir en un monitor real al salir de pytest.
"""

import signal

import pytest

from vislumbra import color, display
from vislumbra.display import (
    ErrorPantalla,
    Monitor,
    MonitorNoEncontrado,
    RampaRechazada,
    SesionGamma,
)


# --- Lectura segura de los monitores reales ----------------------------------------
def test_listar_monitores_devuelve_monitores_coherentes(monitores_reales):
    assert [m.numero for m in monitores_reales] == list(range(1, len(monitores_reales) + 1))
    assert sum(m.principal for m in monitores_reales) == 1
    assert all(m.dispositivo.startswith(r"\\.\DISPLAY") for m in monitores_reales)


def test_leer_rampa_es_valida_y_monotona(monitores_reales):
    for m in monitores_reales:
        r = display.leer_rampa(m)
        assert len(r) == color.LONGITUD_RAMPA
        assert all(isinstance(x, int) and 0 <= x <= color.MAXIMO for x in r)
        for n in range(3):
            canal = r[n * color.PUNTOS:(n + 1) * color.PUNTOS]
            assert all(x <= y for x, y in zip(canal, canal[1:])), f"monitor {m.numero}, canal {n}"


def test_elegir_monitores_con_la_lista_real(monitores_reales):
    assert display.elegir_monitores("principal", monitores_reales) == [
        next(m for m in monitores_reales if m.principal)
    ]
    assert display.elegir_monitores("todos", monitores_reales) == monitores_reales
    for m in monitores_reales:
        assert display.elegir_monitores(str(m.numero), monitores_reales) == [m]
    for malo in ("99", "abc"):
        with pytest.raises(MonitorNoEncontrado):
            display.elegir_monitores(malo, monitores_reales)


@pytest.mark.parametrize("seleccion", ["principal", "todos", "1"])
def test_elegir_monitores_sin_monitores(seleccion):
    with pytest.raises(MonitorNoEncontrado):
        display.elegir_monitores(seleccion, [])


# --- Sesión con dobles ---------------------------------------------------------------------
FALSOS = [Monitor(n, rf"\\.\PRUEBA{n}", "Adaptador de pruebas", None, n == 1) for n in (1, 2, 3)]
AJUSTE_SUAVE = color.construir_rampa(color.Ajuste.uniforme(0.0, 0.0, 1.2, color.TEMPERATURA_NEUTRA))


class PantallaFalsa:
    """Rampas en memoria, una por monitor falso, con fallos programables."""

    def __init__(self, monitores):
        self.rampas = {m.dispositivo: color.rampa_identidad() for m in monitores}
        self.escrituras: list[tuple[int, list[int]]] = []
        self._fallos_escritura: dict[int, list] = {}  # numero -> [excepcion, una_vez]
        self.fallo_lectura: dict[int, BaseException] = {}

    def fallar_escritura(self, numero, excepcion, una_vez=False):
        self._fallos_escritura[numero] = [excepcion, una_vez]

    def escribir(self, m, r):
        fallo = self._fallos_escritura.get(m.numero)
        if fallo:
            if fallo[1]:
                del self._fallos_escritura[m.numero]
            raise fallo[0]
        self.rampas[m.dispositivo] = list(r)
        self.escrituras.append((m.numero, list(r)))

    def leer(self, m):
        if m.numero in self.fallo_lectura:
            raise self.fallo_lectura[m.numero]
        return list(self.rampas[m.dispositivo])

    def rampa(self, numero):
        return self.rampas[FALSOS[numero - 1].dispositivo]

    def escrituras_en(self, numero):
        return [r for n, r in self.escrituras if n == numero]


@pytest.fixture
def pantalla_falsa(monkeypatch):
    pantalla = PantallaFalsa(FALSOS)
    monkeypatch.setattr(display, "_escribir", pantalla.escribir)
    monkeypatch.setattr(display, "leer_rampa", pantalla.leer)
    monkeypatch.setattr(display.atexit, "register", lambda *a, **k: None)
    monkeypatch.setattr(display.atexit, "unregister", lambda *a, **k: None)
    monkeypatch.setattr(SesionGamma, "_instalar_manejadores", lambda self: None)
    monkeypatch.setattr(SesionGamma, "_desinstalar_manejadores", lambda self: None)
    return pantalla


IDENTIDAD = color.rampa_identidad()


def test_reversion_parcial_si_windows_rechaza_a_mitad(pantalla_falsa):
    pantalla_falsa.fallar_escritura(2, RampaRechazada("rechazada"), una_vez=True)
    with SesionGamma(FALSOS) as sesion:
        with pytest.raises(RampaRechazada):
            sesion.aplicar(AJUSTE_SUAVE)
        assert pantalla_falsa.rampa(1) == IDENTIDAD  # el monitor 1 volvió a su original
        assert pantalla_falsa.escrituras_en(3) == []  # el 3 no se tocó
        assert sesion._tocados == set()


@pytest.mark.xfail(strict=True, reason="I-1: un fallo de lectura deja el monitor sin restaurar")
def test_fallo_en_la_lectura_posterior_restaura_el_monitor(pantalla_falsa):
    with SesionGamma(FALSOS) as sesion:
        pantalla_falsa.fallo_lectura[1] = ErrorPantalla("lectura imposible")
        with pytest.raises(ErrorPantalla):
            sesion.aplicar(AJUSTE_SUAVE)
    assert pantalla_falsa.rampa(1) == IDENTIDAD


@pytest.mark.xfail(strict=True, reason="I-1: KeyboardInterrupt a mitad de aplicar deja el monitor sin restaurar")
def test_keyboardinterrupt_a_mitad_de_aplicar_restaura_lo_escrito(pantalla_falsa):
    with pytest.raises(KeyboardInterrupt):
        with SesionGamma(FALSOS) as sesion:
            pantalla_falsa.fallo_lectura[2] = KeyboardInterrupt()
            sesion.aplicar(AJUSTE_SUAVE)
    assert all(pantalla_falsa.rampa(n) == IDENTIDAD for n in (1, 2, 3))


def test_excepcion_dentro_del_with_restaura_y_se_propaga(pantalla_falsa):
    with pytest.raises(RuntimeError, match="fallo ajeno"):
        with SesionGamma(FALSOS) as sesion:
            sesion.aplicar(AJUSTE_SUAVE)
            assert pantalla_falsa.rampa(2) == AJUSTE_SUAVE
            raise RuntimeError("fallo ajeno")
    assert all(pantalla_falsa.rampa(n) == IDENTIDAD for n in (1, 2, 3))


def test_restaurar_es_idempotente(pantalla_falsa):
    with SesionGamma(FALSOS) as sesion:
        sesion.aplicar(AJUSTE_SUAVE)
        sesion.restaurar()
        sesion.restaurar()
    for n in (1, 2, 3):
        assert len(pantalla_falsa.escrituras_en(n)) == 2  # aplicar + una sola restauración


def test_conservar_evita_la_restauracion(pantalla_falsa):
    with SesionGamma(FALSOS) as sesion:
        sesion.aplicar(AJUSTE_SUAVE)
        sesion.conservar()
    for n in (1, 2, 3):
        assert len(pantalla_falsa.escrituras_en(n)) == 1
        assert pantalla_falsa.rampa(n) == AJUSTE_SUAVE


def test_originales_modificados_detecta_una_rampa_ajena(pantalla_falsa):
    ajena = color.construir_rampa(color.Ajuste.uniforme(0.0, 0.0, 1.1, color.TEMPERATURA_NEUTRA))
    pantalla_falsa.rampas[FALSOS[1].dispositivo] = ajena
    with SesionGamma(FALSOS) as sesion:
        assert sesion.originales_modificados() == [FALSOS[1]]
        sesion.aplicar(AJUSTE_SUAVE)
    assert pantalla_falsa.rampa(2) == ajena  # al salir vuelve la ajena, no la identidad


def test_restaurar_identidad_intenta_todos_y_resume_los_fallos(pantalla_falsa):
    for n in (1, 3):
        pantalla_falsa.fallar_escritura(n, RampaRechazada(f"no escribe {n}"))
    with pytest.raises(ErrorPantalla) as e:
        display.restaurar_identidad(FALSOS)
    assert "monitor 1" in str(e.value) and "monitor 3" in str(e.value)
    assert "monitor 2" not in str(e.value)
    assert [n for n, _ in pantalla_falsa.escrituras] == [2]  # el 2 sí se intentó y se escribió


def test_cierre_de_consola_restaura_y_deja_seguir(monkeypatch):
    sesion = SesionGamma(FALSOS)
    llamadas = []
    monkeypatch.setattr(sesion, "_restaurar_sin_excepcion", lambda: llamadas.append(1))
    assert sesion._al_evento_consola(display._CTRL_CLOSE_EVENT) is False
    assert llamadas == [1]


def test_ctrl_c_de_consola_no_restaura_desde_el_manejador_de_consola(monkeypatch):
    sesion = SesionGamma(FALSOS)
    llamadas = []
    monkeypatch.setattr(sesion, "_restaurar_sin_excepcion", lambda: llamadas.append(1))
    assert sesion._al_evento_consola(0) is False  # CTRL_C_EVENT: lo gestiona la señal
    assert llamadas == []


def test_senal_sigint_restaura_y_lanza_keyboardinterrupt(monkeypatch):
    sesion = SesionGamma(FALSOS)
    llamadas = []
    monkeypatch.setattr(sesion, "_restaurar_sin_excepcion", lambda: llamadas.append(1))
    with pytest.raises(KeyboardInterrupt):
        sesion._al_recibir_senal(signal.SIGINT, None)
    assert llamadas == [1]


def test_senal_sigbreak_restaura_y_sale_con_codigo_1(monkeypatch):
    sesion = SesionGamma(FALSOS)
    llamadas = []
    monkeypatch.setattr(sesion, "_restaurar_sin_excepcion", lambda: llamadas.append(1))
    with pytest.raises(SystemExit) as e:
        sesion._al_recibir_senal(signal.SIGBREAK, None)
    assert e.value.code == 1 and llamadas == [1]
