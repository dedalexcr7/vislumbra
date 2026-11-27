# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.teclado``.

Registran **de verdad** combinaciones improbables (Ctrl+Alt+Mayús+F22/F23/F24) y las liberan siempre al terminar; se saltan
si el equipo las tiene ocupadas. ``WM_HOTKEY`` se **simula** con ``PostThreadMessageW``: no se inyectan teclas reales.
"""

import threading
import time

import pytest

from vislumbra import teclado
from vislumbra.atajos import parsear
from vislumbra.teclado import ErrorTeclado, GestorAtajos, Resultado

F24, F23, F22 = parsear("Ctrl+Alt+Shift+F24"), parsear("Ctrl+Alt+Shift+F23"), parsear("Ctrl+Alt+Shift+F22")
A, B = ("accion", "uno"), ("accion", "dos")


@pytest.fixture
def gestores():
    creados, avisos = [], []

    def crear():
        g = GestorAtajos(avisos.append)
        g.iniciar()
        creados.append(g)
        return g

    yield crear, avisos
    for g in creados:
        g.parar()


def esperar(condicion, segundos=3.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.01)
    return False


def registrar_o_saltar(g, mapa):
    res = g.aplicar(mapa)
    if not all(r.ok for r in res.values()):
        pytest.skip("esa combinación está ocupada en este equipo")
    return res


def test_registrar_una_combinacion_libre_de_verdad(gestores):
    crear, _ = gestores
    g = crear()
    res = registrar_o_saltar(g, {A: F24})
    assert res == {A: Resultado(True)} and g.id_de(A) is not None and g.vivo


def test_la_misma_combinacion_dos_veces_falla_con_1409_en_uso(gestores):
    crear, _ = gestores
    g1, g2 = crear(), crear()
    registrar_o_saltar(g1, {A: F24})
    res = g2.aplicar({B: F24})
    assert res[B].ok is False and res[B].codigo == 1409 and res[B].en_uso is True
    assert g2.id_de(B) is None


def test_un_fallo_no_impide_registrar_los_demas(gestores):
    crear, _ = gestores
    g1, g2 = crear(), crear()
    registrar_o_saltar(g1, {A: F24})
    res = g2.aplicar({A: F24, B: F23})
    assert res[A].en_uso and res[B].ok and g2.id_de(B) is not None


def test_wm_hotkey_simulado_avisa_con_la_clave_correcta(gestores):
    crear, avisos = gestores
    g = crear()
    registrar_o_saltar(g, {A: F24, B: F23})
    teclado._user32.PostThreadMessageW(g.thread_id, teclado.WM_HOTKEY, g.id_de(B), 0)
    assert esperar(lambda: avisos == [B])
    teclado._user32.PostThreadMessageW(g.thread_id, teclado.WM_HOTKEY, g.id_de(A), 0)
    assert esperar(lambda: avisos == [B, A])
    teclado._user32.PostThreadMessageW(g.thread_id, teclado.WM_HOTKEY, 9999, 0)  # un identificador que no es nuestro
    time.sleep(0.1)
    assert avisos == [B, A]


def test_pausar_libera_la_combinacion_y_reanudar_la_recupera(gestores):
    crear, avisos = gestores
    g, otro = crear(), crear()
    registrar_o_saltar(g, {A: F24})
    g.pausar()
    assert otro.probar(F24).ok  # mientras está en pausa, otra la puede tener (así se graba sin que salte la acción)
    teclado._user32.PostThreadMessageW(g.thread_id, teclado.WM_HOTKEY, 1, 0)
    time.sleep(0.1)
    assert avisos == []  # en pausa no avisa
    res = g.reanudar()
    assert res[A].ok and g.id_de(A) is not None
    assert otro.probar(F24).en_uso  # ya vuelve a ser nuestra


def test_aplicar_en_pausa_no_registra_hasta_reanudar(gestores):
    crear, _ = gestores
    g, otro = crear(), crear()
    g.pausar()
    assert g.aplicar({A: F24}) == {A: Resultado(True)} and otro.probar(F24).ok and g.id_de(A) is None
    assert g.reanudar()[A].ok and otro.probar(F24).en_uso


def test_cambiar_el_mapa_libera_lo_anterior(gestores):
    crear, _ = gestores
    g, otro = crear(), crear()
    registrar_o_saltar(g, {A: F24})
    registrar_o_saltar(g, {B: F23})
    assert otro.probar(F24).ok and otro.probar(F23).en_uso
    g.aplicar({})
    assert otro.probar(F23).ok


def test_probar_no_deja_nada_registrado(gestores):
    crear, _ = gestores
    g, otro = crear(), crear()
    assert g.probar(F22).ok or pytest.skip("ocupada en este equipo")
    assert otro.probar(F22).ok and g.id_de(A) is None
    registrar_o_saltar(otro, {A: F22})
    assert g.probar(F22).en_uso


def test_parar_libera_todo_y_termina_el_hilo(gestores):
    crear, _ = gestores
    g, otro = crear(), crear()
    registrar_o_saltar(g, {A: F24})
    hilo = g._hilo
    g.parar()
    assert not hilo.is_alive() and not g.vivo
    assert otro.probar(F24).ok
    g.parar()  # varias veces: sin problema
    with pytest.raises(ErrorTeclado, match="no está en marcha"):
        g.aplicar({A: F24})


def test_un_fallo_de_quien_escucha_no_mata_el_hilo(gestores):
    crear, _ = gestores
    llamadas = []

    def mal(clave):
        llamadas.append(clave)
        raise RuntimeError("fallo de quien escucha")

    g = GestorAtajos(mal)
    g.iniciar()
    try:
        registrar_o_saltar(g, {A: F24})
        teclado._user32.PostThreadMessageW(g.thread_id, teclado.WM_HOTKEY, g.id_de(A), 0)
        assert esperar(lambda: llamadas == [A])
        teclado._user32.PostThreadMessageW(g.thread_id, teclado.WM_HOTKEY, g.id_de(A), 0)
        assert esperar(lambda: llamadas == [A, A]) and g.vivo
    finally:
        g.parar()


def test_iniciar_dos_veces_no_crea_otro_hilo(gestores):
    crear, _ = gestores
    g = crear()
    hilo = g._hilo
    g.iniciar()
    assert g._hilo is hilo


def test_desde_varios_hilos_a_la_vez(gestores):
    crear, _ = gestores
    g = crear()
    errores = []

    def usar():
        try:
            for _ in range(20):
                g.probar(F22)
                g.aplicar({})
        except Exception as e:  # noqa: BLE001
            errores.append(e)

    hilos = [threading.Thread(target=usar) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(10)
    assert errores == [] and g.vivo


# --- Lectura del teclado -------------------------------------------------------------------------------------------
def test_leer_modificadores_devuelve_un_conjunto_de_modificadores_validos():
    mods = teclado.leer_modificadores()
    assert isinstance(mods, frozenset) and mods <= {"Ctrl", "Alt", "Shift", "Win"}


def test_el_aviso_de_altgr_solo_aplica_a_combinaciones_con_ctrl_y_alt():
    assert teclado.caracter_con_altgr(parsear("Ctrl+B")) is None
    assert teclado.caracter_con_altgr(parsear("Alt+B")) is None
    assert teclado.caracter_con_altgr(parsear("Ctrl+Alt+Win+Q")) is None
    assert teclado.caracter_con_altgr(parsear("Ctrl+Alt+F5")) is None  # una tecla de función no escribe nada


def test_el_aviso_de_altgr_devuelve_un_caracter_o_nada_sin_fallar():
    for texto in ("Ctrl+Alt+Q", "Ctrl+Alt+P", "Ctrl+Alt+0", "Ctrl+Alt+Shift+E", "Ctrl+Alt+B"):
        r = teclado.caracter_con_altgr(parsear(texto))
        assert r is None or (len(r) == 1 and r.isprintable())
