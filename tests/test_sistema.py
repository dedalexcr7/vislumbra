# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.sistema`` con nombres aleatorios: no interfieren con una app abierta."""

import threading
import time
import uuid

import pytest

from vislumbra import sistema
from vislumbra.sistema import Evento, Mutex


@pytest.fixture
def nom():
    return sistema.nombres(rf"Local\VislumbraPrueba{uuid.uuid4().hex}")


def test_los_nombres_usan_el_prefijo_y_son_distintos():
    n = sistema.nombres()
    assert all(v.startswith("Local\\Vislumbra") for v in n.values())
    assert len(set(n.values())) == len(n) == 4


def test_instancia_unica_con_mutex(nom):
    primero = Mutex(nom["mutex"])
    segundo = Mutex(nom["mutex"])
    try:
        assert primero.ya_existia is False
        assert segundo.ya_existia is True
    finally:
        segundo.cerrar()
        primero.cerrar()
    tercero = Mutex(nom["mutex"])  # al cerrar todos, el nombre queda libre
    assert tercero.ya_existia is False
    tercero.cerrar()


def test_cerrar_dos_veces_no_falla(nom):
    m = Mutex(nom["mutex"])
    m.cerrar()
    m.cerrar()
    e = Evento(nom["mostrar"])
    e.cerrar()
    e.cerrar()


def test_abrir_un_evento_que_no_existe_da_none(nom):
    assert Evento.abrir(nom["mostrar"]) is None


def test_un_evento_con_nombre_se_activa_desde_otra_apertura(nom):
    dueno = Evento(nom["mostrar"])
    otro = Evento.abrir(nom["mostrar"])
    try:
        assert otro is not None
        assert sistema.esperar_alguno([dueno], 0) is None  # nadie lo activó
        otro.activar()
        assert sistema.esperar_alguno([dueno], 1000) == 0
        assert sistema.esperar_alguno([dueno], 0) is None  # reinicio automático
    finally:
        otro.cerrar()
        dueno.cerrar()


def test_esperar_alguno_devuelve_cual_se_activo(nom):
    eventos = [Evento(nom[k]) for k in ("mostrar", "desactivar", "peticion")]
    try:
        eventos[2].activar()
        assert sistema.esperar_alguno(eventos, 1000) == 2
        eventos[1].activar()
        assert sistema.esperar_alguno(eventos, 1000) == 1
    finally:
        for e in eventos:
            e.cerrar()


def test_esperar_se_despierta_desde_otro_hilo():
    e = Evento()  # sin nombre
    try:
        threading.Timer(0.1, e.activar).start()
        t0 = time.monotonic()
        assert sistema.esperar_alguno([e], 5000) == 0
        assert time.monotonic() - t0 < 2
    finally:
        e.cerrar()


def test_limpiar_un_evento_activado(nom):
    e = Evento(nom["peticion"])
    e.activar()
    e.limpiar()
    assert sistema.esperar_alguno([e], 0) is None
    e.cerrar()


def test_area_de_trabajo_tiene_sentido():
    izq, arriba, der, abajo = sistema.area_de_trabajo()
    assert der > izq and abajo > arriba


def test_colocar_abajo_a_la_derecha():
    assert sistema.colocar_abajo_derecha((0, 0, 1920, 1040), 400, 600, margen=10) == (1510, 430)
    # Si la ventana no cabe, se pega a la esquina superior izquierda del área.
    assert sistema.colocar_abajo_derecha((0, 0, 300, 300), 400, 600) == (0, 0)
    assert sistema.colocar_abajo_derecha((100, 50, 500, 450), 100, 100, margen=0) == (400, 350)


def test_redondear_ventana_no_falla_con_una_ventana_invalida():
    class Falsa:
        def wm_frame(self):
            raise RuntimeError("sin ventana")

    assert sistema.redondear_ventana(Falsa(), "#34332d") is False


def test_limitar_al_area_mueve_la_ventana_lo_justo():
    area = (0, 0, 1000, 800)
    assert sistema.limitar_al_area(100, 100, 300, 300, area) == (100, 100)  # ya cabe
    assert sistema.limitar_al_area(900, 100, 300, 300, area) == (700, 100)  # se sale por la derecha
    assert sistema.limitar_al_area(100, 700, 300, 300, area) == (100, 500)  # y por abajo
    assert sistema.limitar_al_area(-50, -20, 300, 300, area) == (0, 0)
    assert sistema.limitar_al_area(5, 5, 2000, 2000, area) == (0, 0)  # no cabe: manda la esquina superior izquierda


def test_menus_oscuros_devuelve_un_booleano_y_no_falla():
    assert isinstance(sistema.menus_oscuros(), bool)
