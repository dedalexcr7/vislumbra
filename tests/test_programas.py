# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``procesos`` (lectura real, solo lectura) y ``programas`` (lógica pura)."""

import os
import sys

import pytest

from vislumbra import procesos, programas
from vislumbra.programas import (
    ALCANCE_ACTIVO, ALCANCE_VENTANA, Asociacion, ErrorPrograma, SeguimientoMonitores, SeguimientoProgramas, alcance_de_monitor,
    buscar, clave_de_alcance, normalizar_alcance, normalizar_exe,
)


# --- procesos (solo lee la lista de procesos) ------------------------------------------------------------
def test_la_lista_incluye_este_mismo_proceso():
    nombres = procesos.nombres_en_ejecucion()
    assert os.path.basename(sys.executable).lower() in nombres
    assert all(n == n.lower() for n in nombres) and len(nombres) > 10


def test_la_lista_para_elegir_no_trae_procesos_del_sistema_ni_repetidos():
    lista = procesos.nombres_ordenados()
    assert lista == sorted(set(lista)) and all(n.endswith(".exe") for n in lista)
    assert "svchost.exe" not in lista and "system" not in lista


# --- normalizar_exe --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("texto, esperado", [
    ("juego.exe", "juego.exe"), ("Juego.EXE", "juego.exe"), ("  juego  ", "juego.exe"),
    (r"C:\Juegos\Mi Juego\Juego.exe", "juego.exe"), ('"D:/Games/otro juego.exe"', "otro juego.exe"),
    ("Mi.Juego.exe", "mi.juego.exe"),
])
def test_normalizar_exe_deja_solo_el_nombre_en_minusculas(texto, esperado):
    assert normalizar_exe(texto) == esperado


def test_normalizar_exe_no_deja_pasar_la_carpeta():
    """Privacidad: aunque se pegue una ruta con el usuario, solo se guarda el nombre del programa."""
    assert "\\" not in normalizar_exe(r"C:\Users\dev\Juegos\juego.exe")
    assert "dev" not in normalizar_exe(r"C:\Users\dev\Juegos\juego.exe")


@pytest.mark.parametrize("texto", ["", "   ", ".exe", "juego.bat", "juego.txt", 'a"b.exe', "a|b.exe", "x" * 70 + ".exe", "con\nsalto.exe", "C:\\carpeta\\"])
def test_normalizar_exe_rechaza_lo_que_no_es_un_programa(texto):
    with pytest.raises(ErrorPrograma):
        normalizar_exe(texto)


def test_buscar():
    lista = [Asociacion("a.exe", "Oscuro"), Asociacion("b.exe", "Código")]
    assert buscar(lista, "b.exe").perfil == "Código" and buscar(lista, "c.exe") is None


# --- SeguimientoProgramas ----------------------------------------------------------------------------------------
def test_sin_programas_abiertos_no_manda_ninguno():
    s = SeguimientoProgramas()
    assert s.actualizar([]) is None and s.actualizar({"a.exe"}) == "a.exe" and s.actualizar([]) is None


def test_manda_el_ultimo_que_se_abrio_y_al_cerrarlo_vuelve_el_anterior():
    s = SeguimientoProgramas()
    assert s.actualizar({"a.exe"}) == "a.exe"
    assert s.actualizar({"a.exe", "b.exe"}) == "b.exe"  # se abrió b después
    assert s.actualizar({"a.exe", "b.exe"}) == "b.exe"  # sigue mandando b
    assert s.actualizar({"a.exe"}) == "a.exe"  # se cerró b
    assert s.actualizar(set()) is None


def test_reabrir_un_programa_lo_pone_el_ultimo():
    s = SeguimientoProgramas()
    s.actualizar({"a.exe", "b.exe"})
    s.actualizar({"b.exe"})
    assert s.actualizar({"a.exe", "b.exe"}) == "a.exe"  # a se abrió de nuevo después


def test_varios_a_la_vez_en_el_primer_muestreo_es_estable():
    assert SeguimientoProgramas().actualizar({"b.exe", "a.exe"}) == SeguimientoProgramas().actualizar({"a.exe", "b.exe"})


# --- Alcance de la asociación ---------------------------------------------------------------------------------------
def test_una_asociacion_por_defecto_cambia_el_perfil_activo():
    assert Asociacion("a.exe", "Oscuro").alcance == ALCANCE_ACTIVO


def test_alcance_de_monitor_ida_y_vuelta():
    assert clave_de_alcance(alcance_de_monitor("MONITOR\\XYZ\\0001")) == "MONITOR\\XYZ\\0001"
    assert clave_de_alcance(ALCANCE_VENTANA) is None and clave_de_alcance(ALCANCE_ACTIVO) is None


@pytest.mark.parametrize("texto, esperado", [
    ("activo", "activo"), ("ventana", "ventana"), ("monitor:abc", "monitor:abc"),
    ("monitor:", "activo"), ("otra cosa", "activo"), (None, "activo"), (5, "activo"), ("monitor:" + "x" * 500, "activo"),
])
def test_normalizar_alcance_cae_al_perfil_activo_si_no_es_valido(texto, esperado):
    assert normalizar_alcance(texto) == esperado


# --- Monitor donde está cada programa -----------------------------------------------------------------------------------
def test_se_recuerda_el_ultimo_monitor_conocido_mientras_el_programa_siga_abierto():
    s = SeguimientoMonitores()
    assert s.actualizar({"juego.exe"}, {"juego.exe": "D1"}) == {"juego.exe": "D1"}
    assert s.actualizar({"juego.exe"}, {}) == {"juego.exe": "D1"}  # minimizado o alt-tab: sin ventana visible
    assert s.actualizar({"juego.exe"}, {"juego.exe": "D2"}) == {"juego.exe": "D2"}  # lo arrastraron a otro monitor
    assert s.actualizar(set(), {}) == {}  # se cerró: se olvida
    assert s.actualizar({"juego.exe"}, {}) == {}  # reabierto sin ventana todavía: no se sabe dónde


def test_cada_programa_tiene_su_monitor():
    s = SeguimientoMonitores()
    assert s.actualizar({"a.exe", "b.exe"}, {"a.exe": "D1", "b.exe": "D3"}) == {"a.exe": "D1", "b.exe": "D3"}
    assert s.actualizar({"b.exe"}, {}) == {"b.exe": "D3"}


# --- Ventanas reales (solo lectura) ----------------------------------------------------------------------------------------
def test_monitores_de_ventanas_sin_programas_o_inexistentes_da_vacio():
    assert procesos.monitores_de_ventanas([]) == {}
    assert procesos.monitores_de_ventanas(["no_existe_jamas.exe"]) == {}


def test_monitores_de_ventanas_devuelve_dispositivos_de_monitores_reales():
    from vislumbra import display

    abiertos = procesos.nombres_en_ejecucion()
    resultado = procesos.monitores_de_ventanas(abiertos)  # lee las ventanas visibles de todo lo abierto
    dispositivos = {m.dispositivo for m in display.listar_monitores()}
    assert all(d in dispositivos for d in resultado.values())
